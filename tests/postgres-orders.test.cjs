const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {test} = require('node:test');
const {PGlite} = require('@electric-sql/pglite');

test('order SQL protects ownership, revision identities, history and runtime isolation', async (t) => {
  const db=new PGlite();
  try {
    await db.exec(`CREATE ROLE control_owner NOLOGIN; CREATE ROLE control_api LOGIN;
      DO $$ BEGIN EXECUTE format('GRANT CREATE ON DATABASE %I TO control_owner',current_database()); END $$;
      SET ROLE control_owner; CREATE SCHEMA control AUTHORIZATION control_owner;
      CREATE TABLE control.schema_migration(name text PRIMARY KEY,sha256 text NOT NULL);`);
    for (const name of ['0001_foundation.sql','0002_sales_order_sample.sql']) await db.exec(readFileSync(join(__dirname,'..','migrations',name),'utf8'));
    await db.exec(`INSERT INTO integration.order_source_epoch VALUES('synthetic','00000000-0000-0000-0000-000000000001','synthetic','company','{}',now());
      INSERT INTO crm.ordering_account(account_id,namespace_id,source_reference) VALUES('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000001','SYNTHETIC');
      INSERT INTO sales.sales_order VALUES('00000000-0000-0000-0000-000000000003','00000000-0000-0000-0000-000000000002',123),('00000000-0000-0000-0000-000000000004','00000000-0000-0000-0000-000000000002',124);
      INSERT INTO sales.order_line VALUES('00000000-0000-0000-0000-000000000005','00000000-0000-0000-0000-000000000003',5),('00000000-0000-0000-0000-000000000006','00000000-0000-0000-0000-000000000004',6);
      INSERT INTO integration.source_observation(observation_id,schema_version,source_system,source_dataset,source_observation_id,source_business_key,source_observed_at,reader_version,coverage_state,freshness_state,authority_state,payload_hash,payload)
      VALUES('00000000-0000-0000-0000-000000000007','source_observation_v1','synthetic','orders','1','1',now(),'test','PARTIAL','UNKNOWN','SHADOW',repeat('a',64),'{}');
      INSERT INTO sales.order_revision(revision_id,order_id,snapshot_observation_id,header_observation_id,source_snapshot_id,translator_version,source_observed_at,oldest_input_at,keyset_basis,reconciliation_status,line_count,interpretation_hash)
      VALUES('00000000-0000-0000-0000-000000000008','00000000-0000-0000-0000-000000000003','00000000-0000-0000-0000-000000000007','00000000-0000-0000-0000-000000000007',1,'sales_snapshot_v1',now(),now(),'SCULPTOR_LIVE_BOUNDED','MISMATCH',1,repeat('b',64));`);
    await t.test('line cannot cross order ownership even with valid individual foreign keys',async()=>{
      await assert.rejects(db.exec(`INSERT INTO sales.line_revision(revision_id,line_id,order_id,item_number,observation_id,numeric_policy) VALUES('00000000-0000-0000-0000-000000000008','00000000-0000-0000-0000-000000000006','00000000-0000-0000-0000-000000000003',1,'00000000-0000-0000-0000-000000000007','JSON_DECIMAL_TEXT_NO_ROUNDING')`),e=>e.code==='23503');
    });
    await t.test('identities and interpretations are append only',async()=>{
      for(const sql of ['UPDATE sales.order_line SET unique_number=7','DELETE FROM sales.order_revision','TRUNCATE sales.order_revision CASCADE','UPDATE crm.ordering_account SET source_reference=\'OTHER\'']) await assert.rejects(db.exec(sql),e=>e.code==='55000');
    });
    await t.test('physical event time cannot be invented from a capture',async()=>{
      await assert.rejects(db.exec(`INSERT INTO sales.order_event VALUES(gen_random_uuid(),'00000000-0000-0000-0000-000000000008','00000000-0000-0000-0000-000000000003','ORDER_SNAPSHOT_OBSERVED',now(),now(),now())`),e=>e.code==='23514');
    });
    await t.test('API can read typed views but cannot read raw evidence or write business state',async()=>{
      await db.exec('RESET ROLE; SET SESSION AUTHORIZATION control_api');
      await db.query('SELECT * FROM reporting.orders');
      for(const sql of ['SELECT * FROM integration.order_import','SELECT * FROM sales.order_revision','DELETE FROM reporting.order_current','SET ROLE control_owner']) await assert.rejects(db.exec(sql),e=>e.code==='42501');
    });
  } finally {await db.close();}
});
