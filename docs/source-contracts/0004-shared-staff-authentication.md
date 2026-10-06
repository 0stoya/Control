# Shared staff authentication contract v1

Status: Implemented and deployed on 6 October 2026. Native synthetic parity,
public boundary and rollback checks passed; controlled existing-account
password/MFA sign-in confirmed by the operator on 6 October 2026. See the staff-auth acceptance runbook.

Authority: the existing V1 `css-auth` service and its `css_app.auth` state remain
the single writer for identity, password/MFA, lockouts, sessions, recovery codes,
roles, profiles and security audit. V2 does not clone these tables or the Fernet
credential. Existing password and authenticator enrolment remain on that authority.
The operator selected this as the first sequential V2 implementation step.

## Identity, state and freshness

Identity is the original auth user ID within the registered V1 authority. The
browser owns no trusted role/user/permission fields. An opaque authority-issued
session token is the only forwarded credential. V2 uses a separate host-only
`__Host-control_v2_session` cookie, Secure/HttpOnly/SameSite=Lax/Path=/, translates
that cookie to the authority's `css_session`, and ignores all other incoming
cookies and identity/forwarding headers. It does not share cookies with V1.

Password acceptance produces PREAUTH with PASSWORD_CHANGE, TOTP_ENROLL or
TOTP_VERIFY. V2 follows the returned stage. PREAUTH grants no protected page or
API access. Existing MFA users verify the existing enrolment; unenrolled users
follow V1's existing enrolment policy. Enrolment/recovery responses remain private
and no-store. Logout revokes this session at the authority.

Each protected request obtains fresh `/auth/session/validate` evidence; no cached
positive identity or offline access. Require state AUTHENTICATED, no challenge,
enabled user, no outstanding password change, active MFA enrolment and the existing
`control.access` permission. Preserve source permissions/profile and do not infer
new entitlements from an administrator role. Shell availability does not enable
any business action or assign new department permissions. Future domain APIs
need their own explicit authorization rules.

Unknown/malformed/redirected/unavailable authority responses fail closed. Missing,
invalid, expired/revoked, disabled and PREAUTH sessions return 401; lack of Control
permission returns 403; unavailable/malformed authority returns 503. Session
validation failure never becomes an empty/anonymous successful identity.

## Private transport and public surface

Use a dedicated noninteractive SSH forwarding identity and a dedicated key
generated/stored on V2. Only its public key reaches V1. Pin V1's public host key
obtained over the existing strictly verified management connection. Forward
V2 loopback 18020 to V1 loopback 8020, with strict host checks and bounded reconnects.
On V1 this identity is restricted to source IP 85.215.119.154, public-key auth,
local forwarding to 127.0.0.1:8020 only, no remote/Unix forwarding, shell, PTY,
agent, X11 or user RC. Preserve management access and test sshd syntax/policy
before reload. The transport has no V1 database/file privilege.

The V2 HTTP gateway exposes a fixed sign-in route allowlist only: login,
challenge, password/change, totp/setup, totp/qr, totp/confirm, totp/verify, me and
logout. It does not proxy arbitrary paths, queries, administration, email or
invitation endpoints. Forward only the selected opaque cookie, approved JSON
payload and Accept/Content-Type; ignore client-supplied identity/authorization
headers. Disable proxies, redirects, retries and upstream error-body logging.
Bound request/response sizes and timeouts. A failed POST is never auto-replayed.

Require the exact configured HTTPS Origin for every POST, plus same-origin
Fetch Metadata when supplied; reject absent/foreign Origin before contacting
the authority. Nginx enforces request/rate limits, strips forwarding/identity
headers and routes through the private V2 API. Public auth health and private
API health are unavailable from the public host. CSP uses same-origin external
script/style files without inline execution; all auth and staff responses are
no-store. Passwords, tokens, MFA seeds and recovery codes are never logged,
stored in browser storage or used in production test fixtures.

## Events, reconciliation and rollback

The authority retains login, MFA, enrolment, password, lockout and logout audit
events. V2 does not invent a second security event/state writer. Deploying a shell
does not move existing roles, business authority, auth storage or mail sending.

Verify configuration, source/public host-key fingerprint, forwarding restrictions,
live authority health, absent/forged/PREAUTH sessions, Origin denial, permissions,
cookie attributes, upstream failure and protected routes. Exercise a synthetic
isolated authoritative auth harness for password/MFA/recovery/replay laws. Final
existing-account acceptance requires a staff member to sign in on V2 using their
existing password and authenticator; no private credentials are requested in chat.
Do not generate login failures against real staff accounts as a diagnostic.

Rollback restores the previous V2 application/proxy release and stops the bridge
if necessary. Retain the single V1 auth state, including consumed counters and
recovery codes. Do not restore an older auth snapshot. Test bridge restart and
failure closed before enabling the public entrypoint. Current service health is
separate from controlled real-account acceptance.

References: [authentication continuity](../runbooks/authentication-migration.md),
[OpenSSH key restrictions](https://man.openbsd.org/sshd.8#AUTHORIZED_KEYS_FILE_FORMAT),
[Nginx proxy headers](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).
