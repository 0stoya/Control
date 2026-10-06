BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='20s';
SET LOCAL lock_timeout='2s';
WITH sales_lines AS MATERIALIZED (
 SELECT o.payload FROM sculptor_live.business_snapshot s JOIN sculptor_live.business_snapshot_line b ON b.snapshot_id=s.id
 JOIN LATERAL (SELECT payload FROM sculptor_live.observation WHERE id=b.observation_id LIMIT 1) o ON true
 WHERE s.kind='SALES_ORDER'
), settled AS MATERIALIZED (SELECT * FROM fulfilment.current_despatch_line_fact),
 positional_ids AS (SELECT sync_run_id,row_no,count(*) n FROM settled GROUP BY sync_run_id,row_no)
SELECT json_build_object(
 'check','missing_fields_and_projection_row_identity_v1','observed_at',clock_timestamp(),
 'retained_sales_lines',(SELECT count(*) FROM sales_lines),
 'kitind_field_absent',(SELECT count(*) FROM sales_lines WHERE NOT (payload ? 'kitind')),
 'kitind_field_null',(SELECT count(*) FROM sales_lines WHERE payload ? 'kitind' AND payload->'kitind'='null'::jsonb),
 'settled_rows',(SELECT count(*) FROM settled),
 'duplicate_sync_row_id_groups',(SELECT count(*) FROM positional_ids WHERE n>1),
 'rows_in_duplicate_sync_row_id_groups',(SELECT COALESCE(sum(n),0) FROM positional_ids WHERE n>1),
 'max_rows_per_sync_row_id',(SELECT max(n) FROM positional_ids),
 'payloads_emitted',false
);
COMMIT;
