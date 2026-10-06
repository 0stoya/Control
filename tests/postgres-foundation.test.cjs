const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { PGlite } = require('@electric-sql/pglite');

// Run real PostgreSQL SQL/constraints in WASM. OS peer auth/systemd require host acceptance.
test('foundation enforces immutable evidence, replay identity and runtime isolation', async (t) => {
  const db = new PGlite();
  try {
    await db.exec(`
      CREATE ROLE control_owner NOLOGIN;
      CREATE ROLE control_api LOGIN;
      DO $$ BEGIN EXECUTE format('GRANT CREATE ON DATABASE %I TO control_owner', current_database()); END $$;
      SET ROLE control_owner;
      CREATE SCHEMA control AUTHORIZATION control_owner;
      CREATE TABLE control.schema_migration (name text PRIMARY KEY, sha256 text NOT NULL);
    `);
    await db.exec(readFileSync(join(__dirname, '..', 'migrations', '0001_foundation.sql'), 'utf8'));
    const insert = `INSERT INTO integration.source_observation
      (schema_version, source_system, source_dataset, source_observation_id,
       source_business_key, source_observed_at, reader_version, coverage_state,
       freshness_state, authority_state, payload_hash, payload)
      VALUES ('source_observation_v1', 'synthetic', 'test', $1, 'order-1',
       '2026-10-06T10:00:00Z', 'test-v1', $2, 'UNKNOWN', 'SHADOW', $3, $4)`;
    const params = ['snapshot-1:row-1', 'UNKNOWN', 'a'.repeat(64), JSON.stringify({ quantity: null })];
    await db.query(insert, params);

    await t.test('duplicate source identity is database-enforced', async () => {
      await assert.rejects(db.query(insert, params), (error) => error.code === '23505');
    });
    await t.test('partial and null evidence remain explicit', async () => {
      await db.query(insert, ['snapshot-1:row-2', 'PARTIAL', 'b'.repeat(64), JSON.stringify({ quantity: null })]);
      const result = await db.query(`SELECT coverage_state, payload->'quantity' AS quantity,
        occurred_at FROM integration.source_observation WHERE source_observation_id='snapshot-1:row-2'`);
      assert.deepEqual(result.rows, [{ coverage_state: 'PARTIAL', quantity: null, occurred_at: null }]);
    });
    await t.test('uncontracted coverage fails', async () => {
      await assert.rejects(db.query(insert, ['snapshot-2:row-1', 'ASSUMED', 'a'.repeat(64), '{}']),
        (error) => error.code === '23514');
    });
    await t.test('evidence cannot be edited, deleted or truncated even by its owner', async () => {
      for (const sql of [
        `UPDATE integration.source_observation SET coverage_state='COMPLETE'`,
        `DELETE FROM integration.source_observation`,
        `TRUNCATE integration.source_observation`,
      ]) {
        await assert.rejects(db.exec(sql), (error) => error.code === '55000');
      }
      const count = await db.query('SELECT count(*)::int AS count FROM integration.source_observation');
      assert.equal(count.rows[0].count, 2);
    });
    await t.test('runtime can read ledger but cannot read evidence or migrate', async () => {
      await db.exec('RESET ROLE; SET SESSION AUTHORIZATION control_api');
      await db.query('SELECT name, sha256 FROM control.schema_migration');
      await assert.rejects(db.query('SELECT * FROM integration.source_observation'),
        (error) => error.code === '42501');
      await assert.rejects(db.exec('CREATE TABLE control.illegal (id int)'),
        (error) => error.code === '42501');
      await assert.rejects(db.exec('SET ROLE control_owner'), (error) => error.code === '42501');
    });
  } finally {
    await db.close();
  }
});
