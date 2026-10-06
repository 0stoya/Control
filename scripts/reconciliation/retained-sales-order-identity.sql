BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '25s';
SET LOCAL lock_timeout = '2s';
WITH snapshots AS MATERIALIZED (
 SELECT id,source_key,observed_at,line_count FROM sculptor_live.business_snapshot WHERE kind='SALES_ORDER'
), lines AS MATERIALIZED (
 SELECT s.id AS snapshot_id,s.source_key->>'cref' AS header_cref,s.source_key->>'ordno' AS header_ordno,b.line_no,
 o.dataset,o.source_instance,o.evidence_level,o.schema_sha256,o.source_key,
 o.payload->>'cref' AS cref,o.payload->>'ordno' AS ordno,o.payload->>'itemno' AS itemno,o.payload->>'uniqueno' AS uniqueno,
 o.payload->>'stcode' AS stcode,o.payload->>'kitind' AS kitind
 FROM snapshots s JOIN sculptor_live.business_snapshot_line b ON b.snapshot_id=s.id
 JOIN LATERAL (SELECT dataset,source_instance,evidence_level,schema_sha256,source_key,payload FROM sculptor_live.observation WHERE id=b.observation_id LIMIT 1) o ON true
), revision_alias AS (
 SELECT snapshot_id,cref,ordno,uniqueno,count(DISTINCT itemno) AS item_ids,count(DISTINCT stcode) AS skus
 FROM lines GROUP BY snapshot_id,cref,ordno,uniqueno
), historical_alias AS (
 SELECT cref,ordno,uniqueno,count(DISTINCT itemno) AS item_ids,count(DISTINCT stcode) AS skus
 FROM lines GROUP BY cref,ordno,uniqueno
), historical_native AS (
 SELECT cref,ordno,itemno,count(DISTINCT uniqueno) AS unique_ids,count(DISTINCT stcode) AS skus
 FROM lines GROUP BY cref,ordno,itemno
)
SELECT json_build_object(
 'check','retained_sales_order_identity_v1','observed_at',clock_timestamp(),
 'population','all retained SALES_ORDER snapshots and their exact line membership',
 'snapshot_count',(SELECT count(*) FROM snapshots),
 'oldest_snapshot',(SELECT min(observed_at) FROM snapshots),'newest_snapshot',(SELECT max(observed_at) FROM snapshots),
 'order_numbers_with_multiple_accounts',(SELECT count(*) FROM (SELECT source_key->>'ordno' FROM snapshots GROUP BY source_key->>'ordno' HAVING count(DISTINCT source_key->>'cref')>1) t),
 'line_counts',json_build_object(
   'total',(SELECT count(*) FROM lines),
   'source_or_identity_invalid',(SELECT count(*) FROM lines WHERE dataset IS DISTINCT FROM 'orditem' OR source_instance IS DISTINCT FROM 'sculptor:live' OR evidence_level IS DISTINCT FROM 'record_validated' OR cref IS DISTINCT FROM header_cref OR ordno IS DISTINCT FROM header_ordno OR itemno IS DISTINCT FROM line_no::text),
   'source_key_disagrees',(SELECT count(*) FROM lines WHERE source_key->>'ordno' IS DISTINCT FROM ordno OR source_key->>'itemno' IS DISTINCT FROM itemno),
   'missing_or_invalid_uniqueno',(SELECT count(*) FROM lines WHERE uniqueno IS NULL OR uniqueno !~ '^[1-9][0-9]{0,4}$' OR (CASE WHEN uniqueno ~ '^[1-9][0-9]{0,4}$' THEN uniqueno::int>65535 ELSE false END)),
   'itemno_equals_uniqueno',(SELECT count(*) FROM lines WHERE itemno=uniqueno),
   'itemno_differs_uniqueno',(SELECT count(*) FROM lines WHERE itemno<>uniqueno),
   'nonblank_kit_indicator',(SELECT count(*) FROM lines WHERE NULLIF(BTRIM(kitind),'') IS NOT NULL),
   'revision_alias_ambiguous',(SELECT count(*) FROM revision_alias WHERE item_ids>1),
   'historical_alias_changes_native_item',(SELECT count(*) FROM historical_alias WHERE item_ids>1),
   'historical_alias_changes_sku',(SELECT count(*) FROM historical_alias WHERE skus>1),
   'historical_native_changes_uniqueno',(SELECT count(*) FROM historical_native WHERE unique_ids>1),
   'historical_native_changes_sku',(SELECT count(*) FROM historical_native WHERE skus>1)
 ),
 'line_schema_hashes',(SELECT json_agg(schema_sha256) FROM (SELECT DISTINCT schema_sha256 FROM lines) t),
 'payloads_emitted',false
);
COMMIT;
