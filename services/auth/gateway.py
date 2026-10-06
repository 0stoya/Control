"""Bounded auth-only transport; no state replication or credential logging."""
from __future__ import annotations

from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from http.client import HTTPException as HttpClientError
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

COOKIE = "__Host-control_v2_session"
# V1 generates token_urlsafe(48): 64 opaque URL-safe characters.
TOKEN = re.compile(r"^[A-Za-z0-9_-]{64}$")
AUTH_ORIGIN = "http://127.0.0.1:18020"
MAX_RESPONSE = 200_000
ROUTES = {
    ("POST", "login"): {"username", "password"},
    ("GET", "challenge"): set(),
    ("POST", "password/change"): {"password"},
    ("POST", "totp/setup"): set(),
    ("GET", "totp/qr"): set(),
    ("POST", "totp/confirm"): {"code"},
    ("POST", "totp/verify"): {"code"},
    ("GET", "me"): set(),
    ("POST", "logout"): set(),
}


class AuthUnavailable(RuntimeError):
    pass


class AuthDenied(RuntimeError):
    def __init__(self, status=401):
        self.status = status


@dataclass(frozen=True)
class UpstreamResponse:
    status: int
    body: bytes
    content_type: str = "application/json"
    set_cookie: str | None = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transport(method: str, path: str, body: bytes | None, token: str | None) -> UpstreamResponse:
    if (method, path) not in ROUTES and (method, path) not in {
        ("GET", "session/validate"), ("GET", "health"),
    }:
        raise AuthUnavailable("uncontracted authority route")
    headers = {"Accept": "application/json"}
    if token:
        if not TOKEN.fullmatch(token):
            raise AuthDenied()
        headers["Cookie"] = "css_session=" + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(AUTH_ORIGIN + "/auth/" + path, data=body, headers=headers, method=method)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        try:
            response = opener.open(request, timeout=4)
        except HTTPError as error:
            response = error
        with response:
            if response.status not in {200, 400, 401, 403, 409, 422}:
                raise AuthUnavailable("authority unavailable")
            payload = response.read(MAX_RESPONSE + 1)
            if len(payload) > MAX_RESPONSE:
                raise AuthUnavailable("authority response exceeds budget")
            return UpstreamResponse(response.status, payload,
                                    response.headers.get("Content-Type", ""),
                                    response.headers.get("Set-Cookie"))
    except (URLError, OSError, ValueError, HttpClientError):
        raise AuthUnavailable("authority transport unavailable") from None


def session_token(cookie_header: str) -> str | None:
    if len(cookie_header) > 8192:
        raise AuthDenied()
    found = []
    for part in cookie_header.split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key == COOKIE:
            found.append(value)
    if not found:
        return None
    if len(found) != 1 or not TOKEN.fullmatch(found[0]):
        raise AuthDenied()
    return found[0]


def translate_cookie(header: str | None) -> tuple[str, int] | None:
    if not header:
        return None
    try:
        cookie = SimpleCookie()
        cookie.load(header)
        if set(cookie) != {"css_session"}:
            raise ValueError
        item = cookie["css_session"]
        age = int(item["max-age"])
        if age < 0 or age > 43200 or item["domain"] or item["path"] != "/":
            raise ValueError
        if not item["secure"] or not item["httponly"] or item["samesite"].lower() != "lax":
            raise ValueError
        if age != 0 and not TOKEN.fullmatch(item.value):
            raise ValueError
        return item.value if age else "", age
    except (ValueError, KeyError, TypeError, CookieError):
        raise AuthUnavailable("invalid authority cookie") from None


def json_body(response: UpstreamResponse) -> dict:
    try:
        if not response.content_type.lower().startswith("application/json"):
            raise ValueError
        value = json.loads(response.body)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise AuthUnavailable("invalid authority response") from None


class AuthGateway:
    def __init__(self, public_origin: str, send=transport):
        if public_origin not in {"https://control.csscdn.co.uk", "https://control.chelmsfordsafety.co.uk"}:
            raise ValueError("reviewed HTTPS public origin required")
        self.public_origin = public_origin
        self.send = send

    def identity(self, token: str | None) -> dict:
        if not token:
            raise AuthDenied()
        response = self.send("GET", "session/validate", None, token)
        if response.status in {401, 403}:
            raise AuthDenied(response.status)
        if response.status != 200:
            raise AuthUnavailable("authority session unavailable")
        body = json_body(response)
        user = body.get("user")
        if body.get("state") != "AUTHENTICATED" or body.get("stage") is not None or not isinstance(user, dict):
            raise AuthDenied()
        if (user.get("enabled") is not True or user.get("must_change_password") is not False
                or user.get("totp_enabled") is not True):
            raise AuthDenied()
        if type(user.get("user_id")) is not int or user["user_id"] < 1:
            raise AuthUnavailable("invalid authority identity")
        permissions = user.get("permissions")
        if not isinstance(permissions, list) or not all(isinstance(x, str) for x in permissions):
            raise AuthUnavailable("invalid authority entitlements")
        if "control.access" not in permissions:
            raise AuthDenied(403)
        return user

    def healthy(self) -> bool:
        try:
            response = self.send("GET", "health", None, None)
            body = json_body(response)
            return response.status == 200 and body.get("status") == "ok" and body.get("database") == "css_app" and body.get("database_user") == "css_auth"
        except AuthUnavailable:
            return False
