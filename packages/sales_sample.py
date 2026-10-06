"""Deterministic, bounded retained-Sculptor translator. No source transport."""
from __future__ import annotations

from datetime import date, datetime
import json
import math
import re
from uuid import UUID, uuid5

from packages.contracts.observation import SourceObservationV1, payload_sha256
from packages.contracts.sales_order_identity import (SourceScope, SalesOrderKey,
    SalesLineIdentity, validate_sales_revision)

VERSION='sales_snapshot_v1'
ADAPTER='v1_sales_export_v1'
IDENTITY_NAMESPACE=UUID('f18c466e-238f-53c6-bbbe-4c4d62f2ae2d')
SCHEMAS={'orders':'0c42ba9faf3a7382fc42cbde8c15dd2118f7311af880b571cb392264acc9b8bb',
         'orditem':'e944a8323287af376ef0bb64b6ac931623355bcd5e505713ef4d03fcc8a17c37'}
EPOCH='fse-css-app-20261006-7667602069027910251-23268'

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def stable_id(kind,*parts):
    return uuid5(IDENTITY_NAMESPACE,canonical([kind,*parts]))

def timestamp(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None: raise ValueError('timezone required')
    return result

def text(value):
    if value is not None and (not isinstance(value,str) or len(value)>2000 or '\x00' in value):
        raise ValueError('captured text invalid')
    return value

def numeric_text(value):
    if value is None: return None
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('captured numeric representation unsupported')
    return canonical(value)

def source_date(value):
    if value is None: return None
    if not isinstance(value,dict) or set(value)!={'$date'}: raise ValueError('source date invalid')
    return date.fromisoformat(value['$date'])

def envelope(epoch,dataset,source_id,business_key,observed_at,payload):
    return SourceObservationV1(schema_version='source_observation_v1',
        source_system='sculptor:live',source_dataset=dataset,
        source_observation_id=f'v1:{epoch}:{source_id}',source_business_key=canonical(business_key),
        source_observed_at=timestamp(observed_at),reader_version=ADAPTER,
        coverage_state='PARTIAL',freshness_state='UNKNOWN',authority_state='SHADOW',
        payload_hash=payload_sha256(payload),payload=payload)

def translate(body):
    unsigned={k:v for k,v in body.items() if k!='manifest_hash'}
    if body.get('manifest_hash')!=payload_sha256(unsigned) or body.get('format')!='v1_sales_sample_v1':
        raise ValueError('manifest hash or format invalid')
    registry=body['registry']
    if (registry['epoch']!=EPOCH or registry['source_instance']!='sculptor:live'
        or registry['company_scope']!='css-profit-live-main'
        or registry['system_id']!='7667602069027910251' or registry['database_oid']!='23268'
        or registry['database']!='css_app' or registry['physical_prefix']!='/usr/livedata/data/'):
        raise ValueError('unaccepted source epoch or namespace')
    if not registry.get('reader_hashes') or any(not re.fullmatch('[0-9a-f]{64}',v) for v in registry['reader_hashes'].values()):
        raise ValueError('reader provenance missing')
    boundary=body['boundary']
    exported_at=timestamp(boundary['exported_at'])
    if boundary['continuation']!='INITIAL_SAVED_SAMPLE_ONLY' or not re.fullmatch('[0-9a-f]{40}',boundary['source_commit']):
        raise ValueError('export boundary invalid')
    selected=body['selected']; snapshots=body['snapshots']; members=body['members']; observations=body['observations']
    if not 1<=len(selected)<=20 or not 1<=len(snapshots)<=600 or len(members)>2000 or len(observations)>2600:
        raise ValueError('import budget exceeded')
    scope=SourceScope(registry['source_instance'],registry['company_scope'])
    namespace=stable_id('namespace',scope.source_instance,scope.company_scope)
    obs={}; envelopes={}
    for o in observations:
        if type(o['id']) is not int or o['id']<1 or o['id'] in obs: raise ValueError('duplicate observation')
        if (o['dataset'] not in SCHEMAS or o['source_instance']!=scope.source_instance
            or o['schema_sha256']!=SCHEMAS[o['dataset']] or o['evidence_level']!='record_validated'
            or o['payload_hash']!=payload_sha256(o['payload']) or o['source_key_hash']!=payload_sha256(o['source_key'])
            or not re.fullmatch('[0-9a-f]{64}',o['raw_record_sha256'] or '')):
            raise ValueError('observation source/schema/hash gate failed')
        if timestamp(o['observed_at'])>exported_at: raise ValueError('observation beyond export')
        obs[o['id']]=o
        e=envelope(EPOCH,o['dataset'],f'observation:{o["id"]}',o['source_key'],o['observed_at'],o)
        envelopes[stable_id('evidence',e.source_observation_id)]=e
    by_snapshot={}; member_ids=set()
    for member in members:
        pair=(member['snapshot_id'],member['line_no'])
        if pair in member_ids: raise ValueError('duplicate membership')
        member_ids.add(pair); by_snapshot.setdefault(member['snapshot_id'],[]).append(member)
    revisions=[]; used_obs=set(); snapshot_ids=set(); histories={}
    for snapshot in snapshots:
        sid=snapshot['id']
        if type(sid) is not int or sid<1 or sid in snapshot_ids or snapshot['kind']!='SALES_ORDER':
            raise ValueError('snapshot identity invalid')
        snapshot_ids.add(sid)
        h=obs[snapshot['header_observation_id']]; hp=h['payload']
        order=SalesOrderKey(scope,hp['cref'],hp['ordno'])
        if h['dataset']!='orders' or h['source_key']!={'cref':hp['cref'],'ordno':hp['ordno']} or snapshot['source_key']!=h['source_key']:
            raise ValueError('header ownership invalid')
        if snapshot['source_key_hash']!=payload_sha256(snapshot['source_key']): raise ValueError('snapshot key hash invalid')
        if timestamp(snapshot['observed_at'])>exported_at:
            raise ValueError('snapshot time invalid')
        account_id=stable_id('account',str(namespace),hp['cref'])
        order_id=stable_id('order',str(account_id),hp['ordno'])
        sm=sorted(by_snapshot.get(sid,[]),key=lambda m:m['line_no'])
        if len(sm)!=snapshot['line_count'] or len(sm)>500: raise ValueError('snapshot membership incomplete')
        input_times=[timestamp(snapshot['observed_at']),timestamp(h['observed_at'])]
        identities=[]; lines=[]; used_obs.add(h['id'])
        for m in sm:
            o=obs[m['observation_id']]; lp=o['payload']
            identity=SalesLineIdentity(SalesOrderKey(scope,lp['cref'],lp['ordno']),lp['itemno'],lp['uniqueno'])
            identities.append(identity)
            if o['dataset']!='orditem' or o['source_key']!={'ordno':lp['ordno'],'itemno':lp['itemno']} or m['line_no']!=lp['itemno']:
                raise ValueError('native line key invalid')
            input_times.append(timestamp(o['observed_at']))
            used_obs.add(o['id'])
            lines.append({'line_id':str(stable_id('line',str(order_id),lp['uniqueno'])),
                'unique_number':lp['uniqueno'],'item_number':lp['itemno'],
                'observation_id':str(stable_id('evidence',f'v1:{EPOCH}:observation:{o["id"]}')),
                'sku':text(lp.get('stcode')),'description':text(lp.get('desc',lp.get('descr'))),
                'captured_quantity':numeric_text(lp.get('quan')),'captured_price':numeric_text(lp.get('price')),
                'captured_unit_text':text(lp.get('iunitdesc')),'numeric_policy':'JSON_DECIMAL_TEXT_NO_ROUNDING'})
        validate_sales_revision(order,identities)
        if snapshot['keyset_basis'] not in {'SCULPTOR_LIVE_BOUNDED','OGL_MIRROR_CURRENT'}: raise ValueError('keyset invalid')
        if snapshot['reconciliation_status'] not in {'MATCH','MISMATCH','MIRROR_MISSING','MIRROR_DELETED','MIRROR_TOMBSTONE'}:
            raise ValueError('reconciliation state invalid')
        snapshot_payload={'snapshot':snapshot,'members':sm}
        e=envelope(EPOCH,'sales_order_snapshot',f'snapshot:{sid}',snapshot['source_key'],snapshot['observed_at'],snapshot_payload)
        evidence_id=stable_id('evidence',e.source_observation_id); envelopes[evidence_id]=e
        typed={'order_id':str(order_id),'account_id':str(account_id),'account_reference':hp['cref'],
            'order_number':hp['ordno'],'source_snapshot_id':sid,'translator_version':VERSION,
            'snapshot_observation_id':str(evidence_id),
            'header_observation_id':str(stable_id('evidence',f'v1:{EPOCH}:observation:{h["id"]}')),
            'source_observed_at':max(input_times).isoformat(),'oldest_input_at':min(input_times).isoformat(),
            'source_order_date':source_date(hp.get('orddate')).isoformat() if hp.get('orddate') is not None else None,
            'captured_rep':text(hp.get('rep')),'keyset_basis':snapshot['keyset_basis'],
            'reconciliation_status':snapshot['reconciliation_status'],'line_count':len(lines),'lines':lines}
        typed['interpretation_hash']=payload_sha256(typed)
        typed['revision_id']=str(stable_id('revision',str(evidence_id),VERSION))
        revisions.append(typed); histories.setdefault(order_id,[]).append(typed)
    if set(by_snapshot)-snapshot_ids or used_obs!=set(obs): raise ValueError('unowned input')
    for history in histories.values():
        if len(history)>30 or sum(r['line_count'] for r in history)>500: raise ValueError('per-order budget exceeded')
    pointer_ids=set(); pointers=[]
    for s in selected:
        matches=[r for r in revisions if r['source_snapshot_id']==s['snapshot_id']]
        if len(matches)!=1: raise ValueError('selected snapshot missing')
        r=matches[0]; oid=r['order_id']
        if oid in pointer_ids or s['source_key']!={'cref':r['account_reference'],'ordno':r['order_number']}:
            raise ValueError('selected order ambiguous')
        if s['line_count']!=r['line_count'] or s['keyset_basis']!=r['keyset_basis']: raise ValueError('selected projection mismatch')
        history=histories[UUID(oid)]
        if s['snapshot_id']!=max(h['source_snapshot_id'] for h in history): raise ValueError('selected boundary mismatch')
        pointer_ids.add(oid); pointers.append((oid,r['revision_id']))
    if set(map(str,histories))!=pointer_ids: raise ValueError('unselected order inputs')
    return {'namespace_id':namespace,'registry':registry,'envelopes':envelopes,'revisions':revisions,
            'pointers':pointers,'body':body,'manifest_hash':body['manifest_hash'],
            'counts':{'orders':len(selected),'revisions':len(revisions),'line_inputs':len(members),'observations':len(envelopes)}}
