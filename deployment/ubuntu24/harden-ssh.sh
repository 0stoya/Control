#!/usr/bin/env bash
# Keep root key login; retain a five-minute systemd rollback until a new login succeeds.
set -euo pipefail
export LC_ALL=C
mode=${1:---check}
[[ "$mode" == --check || "$mode" == --apply ]] || { echo 'Use --check or --apply' >&2; exit 2; }
[[ $EUID == 0 ]] || { echo 'Run as root' >&2; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'Requires Ubuntu 24.04' >&2; exit 2; }
/usr/sbin/sshd -t
[[ "$mode" == --apply ]] || { /usr/sbin/sshd -T | grep -E '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|authenticationmethods|pubkeyauthentication|port) '; exit 0; }
[[ "${2:-}" == --key-login-verified && ( "${3:-}" == --console-recovery-verified || "${3:-}" == --recovery-session-verified ) ]] || {
    echo 'First verify a fresh root key login and a separate retained root recovery session or provider console.' >&2
    echo 'Then use --apply --key-login-verified --recovery-session-verified (or --console-recovery-verified)' >&2; exit 2;
}
[[ -n "${SSH_CONNECTION:-}" && -s /root/.ssh/authorized_keys ]] || {
    echo 'Apply from a root SSH session with an installed authorized key' >&2; exit 1;
}
read -r client_addr _ server_addr server_port <<< "$SSH_CONNECTION"
[[ "$server_port" == 22 ]] || { echo 'This baseline expects SSH port 22' >&2; exit 1; }
exec 9>/run/lock/control-ssh-hardening.lock
flock -n 9 || { echo 'Another SSH change is in progress' >&2; exit 1; }
if systemctl is-active --quiet control-ssh-rollback.timer; then
    echo 'An earlier SSH rollback is still armed' >&2; exit 1
fi
change_dir=$(mktemp -d /var/lib/control-ssh-change.XXXXXXXX)
chmod 0700 "$change_dir"
dropin=/etc/ssh/sshd_config.d/00-control-v2.conf
if [[ -e "$dropin" ]]; then
    cp -p "$dropin" "$change_dir/previous.conf"
fi
cat > "$change_dir/rollback.sh" <<'ROLLBACK'
#!/usr/bin/env bash
set -euo pipefail
change_dir=$(cd -- "$(dirname -- "$0")" && pwd)
dropin=/etc/ssh/sshd_config.d/00-control-v2.conf
if [[ -f "$change_dir/previous.conf" ]]; then
    cp -p "$change_dir/previous.conf" "$dropin"
else
    rm -f -- "$dropin"
fi
/usr/sbin/sshd -t
systemctl reload ssh.service
ROLLBACK
chmod 0700 "$change_dir/rollback.sh"
# Schedule rollback before changing anything. Do not reuse a pending rollback unit.
systemd-run --collect --unit=control-ssh-rollback --on-active=5m /bin/bash "$change_dir/rollback.sh"
rollback_on_error() {
    trap - ERR
    /bin/bash "$change_dir/rollback.sh"
    systemctl stop control-ssh-rollback.timer
    echo 'SSH change failed; previous managed configuration restored' >&2
    exit 1
}
trap rollback_on_error ERR
install -d -o root -g root -m 0755 /etc/ssh/sshd_config.d
cat > "$dropin" <<'CONFIG'
# Control V2: root remains available through public keys.
PermitRootLogin prohibit-password
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30
MaxStartups 10:30:60
X11Forwarding no
AllowAgentForwarding no
# VS Code Remote SSH needs TCP forwarding. Keep it local to the SSH client.
AllowTcpForwarding local
GatewayPorts no
LogLevel VERBOSE
CONFIG
chmod 0644 "$dropin"
/usr/sbin/sshd -t
effective=$(/usr/sbin/sshd -T -C "user=root,host=$client_addr,addr=$client_addr,laddr=$server_addr,lport=$server_port")
grep -Eq '^permitrootlogin (prohibit-password|without-password)$' <<< "$effective"
grep -qx 'pubkeyauthentication yes' <<< "$effective"
grep -qx 'authenticationmethods publickey' <<< "$effective"
grep -qx 'passwordauthentication no' <<< "$effective"
grep -qx 'kbdinteractiveauthentication no' <<< "$effective"
grep -qx 'allowtcpforwarding local' <<< "$effective"
systemctl reload ssh.service
trap - ERR
printf 'Rollback armed for five minutes. Keep this session open.\n'
printf 'Open a NEW root key SSH connection and verify VS Code works.\n'
printf 'Only from the successful new session: systemctl stop control-ssh-rollback.timer\n'
printf 'Recovery script: %s/rollback.sh\n' "$change_dir"
