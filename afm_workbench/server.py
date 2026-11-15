"""Loopback-only HTTP transport. No data access without a per-launch token."""
from __future__ import annotations

from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import hmac
import json
import secrets

from . import MAX_REQUEST_BYTES


def create_server(workbench, host='127.0.0.1', port=0):
    if host != '127.0.0.1':
        raise ValueError('The desktop service binds only to 127.0.0.1.')
    static = Path(__file__).parent / 'static'
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, format, *args):
            pass

        def _host_allowed(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def _origin_allowed(self):
            origin = self.headers.get('Origin')
            return origin is None or origin == self.server.url.rstrip('/')

        def _authorized(self, header=False):
            given = self.headers.get('X-AFM-Token', '')
            if not header:
                try:
                    jar = cookies.SimpleCookie(self.headers.get('Cookie', ''))
                    given = jar['afm_session'].value if 'afm_session' in jar else given
                except cookies.CookieError:
                    return False
            return hmac.compare_digest(given, token)

        def _send(self, status, body, mime='application/json', cookie=False):
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') or mime == 'application/json' else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'")
            if cookie:
                self.send_header('Set-Cookie', f'afm_session={token}; Path=/; HttpOnly; SameSite=Strict')
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message):
            self.close_connection = True
            self._send(status, json.dumps({'error': message}))

        def do_GET(self):
            if not self._host_allowed() or not self._origin_allowed():
                return self._error(403, 'Request origin is not allowed.')
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path.startswith('/api/thumbnail/'):
                if not self._authorized():
                    return self._error(403, 'Session token is required.')
                try:
                    params = parse_qs(parsed.query)
                    png = workbench.thumbnail(path.removeprefix('/api/thumbnail/'),
                                              recipe=params.get('recipe', ['1'])[0] != '0',
                                              palette=params.get('palette', [None])[0],
                                              contrast=params.get('contrast', [None])[0],
                                              level=params.get('level', ['0'])[0] == '1')
                    return self._send(200, png, 'image/png')
                except (ValueError, OSError) as exc:
                    return self._error(400, str(exc))
            files = {'/': ('index.html', 'text/html'), '/index.html': ('index.html','text/html'),
                     '/app.js': ('app.js','text/javascript'), '/style.css': ('style.css','text/css'),
                     '/canvas-controls.js': ('canvas-controls.js','text/javascript'),
                     '/display-controls.js': ('display-controls.js','text/javascript'),
                     '/display-controls.css': ('display-controls.css','text/css'),
                     '/mask-controls.js': ('mask-controls.js','text/javascript'),
                     '/mask-controls.css': ('mask-controls.css','text/css'),
                     '/favicon.svg': ('favicon.svg','image/svg+xml')}
            if path not in files:
                return self._error(404, 'Not found.')
            filename, mime = files[path]
            try:
                content = (static / filename).read_text(encoding='utf-8')
                if filename == 'index.html':
                    content = content.replace('__AFM_TOKEN__', token)
                self._send(200, content, mime, cookie=filename == 'index.html')
            except OSError:
                self._error(404, 'Application asset not found.')

        def do_POST(self):
            if not self._host_allowed() or not self._origin_allowed() or not self._authorized(header=True):
                return self._error(403, 'Session token and same-origin access are required.')
            path = urlparse(self.path).path
            if not path.startswith('/api/') or '/' in path[5:]:
                return self._error(404, 'Not found.')
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self._error(415, 'Use application/json.')
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= MAX_REQUEST_BYTES:
                    return self._error(413, 'Request is too large or has no content length.')
                payload = json.loads(self.rfile.read(length))
                result = workbench.dispatch(path[5:], payload)
                self._send(200, json.dumps(result, ensure_ascii=False, allow_nan=False))
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self._error(400, str(exc))
            except Exception:
                self._error(500, 'The operation could not be completed. Your original files are unchanged.')

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.token = token
    server.url = f'http://127.0.0.1:{server.server_port}/'
    return server
