"""
Scheduled Garmin sync — runs on Vercel Cron (see /vercel.json).

Logs into Garmin Connect with GARMIN_EMAIL / GARMIN_PASSWORD (set these
as Vercel Environment Variables — NEVER commit real credentials here),
pulls today's resting heart rate / body battery / stress / sleep, and
writes them into the same public.app_state Supabase table the rest of
the dashboard already reads from (key = 'garmin').

Required Vercel env vars:
  GARMIN_EMAIL     — your Garmin Connect login email
  GARMIN_PASSWORD  — your Garmin Connect login password
  CRON_SECRET      — any random string; Vercel sends it back as
                      "Authorization: Bearer <CRON_SECRET>" on cron
                      invocations, which this function checks so the
                      public URL can't be used to trigger a Garmin
                      login by anyone who finds it.

We deliberately do NOT cache the Garmin session token anywhere (e.g.
in Supabase) — the same anon key that's already public in every page
of this dashboard can read the app_state table, and a cached session
token there would let anyone with that key pull your Garmin data too.
A fresh login once a day is an acceptable tradeoff for keeping this
simple and not adding a new public-readable secret.
"""

from http.server import BaseHTTPRequestHandler
import os
import json
import datetime

SUPABASE_URL = 'https://qigzwmiypboijszfrhkm.supabase.co'
SUPABASE_KEY = 'sb_publishable_EAe3cddNpZ8vdw17a8kl0w_zDu9CfDb'


def push_to_supabase(data):
    import requests

    url = SUPABASE_URL + '/rest/v1/app_state?on_conflict=key'
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': 'Bearer ' + SUPABASE_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
    }
    body = {
        'key': 'garmin',
        'data': data,
        'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    return requests.post(url, headers=headers, json=body, timeout=20)


def fetch_garmin_data():
    import garminconnect

    email = os.environ['GARMIN_EMAIL']
    password = os.environ['GARMIN_PASSWORD']
    today = datetime.date.today().isoformat()

    client = garminconnect.Garmin(email, password)
    client.login()

    out = {'lastSynced': datetime.datetime.utcnow().isoformat() + 'Z'}

    # --- resting HR / body battery / stress (single daily summary call) ---
    stats = {}
    try:
        stats = client.get_stats(today) or {}
    except Exception as e:
        out['statsError'] = str(e)

    out['restingHr'] = stats.get('restingHeartRate')
    out['bodyBattery'] = stats.get('bodyBatteryMostRecentValue')
    out['stressAvg'] = stats.get('averageStressLevel')

    # Fallback: some garminconnect versions don't put restingHeartRate
    # in get_stats() — try the dedicated RHR endpoint instead.
    if not out['restingHr']:
        try:
            rhr = client.get_rhr_day(today) or {}
            metrics = (rhr.get('allMetrics') or {}).get('metricsMap') or {}
            vals = metrics.get('WELLNESS_RESTING_HEART_RATE') or []
            if vals:
                out['restingHr'] = vals[0].get('value')
        except Exception as e:
            out['rhrError'] = str(e)

    # --- sleep ---
    try:
        sleep = client.get_sleep_data(today) or {}
        dto = sleep.get('dailySleepDTO') or {}
        total_seconds = dto.get('sleepTimeSeconds')
        out['sleepHours'] = round(total_seconds / 3600, 1) if total_seconds else None
        overall = (dto.get('sleepScores') or {}).get('overall') or {}
        out['sleepScore'] = overall.get('value')
    except Exception as e:
        out['sleepError'] = str(e)

    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cron_secret = os.environ.get('CRON_SECRET')
        auth_header = self.headers.get('Authorization', '')
        if cron_secret and auth_header != 'Bearer ' + cron_secret:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return

        try:
            data = fetch_garmin_data()
            resp = push_to_supabase(data)
            ok = resp.status_code < 300
            self.send_response(200 if ok else 502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'ok': ok,
                'data': data,
                'supabaseStatus': resp.status_code,
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'error': str(e)}).encode('utf-8'))
