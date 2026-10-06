import asyncio
from http.cookies import SimpleCookie
import json
import unittest

from services.api.app import create_app
from services.auth.gateway import (AuthDenied, AuthGateway, AuthUnavailable, COOKIE,
                                   UpstreamResponse, session_token, translate_cookie)

ORIGIN = "https://control.csscdn.co.uk"
TOKEN = "s" * 64  # V1 token_urlsafe(48); synthetic, never a live session.


def upstream(value, status=200, cookie=None):
    return UpstreamResponse(status, json.dumps(value).encode(), set_cookie=cookie)


def identity(**overrides):
    return {"state": "AUTHENTICATED", "stage": None, "user": {
        "user_id": 42, "display_name": "Synthetic Staff", "enabled": True,
        "must_change_password": False, "totp_enabled": True,
        "permissions": ["control.access"], "roles": ["control_user"],
        "operational_profile": "purchasing", **overrides,
    }}


async def request(app, path, method="GET", headers=None, body=b"", query=b""):
    messages = []
    delivered = False
    completed = asyncio.Event()
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": method, "scheme": "https", "path": path, "raw_path": path.encode(),
             "query_string": query, "root_path": "", "headers": headers or [],
             "client": ("127.0.0.1", 1234), "server": ("control.csscdn.co.uk", 443)}
    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await completed.wait()
        return {"type": "http.disconnect"}
    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            completed.set()
    await app(scope, receive, send)
    start = next(item for item in messages if item["type"] == "http.response.start")
    payload = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), payload


