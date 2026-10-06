-- Applied as control_owner. Auth migration and business translators are separate slices.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA integration AUTHORIZATION control_owner;
CREATE SCHEMA audit AUTHORIZATION control_owner;
CREATE SCHEMA reporting AUTHORIZATION control_owner;

CREATE TABLE integration.source_observation (
    observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_version text NOT NULL CHECK (schema_version = 'source_observation_v1'),
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    source_dataset text NOT NULL CHECK (btrim(source_dataset) <> ''),
    source_observation_id text NOT NULL CHECK (btrim(source_observation_id) <> ''),
    source_business_key text NOT NULL CHECK (btrim(source_business_key) <> ''),
    source_observed_at timestamptz NOT NULL,
    occurred_at timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reader_version text NOT NULL CHECK (btrim(reader_version) <> ''),
    coverage_state text NOT NULL CHECK (coverage_state IN ('COMPLETE', 'PARTIAL', 'UNKNOWN')),
    freshness_state text NOT NULL CHECK (freshness_state IN ('FRESH', 'STALE', 'UNKNOWN')),
    authority_state text NOT NULL CHECK (authority_state IN ('AUTHORITATIVE', 'SHADOW', 'HISTORICAL', 'UNKNOWN')),
    payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    UNIQUE (source_system, source_dataset, source_observation_id)
);
CREATE INDEX source_observation_business_key_idx
    ON integration.source_observation (source_system, source_dataset, source_business_key, source_observed_at DESC);

CREATE FUNCTION integration.reject_observation_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'source observations are append-only' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER source_observation_no_update_delete
    BEFORE UPDATE OR DELETE ON integration.source_observation
    FOR EACH ROW EXECUTE FUNCTION integration.reject_observation_mutation();
CREATE TRIGGER source_observation_no_truncate
    BEFORE TRUNCATE ON integration.source_observation
    FOR EACH STATEMENT EXECUTE FUNCTION integration.reject_observation_mutation();

-- Runtime can inspect its migration ledger only. Raw evidence is not an API model.
REVOKE ALL ON SCHEMA integration, audit, reporting FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA integration FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA integration FROM PUBLIC;
REVOKE ALL ON SCHEMA control FROM PUBLIC;
GRANT USAGE ON SCHEMA control TO control_api;
GRANT SELECT ON control.schema_migration TO control_api;
ALTER DEFAULT PRIVILEGES FOR ROLE control_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

