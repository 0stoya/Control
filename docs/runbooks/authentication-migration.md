# Preserve Control V1 accounts and authenticator enrolments

Status: Source-code compatibility inspected; live inventory, integration and transfer pending

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

