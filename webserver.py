#!/usr/bin/env python3
"""Simple HTTP Web Server using Python's built-in http.server module."""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

HOST = "0.0.0.0"
PORT = 8080


class SimpleHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler."""

    def _send_response(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_response(status, "application/json; charset=utf-8", body)

    def _send_html(self, status: int, html: str):
        self._send_response(status, "text/html; charset=utf-8", html.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Simple Web Server</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
        code { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>Welcome to Simple Web Server</h1>
    <p>Available endpoints:</p>
    <div class="endpoint"><code>GET /</code> - This page</div>
    <div class="endpoint"><code>GET /api/hello</code> - JSON greeting</div>
    <div class="endpoint"><code>GET /api/echo?msg=your_message</code> - Echo your message</div>
    <div class="endpoint"><code>POST /api/data</code> - Echo POST body as JSON</div>
</body>
</html>"""
            self._send_html(200, html)

        elif path == "/api/hello":
            self._send_json(200, {"message": "Hello, World!", "status": "ok"})

        elif path == "/api/echo":
            msg = query.get("msg", ["No message provided"])[0]
            self._send_json(200, {"echo": msg})

        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {"raw": body}

            self._send_json(200, {"received": data, "status": "ok"})
        else:
            self._send_json(404, {"error": "Not found"})


def main():
    server = HTTPServer((HOST, PORT), SimpleHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
