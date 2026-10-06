BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='20s';
SET LOCAL lock_timeout='2s';
WITH history AS MATERIALIZED (
 SELECT s.source_key->>'cref' AS cref,s.source_key->>'ordno' AS ordno,o.payload->>'uniqueno' AS uniqueno,
        count(DISTINCT o.payload->>'stcode') AS sku_count,min(o.payload->>'stcode') AS stcode,
        array_agg(DISTINCT o.payload->>'itemno') AS native_items
 FROM sculptor_live.business_snapshot s JOIN sculptor_live.business_snapshot_line b ON b.snapshot_id=s.id
 JOIN LATERAL (SELECT payload FROM sculptor_live.observation WHERE id=b.observation_id LIMIT 1) o ON true
 WHERE s.kind='SALES_ORDER'
 GROUP BY s.source_key->>'cref',s.source_key->>'ordno',o.payload->>'uniqueno'
), settled AS MATERIALIZED (
 SELECT * FROM fulfilment.current_despatch_line_fact
), reconciled AS (
 SELECT s.*,h.cref AS captured_cref,h.sku_count,h.stcode,h.native_items
 FROM settled s LEFT JOIN history h ON h.cref=s.source_customer_ref AND h.ordno=s.source_order_no::text AND h.uniqueno=s.source_order_line_no::text
)
SELECT json_build_object(
 'check','settled_to_retained_logical_line_v1','observed_at',clock_timestamp(),
 'population','current effective settled q31 view versus all retained SALES_ORDER snapshot line identities',
 'settled_rows',(SELECT count(*) FROM settled),
 'historical_logical_identities',(SELECT count(*) FROM history),
 'matched',(SELECT count(*) FROM reconciled WHERE captured_cref IS NOT NULL),
 'unresolved',(SELECT count(*) FROM reconciled WHERE captured_cref IS NULL),
 'matched_ambiguous_sku',(SELECT count(*) FROM reconciled WHERE captured_cref IS NOT NULL AND sku_count>1),
 'matched_sku_disagrees',(SELECT count(*) FROM reconciled WHERE captured_cref IS NOT NULL AND stcode IS DISTINCT FROM source_stock_code),
 'delivery_item_not_in_captured_positions',(SELECT count(*) FROM reconciled WHERE captured_cref IS NOT NULL AND NOT (source_delivery_item_no::text=ANY(native_items))),
 'matched_to_line_with_renumber_history',(SELECT count(*) FROM reconciled WHERE cardinality(native_items)>1),
 'payloads_emitted',false
);
COMMIT;
