"""Scoped Sculptor identity laws for the read-only V1 migration shadow.

These types do not assign canonical UUIDs, prove freshness/authority, or resolve
uncovered historical lines. Callers must supply the registered ERP/company
namespace and exact decoded source references from an accepted adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _reference(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a nonblank single-line reference")


def _unsigned(value: int, field: str, maximum: int, *, minimum: int = 1) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{field} is outside its contracted unsigned range")


def _indicator(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) > 1 or value in {"\n", "\r", "\x00"}:
        raise ValueError(f"{field} must be the exact decoded one-character indicator")
    try:
        value.encode("iso-8859-1")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field} is outside the native one-byte encoding") from exc


@dataclass(frozen=True)
class SourceScope:
    source_instance: str
    company_scope: str

    def __post_init__(self) -> None:
        _reference(self.source_instance, "source_instance")
        _reference(self.company_scope, "company_scope")


@dataclass(frozen=True)
class SalesOrderKey:
    scope: SourceScope
    customer_reference: str
    order_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.scope, SourceScope):
            raise ValueError("registered source scope is required")
        _reference(self.customer_reference, "customer_reference")
        _unsigned(self.order_number, "order_number", 0xFFFFFFFF)


@dataclass(frozen=True)
class SalesLineIdentity:
    order: SalesOrderKey
    item_number: int
    unique_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.order, SalesOrderKey):
            raise ValueError("scoped order key is required")
        _unsigned(self.item_number, "item_number", 0xFFFF)
        _unsigned(self.unique_number, "unique_number", 0xFFFF)

    @property
    def logical_key(self) -> tuple[SalesOrderKey, int]:
        """Accepted operational line reference; native position may change."""
        return self.order, self.unique_number

    @property
    def native_key(self) -> tuple[SourceScope, int, int]:
        """Physical orditem key; it must be interpreted within a revision."""
        return self.order.scope, self.order.order_number, self.item_number


def validate_sales_revision(
    order: SalesOrderKey, lines: Iterable[SalesLineIdentity]
) -> tuple[SalesLineIdentity, ...]:
    """Reject mixed owners, reused native slots and ambiguous logical aliases."""
    rows = tuple(lines)
    native_keys, logical_keys = set(), set()
    for row in rows:
        if not isinstance(row, SalesLineIdentity) or row.order != order:
            raise ValueError("line ownership differs from the exact snapshot header")
        if row.native_key in native_keys:
            raise ValueError("duplicate native item identity inside one revision")
        if row.logical_key in logical_keys:
            raise ValueError("ambiguous logical line reference inside one revision")
        native_keys.add(row.native_key)
        logical_keys.add(row.logical_key)
    return rows


@dataclass(frozen=True)
class DeliveryLineIdentity:
    order: SalesOrderKey
    delivery_number: int
    delivery_suffix: int
    print_indicator: str
    item_number: int
    kit_indicator: str
    unique_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.order, SalesOrderKey):
            raise ValueError("scoped order key is required")
        _unsigned(self.delivery_number, "delivery_number", 0xFFFFFFFF)
        _unsigned(self.delivery_suffix, "delivery_suffix", 0xFF, minimum=0)
        _unsigned(self.item_number, "item_number", 0xFFFF, minimum=0)
        _unsigned(self.unique_number, "unique_number", 0xFFFF)
        _indicator(self.print_indicator, "print_indicator")
        _indicator(self.kit_indicator, "kit_indicator")

    @property
    def native_key(self) -> tuple[SourceScope, int, int, int, int, str]:
        """Five-field orddelnt key plus registered scope; uniqueno is a field."""
        return (
            self.order.scope, self.delivery_number, self.delivery_suffix,
            self.order.order_number, self.item_number, self.kit_indicator,
        )

    @property
    def capture_row_key(self) -> tuple:
        """Key within one manifested capture, including the header print state."""
        return self.native_key, self.print_indicator

    @property
    def representation_key(self) -> tuple:
        """Seven-field V1 posting/settlement identity with registered scope."""
        return self.capture_row_key, self.unique_number

    @property
    def logical_line_reference(self) -> tuple[SalesOrderKey, int]:
        return self.order, self.unique_number


def validate_delivery_capture(
    lines: Iterable[DeliveryLineIdentity],
) -> tuple[DeliveryLineIdentity, ...]:
    """Fail before persistence if one capture repeats its native/header row key."""
    rows = tuple(lines)
    keys = set()
    for row in rows:
        if not isinstance(row, DeliveryLineIdentity):
            raise ValueError("delivery line identity is required")
        if row.capture_row_key in keys:
            raise ValueError("duplicate native delivery identity inside one capture")
        keys.add(row.capture_row_key)
    return rows


def resolve_delivery_line(
    delivery: DeliveryLineIdentity,
    revision_order: SalesOrderKey,
    revision_lines: Iterable[SalesLineIdentity],
) -> SalesLineIdentity | None:
    """Exact scoped logical-reference match; no item-number or SKU fallback."""
    rows = validate_sales_revision(revision_order, revision_lines)
    if delivery.order != revision_order:
        return None
    return next(
        (row for row in rows if row.logical_key == delivery.logical_line_reference),
        None,
    )


def delivery_snapshot_observation_key(
    snapshot_id: str, line: DeliveryLineIdentity,
) -> tuple:
    """Same immutable export replays identically; later boundaries stay distinct.

    snapshot_id must name a saved, immutable export boundary, not a regenerated
    ID per retry. The foundation still compares every envelope fact on replay.
    """
    _reference(snapshot_id, "snapshot_id")
    return snapshot_id, line.representation_key
