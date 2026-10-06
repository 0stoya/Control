-- Run as PostgreSQL administrator ONLY in an isolated restored validation database.
-- All synthetic evidence is rolled back. Never use this script as an intake source.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF current_database() NOT LIKE 'control_v2_restore_%' THEN
        RAISE EXCEPTION 'native acceptance requires an isolated restore database';
    END IF;
END;
$$;
SET LOCAL ROLE control_owner;
INSERT INTO integration.source_observation (
    schema_version, source_system, source_dataset, source_observation_id,
    source_business_key, source_observed_at, reader_version, coverage_state,
    freshness_state, authority_state, payload_hash, payload
) VALUES (
    'source_observation_v1', 'synthetic', 'foundation-acceptance', 'validation-1',
    'synthetic-order-1', now(), 'test-v1', 'PARTIAL', 'UNKNOWN', 'SHADOW',
    repeat('a', 64), '{"quantity": null}'::jsonb
);
DO $$
BEGIN
    BEGIN
        INSERT INTO integration.source_observation (
            schema_version, source_system, source_dataset, source_observation_id,
            source_business_key, source_observed_at, reader_version, coverage_state,
            freshness_state, authority_state, payload_hash, payload
        ) SELECT schema_version, source_system, source_dataset, source_observation_id,
            source_business_key, source_observed_at, reader_version, coverage_state,
            freshness_state, authority_state, payload_hash, payload
          FROM integration.source_observation WHERE source_dataset = 'foundation-acceptance';
        RAISE EXCEPTION 'duplicate observation was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        UPDATE integration.source_observation SET coverage_state = 'COMPLETE'
        WHERE source_dataset = 'foundation-acceptance';
        RAISE EXCEPTION 'observation update was accepted';
    EXCEPTION WHEN SQLSTATE '55000' THEN NULL;
    END;
    BEGIN
        DELETE FROM integration.source_observation WHERE source_dataset = 'foundation-acceptance';
        RAISE EXCEPTION 'observation deletion was accepted';
    EXCEPTION WHEN SQLSTATE '55000' THEN NULL;
    END;
    BEGIN
        TRUNCATE integration.source_observation;
        RAISE EXCEPTION 'observation truncate was accepted';
    EXCEPTION WHEN SQLSTATE '55000' THEN NULL;
    END;
    IF NOT EXISTS (
        SELECT FROM integration.source_observation
        WHERE source_dataset = 'foundation-acceptance'
          AND coverage_state = 'PARTIAL' AND occurred_at IS NULL
          AND payload->'quantity' = 'null'::jsonb
    ) THEN
        RAISE EXCEPTION 'unknown/partial evidence was not retained';
    END IF;
END;
$$;
SET LOCAL ROLE control_api;
SELECT count(*) AS readable_migration_rows FROM control.schema_migration;
DO $$
BEGIN
    BEGIN
        PERFORM payload FROM integration.source_observation;
        RAISE EXCEPTION 'runtime can read raw evidence';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        CREATE TABLE control.illegal_runtime_table (id integer);
        RAISE EXCEPTION 'runtime can create schema objects';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF pg_has_role('control_api', 'control_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'runtime can assume migration owner';
    END IF;
END;
$$;
ROLLBACK;
\echo NATIVE_FOUNDATION_BOUNDARIES_PASSED

