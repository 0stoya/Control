# Production foundation: 2026-10-06

Status: Native foundation deployed and verified privately; staff application/public rollout pending

Final infrastructure checks completed at `2026-10-06T09:26:46Z`
(10:26:46 Europe/London).

## Host and release

| Item | Observed value |
| --- | --- |
| Host | `85.215.119.154`, SSH alias `CSS-Live` |
| OS | Ubuntu 24.04.5 LTS, kernel `6.8.0-146-generic` |
| Compute | 16 available CPU threads; approximately 125 GiB reported RAM |
| Storage | Two approximately 1.9 TiB NVMe drives; root RAID 1 approximately 2.04 TB |
| RAID acceptance | `md1`, `md2`, `md4` all `[UU]`; zero degraded members |
| Drive acceptance | Both NVMe SMART health self-assessments passed |
| Clock | UTC, synchronized, NTP active |
| Source release | `foundation-20261006-c2126cc8e286` |
| Release directory | `/srv/control/releases/foundation-20261006-c2126cc8e286` |
| Active release | `/srv/control/current` symlink to that immutable release directory |
| Source archive SHA256 | `c2126cc8e286ed373753edbcf6aa10abcc80ec972ead0c01c62a507995a95f3a` |
| Source provenance | 33 source files with per-file hashes; based on `60a61e0` plus explicit uncommitted foundation changes |
| Node runtime | Official Node.js `v24.21.0`, npm `11.19.0`, under `/opt/control/node` |

The provider's initial root mirror was rebuilding when setup began. Provisioning
remained private during recovery, and the final acceptance waited for all mirrors
to reach two active members. No partitions, RAID membership or filesystem layout
were changed. SMART/mirror checks do not constitute a destructive disk-failover test.

The Node Linux x64 archive was checked against the official SHA256:
`fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6`.
The web application itself is not deployed yet. No Docker was installed.

## SSH and network acceptance

- Root key authentication is retained; password and keyboard-interactive SSH
  authentication are disabled. Effective settings are
  `PermitRootLogin without-password` (OpenSSH's equivalent rendering of
  `prohibit-password`) and `AuthenticationMethods publickey`.
- The existing root password was not changed. Console recovery credentials
  remain separate from SSH authentication.
- VS Code local TCP forwarding is retained through `AllowTcpForwarding local`.
- A separate authenticated root recovery session was held open. The five-minute
  rollback timer was armed, the actual rollback restored the old SSH settings,
  and the final configuration was reapplied and accepted from a fresh key login.
  No rollback timer remains armed.
- UFW is active and enabled on boot: deny inbound, allow outbound, rate-limit
  TCP 22 for IPv4 and IPv6. There are no public web/API/database rules yet.
- Fail2ban's SSH jail is active using the systemd journal. The temporary setup
  address exemption was removed; only loopback networks remain exempt.
- PostgreSQL binds to localhost; the API binds to `127.0.0.1:8100`.
  Nginx is installed but stopped and disabled until hostname/TLS/auth acceptance.
- Persistent journald logging is bounded to 1 GB and 30 days. A deployment
  event was retained under the `control-deployment` identifier.

Observed server ED25519 host-key fingerprint over the authenticated connection:
`SHA256:RmIPN4LsNtd0ucfnX4p0zi4l03/E3sJ6FwnqjZfWris`.

Management-CIDR/VPN restrictions and the provider firewall remain a later network
gate once approved stable management addresses are established. The currently
applied protection is strong key authentication, rate limiting and the SSH jail.

## Database and application acceptance

- Native PostgreSQL 16 database `control_v2` was created fresh.
- `control_owner` is a non-login owner. `control_api` is an unprivileged OS and
  database login using local peer authentication. Neither role has superuser,
  database creation, role creation, replication or RLS-bypass privileges.
- Migration `0001_foundation.sql` applied in a locked transaction. A subsequent
  migration check reported no pending migrations and matched the exact checksum.
- `control-api.service` runs as `control_api`, with code/venv owned by root and
  systemd filesystem/process restrictions. Runtime source-write access was denied.
- Both `/health/live` and `/health/ready` returned HTTP 200 against the actual
  database. API, PostgreSQL, fail2ban and journald services were active; no failed
  systemd units were present at final acceptance.
- All 18 Python tests passed on the native Linux release; pip dependency checks
  passed. The source archive and all 33 file hashes were checked before execution.
- Native OS peer login returned the exact `control_v2`/`control_api` identity.
  A direct runtime read of `integration.source_observation` was denied.

The database contains one migration ledger entry and zero source observations.
No collector, translator, business projection, staff route or source write is
enabled. Infrastructure readiness does not establish business-data freshness,
source completeness, staff authentication or operational authority.

## Backup and recovery acceptance

- The first local backup completed successfully in
  `/var/backups/control/backup-fWHp7HqW`.
- Custom PostgreSQL dump and global-role file SHA256 checks passed.
- The dump was restored into a newly created isolated database
  `control_v2_restore_20261006_c2126`, with public database access revoked.
- `tests/native-foundation.sql` ran there against native PostgreSQL: duplicate
  observation identities failed; UPDATE/DELETE/TRUNCATE failed even for the
  owner; partial/null evidence remained explicit; runtime raw-evidence access
  and schema creation failed; runtime owner membership was absent.
- Synthetic test observations were rolled back. Restored and primary migration/
  observation counts matched `1|0`. The isolated test database was then removed.
- `/var/backups/control/backup-fWHp7HqW/restore-check.json` retains the result.
- `control-backup.timer` is enabled for daily local copies at 02:30 UTC plus
  randomized delay. The backup service result was success with exit status zero.

This verifies recovery of the current foundation schema and empty evidence
population. It does not prove future full-data import, authentication migration
or restoration of user MFA credentials. Encrypted off-server backup, retention,
recovery objectives and alert delivery still require configuration.

## Remaining public/business rollout gates

1. DNS, HTTPS setup and a certificate renewal timer for `control.csscdn.co.uk`
   were added after initial foundation acceptance. See
   [HTTPS acceptance](production-https-2026-10-06.md). Staff routes remain pending;
   later move to `control.chelmsfordsafety.co.uk`.
2. Integrate the confirmed V1 auth service on `FSE-root` (`77.68.81.175`,
   loopback port 8020) through a private authenticated link; retain one writable auth
   authority during overlap. Preserve the existing Argon2 hashes, encrypted TOTP
   seeds and original Fernet credential; prove login/MFA/authorization parity.
3. IONOS Acronis is deferred at the operator's request. Local backups and isolated
   restores remain part of migration acceptance. Off-server protection is not
   configured; revisit it separately when the operator resumes that work.
4. Deploy the Next.js staff UI and its authenticated same-origin API boundary.
5. Accept the first Sales Order Timeline/Despatched Today source contract, then
   deliver translation, projection, API/UI, reconciliation and shadow acceptance.

No V1 authentication records, passwords, MFA seeds, sessions, source payloads or
operational authorities were copied, reset or changed during this setup.

The application release manifest remains immutable. Native acceptance test and
journald configuration were applied separately after the initial source archive;
the repository records those additions and the observed deployment state.
