"""Operator-only V1 integration: synthetic users, disposable DB, no live auth writes.

Run as postgres using the reviewed V1 venv, with V1_ROOT and V2_GATEWAY_FILE.
The disposable database, generated Fernet key and sessions are removed in finally.
"""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

import psycopg
from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.requests import Request
import pyotp

ROOT = Path(os.environ["V1_ROOT"]).resolve()
sys.path.insert(0, str(ROOT))
from services.auth import security, store, http_app as auth

spec = importlib.util.spec_from_file_location("v2_gateway", os.environ["V2_GATEWAY_FILE"])
gateway = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gateway
spec.loader.exec_module(gateway)
DB = "control_auth_acceptance_" + secrets.token_hex(6)
assert DB.startswith("control_auth_acceptance_") and DB != "css_app"
checks = {}

def require(name, condition):
    assert condition, name
    checks[name] = True

def invoke(method, path, body, token):
    request = Request({"type": "http", "headers": (
        [(b"cookie", ("css_session=" + token).encode())] if token else [])})
    data = json.loads(body) if body else {}
    try:
        if path == "login":
            result = auth.login(auth.LoginRequest(**data))
        elif path == "password/change":
            result = auth.change_password(auth.PasswordChangeRequest(**data), request)
        elif path == "totp/setup":
            result = auth.totp_setup(request)
        elif path == "totp/qr":
            result = auth.totp_qr(request)
        elif path == "totp/confirm":
            result = auth.totp_confirm(auth.TotpCodeRequest(**data), request)
        elif path == "totp/verify":
            result = auth.totp_verify(auth.TotpCodeRequest(**data), request)
        elif path == "challenge":
            result = auth.challenge(request)
        elif path == "session/validate":
            result = auth.me(request)
        elif path == "logout":
            result = auth.logout(request)
        else:
            raise AssertionError(path)
        if isinstance(result, dict):
            return gateway.UpstreamResponse(200, json.dumps(result, default=str).encode())
        return gateway.UpstreamResponse(result.status_code, result.body,
            result.headers.get("content-type", ""), result.headers.get("set-cookie"))
    except HTTPException as error:
        return gateway.UpstreamResponse(error.status_code, json.dumps({"detail": error.detail}).encode())

def call(path, token=None, **data):
    response = invoke("POST" if path in {"login", "password/change", "totp/setup", "totp/confirm", "totp/verify", "logout"} else "GET",
                      path, json.dumps(data).encode() if data else None, token)
    return response, gateway.json_body(response)

def login(password):
    response, value = call("login", username="synthetic.staff", password=password)
    require("password_login", response.status == 200)
    token, age = gateway.translate_cookie(response.set_cookie)
    require("native_token_cookie_accepted", len(token) == 64 and age == 43200)
    return token, value

def denied_identity(bridge, token, expected=401):
    try:
        bridge.identity(token)
    except gateway.AuthDenied as error:
        assert error.status == expected
        return True
    return False

with tempfile.TemporaryDirectory(prefix="control-auth-parity-") as temporary:
    key = Path(temporary) / "synthetic.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    os.environ["CSS_AUTH_TOTP_KEY_FILE"] = str(key)
    os.environ["CSS_AUTH_DATABASE_URL"] = "postgresql:///" + DB
    with psycopg.connect("postgresql:///postgres", autocommit=True) as admin:
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(DB)))
    try:
        with store.connect() as conn:
            for name in ("0003_auth.sql", "0004_operational_profiles.sql",
                         "0010_auth_sales_scope.sql", "0011_auth_user_invitations.sql"):
                conn.execute((ROOT / "services/api/migrations" / name).read_text())
            user = store.insert_user(conn, username="synthetic.staff",
                email="staff@example.invalid", display_name="Synthetic Staff",
                password_hash=security.hash_password("Synthetic temporary password"),
                roles=["control_user"], operational_profile="purchasing")
            user_id = user["user_id"]
        bridge = gateway.AuthGateway("https://control.csscdn.co.uk", invoke)
        token, value = login("Synthetic temporary password")
        require("temporary_password_stage", value["stage"] == "PASSWORD_CHANGE")
        require("partial_mfa_denied", denied_identity(bridge, token))
        response, value = call("password/change", token, password="Synthetic permanent password")
        require("password_change_enrol_stage", response.status == 200 and value["stage"] == "TOTP_ENROLL")
        _, setup = call("totp/setup", token)
        qr = invoke("GET", "totp/qr", None, token)
        require("private_qr", qr.status == 200 and qr.content_type.startswith("image/svg+xml"))
        enrol_code = pyotp.TOTP(setup["secret"]).now()
        response, value = call("totp/confirm", token, code=enrol_code)
        require("enrolment_and_identity", response.status == 200 and bridge.identity(token)["user_id"] == user_id)
        codes = value["recovery_codes"]
        token2, value = login("Synthetic permanent password")
        require("existing_password_and_mfa_retained", value["stage"] == "TOTP_VERIFY")
        replay, _ = call("totp/verify", token2, code=enrol_code)
        require("totp_replay_denied", replay.status == 401)
        counter = pyotp.TOTP(setup["secret"]).timecode(store.utcnow()) + 1
        verified, _ = call("totp/verify", token2, code=pyotp.TOTP(setup["secret"]).generate_otp(counter))
        require("existing_authenticator_accepted", verified.status == 200 and bridge.identity(token2)["user_id"] == user_id)
        token3, _ = login("Synthetic permanent password")
        recovered, _ = call("totp/verify", token3, code=codes[0])
        require("recovery_code_accepted", recovered.status == 200)
        token4, _ = login("Synthetic permanent password")
        used, _ = call("totp/verify", token4, code=codes[0])
        require("recovery_code_single_use", used.status == 401)
        wrong, _ = call("login", username="synthetic.staff", password="Synthetic incorrect password")
        require("wrong_password_denied", wrong.status == 401)
        with store.connect() as conn:
            conn.execute("UPDATE auth.app_user SET locked_until=now()+interval '15 minutes' WHERE user_id=%s", (user_id,))
        locked, _ = call("login", username="synthetic.staff", password="Synthetic permanent password")
        require("locked_user_denied", locked.status == 401)
        with store.connect() as conn:
            conn.execute("UPDATE auth.app_user SET enabled=false WHERE user_id=%s", (user_id,))
        require("disabled_session_denied", denied_identity(bridge, token3))
        with store.connect() as conn:
            conn.execute("UPDATE auth.app_user SET enabled=true, locked_until=NULL WHERE user_id=%s", (user_id,))
            conn.execute("DELETE FROM auth.user_role WHERE user_id=%s", (user_id,))
        require("permission_removal_immediate", denied_identity(bridge, token3, 403))
        with store.connect() as conn:
            store.set_roles(conn, user_id, ["control_user"])
        loggedout, _ = call("logout", token3)
        require("logout_revocation", loggedout.status == 200 and denied_identity(bridge, token3))
        token5, _ = login("Synthetic permanent password")
        key.write_bytes(Fernet.generate_key())
        broken, _ = call("totp/verify", token5, code=codes[1])
        require("wrong_encryption_key_fails_closed", broken.status == 500 and denied_identity(bridge, token5))
    finally:
        with psycopg.connect("postgresql:///postgres", autocommit=True) as admin:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(DB)))
        checks["disposable_database_removed"] = True
print(json.dumps({"synthetic_native_auth_checks": checks, "live_auth_state_modified": False}))
