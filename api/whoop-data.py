"""
Proxies read-only requests to the WHOOP API so the browser doesn't hit
api.prod.whoop.com directly (CORS + keeps this a thin passthrough).

Usage from the browser:
  GET /api/whoop-data?type=recovery   -> forwards to WHOOP GET /v2/recovery
  GET /api/whoop-data?type=sleep      -> forwards to WHOOP GET /v2/activity/sleep
  Header: Authorization: Bearer <access_token>   (from whoop_tokens_v1)

Returns WHOOP's JSON response body as-is, with WHOOP's status code passed
through (so the caller can detect a 401 and hit /api/whoop-refresh).
No credentials of ours are involved here - this only forwards the
caller's own access token, so it needs no env vars.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

WHOOP_API_BASE = 'https://api.prod.whoop.com/developer'

TYPE_PATHS = {
    'recovery': '/v2/recovery',
    'sleep': '/v2/activity/sleep',
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        import requests

        query = parse_qs(urlparse(self.path).query)
        req_type = (query.get('type') or [''])[0]
        path = TYPE_PATHS.get(req_type)
        if not path:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'type must be "recovery" or "sleep"'}).encode('utf-8'))
            return

        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'missing bearer token'}).encode('utf-8'))
            return

        try:
            resp = requests.get(
                WHOOP_API_BASE + path,
                headers={'Authorization': auth_header},
                params={'limit': 5},
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
