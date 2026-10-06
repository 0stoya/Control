# Control V2 production launch configuration

Status: HTTPS staff sign-in and protected shell deployed on 2026-10-06; controlled existing-account acceptance pending; Acronis deferred by operator.

## Public addresses and DNS

| Purpose | Hostname | State |
| --- | --- | --- |
| Existing V1 | app.csscdn.co.uk | Retain during migration |
| Initial V2 | control.csscdn.co.uk | HTTPS sign-in and protected staff shell deployed |
| Later V2 | control.chelmsfordsafety.co.uk | Selected; DNS availability expected later |
| V2 server | 85.215.119.154 | Native private foundation deployed |

Before the operator's DNS change, Windows resolution on 2026-10-06 returned:
- control.csscdn.co.uk A: 217.160.0.7
- control.csscdn.co.uk AAAA: 2001:8d8:100f:f000::200
- app.csscdn.co.uk A: 77.68.81.175
- control.chelmsfordsafety.co.uk A: NXDOMAIN

These are dated resolver observations, not a DNS-zone edit or a permanent claim.

After the operator's change, the A record is 85.215.119.154 and the AAAA record
is 2a01:239:0:e0::1. Both match the new server. Authoritative DNS and client/server
resolution were checked; Cloudflare and Google returned the new A record.
External HTTPS probes succeeded over IPv4 and IPv6. See
[HTTPS setup acceptance](production-https-2026-10-06.md). Keep the V1 record intact.

Nginx now serves the staff sign-in gateway with HTTPS and HTTP redirection.
A Let's Encrypt certificate and renewal timer are installed; ports 80/443 are
allowed for IPv4/IPv6. The API and PostgreSQL remain on loopback. HTTPS login
returns 200; anonymous root redirects to sign-in and session API returns 401.
Private health and auth-administration routes are unavailable publicly. Protected
requests freshly validate the V1 authority through a restricted SSH link.

Native synthetic auth, public boundaries, link-outage recovery and previous-release
rollback checks passed. An existing staff account must still complete normal
password/authenticator sign-in at V2 to close account acceptance. No business
screen/import is active. See [staff rollout evidence](staff-auth-2026-10-06.md).

For the later business hostname, prepare DNS and its certificate, switch the
accepted public-origin and CSRF configuration, and verify sign-in before routing
staff to it. Keep cookies host-only and require normal password/MFA sign-in on the
new hostname. Preserve accounts and enrolments; there is no parent-domain cookie.
Keep the previous hostname available through a reviewed redirect/rollback window.

## Authentication continuity

The operator supplied FSE-root for V1 at 77.68.81.175. Read-only inspection
confirmed css-auth.service on 127.0.0.1:8020 and the css_app auth schema.

Use the existing service as the one writable authentication authority during
overlap. The transport from V2 to V1 must be private and authenticated, with a
bounded health check and failure closed. No unauthenticated public port 8020.
The browser uses the V2 same-origin auth route; every protected API request
checks the authoritative session and entitlements.

[Authentication migration](authentication-migration.md) records the inventory,
retained password/MFA state, parity checks and later single-writer transfer.
The shared authority remains on V1 until an explicitly verified transfer.
Its database and encryption credential therefore need recoverable backup
independently of the new V2 machine.

## Deferred off-server backup: IONOS Acronis

The operator deferred Acronis on 2026-10-06. No agent enrolment, protection plan
or provider configuration is to be performed now. The following notes are
retained for a later decision. Daily native PostgreSQL dumps and one isolated
foundation restore have been verified locally; off-server recovery has not
been proved. Database design and development can continue.

IONOS documents downloading the Linux installer from Servers & Cloud >
Backup > Backup Package, selecting the backup location, installing it on the
server and registering the device. Use the installer from the operator's own
contract; treat registration tokens and installer credentials as secrets.
[IONOS Linux agent installation](https://www.ionos.com/help/server-cloud-infrastructure/cloud-backup/installing-the-backup-agent/installing-the-backup-agent-linux/).

The console supplies schedule, retention and encryption controls.
[IONOS backup package information](https://www.ionos.com/help/server-cloud-infrastructure/cloud-backup/important-backup-package-information/).

Configuration and acceptance when off-server protection is resumed:
1. Enrol the actual Ubuntu 24.04 server with a compatible provider agent.
   Verify the current kernel/agent combination before installation.
2. Protect the machine/configuration and completed /var/backups/control dump
   bundles. Include /etc/control credentials when present, systemd/proxy
   configuration, /etc/letsencrypt and release provenance. Keep secrets out of repository copies.
3. Coordinate the protection job with successful completion of control-backup.service.
   Check the fresh bundle and its checksums. A failed or incomplete dump must
   fail backup acceptance; do not treat a live PostgreSQL-directory file copy as
   a substitute for a tested database-consistent recovery method.
4. Enable backup encryption and store its recovery password separately from
   this server. Record the selected backup location, capacity, retention,
   acceptable data loss and recovery-time target with the operator.
5. Confirm recoverable protection for the V1 auth authority and its original
   Fernet credential while it remains on V1. V2-only backup cannot protect it.
6. Restore a cloud-retained bundle to an isolated recovery environment. Prove
   database/role/schema integrity, eventual evidence reconciliation, credential
   recovery and controlled existing-password/MFA login; record duration.
7. Monitor failed jobs, last successful off-server backup age, storage usage
   and restore-test age. Verify actual alert delivery before staff go-live.

Daily local dumps provide only daily recovery points; they do not prove a
smaller loss window. Add a separately tested PostgreSQL WAL/PITR strategy if
the accepted recovery objective requires it. Agent installation, cloud plans,
retention, encryption and alerts are pending, rather than inferred from the
local timer's success.
