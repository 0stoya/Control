"""Stage V1 mail settings over verified SSH without local secret files or sending.

Run from an operator machine with both trusted SSH aliases. --apply creates a new
root-only disabled import on V2. It never modifies V1, installs a service, imports
outboxes or activates credentials. All sensitive bytes stay in subprocess pipes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys


EXPORT = r'''
import json, os, shlex, subprocess
from pathlib import Path
if os.geteuid() != 0: raise SystemExit("root required")
def environment(path, allowed):
 out={}
 for line in Path(path).read_text().splitlines():
  if line.startswith("Environment="):
   parts=shlex.split(line.split("=",1)[1])
  elif not line.strip() or line.lstrip().startswith("#"):
   continue
  else:
   parts=shlex.split(line)
  for item in parts:
   key, sep, value=item.partition("=")
   if sep and allowed(key): out[key]=value
 return out
smtp=environment("/etc/css/css-smtp.env",lambda k: k.startswith("CSS_SMTP_") or k=="CSS_PUBLIC_ORIGIN")
graph=environment("/etc/systemd/system/css-api.service.d/95-po-graph.conf",lambda k:k.startswith("CSS_PO_GRAPH_"))
sql="""BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='15000ms'; SET LOCAL lock_timeout='2000ms';
SELECT json_build_object('profiles',(SELECT coalesce(json_agg(row_to_json(p)),'[]'::json) FROM communication.section_mail_profile p),
 'events',(SELECT coalesce(json_agg(row_to_json(e)),'[]'::json) FROM communication.section_mail_profile_event e));
ROLLBACK;"""
r=subprocess.run(["runuser","-u","postgres","--","psql","-X","-q","-A","-t","-d","css_app","-v","ON_ERROR_STOP=1","-f","-"],input=sql,text=True,capture_output=True,timeout=20)
if r.returncode: raise SystemExit("mail profile export failed")
rows=[json.loads(line) for line in r.stdout.splitlines() if line.strip()]
if len(rows)!=1: raise SystemExit("mail profile export ambiguous")
private_path=graph.get("CSS_PO_GRAPH_PRIVATE_KEY_FILE","/etc/css/control-graph/control-graph-private.key")
cert_path=graph.get("CSS_PO_GRAPH_PUBLIC_CERT_FILE","/etc/css/control-graph/control-graph-public.crt")
password_path=smtp.get("CSS_SMTP_PASSWORD_FILE","/etc/css/credentials/css-smtp-password")
payload={"schema_version":"v1_mail_settings_v1","smtp_environment":smtp,"graph_environment":graph,
 "smtp_password":Path(password_path).read_text(),"graph_private_key":Path(private_path).read_text(),
 "graph_public_certificate":Path(cert_path).read_text(),"profiles":rows[0]}
print(json.dumps(payload,sort_keys=True,separators=(",",":")))
'''


RECEIVE = r'''
import hashlib, json, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
if os.geteuid()!=0: raise SystemExit("root required")
os.umask(0o077)
raw=sys.stdin.buffer.read(2_000_001)
if len(raw)>2_000_000: raise SystemExit("import exceeds budget")
data=json.loads(raw)
required={"schema_version","smtp_environment","graph_environment","smtp_password","graph_private_key","graph_public_certificate","profiles"}
if set(data)!=required or data["schema_version"]!="v1_mail_settings_v1": raise SystemExit("unknown import contract")
if not data["graph_private_key"].startswith("-----BEGIN ") or "PRIVATE KEY-----" not in data["graph_private_key"]: raise SystemExit("invalid credential")
if not data["graph_public_certificate"].startswith("-----BEGIN CERTIFICATE-----"): raise SystemExit("invalid certificate")
if not isinstance(data["profiles"]["profiles"],list) or not isinstance(data["profiles"]["events"],list): raise SystemExit("invalid profiles")
for directory in [Path("/etc/control"),Path("/etc/control/mail"),Path("/etc/control/mail/imports")]:
 if directory.is_symlink(): raise SystemExit("symlink refused")
 directory.mkdir(mode=0o700,exist_ok=True)
 if not directory.is_dir() or directory.stat().st_uid!=0: raise SystemExit("untrusted import parent")
 if directory != Path("/etc/control") and directory.stat().st_mode & 0o077: raise SystemExit("import parent too permissive")
stamp=datetime.now(timezone.utc).strftime("v1-%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
base=Path("/etc/control/mail/imports")
temp=base/(".incoming-"+stamp)
target=base/stamp
temp.mkdir(mode=0o700)
def save(name,value):
 content=value if isinstance(value,str) else json.dumps(value,sort_keys=True,indent=2)+"\n"
 with (temp/name).open("x",encoding="utf-8") as stream: stream.write(content)
save("smtp-settings.json",data["smtp_environment"])
save("smtp-password",data["smtp_password"])
save("graph-settings.json",data["graph_environment"])
save("graph-private.key",data["graph_private_key"])
save("graph-public.crt",data["graph_public_certificate"])
save("section-mail-profiles.json",data["profiles"])
receipt={"schema_version":"mail_import_receipt_v1","source":"FSE-root","created_at":datetime.now(timezone.utc).isoformat(),
 "enabled":False,"worker_installed":False,"profile_count":len(data["profiles"]["profiles"]),
 "profile_event_count":len(data["profiles"]["events"]),"outboxes_imported":False,"source_bundle_sha256":hashlib.sha256(raw).hexdigest()}
save("receipt.json",receipt)
temp.rename(target)
receipt["path"]=str(target)
print(json.dumps(receipt))
'''


def remote_python(ssh: str, alias: str, program: str, payload: bytes | None = None):
    # Encodes only this fixed program, never credentials, in the command argument.
    encoded = base64.b64encode(program.encode()).decode()
    command = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
    return subprocess.run(
        [ssh, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o",
         "ConnectTimeout=10", alias, command], input=payload, capture_output=True,
        timeout=45, check=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-alias", default="FSE-root")
    parser.add_argument("--target-alias", default="CSS-Live")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.source_alias != "FSE-root" or args.target_alias != "CSS-Live":
        raise ValueError("this transfer contract requires the reviewed FSE-root and CSS-Live aliases")
    ssh = shutil.which("ssh")
    if not ssh:
        raise ValueError("SSH unavailable")
    exported = remote_python(ssh, args.source_alias, EXPORT)
    if exported.returncode or len(exported.stdout) > 2_000_000:
        raise ValueError("V1 mail export failed; no payload logged")
    payload = exported.stdout
    data = json.loads(payload)
    summary = {"state": "CHECKED", "profiles": len(data["profiles"]["profiles"]),
               "credentials_present": bool(data["smtp_password"] and data["graph_private_key"]),
               "outboxes_imported": False, "enabled": False}
    if args.apply:
        result = remote_python(ssh, args.target_alias, RECEIVE, payload)
        if result.returncode:
            raise ValueError("V2 disabled staging failed; no payload logged")
        receipt = json.loads(result.stdout)
        if receipt["source_bundle_sha256"] != hashlib.sha256(payload).hexdigest():
            raise ValueError("transfer integrity failed")
        summary.update(state="STAGED_DISABLED", path=receipt["path"],
                       integrity_verified=True, profile_events=receipt["profile_event_count"])
    print(json.dumps(summary))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        # Never print exception data or subprocess output; both can hold secrets.
        print("mail_settings_transfer_failed", file=sys.stderr)
        raise SystemExit(1)