class StaffAuthTests(unittest.TestCase):
    def app(self, result=None):
        self.calls = []
        def send(method, path, body, token):
            self.calls.append((method, path, body, token))
            if isinstance(result, Exception):
                raise result
            if result is not None:
                return result
            if path == "health":
                return upstream({"status": "ok", "database": "css_app", "database_user": "css_auth"})
            return upstream(identity())
        return create_app(lambda: True, AuthGateway(ORIGIN, send))

    def ask(self, app, path, **kwargs):
        return asyncio.run(request(app, path, **kwargs))

    def post_headers(self):
        return [(b"origin", ORIGIN.encode()), (b"content-type", b"application/json")]

    def cookie_headers(self):
        return [(b"cookie", (COOKIE + "=" + TOKEN).encode())]

    def test_anonymous_and_client_identity_headers_do_not_authorize(self):
        app = self.app()
        status, _, _ = self.ask(app, "/api/session", headers=[(b"x-auth-user", b"42"), (b"x-auth-permissions", b"control.access")])
        self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ask(app, "/")[0], 303)

    def test_control_cookie_only_and_revalidation_on_every_request(self):
        app = self.app()
        headers = self.cookie_headers() + [(b"authorization", b"Bearer injected")]
        for _ in range(2):
            status, response_headers, body = self.ask(app, "/api/session", headers=headers)
            self.assertEqual(status, 200)
            self.assertEqual(response_headers[b"cache-control"], b"no-store")
            self.assertEqual(json.loads(body)["user"]["user_id"], 42)
        self.assertEqual(self.calls, [("GET", "session/validate", None, TOKEN)] * 2)
        self.assertEqual(self.ask(app, "/api/session", headers=[(b"cookie", ("css_session=" + TOKEN).encode())])[0], 401)

    def test_preauth_disabled_no_mfa_and_password_change_deny(self):
        values = [upstream({"state": "PREAUTH", "stage": "TOTP_VERIFY", "user": identity()["user"]})]
        values += [upstream(identity(**override)) for override in
                   ({"enabled": False}, {"totp_enabled": False}, {"must_change_password": True})]
        for result in values:
            with self.subTest(result=result):
                self.assertEqual(self.ask(self.app(result), "/api/session", headers=self.cookie_headers())[0], 401)

    def test_administrator_role_does_not_invent_control_permission(self):
        app = self.app(upstream(identity(roles=["administrator"], permissions=[])))
        self.assertEqual(self.ask(app, "/api/session", headers=self.cookie_headers())[0], 403)
        self.assertEqual(self.ask(app, "/", headers=self.cookie_headers())[0], 403)

    def test_authority_outage_and_malformed_identity_fail_closed(self):
        for result in (AuthUnavailable("private-credential"), upstream({"state": "AUTHENTICATED"}),
                       upstream(identity(user_id=True)), UpstreamResponse(200, b"secret-invalid", "text/plain")):
            app = self.app(result)
            status, _, body = self.ask(app, "/api/session", headers=self.cookie_headers())
            self.assertIn(status, (401, 503))
            self.assertNotIn(b"private", body)
            self.assertNotIn(b"secret", body)

    def test_origin_and_fetch_metadata_are_checked_before_forwarding(self):
        for headers in ([ (b"content-type", b"application/json") ],
                        [(b"origin", b"https://attacker.invalid"), (b"content-type", b"application/json")],
                        self.post_headers() + [(b"sec-fetch-site", b"same-site")]):
            app = self.app()
            self.assertEqual(self.ask(app, "/auth/login", method="POST", headers=headers, body=b'{"username":"synthetic","password":"synthetic"}')[0], 403)
            self.assertEqual(self.calls, [])

    def test_unknown_methods_routes_queries_and_payload_fields_are_rejected(self):
        app = self.app()
        for path, method, query in (("/auth/admin/users", "GET", b""), ("/auth/login", "PATCH", b""),
                                    ("/auth/login", "POST", b"password=private")):
            self.assertEqual(self.ask(app, path, method=method, headers=self.post_headers(), query=query)[0], 404)
        self.assertEqual(self.ask(app, "/auth/login", method="POST", headers=self.post_headers(), body=b'{"username":"synthetic","password":"synthetic","roles":["administrator"]}')[0], 422)
        self.assertEqual(self.calls, [])

    def test_login_is_forwarded_once_and_cookie_is_host_only_secure(self):
        cookie = "css_session=" + TOKEN + "; HttpOnly; Max-Age=43200; Path=/; SameSite=lax; Secure"
        app = self.app(upstream({"state": "PREAUTH", "stage": "TOTP_VERIFY"}, cookie=cookie))
        headers = self.post_headers() + [(b"cookie", b"invalid=ignored"), (b"x-auth-user", b"42")]
        status, response_headers, _ = self.ask(app, "/auth/login", method="POST", headers=headers,
                                             body=b'{"username":"synthetic","password":"synthetic"}')
        self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.calls[0][3])
        value = SimpleCookie(response_headers[b"set-cookie"].decode())[COOKIE]
        self.assertTrue(value["secure"] and value["httponly"])
        self.assertEqual((value["path"], value["domain"], value["samesite"]), ("/", "", "lax"))

    def test_logout_clears_translated_cookie_without_domain(self):
        app = self.app(upstream({"status": "ok"}, cookie='css_session=""; HttpOnly; Max-Age=0; Path=/; SameSite=lax; Secure'))
        status, headers, _ = self.ask(app, "/auth/logout", method="POST", headers=self.post_headers()+self.cookie_headers(), body=b'{}')
        self.assertEqual(status, 200)
        self.assertEqual(SimpleCookie(headers[b"set-cookie"].decode())[COOKIE]["max-age"], "0")

    def test_bad_and_duplicate_tokens_and_authority_domain_cookie_are_denied(self):
        for header in (COOKIE + "=wrong", COOKIE + "=" + TOKEN + "; " + COOKIE + "=" + TOKEN):
            with self.assertRaises(AuthDenied):
                session_token(header)
        with self.assertRaises(AuthUnavailable):
            translate_cookie("css_session=" + TOKEN + "; Domain=csscdn.co.uk; HttpOnly; Max-Age=43200; Path=/; SameSite=lax; Secure")

    def test_private_paths_and_failed_authority_prevent_readiness(self):
        app = self.app(AuthUnavailable("private"))
        self.assertEqual(self.ask(app, "/health/ready")[0], 503)
        self.assertEqual(self.ask(app, "/auth/health")[0], 404)
        self.assertEqual(self.ask(app, "/api/orders")[0], 404)

    def test_upstream_failed_post_does_not_retry_or_return_private_error(self):
        app = self.app(UpstreamResponse(500, b"private-password"))
        status, _, body = self.ask(app, "/auth/login", method="POST", headers=self.post_headers(),
                                 body=b'{"username":"synthetic","password":"synthetic"}')
        self.assertEqual(status, 503)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn(b"private", body)


if __name__ == "__main__":
    unittest.main()
