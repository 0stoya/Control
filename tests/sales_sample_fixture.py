"""Synthetic source evidence only; no production identifiers or records."""
from packages.sales_sample import EPOCH,SCHEMAS
from packages.contracts.observation import payload_sha256

def sample():
    observations=[]; snapshots=[]; members=[]
    key={'cref':'SYNTHETIC_ACCOUNT','ordno':123456}
    for sid in (1,2,3):
        at=f'2026-10-06T10:0{sid}:00+00:00'; hid=sid*10
        header={**key,'orddate':{'$date':'2026-09-10'},'rep':'SYNTHETIC'}
        observations.append(observation(hid,'orders',key,header,at))
        snapshot={'id':sid,'kind':'SALES_ORDER','source_key':key,'source_key_hash':payload_sha256(key),
            'header_observation_id':hid,'observed_at':at,'line_count':2 if sid<3 else 1,
            'keyset_basis':'SCULPTOR_LIVE_BOUNDED','reconciliation_status':'MISMATCH','inserted_at':at}
        snapshots.append(snapshot)
        rows=[(5,1 if sid!=2 else 3,'TEST-A',None if sid==1 else 0,12.345678901)]
        if sid<3: rows.append((7 if sid==1 else 9,2,'TEST-B' if sid==1 else 'TEST-C',0,0))
        for offset,(unique,item,sku,quantity,price) in enumerate(rows,1):
            oid=hid+offset; lp={**key,'itemno':item,'uniqueno':unique,'stcode':sku,
                'desc':'Synthetic <script> harmless text','quan':quantity,'price':price,'iunitdesc':'Pairs'}
            observations.append(observation(oid,'orditem',{'ordno':key['ordno'],'itemno':item},lp,at.replace(':00+',':01+')))
            members.append({'snapshot_id':sid,'line_no':item,'observation_id':oid,'inserted_at':at})
    body={'format':'v1_sales_sample_v1','registry':{'epoch':EPOCH,'source_instance':'sculptor:live',
        'company_scope':'css-profit-live-main','system_id':'7667602069027910251','database_oid':'23268',
        'database':'css_app','physical_prefix':'/usr/livedata/data/','ssh_host':'FSE-root','reader_hashes':{'synthetic.py':'a'*64}},
        'boundary':{'exported_at':'2026-10-06T12:00:00+00:00','source_commit':'b'*40,
        'transaction_snapshot':'synthetic:1:','continuation':'INITIAL_SAVED_SAMPLE_ONLY','gaps':['Synthetic sample']},
        'selected':[{'snapshot_id':3,'source_key':key,'line_count':1,'keyset_basis':'SCULPTOR_LIVE_BOUNDED','renumbered':True}],
        'snapshots':snapshots,'members':members,'observations':observations}
    body['manifest_hash']=payload_sha256(body); return body

def observation(oid,dataset,key,payload,at):
    return {'id':oid,'dataset':dataset,'source_instance':'sculptor:live','observed_at':at,
        'schema_sha256':SCHEMAS[dataset],'source_key':key,'source_key_hash':payload_sha256(key),
        'payload':payload,'payload_hash':payload_sha256(payload),'raw_record_sha256':'c'*64,
        'mariadb_table':None,'evidence_level':'record_validated','inserted_at':at}

def rehash(body):
    for o in body['observations']:
        o['payload_hash']=payload_sha256(o['payload']); o['source_key_hash']=payload_sha256(o['source_key'])
    body.pop('manifest_hash',None); body['manifest_hash']=payload_sha256(body); return body
