BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '20s';
SET LOCAL lock_timeout = '2s';
WITH captures AS MATERIALIZED (
 SELECT * FROM sculptor_live.delivery_note_capture
), rows AS MATERIALIZED (
 SELECT l.*,h.customer_ref AS header_customer_ref
 FROM sculptor_live.delivery_note_line_observation l
 JOIN sculptor_live.delivery_note_header_observation h
 USING(capture_id,print_indicator,delivery_no,delivery_suffix,order_no)
), native_history AS (
 SELECT print_indicator,delivery_no,delivery_suffix,order_no,item_no,kit_indicator,
        count(DISTINCT unique_no) AS unique_ids,count(DISTINCT stock_code) AS sku_count
 FROM rows GROUP BY print_indicator,delivery_no,delivery_suffix,order_no,item_no,kit_indicator
), order_unique_groups AS (
 SELECT order_no,unique_no,count(DISTINCT item_no) AS item_ids,count(DISTINCT stock_code) AS sku_count
 FROM rows GROUP BY order_no,unique_no
), latest_nonempty AS (
 SELECT capture_id FROM captures WHERE line_count>0 ORDER BY observed_at DESC,capture_id DESC LIMIT 1
)
SELECT json_build_object(
 'check','retained_delivery_note_identity_v1','observed_at',clock_timestamp(),
 'population','all retained direct delivery-note observations and capture metadata',
 'capture_counts',json_build_object(
   'total',(SELECT count(*) FROM captures),'nonempty',(SELECT count(*) FROM captures WHERE line_count>0),
   'unsafe_counters',(SELECT count(*) FROM captures WHERE NOT end_of_index_reached OR full_file_enumeration_operations<>0 OR sculptor_locking_operations<>0 OR sculptor_write_operations<>0),
   'oldest_observed_at',(SELECT min(observed_at) FROM captures),'newest_observed_at',(SELECT max(observed_at) FROM captures),
   'latest_nonempty_observed_at',(SELECT observed_at FROM captures WHERE capture_id=(SELECT capture_id FROM latest_nonempty)),
   'schema_pairs',(SELECT json_agg(json_build_object('header',header_schema_sha256,'line',line_schema_sha256,'captures',n)) FROM (SELECT header_schema_sha256,line_schema_sha256,count(*) n FROM captures GROUP BY 1,2) t)
 ),
 'line_counts',json_build_object(
   'total',(SELECT count(*) FROM rows),
   'native_identity_groups',(SELECT count(*) FROM native_history),
   'native_identity_changes_uniqueno',(SELECT count(*) FROM native_history WHERE unique_ids>1),
   'native_identity_changes_sku',(SELECT count(*) FROM native_history WHERE sku_count>1),
   'header_customer_disagrees',(SELECT count(*) FROM rows WHERE customer_ref IS DISTINCT FROM header_customer_ref),
   'itemno_equals_uniqueno',(SELECT count(*) FROM rows WHERE item_no=unique_no),
   'itemno_differs_uniqueno',(SELECT count(*) FROM rows WHERE item_no<>unique_no),
   'zero_uniqueno',(SELECT count(*) FROM rows WHERE unique_no=0),
   'nonblank_kit_indicator',(SELECT count(*) FROM rows WHERE NULLIF(BTRIM(kit_indicator),'') IS NOT NULL),
   'itemno_at_least_1000',(SELECT count(*) FROM rows WHERE item_no>=1000),
   'order_unique_groups',(SELECT count(*) FROM order_unique_groups),
   'order_unique_multiple_native_items',(SELECT count(*) FROM order_unique_groups WHERE item_ids>1),
   'order_unique_multiple_skus',(SELECT count(*) FROM order_unique_groups WHERE sku_count>1),
   'latest_nonempty_rows',(SELECT count(*) FROM rows WHERE capture_id=(SELECT capture_id FROM latest_nonempty))
 ),
 'payloads_emitted',false
);
COMMIT;
