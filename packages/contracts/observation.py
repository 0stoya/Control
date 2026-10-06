"""Versioned evidence envelope; validation does not establish source authority."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator


def payload_sha256(payload: dict[str, JsonValue]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class SourceObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["source_observation_v1"]
    source_system: str = Field(min_length=1, max_length=128, pattern=r"\S")
    source_dataset: str = Field(min_length=1, max_length=128, pattern=r"\S")
    source_observation_id: str = Field(min_length=1, max_length=512, pattern=r"\S")
    source_business_key: str = Field(min_length=1, max_length=1024, pattern=r"\S")
    source_observed_at: AwareDatetime
    occurred_at: AwareDatetime | None = None
    reader_version: str = Field(min_length=1, max_length=128, pattern=r"\S")
    coverage_state: Literal["COMPLETE", "PARTIAL", "UNKNOWN"]
    freshness_state: Literal["FRESH", "STALE", "UNKNOWN"]
    authority_state: Literal["AUTHORITATIVE", "SHADOW", "HISTORICAL", "UNKNOWN"]
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def check_payload_hash(self) -> SourceObservationV1:
        if self.payload_hash != payload_sha256(self.payload):
            raise ValueError("payload hash does not match canonical payload")
        return self

