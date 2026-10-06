import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch

from services.auth import gateway


class AuthTransportTests(unittest.TestCase):
    def test_redirect_does_not_forward_credentials_and_response_budget_is_bounded(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                seen.append((self.path, dict(self.headers),
                             self.rfile.read(int(self.headers.get("Content-Length", "0")))))
                self.send_response(307)
                self.send_header("Location", "/credential-sink")
                self.end_headers()
            def do_GET(self):
                seen.append((self.path, dict(self.headers), b""))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try:
                    self.wfile.write(b"x" * (gateway.MAX_RESPONSE + 1))
                except (BrokenPipeError, ConnectionResetError):
                    pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(gateway, "AUTH_ORIGIN", f"http://127.0.0.1:{server.server_port}"):
                with self.assertRaises(gateway.AuthUnavailable):
                    gateway.transport("POST", "login", b'{"password":"synthetic"}', None)
                self.assertEqual([item[0] for item in seen], ["/auth/login"])
                with self.assertRaises(gateway.AuthUnavailable):
                    gateway.transport("GET", "session/validate", None, "s" * 64)
                self.assertEqual(seen[-1][1]["Cookie"], "css_session=" + "s" * 64)
                self.assertNotIn("Authorization", seen[-1][1])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unknown_route_is_rejected_before_network(self):
        with patch.object(gateway, "build_opener") as opener:
            with self.assertRaises(gateway.AuthUnavailable):
                gateway.transport("POST", "admin/users", b"{}", None)
            opener.assert_not_called()
