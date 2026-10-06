#!/usr/bin/env bash
# Local recovery copy only. An encrypted off-server copy is a separate acceptance gate.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root' >&2; exit 2; }
umask 077
exec 9>/run/lock/control-backup.lock
flock -n 9 || { echo 'A backup is already running' >&2; exit 1; }
install -d -o root -g root -m 0700 /var/backups/control
backup_dir=$(mktemp -d /var/backups/control/backup-XXXXXXXX)
trap 'echo "Backup incomplete; inspect the partial directory" >&2' ERR
runuser -u postgres -- pg_dump --format=custom --dbname=control_v2 > "$backup_dir/control_v2.dump.partial"
pg_restore --list "$backup_dir/control_v2.dump.partial" > /dev/null
mv -- "$backup_dir/control_v2.dump.partial" "$backup_dir/control_v2.dump"
runuser -u postgres -- pg_dumpall --globals-only > "$backup_dir/roles.sql"
cp -a -- /etc/control "$backup_dir/config"
# /etc/control must contain the retained TOTP credential when auth is migrated.
# Secrets in this backup require encryption before any off-server transfer.
date -u +%FT%TZ > "$backup_dir/created-at.txt"
if [[ -L /srv/control/current ]]; then readlink /srv/control/current > "$backup_dir/release.txt"; fi
(cd -- "$backup_dir" && sha256sum control_v2.dump roles.sql > SHA256SUMS)
trap - ERR
printf 'Local backup created: %s\n' "$backup_dir"
printf 'Next: encrypted off-server copy and isolated restore drill. No retention deletes are automatic.\n'

