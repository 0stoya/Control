"""Read-only typed PostgreSQL projections. No legacy connection."""
from datetime import datetime, timezone
from uuid import UUID
import psycopg
from psycopg.rows import dict_row

def age(row,now):
    row=dict(row)
    row['source_age_seconds']=max(0,int((now-row['oldest_input_at']).total_seconds()))
    row['freshness_reason']='NO_ACCEPTED_CADENCE_OR_REVISIT_SLO'
    return row

def changes(previous,current):
    if previous is None: return {'basis':'FIRST_RETAINED_CAPTURE','added':None,'removed':None,'moved':None,'values_changed':None}
    left={r['line_id']:r for r in previous}; right={r['line_id']:r for r in current}
    common=left.keys() & right.keys()
    fields=('sku','description','captured_quantity','captured_price','captured_unit_text')
    return {'basis':'PREVIOUS_RETAINED_CAPTURE','added':len(right.keys()-left.keys()),
            'removed':len(left.keys()-right.keys()),
            'moved':sum(left[k]['item_number']!=right[k]['item_number'] for k in common),
            'values_changed':sum(any(left[k][f]!=right[k][f] for f in fields) for k in common)}

class OrderRepository:
    def connect(self):
        return psycopg.connect(dbname='control_v2',user='control_api',host='/var/run/postgresql',
            row_factory=dict_row,connect_timeout=3,
            options='-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=1000')

    def listing(self):
        now=datetime.now(timezone.utc)
        with self.connect() as conn:
            rows=conn.execute('SELECT * FROM reporting.orders ORDER BY order_number DESC LIMIT 21').fetchall()
        if len(rows)>20: raise ValueError('population budget exceeded')
        return {'mode':'READ_ONLY_SAMPLE','coverage_state':'PARTIAL','authority_state':'SHADOW',
                'feed_state':'INITIAL_SAVED_SAMPLE_ONLY','orders':[age(row,now) for row in rows],
                'population_count':len(rows),'evaluated_at':now,
                'blocked_lanes':['FULFILMENT','INVOICE','PAYMENT','PROMISE'],
                'scope_note':'Saved sample from retained V1 captures. Other orders and uncaptured history are excluded.'}

    def detail(self,order_id:UUID):
        now=datetime.now(timezone.utc)
        with self.connect() as conn:
            # Three related queries share a consistent projection generation.
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            order=conn.execute('SELECT * FROM reporting.orders WHERE order_id=%s',(order_id,)).fetchone()
            if order is None: return None
            revisions=conn.execute('SELECT * FROM reporting.order_history WHERE order_id=%s ORDER BY source_snapshot_id',(order_id,)).fetchall()
            lines=conn.execute('SELECT * FROM reporting.order_revision_lines WHERE order_id=%s ORDER BY revision_id,item_number',(order_id,)).fetchall()
        if len(revisions)>30 or len(lines)>500: raise ValueError('history budget exceeded')
        grouped={r['revision_id']:[] for r in revisions}
        for line in lines: grouped[line['revision_id']].append(line)
        previous=None; history=[]
        for revision in revisions:
            current=grouped[revision['revision_id']]
            revision=age(revision,now)
            revision['lines']=current; revision['captured_changes']=changes(previous,current)
            history.append(revision); previous=current
        return {'order':age(order,now),'history':list(reversed(history)),'evaluated_at':now,
                'history_coverage':'RETAINED_CAPTURES_ONLY','currency_state':'UNKNOWN',
                'quantity_unit_state':'CAPTURED_TEXT_ONLY','kit_state':'UNKNOWN'}

    def healthy(self):
        with self.connect() as conn:
            row=conn.execute('SELECT count(*) count,count(DISTINCT manifest_hash) manifests FROM reporting.orders').fetchone()
        return row['count']==20 and row['manifests']==1
