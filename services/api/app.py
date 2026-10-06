"""Private foundation health API. Business routes await authenticated slices."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from packages.migrations import migration_manifest

LOG = logging.getLogger("control.health")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def database_is_ready() -> bool:
    # Unix-socket peer authentication; service cannot connect to a legacy database.
    with psycopg.connect(
        dbname="control_v2", user="control_api", host="/var/run/postgresql",
        connect_timeout=3,
        options="-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=1000",
    ) as conn:
        identity = conn.execute("SELECT current_database(), current_user").fetchone()
        if identity != ("control_v2", "control_api"):
            return False
        applied = dict(conn.execute(
            "SELECT name, sha256 FROM control.schema_migration ORDER BY name"
        ).fetchall())
        return applied == migration_manifest(MIGRATIONS)


def create_app(readiness_probe: Callable[[], bool] = database_is_ready) -> FastAPI:
    app = FastAPI(title="Control V2 foundation", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health/live")
    def live() -> JSONResponse:
        return JSONResponse({"state": "LIVE"}, headers={"Cache-Control": "no-store"})

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        try:
            ready_state = readiness_probe()
        except (psycopg.Error, OSError, ValueError):
            # Exception text can contain DSNs or data. Emit a fixed message only.
            LOG.warning("control_readiness_dependency_unavailable")
            ready_state = False
        return JSONResponse(
            {"state": "READY" if ready_state else "NOT_READY"},
            status_code=200 if ready_state else 503,
            headers={"Cache-Control": "no-store"},
        )

    return app


app = create_app()
