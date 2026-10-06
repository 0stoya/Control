"""Forward-only migrations. Run locally as OS postgres on the fresh V2 server."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from packages.migrations import migration_manifest, pending_migrations

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    expected = migration_manifest(MIGRATIONS)
    try:
        with psycopg.connect(
            dbname="control_v2", user="postgres", host="/var/run/postgresql", connect_timeout=3,
            options="-c statement_timeout=60000 -c lock_timeout=5000",
        ) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(185215119)")
                conn.execute("SET ROLE control_owner")
                exists = conn.execute("SELECT to_regclass('control.schema_migration')").fetchone()[0]
                applied = dict(conn.execute(
                    "SELECT name, sha256 FROM control.schema_migration ORDER BY name"
                ).fetchall()) if exists else {}
                pending = pending_migrations(expected, applied)
                if args.apply:
                    conn.execute("CREATE SCHEMA IF NOT EXISTS control AUTHORIZATION control_owner")
                    conn.execute("""CREATE TABLE IF NOT EXISTS control.schema_migration (
                        name text PRIMARY KEY, sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
                        applied_at timestamptz NOT NULL DEFAULT now())""")
                    for name in pending:
                        conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
                        conn.execute("INSERT INTO control.schema_migration (name, sha256) VALUES (%s, %s)",
                                     (name, expected[name]))
        print(json.dumps({"state": "APPLIED" if args.apply else "CHECKED", "pending": pending}))
        return 0
    except (psycopg.Error, OSError, ValueError):
        print(json.dumps({"state": "FAILED", "reason": "MIGRATION_OR_DATABASE_CHECK_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

