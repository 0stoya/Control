from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg
from pydantic import ValidationError

from packages.contracts.observation import SourceObservationV1, payload_sha256
from packages.migrations import migration_manifest, pending_migrations
from services.api.app import create_app, database_is_ready


def envelope(payload=None, **overrides):
    payload = {"quantity": None, "unit": "EA"} if payload is None else payload
    value = {
        "schema_version": "source_observation_v1", "source_system": "synthetic",
        "source_dataset": "test", "source_observation_id": "snapshot-1:row-1",
        "source_business_key": "synthetic-order-1", "source_observed_at": "2026-10-06T10:00:00Z",
        "reader_version": "test-v1", "coverage_state": "UNKNOWN",
        "freshness_state": "UNKNOWN", "authority_state": "SHADOW",
        "payload_hash": payload_sha256(payload), "payload": payload,
    }
    return value | overrides


async def get(app, path):
    messages = []
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "headers": [],
        "client": ("127.0.0.1", 10000), "server": ("127.0.0.1", 8100),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(item for item in messages if item["type"] == "http.response.start")
    body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), json.loads(body)


class ObservationTests(unittest.TestCase):
    def test_null_unknown_and_unknown_event_time_are_preserved(self):
        observed = SourceObservationV1.model_validate(envelope())
        self.assertIsNone(observed.payload["quantity"])
        self.assertIsNone(observed.occurred_at)
        self.assertEqual(observed.coverage_state, "UNKNOWN")

    def test_hash_is_reproducible_across_nested_key_order(self):
        left = {"b": {"z": 0, "a": None}, "a": "synthetic"}
        right = {"a": "synthetic", "b": {"a": None, "z": 0}}
        self.assertEqual(payload_sha256(left), payload_sha256(right))

    def test_null_does_not_become_zero(self):
        self.assertNotEqual(payload_sha256({"quantity": None}), payload_sha256({"quantity": 0}))

    def test_modified_payload_is_rejected(self):
        changed = envelope()
        changed["payload"]["quantity"] = 10
        with self.assertRaises(ValidationError):
            SourceObservationV1.model_validate(changed)

    def test_ambiguous_naive_timestamps_are_rejected(self):
        with self.assertRaises(ValidationError):
            SourceObservationV1.model_validate(envelope(source_observed_at="2026-10-06T10:00:00"))

    def test_missing_coverage_and_invented_state_are_rejected(self):
        missing = envelope()
        del missing["coverage_state"]
        for value in (missing, envelope(coverage_state="ASSUMED_COMPLETE")):
            with self.subTest(value=value.get("coverage_state")):
                with self.assertRaises(ValidationError):
                    SourceObservationV1.model_validate(value)

    def test_unknown_fields_cannot_silently_change_the_contract(self):
        with self.assertRaises(ValidationError):
            SourceObservationV1.model_validate(envelope(cancelled=True))

    def test_non_json_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            payload_sha256({"quantity": float("nan")})


class MigrationTests(unittest.TestCase):
    def test_applied_sql_cannot_be_rewritten(self):
        with self.assertRaises(ValueError):
            pending_migrations({"0001_first.sql": "new"}, {"0001_first.sql": "old"})

    def test_unknown_and_out_of_order_history_fail_closed(self):
        expected = {"0001_first.sql": "a", "0002_second.sql": "b"}
        for applied in ({"0002_second.sql": "b"}, {"0000_foreign.sql": "c"}):
            with self.assertRaises(ValueError):
                pending_migrations(expected, applied)

    def test_exact_replay_has_no_pending_migrations(self):
        expected = {"0001_first.sql": "a", "0002_second.sql": "b"}
        self.assertEqual(pending_migrations(expected, expected), [])
        self.assertEqual(pending_migrations(expected, {"0001_first.sql": "a"}), ["0002_second.sql"])

    def test_duplicate_migration_number_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
            (directory / "0001_b.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaises(ValueError):
                migration_manifest(directory)


class HealthTests(unittest.TestCase):
    def test_liveness_does_not_require_database_or_claim_readiness(self):
        def must_not_run():
            raise AssertionError("liveness contacted database")
        status, headers, data = asyncio.run(get(create_app(must_not_run), "/health/live"))
        self.assertEqual((status, data), (200, {"state": "LIVE"}))
        self.assertEqual(headers[b"cache-control"], b"no-store")

    def test_readiness_failures_never_return_ok(self):
        for error in (psycopg.OperationalError("private-credential"), OSError("private-path"), ValueError("private-data")):
            def failed():
                raise error
            with self.subTest(error=type(error).__name__), self.assertLogs("control.health", "WARNING") as logs:
                status, headers, data = asyncio.run(get(create_app(failed), "/health/ready"))
                self.assertEqual((status, data), (503, {"state": "NOT_READY"}))
                self.assertNotIn("private", " ".join(logs.output))

    def test_readiness_reports_false_and_true_explicitly(self):
        for ready, code in ((False, 503), (True, 200)):
            status, headers, data = asyncio.run(get(create_app(lambda: ready), "/health/ready"))
            self.assertEqual(status, code)
            self.assertEqual(data["state"], "READY" if ready else "NOT_READY")

    def test_readiness_rejects_wrong_database_or_role(self):
        with patch("services.api.app.psycopg.connect") as connect:
            conn = connect.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = ("css_app", "postgres")
            self.assertFalse(database_is_ready())

    def test_readiness_rejects_missing_or_changed_migrations(self):
        for applied in ([], [("0001_foundation.sql", "tampered")]):
            with patch("services.api.app.psycopg.connect") as connect:
                conn = connect.return_value.__enter__.return_value
                conn.execute.return_value.fetchone.return_value = ("control_v2", "control_api")
                conn.execute.return_value.fetchall.return_value = applied
                self.assertFalse(database_is_ready())

    def test_docs_and_unimplemented_business_routes_are_unavailable(self):
        for path in ("/docs", "/openapi.json", "/api/orders"):
            status, _, _ = asyncio.run(get(create_app(lambda: True), path))
            self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()

