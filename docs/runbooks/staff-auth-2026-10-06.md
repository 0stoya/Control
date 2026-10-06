# Staff sign-in and V2 shell acceptance

6 October 2026, 16:12 BST. Staff gateway and protected shell are deployed.
Existing-staff password/MFA sign-in was confirmed by the operator at 17:23 BST. No business migration belongs to this step.

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

Deployed commit: e26a7f92ae0c09a63534399d2bdb9d325dce1da8.
Immutable release: /srv/control/releases/staff-auth-20261006-e26a7f92ae0c.
Previous release: /srv/control/releases/foundation-20261006-c2126cc8e286.
Root-only receipt: /etc/control/rollback/staff-auth-20261006-e26a7f92ae0c/deployment-receipt.json.

Observed host checks passed:
- Private readiness, authentication authority health and link recovery.
- Stopped V2 bridge: readiness and a protected request both returned 503; after
  restart readiness returned 200. No offline/cached successful identity.
- Previous release was restored and restarted privately, with its absent login
  route verified, then the new staff release was restored.
- HTTPS login/assets 200, anonymous root 303 to sign-in, API session 401.
- Public private-health/auth-health/admin endpoints 404; wrong-origin login 403.
- No-store and CSP headers verified. nginx syntax and reload verified.
- Public login was checked in the in-app browser: layout correct, expected fields
  available and no script errors reported.
- API, auth bridge, nginx, PostgreSQL, fail2ban and control-backup.timer active.
  Auth environment root-only 0600. Database still has only 0001_foundation.sql
  and zero source observations.

The first attempt's automatic rollback was also observed independently: previous
foundation symlink, setup proxy, absent staff auth environment and active services.
This is application/transport acceptance, not a business authority cutover.

## Staff acceptance

Confirmed by the operator on 6 October 2026, 17:23 BST:
“confirmed - i can log in and authenticate”.

Existing-account password and authenticator continuity is accepted for the
deployed V2 sign-in. Credentials/codes stayed in the browser. Real-account
sign-out was not separately reported; logout revocation passed native synthetic
integration. Staff/business permission cutovers remain separate.

The shell offers a link to current Control and labels operational workspaces as
Preparing. No V2 order/account import or mailbox worker is enabled by this slice.
