"""Operator-only native PostgreSQL sample acceptance in a disposable named DB."""
import argparse
from copy import deepcopy
import json
import re
import sys
import psycopg
from packages.sales_sample import translate
from packages.contracts.observation import payload_sha256
from scripts.import_sales_sample import ingest,InputConflict,pointer_digest

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--database',required=True); args=parser.parse_args()
    if not re.fullmatch('control_order_check_[0-9a-f]{12}',args.database): raise SystemExit('ISOLATED_DATABASE_REQUIRED')
    data=sys.stdin.buffer.read(12_000_001)
    if len(data)>12_000_000: raise SystemExit('INPUT_BUDGET_EXCEEDED')
    body=json.loads(data); bundle=translate(body); checks={}
    with psycopg.connect(dbname=args.database,user='postgres',host='/var/run/postgresql') as conn:
        checks['initial_import']=ingest(conn,bundle)['state']=='IMPORTED'
        conn.execute('SET ROLE control_owner'); before=pointer_digest(conn); conn.commit()
        checks['exact_replay']=ingest(conn,bundle)['state']=='REPLAY_VERIFIED'
        bad=deepcopy(body)
        target=next(o for o in bad['observations'] if o['dataset']=='orditem')
        target['payload']['desc']='SYNTHETIC CONFLICT PROBE'
        target['payload_hash']=payload_sha256(target['payload'])
        bad.pop('manifest_hash'); bad['manifest_hash']=payload_sha256(bad)
        try: ingest(conn,translate(bad))
        except InputConflict: checks['conflict_rejected']=True
        else: raise RuntimeError('conflict accepted')
        checks['conflict_did_not_advance']=pointer_digest(conn)==before
        conn.execute('DELETE FROM reporting.order_current WHERE order_id IN (SELECT order_id FROM reporting.order_current LIMIT 2)'); conn.commit()
        checks['missing_projection_rebuilt']=ingest(conn,bundle,rebuild=True)['state']=='REBUILT'
        checks['rebuild_identity_parity']=pointer_digest(conn)==before
        conn.commit()
    with psycopg.connect(dbname=args.database,user='postgres',host='/var/run/postgresql',autocommit=True) as conn:
        for table in ('integration.source_observation','integration.order_import','sales.order_revision','sales.line_revision','sales.order_event'):
            try: conn.execute(f'DELETE FROM {table}')
            except psycopg.Error as error: assert error.sqlstate=='55000'
            else: raise RuntimeError('append only guard missing')
        checks['immutable_evidence_and_history']=True
        conn.execute('SET SESSION AUTHORIZATION control_api')
        row=conn.execute("SELECT count(*),bool_and(fulfilment_state='UNKNOWN' AND invoice_state='UNKNOWN' AND freshness_state='UNKNOWN') FROM reporting.orders").fetchone()
        checks['runtime_typed_projection']=row==(20,True)
        for sql in ('SELECT * FROM integration.source_observation','SELECT * FROM sales.order_revision','DELETE FROM reporting.order_current','SET ROLE control_owner'):
            try: conn.execute(sql)
            except psycopg.Error as error: assert error.sqlstate=='42501'
            else: raise RuntimeError('runtime privilege widened')
        checks['runtime_least_privilege']=True
    assert all(checks.values())
    print(json.dumps({'state':'PASSED','checks':checks,**bundle['counts'],'manifest_hash':bundle['manifest_hash']}))

if __name__=='__main__': main()
