BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '20s';
SET LOCAL lock_timeout = '2s';
WITH headers AS MATERIALIZED (
 SELECT * FROM crm_read.current_business_order_header_projection WHERE kind='SALES_ORDER'
), selected AS MATERIALIZED (
 SELECT h.party_ref,h.order_no,h.selected_source,h.line_count AS projected_line_count,h.keyset_basis AS projected_keyset_basis,h.observed_at AS projected_observed_at,
        s.id,s.kind,s.line_count,s.source_key,s.keyset_basis,s.observed_at,s.header_observation_id
 FROM headers h LEFT JOIN sculptor_live.business_snapshot s ON s.id=h.sculptor_snapshot_id
), header_evidence AS MATERIALIZED (
 SELECT s.*,o.dataset,o.source_instance,o.evidence_level,o.payload,o.schema_sha256
 FROM selected s LEFT JOIN LATERAL (
   SELECT dataset,source_instance,evidence_level,payload,schema_sha256 FROM sculptor_live.observation WHERE id=s.header_observation_id LIMIT 1
 ) o ON true
), lines AS MATERIALIZED (
 SELECT h.party_ref,h.order_no AS owner_order_no,h.id AS snapshot_id,b.line_no,o.dataset,o.source_instance,o.evidence_level,o.source_key,o.payload,
        CASE WHEN o.payload->>'ordno' ~ '^[0-9]{1,10}$' THEN (o.payload->>'ordno')::bigint END AS ordno,
        CASE WHEN o.payload->>'itemno' ~ '^[0-9]{1,5}$' THEN (o.payload->>'itemno')::integer END AS itemno,
        CASE WHEN o.payload->>'uniqueno' ~ '^[0-9]{1,5}$' THEN (o.payload->>'uniqueno')::integer END AS uniqueno,
        o.payload->>'cref' AS cref,o.payload->>'stcode' AS stcode,o.payload->>'kitind' AS kitind
 FROM selected h JOIN sculptor_live.business_snapshot_line b ON b.snapshot_id=h.id
 JOIN LATERAL (SELECT dataset,source_instance,evidence_level,source_key,payload FROM sculptor_live.observation WHERE id=b.observation_id LIMIT 1) o ON true
), line_counts AS (
 SELECT snapshot_id,count(*) AS n FROM lines GROUP BY snapshot_id
), alias_groups AS (
 SELECT party_ref,owner_order_no,uniqueno,count(*) AS n,count(DISTINCT itemno) AS item_count,count(DISTINCT stcode) AS sku_count
 FROM lines WHERE uniqueno IS NOT NULL GROUP BY party_ref,owner_order_no,uniqueno
)
SELECT json_build_object(
 'check','current_sales_order_identity_v1','observed_at',clock_timestamp(),
 'population','all current SALES_ORDER header projection rows and their selected immutable snapshots',
 'header_counts',json_build_object(
   'total',(SELECT count(*) FROM headers),
   'selected_sources',(SELECT json_object_agg(selected_source,n) FROM (SELECT selected_source,count(*) n FROM headers GROUP BY selected_source) t),
   'missing_snapshot',(SELECT count(*) FROM selected WHERE id IS NULL),
   'wrong_snapshot_kind',(SELECT count(*) FROM selected WHERE kind IS DISTINCT FROM 'SALES_ORDER' AND id IS NOT NULL),
   'header_evidence_invalid',(SELECT count(*) FROM header_evidence WHERE id IS NOT NULL AND (dataset IS DISTINCT FROM 'orders' OR source_instance IS DISTINCT FROM 'sculptor:live' OR evidence_level IS DISTINCT FROM 'record_validated' OR payload->>'cref' IS DISTINCT FROM party_ref OR payload->>'ordno' IS DISTINCT FROM order_no::text)),
   'snapshot_source_key_disagrees',(SELECT count(*) FROM selected WHERE id IS NOT NULL AND (source_key->>'cref' IS DISTINCT FROM party_ref OR source_key->>'ordno' IS DISTINCT FROM order_no::text)),
   'snapshot_line_count_disagrees',(SELECT count(*) FROM selected s LEFT JOIN line_counts c ON c.snapshot_id=s.id WHERE s.id IS NOT NULL AND COALESCE(c.n,0)<>s.line_count),
   'projected_line_count_disagrees',(SELECT count(*) FROM selected WHERE id IS NOT NULL AND projected_line_count IS DISTINCT FROM line_count),
   'keyset_basis_disagrees',(SELECT count(*) FROM selected WHERE id IS NOT NULL AND projected_keyset_basis IS DISTINCT FROM keyset_basis),
   'order_numbers_with_multiple_accounts',(SELECT count(*) FROM (SELECT order_no FROM headers GROUP BY order_no HAVING count(DISTINCT party_ref)>1) t),
   'oldest_source_observed_at',(SELECT min(observed_at) FROM selected),
   'newest_source_observed_at',(SELECT max(observed_at) FROM selected)
 ),
 'line_counts',json_build_object(
   'total',(SELECT count(*) FROM lines),
   'source_or_identity_invalid',(SELECT count(*) FROM lines WHERE dataset IS DISTINCT FROM 'orditem' OR source_instance IS DISTINCT FROM 'sculptor:live' OR evidence_level IS DISTINCT FROM 'record_validated' OR ordno IS DISTINCT FROM owner_order_no OR itemno IS DISTINCT FROM line_no OR cref IS DISTINCT FROM party_ref),
   'source_key_disagrees',(SELECT count(*) FROM lines WHERE source_key->>'ordno' IS DISTINCT FROM ordno::text OR source_key->>'itemno' IS DISTINCT FROM itemno::text),
   'missing_or_invalid_uniqueno',(SELECT count(*) FROM lines WHERE uniqueno IS NULL OR uniqueno NOT BETWEEN 1 AND 65535),
   'itemno_equals_uniqueno',(SELECT count(*) FROM lines WHERE itemno=uniqueno),
   'itemno_differs_uniqueno',(SELECT count(*) FROM lines WHERE itemno<>uniqueno),
   'itemno_under_1000',(SELECT count(*) FROM lines WHERE itemno<1000),
   'itemno_at_least_1000',(SELECT count(*) FROM lines WHERE itemno>=1000),
   'nonblank_kit_indicator',(SELECT count(*) FROM lines WHERE NULLIF(BTRIM(kitind),'') IS NOT NULL),
   'unique_alias_groups',(SELECT count(*) FROM alias_groups),
   'ambiguous_unique_alias_groups',(SELECT count(*) FROM alias_groups WHERE item_count>1),
   'ambiguous_unique_alias_skus',(SELECT count(*) FROM alias_groups WHERE sku_count>1)
 ),
 'schema_hashes',(SELECT json_agg(schema_sha256) FROM (SELECT DISTINCT schema_sha256 FROM header_evidence WHERE schema_sha256 IS NOT NULL) t),
 'payloads_emitted',false
);
COMMIT;
