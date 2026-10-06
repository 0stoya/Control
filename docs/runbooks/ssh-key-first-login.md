# First root key login from Windows / VS Code

The new server currently uses root password login. Keep that working until a new
key login is proved. Run these commands yourself in PowerShell; ssh-keygen asks
for a passphrase. Keep the private key on your PC.

```powershell
$controlSshDirectory = Join-Path $env:USERPROFILE '.ssh'
New-Item -ItemType Directory -Path $controlSshDirectory -Force | Out-Null
$controlSshKeyPath = Join-Path $controlSshDirectory 'control_v2_ed25519'
# If this key path already exists, reuse/review it; do not overwrite it.
ssh-keygen -t ed25519 -a 100 -C 'control-v2-Chris' -f $controlSshKeyPath
Get-Content -LiteralPath ($controlSshKeyPath + '.pub')
```

In your existing VS Code root terminal or provider console on `85.215.119.154`:

```bash
install -d -m 0700 /root/.ssh
touch /root/.ssh/authorized_keys
chmod 0600 /root/.ssh/authorized_keys
# Paste the single PUBLIC ssh-ed25519 line into this file, preserving existing keys.
nano /root/.ssh/authorized_keys
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

The fingerprint is public and may be shared. Verify it through the trusted
provider console before accepting the Windows SSH host-key prompt. Do not send
the root password, private key or key passphrase in chat.

Back in PowerShell, open a new connection using the dedicated key:

```powershell
ssh -o IdentitiesOnly=yes -o PreferredAuthentications=publickey -i $controlSshKeyPath root@85.215.119.154
```

If it falls back to a root password or fails, key login is not yet proved. Entering
the local private-key passphrase is expected. After trust and login are verified,
add this host to your existing SSH config without replacing unrelated entries:

```text
Host ControlV2
    HostName 85.215.119.154
    User root
    IdentityFile ~/.ssh/control_v2_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
```

Check VS Code Remote SSH using `ControlV2`, then proceed with the controlled SSH
hardening runbook. For unattended access by this session, load the
passphrase-protected key in your local SSH agent through your normal trusted
Windows workflow; do not remove its passphrase for automation.

