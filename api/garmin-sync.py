"""
Scheduled Garmin sync — runs on Vercel Cron (see /vercel.json).

Logs into Garmin Connect with GARMIN_EMAIL / GARMIN_PASSWORD (set these
as Vercel Environment Variables — NEVER commit real credentials here),
pulls today's resting heart rate / body battery / stress / sleep, and
writes them into the same public.app_state Supabase table the rest of
the dashboard already reads from (key = 'garmin').

Requests are authorized two ways: the CRON_SECRET bearer token (used by
the scheduled GitHub Actions job), or a valid Supabase Auth session
token for our one dashboard user (used by the "Sync now" button in the
settings panel - verified by asking Supabase's own /auth/v1/user
endpoint whether the token is real, so no new secret is needed for
that path and nothing here has to parse/verify JWTs itself).

Required Vercel env vars:
  GARMIN_EMAIL              — your Garmin Connect login email
  GARMIN_PASSWORD           — your Garmin Connect login password
  CRON_SECRET               — any random string; Vercel sends it back as
                               "Authorization: Bearer <CRON_SECRET>" on
                               cron invocations, which this function
                               checks so the public URL can't be used
                               to trigger a Garmin login by anyone who
                               finds it.
  SUPABASE_SERVICE_ROLE_KEY — the project's service_role key (Supabase
                               dashboard -> Settings -> API). app_state's
                               RLS only allows the "authenticated" role
                               to read/write, and this function has no
                               user session of its own to authenticate
                               with - the service_role key bypasses RLS
                               entirely, which is the standard pattern
                               for a trusted server-side job. NEVER put
                               this key in any client-side file - it
                               must only ever live here, server-side.

We deliberately do NOT cache the Garmin session token anywhere (e.g.
in Supabase) to avoid adding another sensitive value to persist and
protect. A fresh login once a day is an acceptable tradeoff for
keeping this simple.
"""

from http.server import BaseHTTPRequestHandler
import os
import json
import datetime

SUPABASE_URL = 'https://qigzwmiypboijszfrhkm.supabase.co'
SUPABASE_ANON_KEY = 'sb_publishable_EAe3cddNpZ8vdw17a8kl0w_zDu9CfDb'


def is_authorized(auth_header):
    cron_secret = os.environ.get('CRON_SECRET')
    if cron_secret and auth_header == 'Bearer ' + cron_secret:
        return True
    if auth_header.startswith('Bearer '):
        token = auth_header[len('Bearer '):]
        try:
            import requests
            resp = requests.get(
                SUPABASE_URL + '/auth/v1/user',
                headers={'Authorization': 'Bearer ' + token, 'apikey': SUPABASE_ANON_KEY},
                timeout=8,
            )
            if resp.status_code == 200:
                return True
        except Exception:
            pass
    return False


def push_to_supabase(data):
    import requests

    service_key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    url = SUPABASE_URL + '/rest/v1/app_state?on_conflict=key'
    headers = {
        'apikey': service_key,
        'Authorization': 'Bearer ' + service_key,
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

    # --- sleep (duration/score, plus start/end for the caffeine page's
    # wake/bedtime-aware energy model) ---
    try:
        sleep = client.get_sleep_data(today) or {}
        dto = sleep.get('dailySleepDTO') or {}
        total_seconds = dto.get('sleepTimeSeconds')
        out['sleepHours'] = round(total_seconds / 3600, 1) if total_seconds else None
        overall = (dto.get('sleepScores') or {}).get('overall') or {}
        out['sleepScore'] = overall.get('value')

        # Garmin's "...Local" timestamps are epoch-ms that decode to the
        # correct local wall-clock time when read as UTC (no separate
        # timezone field needed) - a quirk of their API, not a bug here.
        start_ms = dto.get('sleepStartTimestampLocal') or dto.get('sleepStartTimestampGMT')
        end_ms = dto.get('sleepEndTimestampLocal') or dto.get('sleepEndTimestampGMT')
        if start_ms:
            out['sleepStart'] = datetime.datetime.utcfromtimestamp(start_ms / 1000).isoformat() + 'Z'
        if end_ms:
            out['sleepEnd'] = datetime.datetime.utcfromtimestamp(end_ms / 1000).isoformat() + 'Z'
    except Exception as e:
        out['sleepError'] = str(e)

    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        auth_header = self.headers.get('Authorization', '')
        if not is_authorized(auth_header):
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
