-- Additive read-only shadow. Source capture remains owned by V1.
CREATE SCHEMA crm AUTHORIZATION control_owner;
CREATE SCHEMA sales AUTHORIZATION control_owner;
REVOKE ALL ON SCHEMA crm, sales FROM PUBLIC;

CREATE TABLE integration.order_source_epoch (
    epoch text PRIMARY KEY,
    namespace_id uuid NOT NULL UNIQUE,
    source_instance text NOT NULL,
    company_scope text NOT NULL,
    registry jsonb NOT NULL CHECK (jsonb_typeof(registry)='object'),
    registered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (source_instance, company_scope), UNIQUE (epoch, namespace_id)
);
CREATE TABLE integration.order_import (
    manifest_hash text PRIMARY KEY CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    epoch text NOT NULL UNIQUE REFERENCES integration.order_source_epoch,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='object'),
    order_count integer NOT NULL CHECK (order_count BETWEEN 1 AND 20),
    revision_count integer NOT NULL CHECK (revision_count BETWEEN 1 AND 600),
    line_count integer NOT NULL CHECK (line_count BETWEEN 0 AND 2000),
    observation_count integer NOT NULL CHECK (observation_count > 0),
    translator_version text NOT NULL CHECK (translator_version='sales_snapshot_v1'),
    committed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE crm.ordering_account (
    account_id uuid PRIMARY KEY,
    namespace_id uuid NOT NULL REFERENCES integration.order_source_epoch(namespace_id),
    source_reference text NOT NULL CHECK (btrim(source_reference) <> ''),
    UNIQUE(namespace_id, source_reference), UNIQUE(account_id, namespace_id)
);
CREATE TABLE sales.sales_order (
    order_id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES crm.ordering_account,
    order_number bigint NOT NULL CHECK (order_number BETWEEN 1 AND 4294967295),
    UNIQUE(account_id, order_number)
);
CREATE TABLE sales.order_line (
    line_id uuid PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES sales.sales_order,
    unique_number integer NOT NULL CHECK (unique_number BETWEEN 1 AND 65535),
    UNIQUE(order_id, unique_number), UNIQUE(line_id, order_id)
);
CREATE TABLE sales.order_revision (
    revision_id uuid PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES sales.sales_order,
    snapshot_observation_id uuid NOT NULL REFERENCES integration.source_observation,
    header_observation_id uuid NOT NULL REFERENCES integration.source_observation,
    source_snapshot_id bigint NOT NULL CHECK (source_snapshot_id > 0),
    translator_version text NOT NULL CHECK (translator_version='sales_snapshot_v1'),
    source_observed_at timestamptz NOT NULL,
    oldest_input_at timestamptz NOT NULL CHECK(oldest_input_at<=source_observed_at),
    source_order_date date,
    captured_rep text,
    keyset_basis text NOT NULL CHECK (keyset_basis IN ('SCULPTOR_LIVE_BOUNDED','OGL_MIRROR_CURRENT')),
    reconciliation_status text NOT NULL CHECK (reconciliation_status IN ('MATCH','MISMATCH','MIRROR_MISSING','MIRROR_DELETED','MIRROR_TOMBSTONE')),
    line_count integer NOT NULL CHECK (line_count BETWEEN 0 AND 500),
    interpretation_hash text NOT NULL CHECK (interpretation_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(snapshot_observation_id, translator_version), UNIQUE(revision_id, order_id)
);
CREATE TABLE sales.line_revision (
    revision_id uuid NOT NULL,
    line_id uuid NOT NULL,
    order_id uuid NOT NULL,
    item_number integer NOT NULL CHECK (item_number BETWEEN 1 AND 65535),
    observation_id uuid NOT NULL REFERENCES integration.source_observation,
    sku text,
    description text,
    captured_quantity text,
    captured_price text,
    captured_unit_text text,
    numeric_policy text NOT NULL CHECK (numeric_policy='JSON_DECIMAL_TEXT_NO_ROUNDING'),
    PRIMARY KEY(revision_id,line_id), UNIQUE(revision_id,item_number),
    FOREIGN KEY(revision_id,order_id) REFERENCES sales.order_revision(revision_id,order_id),
    FOREIGN KEY(line_id,order_id) REFERENCES sales.order_line(line_id,order_id)
);
CREATE TABLE sales.order_event (
    event_id uuid PRIMARY KEY,
    revision_id uuid NOT NULL UNIQUE,
    order_id uuid NOT NULL,
    event_type text NOT NULL CHECK (event_type='ORDER_SNAPSHOT_OBSERVED'),
    occurred_at timestamptz CHECK (occurred_at IS NULL),
    source_observed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(revision_id,order_id) REFERENCES sales.order_revision(revision_id,order_id)
);
CREATE TABLE reporting.order_current (
    order_id uuid PRIMARY KEY,
    revision_id uuid NOT NULL,
    manifest_hash text NOT NULL REFERENCES integration.order_import,
    calculated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(revision_id,order_id) REFERENCES sales.order_revision(revision_id,order_id)
);
CREATE TABLE audit.order_import_failure (
    failure_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    manifest_hash text NOT NULL CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    reason text NOT NULL CHECK (reason IN ('INPUT_CONFLICT','IMPORT_FAILED')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

DO $$ DECLARE name text; BEGIN
    FOREACH name IN ARRAY ARRAY['integration.order_source_epoch','integration.order_import',
        'crm.ordering_account','sales.sales_order','sales.order_line','sales.order_revision',
        'sales.line_revision','sales.order_event','audit.order_import_failure'] LOOP
        EXECUTE format('CREATE TRIGGER append_only_rows BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION integration.reject_observation_mutation()',name);
        EXECUTE format('CREATE TRIGGER append_only_table BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION integration.reject_observation_mutation()',name);
    END LOOP;
END $$;

CREATE VIEW reporting.orders AS
SELECT o.order_id, a.source_reference AS account_reference, o.order_number,
       r.revision_id, r.source_observed_at, r.oldest_input_at, r.source_order_date, r.line_count,
       r.keyset_basis, r.reconciliation_status, r.translator_version,
       c.calculated_at, c.manifest_hash, i.committed_at AS imported_at,
       'UNKNOWN'::text AS commercial_state, 'UNKNOWN'::text AS fulfilment_state,
       'UNKNOWN'::text AS invoice_state, 'UNKNOWN'::text AS payment_state,
       'UNKNOWN'::text AS promise_state, 'PRESENT_IN_CAPTURE'::text AS source_state,
       'PARTIAL'::text AS coverage_state, 'UNKNOWN'::text AS freshness_state,
       'SHADOW'::text AS authority_state
FROM reporting.order_current c JOIN sales.sales_order o USING(order_id)
JOIN crm.ordering_account a USING(account_id)
JOIN sales.order_revision r ON r.revision_id=c.revision_id
JOIN integration.order_import i USING(manifest_hash);
CREATE VIEW reporting.order_history AS
SELECT r.order_id, r.revision_id, r.source_snapshot_id, r.source_observed_at, r.oldest_input_at,
       r.source_order_date, r.line_count, r.keyset_basis, r.reconciliation_status,
       r.translator_version, r.interpretation_hash, r.recorded_at,
       e.event_type, e.occurred_at, (r.revision_id=c.revision_id) AS selected
FROM sales.order_revision r JOIN reporting.order_current c USING(order_id)
JOIN sales.order_event e ON e.revision_id=r.revision_id AND e.order_id=r.order_id;
CREATE VIEW reporting.order_revision_lines AS
SELECT l.order_id, l.revision_id, l.line_id, k.unique_number, l.item_number,
       l.sku, l.description, l.captured_quantity, l.captured_price,
       l.captured_unit_text, l.numeric_policy
FROM sales.line_revision l JOIN sales.order_line k USING(line_id,order_id)
JOIN reporting.order_current c USING(order_id);
GRANT USAGE ON SCHEMA reporting TO control_api;
GRANT SELECT ON reporting.orders, reporting.order_history, reporting.order_revision_lines TO control_api;
