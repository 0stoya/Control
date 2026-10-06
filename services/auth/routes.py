"""Same-origin sign-in gateway and freshly authorized staff shell."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from services.orders.access import order_access_allowed

from services.auth.gateway import (
    AuthDenied, AuthGateway, AuthUnavailable, COOKIE, ROUTES,
    json_body, session_token, translate_cookie,
)

WEB = Path(__file__).resolve().parents[2] / "web" / "static"
PRIVATE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def error(status: int, detail: str):
    return JSONResponse({"detail": detail}, status_code=status, headers=PRIVATE)


def mount_staff_routes(app: FastAPI, gateway: AuthGateway, orders_enabled=False):
    @app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def authentication(path: str, request: Request):
        fields = ROUTES.get((request.method, path))
        if fields is None or request.url.query:
            return error(404, "Not found")
        if request.method == "POST":
            if request.headers.get("origin") != gateway.public_origin:
                return error(403, "Authentication request origin denied")
            if request.headers.get("sec-fetch-site") not in {None, "same-origin"}:
                return error(403, "Authentication request origin denied")
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                return error(415, "JSON request required")
            body = await request.body()
            if len(body) > 16384:
                return error(413, "Authentication request exceeds limit")
            try:
                data = json.loads(body or b"{}")
                if not isinstance(data, dict) or set(data) != fields:
                    raise ValueError
                for key, value in data.items():
                    if not isinstance(value, str) or not value or len(value) > {"username": 320, "password": 1024, "code": 64}[key]:
                        raise ValueError
            except (ValueError, TypeError):
                return error(422, "Invalid authentication request")
            body = json.dumps(data, separators=(",", ":")).encode()
        else:
            body = None
        try:
            token = None if path == "login" else session_token(request.headers.get("cookie", ""))
            upstream = await run_in_threadpool(gateway.send, request.method, path, body, token)
            if upstream.status not in {200, 400, 401, 403, 409, 422}:
                raise AuthUnavailable("authority response unavailable")
            if path == "totp/qr" and upstream.status == 200:
                if not upstream.content_type.startswith("image/svg+xml"):
                    raise AuthUnavailable("invalid authority QR")
                response = Response(upstream.body, media_type="image/svg+xml", headers=PRIVATE)
            else:
                payload = json_body(upstream)
                response = JSONResponse(payload, status_code=upstream.status, headers=PRIVATE)
            cookie = translate_cookie(upstream.set_cookie)
            if cookie is not None:
                value, age = cookie
                response.set_cookie(COOKIE, value, max_age=age, path="/", secure=True,
                                    httponly=True, samesite="lax")
            return response
        except AuthDenied as denied:
            return error(denied.status, "Authentication required")
        except AuthUnavailable:
            return error(503, "Sign-in service is temporarily unavailable")

    @app.get("/login")
    def login():
        return FileResponse(WEB / "login.html", media_type="text/html", headers=PRIVATE)

    @app.get("/assets/{name}")
    def asset(name: str):
        allowed = {"control.css": "text/css", "orders.css": "text/css", "login.js": "application/javascript", "workspace.js": "application/javascript", "orders.js": "application/javascript"}
        if name not in allowed:
            return error(404, "Not found")
        return FileResponse(WEB / name, media_type=allowed[name], headers=PRIVATE)

    @app.get("/")
    def workspace(request: Request):
        try:
            gateway.identity(session_token(request.headers.get("cookie", "")))
            return FileResponse(WEB / "workspace.html", media_type="text/html", headers=PRIVATE)
        except AuthDenied as denied:
            if denied.status == 401:
                return RedirectResponse("/login", status_code=303, headers=PRIVATE)
            return error(403, "Your account does not have Control access")
        except AuthUnavailable:
            return error(503, "Sign-in service is temporarily unavailable")

    @app.get("/api/session")
    def current_identity(request: Request):
        try:
            user = gateway.identity(session_token(request.headers.get("cookie", "")))
            return JSONResponse({"state": "AUTHENTICATED", "user": {
                key: user.get(key) for key in ("user_id", "display_name", "operational_profile", "permissions")
            }, "capabilities": {"orders": orders_enabled and order_access_allowed(user)}}, headers=PRIVATE)
        except AuthDenied as denied:
            return error(denied.status, "Authentication required" if denied.status == 401 else "Control access required")
        except AuthUnavailable:
            return error(503, "Sign-in service is temporarily unavailable")
