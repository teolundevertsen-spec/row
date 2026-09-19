"""
Refreshes an expired WHOOP access token using the stored refresh token.

Usage from the browser:
  POST /api/whoop-refresh   body: {"refresh_token": "..."}
  -> { access_token, refresh_token, expires_in, ... } on success

Needs WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET as Vercel env vars - the
token refresh grant requires the app's client secret, which must never
be sent to or stored in the browser. If those env vars aren't set,
this just 500s and the caffeine page's WHOOP integration quietly stays
disabled (data sources are meant to degrade gracefully when missing).
"""

from http.server import BaseHTTPRequestHandler
import os
import json

WHOOP_TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        import requests

        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b'{}'
        try:
            body = json.loads(raw or b'{}')
        except Exception:
            body = {}
        refresh_token = body.get('refresh_token')

        client_id = os.environ.get('WHOOP_CLIENT_ID')
        client_secret = os.environ.get('WHOOP_CLIENT_SECRET')

        if not refresh_token or not client_id or not client_secret:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'missing refresh_token or WHOOP client env vars'}).encode('utf-8'))
            return

        try:
            resp = requests.post(
                WHOOP_TOKEN_URL,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'scope': 'offline',
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
            )
            self.send_response(resp.status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
