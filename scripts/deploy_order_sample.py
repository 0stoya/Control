"""Prepare/rehearse, then activate a committed bounded order sample on CSS-Live."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

REMOTE=r'''
import base64,hashlib,io,json,os,pathlib,re,subprocess,sys,tarfile,time,urllib.request,urllib.error
p=json.load(sys.stdin); commit=p['commit']
assert re.fullmatch('[0-9a-f]{40}',commit)
root=pathlib.Path('/srv/control/releases'); current=pathlib.Path('/srv/control/current')
release=root/('orders-20261006-'+commit[:12]); previous=root/p['expected_current']
assert previous.parent==root and current.resolve()==previous
assert 'staff-auth-20261006-' in previous.name
site=pathlib.Path('/etc/nginx/sites-enabled/control-v2').resolve()
assert site==pathlib.Path('/etc/nginx/sites-available/control-v2')
env=pathlib.Path('/etc/control/staff-auth.env'); original_env=env.read_bytes(); original_site=site.read_bytes()
assert b'CONTROL_AUTH_ENABLED=1' in original_env and b'CONTROL_ORDERS_ENABLED' not in original_env
backup=pathlib.Path('/etc/control/rollback')/release.name
payload_dir=pathlib.Path('/etc/control/imports')/('sales-sample-'+p['manifest_hash'][:16])
assert re.fullmatch('[0-9a-f]{64}',p['manifest_hash'])
payload_path=payload_dir/'initial-sales-sample.json'
checks={}; phase='START'; schema_applied=False
def run(*args,input=None,timeout=55):
    result=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode: raise RuntimeError('COMMAND_FAILED')
    return result.stdout
def sql(db,query):
    assert db=='control_v2' or re.fullmatch('control_order_check_[0-9a-f]{12}',db)
    return run('runuser','-u','postgres','--','psql','-XAt','-v','ON_ERROR_STOP=1','-d',db,input=query.encode())
def drop(db):
    assert re.fullmatch('control_order_check_[0-9a-f]{12}',db) and db!='control_v2'
    run('runuser','-u','postgres','--','dropdb',db)
def execute(module,*args,data=None):
    return json.loads(run('runuser','-u','postgres','--',str(release/'.venv/bin/python'),'-B','-m',module,*args,input=data,timeout=55))
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def fetch(path,public=False,headers=None):
    origin='https://control.csscdn.co.uk' if public else 'http://127.0.0.1:8100'
    try: response=opener.open(urllib.request.Request(origin+path,headers=headers or {}),timeout=8)
    except urllib.error.HTTPError as error: response=error
    with response: return response.status,dict(response.headers),response.read(200001)
def ready():
    for attempt in range(20):
        try:
            if fetch('/health/ready')[0]==200: return
        except (OSError,urllib.error.URLError): pass
        time.sleep(0.5)
    raise RuntimeError('READINESS_FAILED')
def switch(target):
    tmp=pathlib.Path('/srv/control/.current-orders')
    assert not tmp.exists() and not tmp.is_symlink()
    tmp.symlink_to(target); os.replace(tmp,current)
def feature(enabled):
    env.write_bytes(original_env.rstrip()+b'\nCONTROL_ORDERS_ENABLED='+str(int(enabled)).encode()+b'\n')
    env.chmod(0o600)
def receipt(name,value):
    path=backup/name; path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n'); path.chmod(0o600)
def database_digest(db):
    tables=['control.schema_migration','integration.source_observation','integration.order_source_epoch',
        'integration.order_import','crm.ordering_account','sales.sales_order','sales.order_line',
        'sales.order_revision','sales.line_revision','sales.order_event','reporting.order_current']
    pieces=[]
    for table in tables:
        pieces.append("SELECT '"+table+"' name,count(*) n,encode(sha256(convert_to(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text,'UTF8')),'hex') sha FROM "+table+" t")
    return json.loads(sql(db,'SELECT jsonb_agg(x ORDER BY name) FROM ('+' UNION ALL '.join(pieces)+') x;'))
try:
    if p['mode']=='prepare':
        phase='PREPARE_RELEASE'
        assert not release.exists(); backup.mkdir(parents=True,mode=0o700); backup.chmod(0o700)
        release.mkdir(mode=0o755)
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(p['archive'])),mode='r:') as archive:
            for member in archive.getmembers():
                path=pathlib.PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts and (member.isfile() or member.isdir())
            archive.extractall(release,filter='data')
        for name in ('requirements.txt','requirements.lock'):
            assert (release/name).read_bytes()==(previous/name).read_bytes()
        (release/'.venv').symlink_to(previous/'.venv')
        archive_hash=hashlib.sha256(base64.b64decode(p['archive'])).hexdigest()
        payload_dir.mkdir(parents=True,mode=0o700); payload_dir.chmod(0o700)
        assert not payload_path.exists()
        data=base64.b64decode(p['input']); body=json.loads(data)
        supplied=body.pop('manifest_hash')
        actual=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        assert supplied==actual==p['manifest_hash']
        payload_path.write_bytes(data); payload_path.chmod(0o600)
        phase='NATIVE_ISOLATED_REHEARSAL'; db='control_order_check_'+commit[:12]
        run('runuser','-u','postgres','--','createdb',db)
        try:
            sql(db,'GRANT CREATE ON DATABASE "'+db+'" TO control_owner;')
            manifest={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((release/'migrations').glob('*.sql'))}
            migration_sql='BEGIN; SET ROLE control_owner; CREATE SCHEMA control AUTHORIZATION control_owner; CREATE TABLE control.schema_migration(name text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now());\n'
            for name,sha in manifest.items():
                migration_sql+=(release/'migrations'/name).read_text()+"\nINSERT INTO control.schema_migration(name,sha256) VALUES ('"+name+"','"+sha+"');\n"
            sql(db,migration_sql+'COMMIT;')
            os.chdir(release)
            native=execute('tests.native_sales_acceptance','--database',db,data=data)
            assert native['state']=='PASSED' and native['orders']==20
            checks['native_acceptance']=native
        finally: drop(db)
        checks['source_payload_protected']=payload_path.stat().st_mode & 0o777 == 0o600
        value={'state':'PREPARED','commit':commit,'release':str(release),'previous':str(previous),
            'manifest_hash':p['manifest_hash'],'archive_sha256':archive_hash,'checks':checks,
            'actor':'root via trusted CSS-Live SSH key','source_collector':'V1_ONLY'}
        receipt('preparation.json',value); print(json.dumps(value)); sys.exit(0)
    phase='ACTIVATION_PRECONDITIONS'
    prepared=json.loads((backup/'preparation.json').read_text()); assert prepared['state']=='PREPARED' and prepared['commit']==commit and prepared['manifest_hash']==p['manifest_hash']
    for path,data in ((backup/'staff-auth.env',original_env),(backup/'control-v2',original_site)):
        path.write_bytes(data); path.chmod(0o600)
    (backup/'previous-release').write_text(str(previous))
    phase='PRE_MIGRATION_BACKUP'
    run('bash',str(release/'deployment/ubuntu24/backup.sh'))
    phase='FORWARD_MIGRATION'; os.chdir(release)
    migration=execute('scripts.migrate','--apply'); assert migration['state']=='APPLIED'; schema_applied=True
    phase='PRODUCTION_IMPORT'
    imported=execute('scripts.import_sales_sample','--input','-',data=payload_path.read_bytes()); assert imported['state']=='IMPORTED'
    replay=execute('scripts.import_sales_sample','--input','-',data=payload_path.read_bytes()); assert replay['state']=='REPLAY_VERIFIED'
    checks['import']=imported; checks['exact_replay']=replay
    phase='FEATURE_ROLLBACK_REHEARSAL'
    feature(False); switch(release); run('systemctl','restart','control-api.service'); ready()
    assert fetch('/api/orders')[0]==404 and fetch('/api/session')[0]==401
    checks['feature_rollback_keeps_auth_and_schema_ready']=True
    phase='APP_ACTIVATION'
    feature(True); run('systemctl','restart','control-api.service'); ready()
    assert fetch('/api/orders')[0]==401 and fetch('/orders')[0]==303
    checks['private_anonymous_denied']=True
    phase='PUBLIC_ROUTE_ACTIVATION'
    site.write_bytes((release/'deployment/nginx/control.csscdn.co.uk.conf').read_bytes()); site.chmod(0o644)
    run('nginx','-t'); run('systemctl','reload','nginx')
    for attempt in range(20):
        if fetch('/api/orders',True)[0]==401: break
        time.sleep(0.5)
    else: raise RuntimeError('PUBLIC_GATEWAY_FAILED')
    for path,status in (('/orders',303),('/api/orders',401),('/api/orders/00000000-0000-0000-0000-000000000001',401),('/login',200),('/assets/orders.js',200),('/assets/orders.css',200),('/health/ready',404),('/docs',404),('/integration/source_observation',404),('/assets/orders.html',404)):
        response=fetch(path,True); assert response[0]==status
        assert response[1].get('Cache-Control')=='no-store'
    assert fetch('/api/orders',True,{'Cookie':'__Host-control_v2_session='+'x'*64,'X-CSS-Actor-User-Id':'1','X-CSS-Operational-Profile':'purchasing'})[0]==401
    checks['public_auth_and_route_boundaries']=True
    phase='POPULATED_BACKUP_RESTORE'
    before=set(pathlib.Path('/var/backups/control').glob('backup-*'))
    run('bash',str(release/'deployment/ubuntu24/backup.sh'))
    created=set(pathlib.Path('/var/backups/control').glob('backup-*'))-before
    assert len(created)==1; backup_dir=created.pop(); dump=backup_dir/'control_v2.dump'
    assert dump.is_file()
    result=subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=backup_dir,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    assert result.returncode==0
    db='control_order_check_'+commit[:12]
    run('runuser','-u','postgres','--','createdb',db)
    try:
        with dump.open('rb') as source:
            result=subprocess.run(['runuser','-u','postgres','--','pg_restore','--exit-on-error','--dbname',db],stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=55)
        assert result.returncode==0
        live=database_digest('control_v2'); restored=database_digest(db); assert live==restored
        checks['populated_restore']={'state':'PASSED','tables':live,'backup':str(backup_dir),'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest()}
    finally: drop(db)
    assert run('systemctl','is-active','control-api.service','control-auth-bridge.service','nginx','postgresql','control-backup.timer').decode().splitlines()==['active']*5
    ready()
    value={'state':'DEPLOYED','commit':commit,'release':str(release),'previous':str(previous),
        'manifest_hash':p['manifest_hash'],'checks':checks,'operator_visual_acceptance':'PENDING',
        'authority':'READ_ONLY_SHADOW','feed':'INITIAL_SAVED_SAMPLE_ONLY','actor':'root via trusted CSS-Live SSH key'}
    receipt('deployment-receipt.json',value); print(json.dumps(value))
except Exception as error:
    failed_phase=phase
    if p['mode']=='activate':
        try:
            applied=sql('control_v2',"SELECT count(*) FROM control.schema_migration WHERE name='0002_sales_order_sample.sql';").strip()==b'1'
            if applied:
                feature(False)
                if current.resolve()!=release: switch(release)
            else:
                env.write_bytes(original_env); env.chmod(0o600)
                if current.resolve()!=previous: switch(previous)
            site.write_bytes(original_site); site.chmod(0o644)
            run('nginx','-t'); run('systemctl','reload','nginx'); run('systemctl','restart','control-api.service'); ready()
            state='ROLLED_BACK_CAPABILITY'
        except Exception: state='ROLLBACK_REQUIRES_ATTENTION'
    else: state='PREPARATION_FAILED'
    value={'state':state,'phase':failed_phase,'error_type':type(error).__name__,'checks_completed':checks}
    if backup.exists(): receipt('failure.json',value)
    print(json.dumps(value)); sys.exit(1)
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('prepare','activate'),required=True)
    parser.add_argument('--expected-current',required=True)
    parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[1]
    def git(*args): return subprocess.check_output(['git','-C',str(root),*args])
    if git('status','--porcelain').strip(): raise SystemExit('CLEAN_COMMITTED_CHECKOUT_REQUIRED')
    data=args.input.read_bytes(); body=json.loads(data)
    if len(data)>12_000_000: raise SystemExit('INPUT_BUDGET_EXCEEDED')
    payload={'mode':args.mode,'commit':git('rev-parse','HEAD').decode().strip(),
             'expected_current':args.expected_current,'manifest_hash':body['manifest_hash']}
    if args.mode=='prepare':
        payload.update({'archive':base64.b64encode(git('archive','--format=tar','HEAD')).decode(),'input':base64.b64encode(data).decode()})
    ssh=r'C:\Windows\System32\OpenSSH\ssh.exe' if sys.platform=='win32' else 'ssh'
    program=base64.b64encode(REMOTE.encode()).decode()
    command=[ssh,'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','CSS-Live',
             'python3 -c "import base64;exec(base64.b64decode(\''+program+'\'))"']
    result=subprocess.run(command,input=json.dumps(payload).encode()); raise SystemExit(result.returncode)

if __name__=='__main__': main()
