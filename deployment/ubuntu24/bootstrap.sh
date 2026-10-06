#!/usr/bin/env bash
# Native Ubuntu 24.04 foundation. Does not alter SSH, firewall, RAID or source systems.
set -euo pipefail
export LC_ALL=C
mode=${1:---check}
[[ "$mode" == --check || "$mode" == --apply ]] || { echo 'Use --check or --apply' >&2; exit 2; }
[[ $EUID == 0 ]] || { echo 'Run as root' >&2; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'Requires Ubuntu 24.04' >&2; exit 2; }
printf 'Host: %s\nOS: %s\n' "$(hostname)" "$PRETTY_NAME"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
cat /proc/mdstat
df -h /
ss -lnt
[[ "$mode" == --apply ]] || { echo 'CHECK ONLY: no changes made'; exit 0; }

# This bootstrap is for the new dedicated server, not a live CSS host.
if ss -H -lnt '( sport = :80 or sport = :443 )' | grep -q .; then
    echo 'HTTP/HTTPS listener already exists; review it before bootstrapping' >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive
# Ubuntu's minimal image uses the journal rather than /var/log/auth.log.
# Install the backend configuration before the package can start the jail.
deployment_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
install -d -o root -g root -m 0755 /etc/systemd/journald.conf.d
install -o root -g root -m 0644 "$deployment_dir/journald/control.conf" /etc/systemd/journald.conf.d/10-control.conf
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald.service
journalctl --flush
install -d -o root -g root -m 0755 /etc/fail2ban/jail.d
install -o root -g root -m 0644 "$deployment_dir/fail2ban/control-sshd.local" /etc/fail2ban/jail.d/control-sshd.local
if [[ -n "${SSH_CONNECTION:-}" ]]; then
    read -r management_addr _ <<< "$SSH_CONNECTION"
    python3 -c 'import ipaddress,sys; ipaddress.ip_address(sys.argv[1])' "$management_addr"
    # Avoid banning the setup session for old authentication failures. Remove
    # this temporary override after fresh key-only login and firewall verification.
    printf '[sshd]\nignoreip = 127.0.0.1/8 ::1 %s\n' "$management_addr" \
        > /etc/fail2ban/jail.d/99-control-bootstrap.local
    chmod 0644 /etc/fail2ban/jail.d/99-control-bootstrap.local
fi
apt-get update
apt-get install -y ca-certificates curl git rsync python3 python3-venv python3-pip \
    postgresql-16 postgresql-client-16 nginx ufw fail2ban unattended-upgrades \
    smartmontools mdadm

# Public web access follows authentication and TLS acceptance.
systemctl disable --now nginx
systemctl enable --now postgresql
if ! id control_api >/dev/null 2>&1; then
    useradd --system --user-group --home-dir /var/lib/control --shell /usr/sbin/nologin control_api
fi
[[ "$(getent passwd control_api | cut -d: -f7)" == /usr/sbin/nologin ]] || {
    echo 'Existing control_api account has an unexpected shell' >&2; exit 1;
}
install -d -o root -g root -m 0755 /srv/control /srv/control/releases
install -d -o root -g root -m 0700 /etc/control /var/backups/control
install -d -o control_api -g control_api -m 0750 /var/lib/control

runuser -u postgres -- psql -X --set=ON_ERROR_STOP=1 --dbname=postgres <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'control_owner') THEN
        CREATE ROLE control_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'control_api') THEN
        CREATE ROLE control_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('control_owner', 'control_api')
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT FROM pg_roles WHERE rolname = 'control_owner' AND rolcanlogin)
       OR EXISTS (SELECT FROM pg_roles WHERE rolname = 'control_api' AND NOT rolcanlogin)
       OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
                   WHERE r.rolname IN ('control_owner', 'control_api')) THEN
        RAISE EXCEPTION 'Existing Control roles exceed the allowed privileges';
    END IF;
END;
$$;
SQL
db_exists=$(runuser -u postgres -- psql -X --tuples-only --no-align --dbname=postgres \
    --command="SELECT 1 FROM pg_database WHERE datname = 'control_v2'")
if [[ "$db_exists" != 1 ]]; then
    runuser -u postgres -- createdb --owner=control_owner control_v2
fi
runuser -u postgres -- psql -X --set=ON_ERROR_STOP=1 --dbname=control_v2 <<'SQL'
DO $$
BEGIN
    IF (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()) <> 'control_owner' THEN
        RAISE EXCEPTION 'control_v2 has an unexpected owner';
    END IF;
END;
$$;
REVOKE ALL ON DATABASE control_v2 FROM PUBLIC;
GRANT CONNECT ON DATABASE control_v2 TO control_api;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
runuser -u control_api -- psql -X --set=ON_ERROR_STOP=1 --dbname=control_v2 \
    --command='SELECT current_database(), current_user'
fail2ban-client -t
systemctl enable --now fail2ban
systemctl restart fail2ban
echo 'Foundation installed. SSH and firewall still need the documented controlled setup.'
echo 'Inspect /var/run/reboot-required, RAID health and PostgreSQL listeners before deployment.'
echo 'After verification, remove /etc/fail2ban/jail.d/99-control-bootstrap.local and reload fail2ban.'
