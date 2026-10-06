# ADR 0002: Native production foundation and authentication continuity

Status: Foundation deployed privately; public rollout and capability acceptance pending

Date: 2026-10-06

## Context

Control V2 has a dedicated server at `85.215.119.154`, running Ubuntu 24.04.
The supplied hardware is an Intel Xeon E-2478, 128 GB RAM, NVMe storage and
software RAID 1. Actual CPU, usable RAID capacity, devices and health must be
verified on the host. The user requires no Docker, root SSH access, public
internet access with staff sign-in, a separate migration hostname, and retention
of the existing Control V1 passwords and authenticator enrolments.

## Decision

Use native systemd services, PostgreSQL 16 from Ubuntu's supported packages,
Python 3.12/FastAPI, and a subsequent Node/Next.js presentation service. Nginx
will terminate HTTPS after the hostname, authentication integration and TLS are
validated. No application or database port is exposed publicly.

Keep root SSH with `PermitRootLogin prohibit-password` and
`AuthenticationMethods publickey`. Keys should be passphrase protected, with a
separate key for each operator. Retain local TCP forwarding for VS Code Remote
SSH. Limit management access through the provider firewall and UFW once the
management addresses or VPN are established. Do not change ports as a substitute
for authentication. Apply SSH changes with configuration checks, a fresh key
login and automatic rollback.

Use separate OS and database identities. `control_owner` owns migrations and
cannot log in. `control_api` is an unprivileged OS service account and a database
login via a local Unix socket and peer authentication. It currently has access
only to the migration ledger. Future slices grant access to their explicit
projections; the API never becomes database owner or reads raw evidence by default.

Reuse the existing authentication authority during overlap. Plan a controlled
transfer of the auth schema and TOTP credential instead of resetting accounts
or independently operating two mutable copies. See the authentication runbook.

## Implemented boundary

- An internal liveness endpoint and a readiness endpoint that checks the correct
  database, runtime role and exact migration checksums.
- Forward-only, ordered, checksum-verified migrations in one locked transaction.
- An immutable source-observation table and validated versioned evidence envelope.
- Native bootstrap, root SSH hardening, API unit, persistent logging and local backup units.
- No collectors, translator, staff-facing business API, public proxy or UI yet.

Infrastructure readiness does not mean data freshness, staff authentication,
operational authority or production acceptance. No V1 business dependency changes.
The actual deployed release and native acceptance evidence are recorded in
[the foundation deployment record](../runbooks/production-foundation-2026-10-06.md).

## Acceptance

Before public access: authenticated server inventory; healthy RAID; provider
console recovery; new root key login; effective SSH configuration; verified
IPv4/IPv6 firewall policy; OS patch/reboot handling; TLS; authentication parity;
negative authorization tests; encrypted off-server backup and isolated restore;
and monitored service failures, disk, RAID, certificates and backup age.

## References

- [Ubuntu OpenSSH server](https://ubuntu.com/server/docs/how-to/security/openssh-server/)
- [OpenSSH configuration](https://github.com/openssh/openssh-portable/blob/master/sshd_config.5)
- [Ubuntu firewall](https://ubuntu.com/server/docs/how-to/security/firewalls/)
- [PostgreSQL peer authentication](https://www.postgresql.org/docs/16/auth-peer.html)
