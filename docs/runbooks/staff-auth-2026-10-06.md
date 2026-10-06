# Staff sign-in and V2 shell acceptance

6 October 2026. Public activation and existing-staff acceptance are pending until
the host checks below are recorded. No business migration belongs to this step.

## Implemented and tested

- Explicit auth source contract and single V1 writer, bounded auth-only gateway,
  same-origin mutation checks and explicit control.access permission.
- Separate Secure, HttpOnly, SameSite=Lax, host-only V2 cookie. V1 generates
  token_urlsafe(48), giving 64 opaque URL-safe characters; native integration
  proves that the real cookie is accepted and translated.
- Existing password/MFA, required password changes, enrolment/QR and one-time
  recovery-code display. Protected staff shell with forthcoming workspaces.
- 68 local Python tests, six foundation PostgreSQL checks and both JavaScript
  syntax checks passed.
- A disposable native PostgreSQL database on FSE-root exercised reviewed V1 auth
  code using generated synthetic identities and a separate generated Fernet key.
  Nineteen assertions passed: password/enrolment/MFA, replay prevention, recovery
  consumption, lockout/disable/permission removal, logout, wrong-key failure and
  cleanup. No live staff state or auth credential was copied or changed.
- Private forwarding-only identity provisioned on both hosts. Key generated and
  retained on CSS-Live, with pinned V1 host key. Native negative probes denied
  shell access, database forwarding and reverse forwarding; allowed auth health
  succeeded. Existing root management access remained available.

## Deployment

From a clean committed Control checkout, inspect then apply:

    python -B scripts/deploy_staff_auth.py --expected-current foundation-20261006-c2126cc8e286
    python -B scripts/deploy_staff_auth.py --expected-current foundation-20261006-c2126cc8e286 --apply

The operator must use trusted CSS-Live/FSE-root SSH aliases. The deployer archives
tracked code only, checks unchanged dependencies, creates an immutable release
and retains the existing immutable foundation virtualenv. It enables the API
through root-only /etc/control/staff-auth.env, rehearses the previous release,
tests authority-link loss/recovery, then verifies nginx before public activation.
Deployment failure restores the previous release/unit/env/proxy.
Public acceptance waits within a bounded window for nginx's new workers after
reload. An initial immediate probe returned the old setup HTTP 503; automatic
rollback restored the foundation release, setup proxy and absent auth environment.
All three API/bridge/nginx services were active after that rollback.

Root-only rollback state and deployment receipt are under
/etc/control/rollback/staff-auth-20261006-COMMIT_PREFIX. Neither directory nor
credentials are served by nginx. Recovery can restore that snapshot's proxy,
unit, environment (or remove the environment if it did not previously exist) and
previous-release symlink, then daemon-reload/restart API and nginx-test/reload.
Keep the auth link for continuing V2 rollout; stop it if the rollout is abandoned.
V1 auth state remains current through application rollback.

## Host acceptance

Pending: record release/commit, LIVE/READY, authority outage fail-closed, link
recovery, previous-release rehearsal, public login/assets, anonymous redirect,
API denial, private endpoint denial, wrong-origin denial and security headers.

## Staff acceptance

Pending: an existing staff member signs in directly at
https://control.csscdn.co.uk using their existing password and authenticator,
confirms the shell opens and signs out. Credentials and codes must stay in that
browser. Synthetic integration proves protocol behavior; it does not replace
this real-account acceptance check.

The shell offers a link to current Control and labels operational workspaces as
Preparing. No V2 order/account import or mailbox worker is enabled by this slice.
