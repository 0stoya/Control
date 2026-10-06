"""Deploy a clean committed staff-auth release through the trusted CSS-Live alias."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

REMOTE = r"""
import base64,io,json,os,pathlib,subprocess,tarfile,time,urllib.request,urllib.error
payload=json.load(__import__('sys').stdin)
root=pathlib.Path('/srv/control/releases').resolve()
current=pathlib.Path('/srv/control/current')
previous=current.resolve()
assert previous.parent == root and previous.name == payload['expected_current']
assert len(payload['commit']) == 40 and all(c in '0123456789abcdef' for c in payload['commit'])
release=root/('staff-auth-20261006-'+payload['commit'][:12])
assert not release.exists()
def run(*args):
    return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=40)
assert run('systemctl','is-active','control-auth-bridge.service').stdout.strip() == 'active'
site=pathlib.Path('/etc/nginx/sites-enabled/control-v2').resolve()
assert site.parent == pathlib.Path('/etc/nginx/sites-available') and site.name == 'control-v2'
assert 'error_page 503' in site.read_text(), 'expected setup proxy required'
unit=pathlib.Path('/etc/systemd/system/control-api.service')
env=pathlib.Path('/etc/control/staff-auth.env')
backup=pathlib.Path('/etc/control/rollback')/release.name
backup.mkdir(parents=True,mode=0o700)
backup.chmod(0o700)
original={site:site.read_bytes(),unit:unit.read_bytes(),env:env.read_bytes() if env.exists() else None}
for path,data in original.items():
    if data is not None:
        target=backup/path.name
        target.write_bytes(data)
        target.chmod(0o600)
(backup/'previous-release').write_text(str(previous))
def switch(target):
    temporary=pathlib.Path('/srv/control/.current-staff-auth')
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(target)
    os.replace(temporary,current)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def fetch(path,public=False,headers=None,body=None):
    origin='https://control.csscdn.co.uk' if public else 'http://127.0.0.1:8100'
    request=urllib.request.Request(origin+path,data=body,headers=headers or {})
    try:
        response=opener.open(request,timeout=8)
    except urllib.error.HTTPError as error:
        response=error
    with response:
        return response.status,dict(response.headers),response.read(200001)
def ready():
    for attempt in range(15):
        try:
            if fetch('/health/ready')[0] == 200:
                return
        except (OSError,urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError('private readiness did not recover')
checks={}
try:
    release.mkdir(mode=0o755)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(payload['archive'])),mode='r:') as archive:
        for member in archive.getmembers():
            path=pathlib.PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert member.isfile() or member.isdir()
        archive.extractall(release,filter='data')
    for name in ('requirements.txt','requirements.lock'):
        assert (release/name).read_text() == (previous/name).read_text(), 'unreviewed dependency change'
    (release/'.venv').symlink_to(previous/'.venv')
    for path in release.rglob('*'):
        if path.is_symlink():
            continue
        path.chmod(0o755 if path.is_dir() else 0o644)
    run('runuser','-u','control_api','--','env','PYTHONDONTWRITEBYTECODE=1',
        str(release/'.venv/bin/python'),'-B','-c',
        "import sys;sys.path.insert(0,"+repr(str(release))+");from services.auth.gateway import AuthGateway;assert AuthGateway('https://control.csscdn.co.uk').healthy()")
    env.write_text('CONTROL_AUTH_ENABLED=1\nCONTROL_PUBLIC_ORIGIN=https://control.csscdn.co.uk\n')
    env.chmod(0o600)
    unit.write_bytes((release/'deployment/systemd/control-api.service').read_bytes())
    unit.chmod(0o644)
    run('systemd-analyze','verify',str(unit))
    run('systemctl','daemon-reload')
    switch(release)
    run('systemctl','restart','control-api.service')
    ready()
    checks['private_ready']=True
    assert fetch('/login')[0] == 200
    assert fetch('/api/session')[0] == 401
    run('systemctl','stop','control-auth-bridge.service')
    try:
        assert fetch('/health/ready')[0] == 503
        assert fetch('/api/session',headers={'Cookie':'__Host-control_v2_session='+'s'*64})[0] == 503
        checks['authority_outage_fails_closed']=True
    finally:
        run('systemctl','start','control-auth-bridge.service')
    ready()
    # Rehearse the previous release before any public application exposure.
    switch(previous)
    run('systemctl','restart','control-api.service')
    ready()
    assert fetch('/login')[0] == 404
    checks['previous_release_rollback_rehearsed']=True
    switch(release)
    run('systemctl','restart','control-api.service')
    ready()
    site.write_bytes((release/'deployment/nginx/control.csscdn.co.uk.conf').read_bytes())
    site.chmod(0o644)
    run('nginx','-t')
    run('systemctl','reload','nginx')
    # Reload signals nginx; the command can finish before new workers accept.
    deadline=time.monotonic()+15
    while fetch('/login',public=True)[0] != 200:
        if time.monotonic() >= deadline:
            raise RuntimeError('public login did not become ready after reload')
        time.sleep(0.5)
    for path,status in [('/login',200),('/',303),('/api/session',401),('/health/ready',404),
                        ('/auth/health',404),('/auth/admin/users',404),
                        ('/assets/control.css',200),('/assets/login.js',200),('/assets/workspace.js',200)]:
        actual,headers,body=fetch(path,public=True)
        assert actual == status, (path,actual)
        assert headers.get('Cache-Control') == 'no-store'
        assert 'frame-ancestors' in headers.get('Content-Security-Policy','')
    checks['public_boundary_and_security_headers']=True
    status,_,_=fetch('/auth/login',public=True,headers={'Content-Type':'application/json','Origin':'https://denied.example.invalid'},
                    body=b'{"username":"synthetic","password":"synthetic"}')
    assert status == 403
    checks['public_wrong_origin_denied']=True
    checks['private_auth_link_recovered']=True
    receipt={'release':str(release),'previous_release':str(previous),'commit':payload['commit'],
             'checks':checks,'existing_staff_acceptance':'PENDING','auth_authority':'V1_SINGLE_WRITER',
             'database_migrations_changed':False}
    (backup/'deployment-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (backup/'deployment-receipt.json').chmod(0o600)
    print(json.dumps(receipt))
except Exception as error:
    try:
        run('systemctl','start','control-auth-bridge.service')
        switch(previous)
        for path,data in original.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
                path.chmod(0o600 if path == env else 0o644)
        run('systemctl','daemon-reload')
        run('systemctl','restart','control-api.service')
        run('nginx','-t')
        run('systemctl','reload','nginx')
        print(json.dumps({'state':'ROLLED_BACK','error_type':type(error).__name__,'failed_check':str(error),'checks_completed':checks}))
    finally:
        raise SystemExit(1)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-current", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args])
    if git("status", "--porcelain").strip():
        raise SystemExit("clean committed checkout required")
    commit = git("rev-parse", "HEAD").decode().strip()
    if not args.apply:
        print(json.dumps({"host": "CSS-Live", "commit": commit, "expected_current": args.expected_current,
                          "state": "PLAN", "auth_authority": "V1_SINGLE_WRITER"}))
        return
    payload = json.dumps({"commit": commit, "expected_current": args.expected_current,
                          "archive": base64.b64encode(git("archive", "--format=tar", "HEAD")).decode()})
    encoded = base64.b64encode(REMOTE.encode()).decode()
    ssh = r"C:\Windows\System32\OpenSSH\ssh.exe" if sys.platform == "win32" else "ssh"
    command = [ssh, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=10", "CSS-Live",
               "python3 -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""]
    result = subprocess.run(command, input=payload.encode(), check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
