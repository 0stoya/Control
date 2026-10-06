# Control V2 production server

Status: Native foundation deployed privately on 2026-10-06; public rollout pending

Target: `85.215.119.154`, Ubuntu 24.04, native services, no Docker.

The applied release and acceptance results are in
[the deployment record](production-foundation-2026-10-06.md). The following steps
describe the procedure; do not rerun initial release creation against a populated
release directory. Native Node.js 24.21.0 is installed under `/opt/control/node`.

## 1. Verify access and inventory

Confirm the SSH host-key SHA256 fingerprint through the provider console before
trusting it. Do not bypass StrictHostKeyChecking. Use the actual key/host entry
used by VS Code, retaining a provider-console recovery route.

```bash
id
cat /etc/os-release
lscpu
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
cat /proc/mdstat
df -h
ss -lntup
timedatectl
```

Check actual NVMe devices and SMART health with `smartctl`; inspect each RAID
array with `mdadm --detail`. RAID 1 must show all expected active members. Do not
partition, format or rebuild disks from this runbook. Confirm the provider's
claimed capacity against the usable array, root volume and free space. RAID
redundancy is separate from off-server backup.

## 2. Install the native foundation

Copy the reviewed Control release to the new host. From its root:

```bash
bash deployment/ubuntu24/bootstrap.sh --check
bash deployment/ubuntu24/bootstrap.sh --apply
```

This creates `/srv/control/releases`, an unprivileged `control_api` service
identity, a fresh `control_v2` PostgreSQL database and a non-login migration
owner. It installs Ubuntu packages, keeps Nginx stopped and leaves SSH/firewall
configuration for the next steps. It does not install Docker or touch V1.
Fail2ban uses the systemd journal. Bootstrap temporarily exempts the active
management address to avoid banning setup for earlier failed logins; remove
`/etc/fail2ban/jail.d/99-control-bootstrap.local` and reload the SSH jail after
fresh key login and firewall verification. This cleanup was completed on the target.
Journald retains persistent logs, bounded to 1 GB and 30 days.

Review OS updates and any reboot requirement before serving users. Configure
unattended security updates with planned reboot windows; do not enable automatic
reboots during the migration without an operating plan. Verify time synchronization
for TOTP. Confirm PostgreSQL listens only on loopback or Unix sockets with
`ss -lntp` and `SHOW listen_addresses`; do not expose port 5432.

## 3. Secure root SSH without losing VS Code access

Use a separate passphrase-protected key per administrator. Install only public
keys; never move private keys to the server. If access currently uses a password,
first install a public key and prove a fresh key-only login. Keep two sessions
and a retained independent root recovery session or provider console available.
Then, as root in the established SSH session:

```bash
bash deployment/ubuntu24/harden-ssh.sh --check
bash deployment/ubuntu24/harden-ssh.sh --apply --key-login-verified --console-recovery-verified
```

For a verified independent recovery SSH session, use
`--recovery-session-verified` instead of `--console-recovery-verified`. The target's
change used that recovery channel and the actual rollback was exercised before
final acceptance.

The script verifies syntax and effective root authentication, reloads SSH and
arms a five-minute rollback of its managed drop-in. Immediately open a new root
connection using the key, and verify VS Code Remote SSH. Only in that successful
new session cancel rollback:

```bash
systemctl stop control-ssh-rollback.timer
sshd -T | grep -E '^(permitrootlogin|authenticationmethods|passwordauthentication|kbdinteractiveauthentication|allowtcpforwarding) '
```

Keep local TCP forwarding enabled for VS Code. Password and keyboard-interactive
SSH authentication are disabled; root public-key authentication remains enabled.
Check any existing Match blocks for every approved management address as well.

## 4. Restrict network access

The initial applied policy is deny incoming, allow outgoing and `LIMIT 22/tcp`
for IPv4/IPv6. Application and database ports remain private. Replace broad SSH
reachability with approved management CIDRs or a VPN once those addresses are
established; do not assume a residential management IP is permanent.

Record the actual management CIDR before enabling the firewall. Ensure it contains
the source address of the current SSH connection. Review existing UFW rules,
IPv6 support and provider firewall rules. Add the management SSH rule first:

```bash
ufw status numbered
# Replace ADMIN_CIDR with the verified management IPv4/IPv6 address range.
ufw allow from ADMIN_CIDR to any port 22 proto tcp
ufw default deny incoming
ufw default allow outgoing
ufw enable
ufw status verbose
```

Test a fresh root/VS Code connection, then remove any superseded broad SSH rule
by its reviewed rule number. Do not reset an existing firewall. Public web access
will later allow 80/443, with TLS redirection and staff sign-in. Ports 3000, 8100,
the auth port and 5432 remain private. IPv6 must follow the same policy. Maintain
provider-console recovery while changing either firewall.

## 5. Create an immutable release and deploy the private API

