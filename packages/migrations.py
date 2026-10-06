from __future__ import annotations

import hashlib
import re
from pathlib import Path


def migration_manifest(directory: Path) -> dict[str, str]:
    paths = sorted(directory.glob("*.sql"))
    if not paths:
        raise ValueError("no migrations found")
    if any(not re.fullmatch(r"\d{4}_[a-z0-9_]+\.sql", path.name) for path in paths):
        raise ValueError("migration names must be NNNN_lowercase_name.sql")
    prefixes = [path.name[:4] for path in paths]
    if len(prefixes) != len(set(prefixes)):
        raise ValueError("migration numbers must be unique")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def pending_migrations(expected: dict[str, str], applied: dict[str, str]) -> list[str]:
    for name, checksum in applied.items():
        if name not in expected or expected[name] != checksum:
            raise ValueError("applied migration is unknown or has changed")
    applied_names = sorted(applied)
    if applied_names != list(expected)[:len(applied_names)]:
        raise ValueError("applied migrations are not an ordered prefix")
    return [name for name in expected if name not in applied]

