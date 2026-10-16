"""Run the unchanged public probe against real loopback responses only."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import urllib.error
import urllib.parse
import urllib.request

class Handler(BaseHTTPRequestHandler):
    unhealthy = False
    def log_message(self, *args):
        pass
    def do_GET(self):
        status = 200
        location = None
        if self.path == '/api/contact': status = 405
        if self.path == '/pricing' and self.unhealthy: status = 503
        if self.path == '/canonical':
            status, location = 308, 'https://www.globriq.com/'
        if self.path == '/protected':
            status, location = 302, 'https://vercel.com/sso-api?opaque=not-retained'
        self.send_response(status)
        for k, v in {'Content-Security-Policy': "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
                     'Content-Security-Policy-Report-Only': "default-src 'self'",
                     'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                     'Strict-Transport-Security': 'max-age=63072000'}.items(): self.send_header(k, v)
        if location: self.send_header('Location', location)
        self.end_headers()
        self.wfile.write(b'<form data-el="cform" action="/api/contact" method="post"></form>')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

class Loopback:
    def __init__(self, port):
        self.port = port
        self.opener = urllib.request.build_opener(NoRedirect)
    def open(self, req, timeout):
        assert req.method == 'GET' and req.data is None
        url = urllib.parse.urlsplit(req.full_url)
        path = url.path
        if url.hostname == 'globriq.com': path = '/canonical'
        if 'globriq-website-' in url.hostname: path = '/protected'
        local = urllib.request.Request('http://127.0.0.1:' + str(self.port) + path, method='GET')
        try: return self.opener.open(local, timeout=timeout)
        except urllib.error.HTTPError as e: return e

def samples(unhealthy):
    from monitor import probe
    Handler.unhealthy = unhealthy
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        opener = Loopback(server.server_port)
        return probe(opener), probe(opener)
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    first, second = samples(True)
    assert len(first) == len(second) == 1
    assert first[0]['kind'] == 'status' and first[0]['status'] == 503
    assert samples(False) == ([], [])
    print('Actual loopback healthy/503 probes PASS; production requests: 0')