Use a reviewed Git commit as the release ID. Keep code/venv owned by root and
readable by the runtime; the service cannot modify its own deployment. Example
for a populated release directory, replacing RELEASE_ID with the actual ID:

```bash
cd /srv/control/releases/RELEASE_ID
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pip freeze > installed-requirements.txt
.venv/bin/python -m unittest discover -s tests -v
chown -R root:root /srv/control/releases/RELEASE_ID
chmod -R u=rwX,go=rX /srv/control/releases/RELEASE_ID
runuser -u postgres -- env PYTHONPATH="$PWD" .venv/bin/python scripts/migrate.py --check
runuser -u postgres -- env PYTHONPATH="$PWD" .venv/bin/python scripts/migrate.py --apply
ln -s /srv/control/releases/RELEASE_ID /srv/control/next
mv -Tf /srv/control/next /srv/control/current
install -m 0644 deployment/systemd/control-api.service /etc/systemd/system/control-api.service
systemctl daemon-reload
systemctl enable --now control-api.service
curl --fail http://127.0.0.1:8100/health/live
curl --fail http://127.0.0.1:8100/health/ready
```

Do not overwrite a populated release directory. Use a new release for every
change. The symlink switch is atomic; restart the API for subsequent releases.
Archive the complete resolved Python package set with each tested release.
The committed requirements constrain the tested transitive resolution. The
initial Windows environment and the native Linux environment both installed and
passed Python checks. Retain exact package versions and archive verification
evidence for every subsequent release.

Readiness verifies PostgreSQL identity, privilege context and migration hashes.
It does not claim source freshness or business acceptance. If it fails, inspect
`systemctl status control-api` and `journalctl -u control-api` locally. Errors
intentionally avoid printing credentials or source payloads.

## 6. Enable backup and prove recovery

```bash
install -m 0644 deployment/systemd/control-backup.service /etc/systemd/system/control-backup.service
install -m 0644 deployment/systemd/control-backup.timer /etc/systemd/system/control-backup.timer
systemctl daemon-reload
systemctl start control-backup.service
systemctl enable --now control-backup.timer
systemctl list-timers control-backup.timer
```

The timer creates a daily local custom-format PostgreSQL dump, role definitions
and root-only `/etc/control` configuration copies. This is not an off-server
backup. It includes secrets when auth is migrated. The operator has deferred
IONOS Acronis; no agent or protection plan is being configured now. Local
backups and isolated restore checks remain part of database migration work.
See [launch configuration](production-launch.md) for the recorded backup status
and retained provider notes.
No backup retention deletion is enabled by this initial scaffold; monitor disk
space until a reviewed retention policy is installed.

Copy a complete encrypted backup off the host. Restore into an isolated database
on a private recovery host, not over `control_v2`. Validate checksums, roles,
schema ledger, evidence count/hash parity, auth-key decryption and controlled
login/MFA tests, then measure recovery time and record the result. A dump listing
alone is not restore evidence. Monitor timer failures and age of the latest
successful off-server backup.

## 7. Public hostname, TLS and authentication

Use `control.csscdn.co.uk` initially, followed by
`control.chelmsfordsafety.co.uk` when its DNS is available. On 2026-10-06 the
initial hostname first resolved to another IPv4/IPv6 destination. The operator
subsequently corrected both records; HTTPS setup, web firewall rules and the
certificate renewal timer are now deployed. See
[HTTPS acceptance](production-https-2026-10-06.md). Staff sign-in and application
rollout remain pending. Keep `app.csscdn.co.uk` serving V1 until an
explicit cutover. Complete the authentication continuity runbook, then
add the Next.js service on loopback and a same-origin Nginx proxy. Obtain and
verify TLS, automated renewal, correct origin/CSRF rules, request size/time
limits, safe logging and sign-in rate limits before enabling public traffic.
Do not expose the foundation API as a public unauthenticated application.

## 8. First business slice and operational cutover

Implement the Sales Order Timeline and Despatched Today contract before intake:
grain and stable identity, exact source ownership, separate milestones, currency
and quantity laws, freshness/coverage/absence rules, replay and rebuild,
reconciliation and rollback. Consume the accepted V1 evidence feed first; do not
start a competing Sculptor collector on the new host.

Build migration, translator, PostgreSQL read projection, authenticated API,
focused UI and health signals as one slice. Shadow the same population and
record explained differences. Move authority only after accepted production-like
recovery, reconciliation and rollback evidence. Promise/SLA adapters follow
through a versioned input bundle with the existing formula preserved.

Initial database tuning should follow measured load rather than the installed
RAM alone. Track query plans, connection counts, I/O, memory and ingestion backlog
before adjusting shared buffers, work memory or worker counts. Add monitoring for
service health, disk/inodes, RAID degradation, SMART, memory pressure, certificates,
backups and source freshness; no monitor is deployed by the foundation scaffold.
