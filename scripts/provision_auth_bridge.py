"""Provision the reviewed auth-only SSH link using both trusted management aliases.

Only the new client public key leaves V2. No auth/SMTP/Graph private credential
is copied. No existing auth state or service code is changed. --apply is required.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def remote(ssh, alias, program):
    encoded = base64.b64encode(program.encode()).decode()
    command = "python3 -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""
    result = subprocess.run([ssh, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o",
                             "ConnectTimeout=10", alias, command], capture_output=True, timeout=50)
    if result.returncode:
        raise ValueError("bridge provisioning failed; no remote output logged")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ssh = shutil.which("ssh")
    if not ssh:
        raise ValueError("SSH unavailable")
    if not args.apply:
        print(json.dumps({"state":"REVIEWED_PLAN", "source":"FSE-root", "target":"CSS-Live",
                          "forward":"V2 loopback 18020 -> V1 loopback 8020", "copies_auth_state":False}))
        return
    trust = remote(ssh, "FSE-root", '''
import json,pathlib,subprocess
print(json.dumps({"host_key":pathlib.Path("/etc/ssh/ssh_host_ed25519_key.pub").read_text().strip(),
 "ssh_policy":subprocess.check_output(["sshd","-T"],text=True).splitlines()}))
''')
    # This recipe was inspected against the existing root/chris allowlist.
    if {x for x in trust["ssh_policy"] if x.startswith("allowusers ")} != {"allowusers root", "allowusers chris"}:
        raise ValueError("V1 SSH allowlist changed; review required")
    destination = remote(ssh, "CSS-Live", '''
import pathlib,os,pwd,subprocess,json
if os.geteuid()!=0: raise SystemExit("root required")
os.umask(0o077)
base=pathlib.Path("/etc/control/auth-bridge")
if base.is_symlink(): raise SystemExit("symlink refused")
base.mkdir(mode=0o700,exist_ok=True)
if base.stat().st_uid!=0 or base.stat().st_mode & 0o077: raise SystemExit("untrusted credential directory")
try:
 user=pwd.getpwnam("control_auth_bridge")
 if user.pw_shell!="/usr/sbin/nologin": raise SystemExit("unexpected service identity")
except KeyError:
 subprocess.run(["useradd","--system","--user-group","--home-dir","/var/lib/control-auth-bridge","--shell","/usr/sbin/nologin","control_auth_bridge"],check=True)
key=base/"identity"
if not key.exists(): subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-C","control-v2-auth-bridge","-f",str(key)],check=True)
if key.is_symlink() or key.stat().st_uid!=0 or key.stat().st_mode & 0o077: raise SystemExit("untrusted client key")
public=subprocess.check_output(["ssh-keygen","-y","-f",str(key)],text=True).strip()
print(json.dumps({"public_key":public}))
''')
    configuration = (ROOT / "deployment/ssh/control-auth-bridge.conf").read_text()
    key_line = 'restrict,port-forwarding,from="85.215.119.154",permitopen="127.0.0.1:8020",command="/bin/false" ' + destination["public_key"] + " control-v2-auth-bridge\n"
    source_program = '''
import pathlib,os,pwd,subprocess,json
if os.geteuid()!=0: raise SystemExit("root required")
configuration=CONFIGURATION
key_line=KEY_LINE
config=pathlib.Path("/etc/ssh/sshd_config.d/99-control-auth-bridge.conf")
keys=pathlib.Path("/etc/ssh/control-auth-bridge.keys")
if config.exists() or keys.exists(): raise SystemExit("bridge source already configured; no overwrite")
try:
 pwd.getpwnam("control_auth_bridge")
 raise SystemExit("existing source identity requires review")
except KeyError: pass
subprocess.run(["useradd","--system","--user-group","--home-dir","/var/lib/control-auth-bridge","--shell","/usr/sbin/nologin","control_auth_bridge"],check=True)
pathlib.Path("/var/lib/control-auth-bridge").mkdir(mode=0o755,exist_ok=True)
keys.write_text(key_line);keys.chmod(0o644)
config.write_text(configuration);config.chmod(0o644)
try:
 subprocess.run(["sshd","-t"],check=True,capture_output=True)
 lines=subprocess.check_output(["sshd","-T","-C","user=control_auth_bridge,addr=85.215.119.154,host=CSS-Live"],text=True).splitlines()
 required={"allowtcpforwarding local","permitopen 127.0.0.1:8020","permitlisten none","forcecommand /bin/false","authenticationmethods publickey","permittty no"}
 if not required.issubset(set(lines)): raise ValueError("restricted policy mismatch")
 if not {"allowusers root","allowusers chris","allowusers control_auth_bridge@85.215.119.154"}.issubset(set(lines)): raise ValueError("management allowlist mismatch")
 subprocess.run(["systemctl","reload","ssh.service"],check=True)
except Exception:
 config.unlink(missing_ok=True);keys.unlink(missing_ok=True)
 subprocess.run(["sshd","-t"],check=True,capture_output=True)
 subprocess.run(["systemctl","reload","ssh.service"],check=True)
 raise SystemExit("bridge source configuration rolled back")
print(json.dumps({"restricted_identity_configured":True,"management_allowlist_retained":True}))
'''.replace("CONFIGURATION", repr(configuration)).replace("KEY_LINE", repr(key_line))
    source = remote(ssh, "FSE-root", source_program)
    # Prove fresh management login after the narrowly scoped SSH reload.
    remote(ssh, "FSE-root", 'import json;print(json.dumps({"fresh_management_login":True}))')
    known_hosts = "77.68.81.175 " + " ".join(trust["host_key"].split()[:2]) + "\n"
    unit = (ROOT / "deployment/systemd/control-auth-bridge.service").read_text()
    target_program = '''
import pathlib,subprocess,json,time,urllib.request
base=pathlib.Path("/etc/control/auth-bridge")
known=base/"known_hosts"
known.write_text(KNOWN_HOSTS);known.chmod(0o600)
unit=pathlib.Path("/etc/systemd/system/control-auth-bridge.service")
if unit.exists(): raise SystemExit("bridge unit already exists; no overwrite")
unit.write_text(UNIT);unit.chmod(0o644)
subprocess.run(["systemd-analyze","verify",str(unit)],check=True,capture_output=True)
subprocess.run(["systemctl","daemon-reload"],check=True)
subprocess.run(["systemctl","enable","--now","control-auth-bridge.service"],check=True,capture_output=True)
for attempt in range(12):
 try:
  with urllib.request.urlopen("http://127.0.0.1:18020/auth/health",timeout=2) as r: body=json.load(r)
  if body.get("status")=="ok" and body.get("database")=="css_app" and body.get("database_user")=="css_auth": break
 except Exception: pass
 time.sleep(1)
else:
 subprocess.run(["systemctl","disable","--now","control-auth-bridge.service"],check=True,capture_output=True)
 raise SystemExit("bridge health failed; service stopped")
print(json.dumps({"bridge_active":True,"authority_health":"ok","private_key_remained_on_v2":True}))
'''.replace("KNOWN_HOSTS", repr(known_hosts)).replace("UNIT", repr(unit))
    target = remote(ssh, "CSS-Live", target_program)
    print(json.dumps({"state":"PRIVATE_AUTH_LINK_READY", **source, **target}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError):
        print("auth_bridge_provisioning_failed", file=sys.stderr)
        raise SystemExit(1)
