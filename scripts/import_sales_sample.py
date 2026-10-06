"""Operator-only atomic import/replay/rebuild of the accepted saved Sales sample."""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from packages.sales_sample import translate, stable_id, timestamp, VERSION

class InputConflict(ValueError): pass

def ensure(conn,table,keys,values):
    # Table/column names are constants in this file, never source values.
    columns=list(values)
    placeholders=','.join(['%s']*len(columns))
    args=[Jsonb(v) if isinstance(v,dict) else v for v in values.values()]
    found=conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING RETURNING 1',args).fetchone()
    if found: return
    where=' AND '.join(f'{k}=%s' for k in keys)
    existing=conn.execute(f'SELECT {",".join(columns)} FROM {table} WHERE {where}',[values[k] for k in keys]).fetchone()
    if existing is None or tuple(values.values())!=existing: raise InputConflict('immutable input conflict')

def pointer_digest(conn):
    return conn.execute('SELECT order_id::text,revision_id::text,manifest_hash FROM reporting.order_current ORDER BY order_id').fetchall()

def ingest(conn,bundle,rebuild=False):
    body=bundle['body']; registry=bundle['registry']; counts=bundle['counts']; mh=bundle['manifest_hash']
    with conn.transaction():
        conn.execute('SET LOCAL ROLE control_owner')
        conn.execute('SELECT pg_advisory_xact_lock(185215120)')
        before=pointer_digest(conn)
        exists=conn.execute('SELECT manifest FROM integration.order_import WHERE manifest_hash=%s',(mh,)).fetchone()
        if rebuild and exists is None: raise ValueError('rebuild requires committed input')
        ensure(conn,'integration.order_source_epoch',['epoch'],{'epoch':registry['epoch'],
            'namespace_id':bundle['namespace_id'],'source_instance':registry['source_instance'],
            'company_scope':registry['company_scope'],'registry':registry})
        for oid,e in bundle['envelopes'].items():
            values={'observation_id':oid,**e.model_dump()}
            ensure(conn,'integration.source_observation',['observation_id'],values)
        for r in bundle['revisions']:
            order_id=UUID(r['order_id']); revision_id=UUID(r['revision_id'])
            ensure(conn,'crm.ordering_account',['account_id'],{'account_id':UUID(r['account_id']),
                'namespace_id':bundle['namespace_id'],'source_reference':r['account_reference']})
            ensure(conn,'sales.sales_order',['order_id'],{'order_id':order_id,'account_id':UUID(r['account_id']),'order_number':r['order_number']})
            values={k:r[k] for k in ('source_snapshot_id','translator_version','captured_rep','keyset_basis','reconciliation_status','line_count','interpretation_hash')}
            values.update({'revision_id':revision_id,'order_id':order_id,
                'snapshot_observation_id':UUID(r['snapshot_observation_id']),'header_observation_id':UUID(r['header_observation_id']),
                'source_observed_at':timestamp(r['source_observed_at']),
                'oldest_input_at':timestamp(r['oldest_input_at']),
                'source_order_date':date.fromisoformat(r['source_order_date']) if r['source_order_date'] else None})
            ensure(conn,'sales.order_revision',['revision_id'],values)
            for l in r['lines']:
                line_id=UUID(l['line_id'])
                ensure(conn,'sales.order_line',['line_id'],{'line_id':line_id,'order_id':order_id,'unique_number':l['unique_number']})
                values={k:l[k] for k in ('item_number','sku','description','captured_quantity','captured_price','captured_unit_text','numeric_policy')}
                values.update({'revision_id':revision_id,'line_id':line_id,'order_id':order_id,'observation_id':UUID(l['observation_id'])})
                ensure(conn,'sales.line_revision',['revision_id','line_id'],values)
            ensure(conn,'sales.order_event',['event_id'],{'event_id':stable_id('event',r['revision_id'],'ORDER_SNAPSHOT_OBSERVED'),
                'revision_id':revision_id,'order_id':order_id,'event_type':'ORDER_SNAPSHOT_OBSERVED','occurred_at':None,
                'source_observed_at':timestamp(r['source_observed_at'])})
        ensure(conn,'integration.order_import',['manifest_hash'],{'manifest_hash':mh,'epoch':registry['epoch'],
            'manifest':body,'order_count':counts['orders'],'revision_count':counts['revisions'],
            'line_count':counts['line_inputs'],'observation_count':counts['observations'],'translator_version':VERSION})
        if exists is None or rebuild:
            if rebuild: conn.execute('DELETE FROM reporting.order_current')
            for oid,rid in bundle['pointers']:
                conn.execute('INSERT INTO reporting.order_current(order_id,revision_id,manifest_hash) VALUES (%s,%s,%s)',(UUID(oid),UUID(rid),mh))
        after=pointer_digest(conn)
        if len(after)!=counts['orders'] or set((a,b) for a,b,_ in after)!=set(bundle['pointers']): raise InputConflict('projection mismatch')
        if exists is not None and not rebuild and before!=after: raise InputConflict('replay changed identity or membership')
        actual=conn.execute('SELECT (SELECT count(*) FROM sales.order_revision),(SELECT count(*) FROM sales.line_revision),(SELECT count(*) FROM integration.source_observation)').fetchone()
        if actual!=(counts['revisions'],counts['line_inputs'],counts['observations']): raise InputConflict('count reconciliation mismatch')
    return {'state':'REBUILT' if rebuild else 'REPLAY_VERIFIED' if exists else 'IMPORTED',
            'manifest_hash':mh,**counts,'translator_version':VERSION,'continuation':'INITIAL_SAVED_SAMPLE_ONLY'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--database',default='control_v2')
    parser.add_argument('--rebuild',action='store_true')
    args=parser.parse_args()
    if args.database!='control_v2' and not re.fullmatch(r'control_order_check_[0-9a-f]{12}',args.database):
        raise SystemExit('DATABASE_NOT_ALLOWED')
    data=sys.stdin.buffer.read(12_000_001) if str(args.input)=='-' else args.input.read_bytes()
    if len(data)>12_000_000: raise SystemExit('INPUT_BUDGET_EXCEEDED')
    try: bundle=translate(json.loads(data))
    except (ValueError,KeyError,TypeError,OverflowError):
        print(json.dumps({'state':'FAILED','reason':'SOURCE_CONTRACT_VALIDATION_FAILED'})); return 1
    try:
        with psycopg.connect(dbname=args.database,user='postgres',host='/var/run/postgresql',connect_timeout=3,
                            options='-c statement_timeout=60000 -c lock_timeout=5000') as conn:
            print(json.dumps(ingest(conn,bundle,args.rebuild)))
        return 0
    except (psycopg.Error,ValueError):
        reason='INPUT_CONFLICT'
        with psycopg.connect(dbname=args.database,user='postgres',host='/var/run/postgresql',connect_timeout=3) as audit:
            audit.execute('SET ROLE control_owner')
            audit.execute('INSERT INTO audit.order_import_failure(manifest_hash,reason) VALUES (%s,%s)',(bundle['manifest_hash'],reason))
        print(json.dumps({'state':'FAILED','reason':reason})); return 1

if __name__=='__main__': raise SystemExit(main())
