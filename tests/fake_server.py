"""A small HTTP server on 127.0.0.1 for the remote tests, standing in for Zenodo.

It serves `files` ({name: bytes}) at http://127.0.0.1:<port>/<name>: HEAD gives
the size, GET with a Range header gives those bytes (206), GET without one
the whole file (200). Every request is logged in `requests`, and `sent`
counts the bytes of each file that really left the server.

`failures` ({name: mode}) makes one file misbehave:
    "404", "403"      every request gets that status
    "429 once"        the first request gets 429 with Retry-After: 3, then normal
    "no length"       no Content-Length anywhere; GET always sends the whole file
    "ignore range"    HEAD gives the size, GET always sends the whole file (200)
    "short range"     a 206 carries one byte less than asked
"""

import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeServer:
    def __init__(self):
        self.files = {}
        self.failures = {}
        self.requests = []  # (method, name, Range header or None)
        self.sent = {}  # name -> bytes of the body written to the client
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # keep the test output clean

            def do_HEAD(self):
                server.handle(self, "HEAD")

            def do_GET(self):
                server.handle(self, "GET")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )  # a short poll: stop() waits for it

    def url(self, name):
        return f"http://127.0.0.1:{self.httpd.server_port}/{name}"

    def gets(self, name):
        """The Range headers of the GET requests for one file (None: the whole file)."""
        return [r for method, n, r in self.requests if method == "GET" and n == name]

    def handle(self, request, method):
        name = request.path.lstrip("/")
        byte_range = request.headers.get("Range")
        self.requests.append((method, name, byte_range))
        mode = self.failures.get(name)
        if name not in self.files or mode in ("404", "403"):
            request.send_response(int(mode or 404))
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        if mode == "429 once":
            del self.failures[name]
            request.send_response(429)
            request.send_header("Retry-After", "3")
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        data = self.files[name]
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", byte_range or "")
        if method == "GET" and match and mode not in ("no length", "ignore range"):
            start, end = int(match[1]), min(int(match[2]), len(data) - 1)
            body = data[start : end + 1]
            if mode == "short range":
                body = body[:-1]
            request.send_response(206)
            request.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        else:
            body = data
            request.send_response(200)
        if mode != "no length":  # without it, the body ends when the connection closes
            request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        if method == "GET":
            for start in range(0, len(body), 1 << 16):  # in pieces, to count what got through
                chunk = body[start : start + (1 << 16)]
                try:
                    request.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break  # the client stopped reading, as it should when it gets the wrong answer
                self.sent[name] = self.sent.get(name, 0) + len(chunk)

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
