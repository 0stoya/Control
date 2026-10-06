"""Save a bounded immutable export through trusted FSE-root; emit counts only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

READERS = ('services/connector/sculptor_business_live.py',
           'services/connector/sculptor_live.py', 'services/connector/ogl_history_mirror.py')
REMOTE = r'''
import hashlib,json,pathlib,subprocess,sys
expected=__EXPECTED_READERS__
repo=pathlib.Path('/srv/css/repository')
actual={p:hashlib.sha256((repo/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in expected}
if actual != expected: raise SystemExit('SOURCE_READER_CHANGED')
git=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
q=__QUERY__
r=subprocess.run(['runuser','-u','postgres','--','psql','-XAt','-v','ON_ERROR_STOP=1','-d','css_app'],input=q,capture_output=True,text=True,timeout=55)
if r.returncode: raise SystemExit('BOUNDED_EXPORT_QUERY_FAILED')
values=[line for line in r.stdout.splitlines() if line.startswith('{')]
if len(values)!=1: raise SystemExit('EXPORT_BOUNDARY_FAILED')
body=json.loads(values[0])
body['format']='v1_sales_sample_v1'
body['registry']={'epoch':'fse-css-app-20261006-7667602069027910251-23268',
 'system_id':'7667602069027910251','database_oid':'23268','database':'css_app',
 'ssh_host':'FSE-root','source_instance':'sculptor:live','company_scope':'css-profit-live-main',
 'physical_prefix':'/usr/livedata/data/','reader_hashes':actual}
if body.pop('system_id')!=body['registry']['system_id'] or body.pop('database_oid')!=body['registry']['database_oid']:
 raise SystemExit('DATABASE_EPOCH_CHANGED')
body['boundary']['source_commit']=git
body['boundary']['continuation']='INITIAL_SAVED_SAMPLE_ONLY'
body['boundary']['gaps']=['OGL-selected orders excluded','Retained captures only','No recurring continuation','No milestone evidence']
canonical=lambda v:json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
body['manifest_hash']=hashlib.sha256(canonical(body).encode()).hexdigest()
sys.stdout.write(canonical(body))
'''
QUERY = """
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='40000';
SET LOCAL lock_timeout='2000';
WITH current AS (
 SELECT c.*, b.source_key AS snapshot_key
 FROM crm_read.current_business_order_header_projection c
 JOIN sculptor_live.business_snapshot b ON b.id=c.sculptor_snapshot_id
 WHERE c.kind='SALES_ORDER' AND c.selected_source='SCULPTOR_LIVE'
   AND b.kind=c.kind AND b.source_key=c.source_key
   AND b.line_count=c.line_count AND b.keyset_basis=c.keyset_basis
), history AS (
 SELECT c.sculptor_snapshot_id current_id,b.* FROM current c
 JOIN sculptor_live.business_snapshot b ON b.kind=c.kind
 AND b.source_key=c.snapshot_key AND b.id<=c.sculptor_snapshot_id
), budget AS (
 SELECT current_id,count(*) revisions,sum(line_count) inputs FROM history
 GROUP BY current_id HAVING count(*)<=30 AND sum(line_count)<=100
), changes AS (
 SELECT current_id,bool_or(positions>1) renumbered FROM (
 SELECT h.current_id,o.payload->'uniqueno' logical,count(DISTINCT o.payload->'itemno') positions
 FROM history h JOIN sculptor_live.business_snapshot_line l ON l.snapshot_id=h.id
 JOIN sculptor_live.observation o ON o.id=l.observation_id
 JOIN budget b ON b.current_id=h.current_id GROUP BY h.current_id,o.payload->'uniqueno'
 ) x GROUP BY current_id
), selected AS (
 SELECT c.*, b.revisions,b.inputs,coalesce(x.renumbered,false) renumbered
 FROM current c JOIN budget b ON b.current_id=c.sculptor_snapshot_id
 LEFT JOIN changes x ON x.current_id=c.sculptor_snapshot_id
 ORDER BY coalesce(x.renumbered,false) DESC,c.observed_at DESC,c.sculptor_snapshot_id DESC LIMIT 20
), revisions AS (
 SELECT h.* FROM history h JOIN selected c ON c.sculptor_snapshot_id=h.current_id
), observation_ids AS (
 SELECT header_observation_id id FROM revisions UNION
 SELECT l.observation_id FROM revisions r JOIN sculptor_live.business_snapshot_line l ON l.snapshot_id=r.id
)
SELECT jsonb_build_object(
 'system_id',(SELECT system_identifier::text FROM pg_control_system()),
 'database_oid',(SELECT oid::text FROM pg_database WHERE datname=current_database()),
 'boundary',jsonb_build_object('exported_at',clock_timestamp(),'transaction_snapshot',pg_current_snapshot()::text),
 'selected',(SELECT coalesce(jsonb_agg(jsonb_build_object('snapshot_id',sculptor_snapshot_id,'source_key',source_key,
    'line_count',line_count,'keyset_basis',keyset_basis,'renumbered',renumbered) ORDER BY sculptor_snapshot_id),'[]') FROM selected),
 'snapshots',(SELECT coalesce(jsonb_agg(to_jsonb(r)-'current_id' ORDER BY r.id),'[]') FROM revisions r),
 'members',(SELECT coalesce(jsonb_agg(to_jsonb(l) ORDER BY l.snapshot_id,l.line_no),'[]') FROM revisions r
 JOIN sculptor_live.business_snapshot_line l ON l.snapshot_id=r.id),
 'observations',(SELECT coalesce(jsonb_agg(to_jsonb(o) ORDER BY o.id),'[]') FROM observation_ids i
 JOIN sculptor_live.observation o ON o.id=i.id));
ROLLBACK;
"""

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-checkout',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise SystemExit('EXPORT_ALREADY_EXISTS')
    expected={p:hashlib.sha256((args.source_checkout/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in READERS}
    program=REMOTE.replace('__EXPECTED_READERS__',repr(expected)).replace('__QUERY__',repr(QUERY))
    ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','FSE-root','python3 -']
    result=subprocess.run(ssh,input=program.encode(),capture_output=True,timeout=65)
    if result.returncode or len(result.stdout)>12_000_000:
        raise SystemExit('SOURCE_EXPORT_FAILED_OR_BUDGET_EXCEEDED')
    value=json.loads(result.stdout)
    if not 1<=len(value['selected'])<=20 or len(value['members'])>2000: raise SystemExit('EXPORT_POPULATION_INVALID')
    with args.output.open('xb') as output: output.write(result.stdout)
    print(json.dumps({'state':'EXPORTED','manifest_hash':value['manifest_hash'],
                     'orders':len(value['selected']),'revisions':len(value['snapshots']),
                     'line_inputs':len(value['members']),'observations':len(value['observations']),
                     'renumbered_orders':sum(s['renumbered'] for s in value['selected'])}))

if __name__=='__main__': main()
