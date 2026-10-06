# Preserve Control V1 accounts and authenticator enrolments

Status: Source-code compatibility and read-only live inventory inspected; integration and transfer pending

## Confirmed V1 host and read-only inventory

On 2026-10-06 the operator identified `FSE-root` as the V1 SSH alias:
`root@77.68.81.175`, using `~/.ssh/oneflow_prod_ed25519`, repository
`/srv/css/repository`. The connection succeeded with strict host-key verification.
Only service metadata, schema definitions, source-file hashes and aggregate counts
were read; no password hash, MFA ciphertext, recovery-code hash or key was retrieved.

- Host: `oneflow-prod-01`; `css-auth.service` active under `css_auth`.
- Listener: `127.0.0.1:8020`; `/auth/health` returned `ok`, database `css_app`,
  runtime database identity `css_auth`, PostgreSQL version number `160015`.
- `css-control.service` active under `css_control`.
- Repository revision: `980a58325447c2c1d2a5fc5daca6b041d4ff1ecb`;
  current UI release: `26ecb133833c30d26414901480d5c2fa49d9a0e1`.
  There were no working-tree changes in the inspected auth source/migration paths.
- Expected credential file exists at `/etc/css/credentials/css-auth-totp.key`,
  owner `root:root`, mode `0600`. Its value and decryption were not inspected.
  The live unit maps `LoadCredential=css-auth-totp-key` to that path and runs
  `services.auth.scoped_http_app:app` with the repository's Python virtualenv.
- All 11 auth tables exist: `app_user`, `audit_event`, `mail_outbox`,
  `operational_profile`, `permission`, `recovery_code`, `role`,
  `role_permission`, `session`, `user_invitation`, `user_role`.
- Seven users, all enabled and all with Argon2-formatted hashes. Four have a
  recorded TOTP enrolment; none of those four lack encrypted seed data.
  The remaining accounts retain the authority's existing enrolment policy.
- Four operational profiles, 15 role-permission links and 40 recovery-code rows
  were counted. User-role assignment totals: administrator 7, control_operator 4,
  control_user 4, flow_user 2. Permissions must be reviewed explicitly before V2
  activation; migration must not silently grant or remove entitlements.
- NTP synchronized. No table with `migration` in its name was found in the
  inspected `css_app` information schema; do not infer an applied ledger from
  repository migration filenames alone.

This is structural inventory, not login/MFA parity acceptance. No account,
authentication state, source authority or V1 runtime was changed.
The V2 hostnames and shared-auth rollout gates are recorded in
[production launch](production-launch.md).

## Proven V1 code

The sibling CSS repository contains:

- `services/auth/security.py`: Argon2 verification, SHA256 session/recovery-code
  hashing, six-digit TOTP with a 30-second default step, a +/- one-step window and
  replay prevention through `totp_last_counter`.
- `services/auth/security.py`: Fernet encryption of TOTP seeds using the
  `CSS_AUTH_TOTP_KEY_FILE` file or the systemd credential `css-auth-totp-key`.
- `services/auth/http_app.py`: login/challenge/session flows and a Secure,
  HttpOnly, SameSite=Lax host-only cookie.
- `services/api/migrations/0003_auth.sql`, `0004_operational_profiles.sql`,
  `0010_auth_sales_scope.sql`, `0011_auth_user_invitations.sql`: identity, roles,
  permissions, recovery codes, sessions, scope, invitations and audit state.

These are code findings, not a claim about the live installed schema or key path.
Record the live auth release, applied schema, role grants and secret location
before moving it. Do not print the key, password hashes or TOTP seeds.

## During parallel V1/V2 use

Use one authentication service and one writable authentication database as the
authority. The V2 browser talks to its own same-origin `/auth` proxy. The V2
server reaches that auth service over a private management link or mutually
authenticated TLS, with strict certificate checks and bounded request timeouts.
Do not publish an internal auth port.

V2 validates the opaque session with the authority on every protected request,
including user enabled state and permissions. Never trust a user ID or roles
sent by the browser. Map any new V2 permissions explicitly. Keep source ERP/API
authorization separate from the auth migration.

Keep cookies host-only, Secure, HttpOnly and SameSite=Lax, with no parent-domain
cookie. The separate V2 hostname requires a normal login using the existing
password and authenticator; enrolment is retained. Do not bypass MFA or infer a
V2 login from a browser-provided V1 cookie. Validate Origin/CSRF protections on
state-changing requests and strip untrusted identity/forwarding headers at the
proxy. Rate limits, lockouts and auth audit reporting remain in the authority.

Two writable auth copies would independently accept the same TOTP counter,
consume recovery codes, reset passwords and disable users. Do not operate them
in parallel. No authentication proxy is enabled in the foundation build.

## Eventual auth cutover

1. Take encrypted, verified backups of the current auth schema and exact Fernet
   credential. Keep both outside Git and logs, with root-only access at rest.
2. Inventory all auth tables, identity sequences, constraints, triggers,
   permissions, operational profiles, sales scope and invitation/outbox state.
   Do not restore only `auth.app_user` or blindly run old seed migrations.
3. Restore into an isolated private database using the accepted auth release.
   Preserve user IDs, usernames, complete Argon2 hashes, encrypted TOTP seeds,
   enrolment times, last counters, enabled state, lockouts, password-change
   requirements, role/permission mappings and recovery consumption.
4. Install the original Fernet key as a systemd credential. A newly generated
   key cannot decrypt the retained seeds. Any later key rotation needs a separate
   transactional decrypt/re-encrypt procedure with recovery evidence.
5. Prevent duplicate mail delivery when transferring invitation/outbox rows.
   Decide outstanding invitation-token behavior explicitly.
6. Prove parity with controlled test accounts: existing password accepted, wrong
   password rejected, existing authenticator accepted, used counter rejected,
   recovery code accepted once, disabled/locked user denied, scoped permissions
   retained, unauthenticated/partial-MFA requests denied and key failure closed.
7. Quiesce authentication writes, take the final consistent snapshot and transfer
   both state and the credential. Reconcile counts and private record digests,
   fix identity sequences, then switch both applications to the same new service.
8. Expire sessions at the transfer unless a separately accepted session migration
   preserves all expiry/revocation semantics. This requires sign-in, not account
   recreation or MFA enrolment.
9. Maintain one writer through rollback too. Once the destination accepts auth
   writes, switching to the old snapshot would resurrect consumed recovery codes
   and lose password changes. Reconcile/transfer destination auth changes before
   rollback; never simply point the service back at stale auth state.

The live transfer is not performed by this foundation. No existing password,
seed, account or cookie has been modified.
