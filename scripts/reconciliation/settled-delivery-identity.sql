BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='20s';
SET LOCAL lock_timeout='2s';
WITH settled AS MATERIALIZED (
 SELECT * FROM fulfilment.current_despatch_line_fact
), current_lines AS MATERIALIZED (
 SELECT h.party_ref AS cref,h.order_no,
   CASE WHEN o.payload->>'itemno' ~ '^[0-9]{1,5}$' THEN (o.payload->>'itemno')::int END AS itemno,
   CASE WHEN o.payload->>'uniqueno' ~ '^[0-9]{1,5}$' THEN (o.payload->>'uniqueno')::int END AS uniqueno,
   o.payload->>'stcode' AS stcode
 FROM crm_read.current_business_order_header_projection h
 JOIN sculptor_live.business_snapshot_line b ON b.snapshot_id=h.sculptor_snapshot_id
 JOIN LATERAL (SELECT payload FROM sculptor_live.observation WHERE id=b.observation_id LIMIT 1) o ON true
 WHERE h.kind='SALES_ORDER' AND h.selected_source='SCULPTOR_LIVE'
), semantic_groups AS (
 SELECT source_delivery_no,source_delivery_suffix,source_print_indicator,source_order_no,source_delivery_item_no,source_kit_indicator,source_order_line_no,
        count(*) AS rows,count(DISTINCT source_stock_code) AS sku_count
 FROM settled GROUP BY 1,2,3,4,5,6,7
), native_groups AS (
 SELECT source_delivery_no,source_delivery_suffix,source_print_indicator,source_order_no,source_delivery_item_no,source_kit_indicator,
        count(DISTINCT source_order_line_no) AS unique_ids
 FROM settled GROUP BY 1,2,3,4,5,6
), resolved AS (
 SELECT s.*,l.itemno AS current_native_item,l.stcode AS current_sku,
   EXISTS(SELECT 1 FROM current_lines c WHERE c.cref=s.source_customer_ref AND c.order_no=s.source_order_no) AS current_order_present,
   EXISTS(SELECT 1 FROM current_lines c WHERE c.cref=s.source_customer_ref AND c.order_no=s.source_order_no AND c.itemno=s.source_order_line_no AND c.uniqueno<>s.source_order_line_no) AS naive_unique_to_item_hits_another_line
 FROM settled s LEFT JOIN current_lines l ON l.cref=s.source_customer_ref AND l.order_no=s.source_order_no AND l.uniqueno=s.source_order_line_no
)
SELECT json_build_object(
 'check','settled_delivery_identity_v1','observed_at',clock_timestamp(),
 'population','current effective settled q31 view, including accepted rolling-day publication',
 'rows',(SELECT count(*) FROM settled),
 'oldest_business_date',(SELECT min(despatch_date) FROM settled),
 'newest_business_date',(SELECT max(despatch_date) FROM settled),
 'missing_semantic_key_fields',(SELECT count(*) FROM settled WHERE source_delivery_no IS NULL OR source_delivery_suffix IS NULL OR source_print_indicator IS NULL OR source_order_no IS NULL OR source_delivery_item_no IS NULL OR source_kit_indicator IS NULL OR source_order_line_no IS NULL),
 'semantic_identity_groups',(SELECT count(*) FROM semantic_groups),
 'duplicate_semantic_groups',(SELECT count(*) FROM semantic_groups WHERE rows>1),
 'semantic_groups_multiple_skus',(SELECT count(*) FROM semantic_groups WHERE sku_count>1),
 'native_groups_multiple_uniqueno',(SELECT count(*) FROM native_groups WHERE unique_ids>1),
 'itemno_equals_uniqueno',(SELECT count(*) FROM settled WHERE source_delivery_item_no=source_order_line_no),
 'itemno_differs_uniqueno',(SELECT count(*) FROM settled WHERE source_delivery_item_no<>source_order_line_no),
 'zero_uniqueno',(SELECT count(*) FROM settled WHERE source_order_line_no=0),
 'nonblank_kit_indicator',(SELECT count(*) FROM settled WHERE NULLIF(BTRIM(source_kit_indicator),'') IS NOT NULL),
 'itemno_at_least_1000',(SELECT count(*) FROM settled WHERE source_delivery_item_no>=1000),
 'current_snapshot_resolution',json_build_object(
   'exact_logical_matches',(SELECT count(*) FROM resolved WHERE current_native_item IS NOT NULL),
   'matched_sku_disagrees',(SELECT count(*) FROM resolved WHERE current_native_item IS NOT NULL AND current_sku IS DISTINCT FROM source_stock_code),
   'matched_native_position_changed',(SELECT count(*) FROM resolved WHERE current_native_item IS NOT NULL AND current_native_item<>source_delivery_item_no),
   'unresolved_with_current_order',(SELECT count(*) FROM resolved WHERE current_order_present AND current_native_item IS NULL),
   'no_current_captured_order',(SELECT count(*) FROM resolved WHERE NOT current_order_present),
   'naive_unique_to_item_hits_another_line',(SELECT count(*) FROM resolved WHERE naive_unique_to_item_hits_another_line)
 ),
 'payloads_emitted',false
);
COMMIT;
