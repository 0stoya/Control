# Foundation validation: 2026-10-06

Status: Initial local checks passed; native deployment acceptance is recorded separately

This is the initial pre-deployment record. The later authenticated server setup
and native checks are in [the production foundation record](production-foundation-2026-10-06.md).

## Local environment and evidence

Windows, Python 3.12.14, Node 24.16.0. The production target is Ubuntu 24.04
with native PostgreSQL 16 and systemd. No Docker is used.

- `python -m unittest discover -s tests -v`: **18 passed** in an isolated
  environment installed from the pinned Python requirements.
- `npm run test:database`: **6 reported tests passed** (one parent and five
  subtests) using PGlite 0.5.8 and the actual committed foundation SQL.
- `python -m pip check`: no broken requirements; the requirements/constraints
  resolution was also checked with a pip dry run.
- ShellCheck 0.11.0: bootstrap, SSH hardening and backup scripts passed with no
  findings. This validates syntax/static behavior, not a live server change.
- Running Uvicorn over loopback returned liveness HTTP 200 and missing-database
  readiness HTTP 503, with the server header suppressed. The test process was
  stopped after verification.

The SQL checks prove unique replay identities, null/partial preservation,
rejection of invalid coverage, UPDATE/DELETE/TRUNCATE rejection even for the
table owner, readable runtime migration state, and denial of runtime evidence
access, schema creation and migration-owner assumption.

## Remote observations and remaining acceptance

A read-only SSH handshake received an Ubuntu OpenSSH 9.6p1 banner on port 22.
A strict, noninteractive root connection was refused because this session has
no trusted host key for the address. The user confirmed the server currently
uses root password login and is not configured yet. No authenticated remote
commands or configuration changes were performed.

Complete the first-key-login runbook and verify the host fingerprint before
server provisioning. Native package installation, actual peer authentication,
systemd hardening, timed SSH rollback/recovery, firewall behavior, RAID/SMART,
TLS, shared authentication, backup/restore and operational monitoring have not
been exercised on the production target.

V1 auth code was inspected; no auth records, password hashes, encryption keys,
sessions, recovery codes or live operational payloads were copied or changed.
No production/business authority is claimed by these local checks.
