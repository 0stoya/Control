"""Deterministic candidate comparison against an exact issued PO revision.

Extraction and approved supplier aliases are separate inputs. A comparison never
accepts a supplier assertion or modifies a PO. Production payloads are not fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Mapping

VERSION = "supplier_confirmation_v1"


def _number(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("finite nonnegative Decimal required")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty identity required")


def _hash(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("SHA256 required")


@dataclass(frozen=True, order=True)
class VariantKey:
    style: str
    colour: str
    size: str

    def __post_init__(self):
        for value in (self.style, self.colour, self.size):
            _text(value)


@dataclass(frozen=True)
class ConfirmationLine:
    variant: VariantKey
    quantity: Decimal
    unit_price: Decimal
    unit: str
    evidence_ref: str
    stock_return_date: date | None = None
    delivery_date: date | None = None

    def __post_init__(self):
        _number(self.quantity)
        _number(self.unit_price)
        _text(self.unit)
        _text(self.evidence_ref)


@dataclass(frozen=True)
class PoLine:
    line_id: str
    quantity: Decimal
    unit_price: Decimal
    unit: str
    required_date: date | None

    def __post_init__(self):
        _text(self.line_id)
        _text(self.unit)
        _number(self.quantity)
        _number(self.unit_price)


@dataclass(frozen=True)
class ApprovedLineMapping:
    po_line_id: str
    source_unit: str
    po_unit: str
    # Source quantity * factor = PO quantity; source price / factor = PO price.
    quantity_factor: Decimal | None
    evidence_ref: str

    def __post_init__(self):
        _text(self.po_line_id)
        _text(self.source_unit)
        _text(self.po_unit)
        _text(self.evidence_ref)
        if self.quantity_factor is not None:
            _number(self.quantity_factor)
            if self.quantity_factor == 0:
                raise ValueError("positive conversion factor required")


@dataclass(frozen=True)
class PoBaseline:
    supplier_ref: str
    po_number: str
    revision: int
    document_sha256: str
    currency: str
    lines: tuple[PoLine, ...]
    goods: Decimal
    carriage: Decimal
    discount: Decimal
    vat: Decimal
    gross: Decimal
    issued_revision_verified: bool
    line_set_complete: bool

    def __post_init__(self):
        for value in (self.supplier_ref, self.po_number, self.currency):
            _text(value)
        _hash(self.document_sha256)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("positive revision required")
        if len({line.line_id for line in self.lines}) != len(self.lines):
            raise ValueError("ambiguous PO line identity")
        for value in (self.goods, self.carriage, self.discount, self.vat, self.gross):
            _number(value)


@dataclass(frozen=True)
class Confirmation:
    supplier_ref: str
    our_po_reference: str
    supplier_order_number: str
    document_sha256: str
    parser_version: str
    currency: str
    lines: tuple[ConfirmationLine, ...]
    goods: Decimal
    vat: Decimal
    gross: Decimal
    carriage: Decimal | None
    discount: Decimal | None
    despatch_date: date | None
    supplier_link_verified: bool
    extraction_complete: bool

    def __post_init__(self):
        for value in (self.supplier_ref, self.our_po_reference,
                      self.supplier_order_number, self.parser_version, self.currency):
            _text(value)
        _hash(self.document_sha256)
        for value in (self.goods, self.vat, self.gross, self.carriage, self.discount):
            if value is not None:
                _number(value)


@dataclass(frozen=True)
class Difference:
    code: str
    po_line_id: str | None = None
    variant: VariantKey | None = None
    expected: str | None = None
    received: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    state: str
    commercial_state: str
    timing_state: str
    differences: tuple[Difference, ...]
    validation_version: str
    mapping_version: str
    po_revision: int
    po_document_sha256: str
    confirmation_document_sha256: str


def validate_confirmation(
    po: PoBaseline, candidate: Confirmation,
    mappings: Mapping[VariantKey, ApprovedLineMapping], *, mapping_version: str,
) -> ValidationResult:
    """Produce review evidence. Exact aliases and unit conversions are mandatory."""
    _text(mapping_version)
    issues: list[Difference] = []
    commercial_unknown = False
    commercial_diff = False
    timing_unknown = False
    timing_exception = False

    def unknown(code: str, line_id=None, variant=None):
        nonlocal commercial_unknown
        commercial_unknown = True
        issues.append(Difference(code, line_id, variant))

    def compare(code: str, expected, received, line_id=None, variant=None):
        nonlocal commercial_diff
        if expected != received:
            commercial_diff = True
            issues.append(Difference(code, line_id, variant, str(expected), str(received)))

    identity_proven = (po.issued_revision_verified and po.line_set_complete
                       and bool(po.lines) and candidate.supplier_link_verified
                       and candidate.supplier_ref == po.supplier_ref
                       and candidate.our_po_reference == po.po_number
                       and candidate.extraction_complete)
    if not po.issued_revision_verified:
        unknown("ISSUED_REVISION_UNVERIFIED")
    if not po.line_set_complete or not po.lines:
        unknown("PO_LINE_SET_INCOMPLETE")
    if not candidate.extraction_complete or not candidate.lines:
        unknown("EXTRACTION_INCOMPLETE")
    if not candidate.supplier_link_verified or candidate.supplier_ref != po.supplier_ref:
        unknown("SUPPLIER_LINK_UNVERIFIED")
    if candidate.our_po_reference != po.po_number:
        unknown("PO_REFERENCE_MISMATCH")
    compare("CURRENCY_DIFFERENCE", po.currency, candidate.currency)

    # Confirmations must internally reconcile before comparing accepted money.
    if sum((x.quantity * x.unit_price for x in candidate.lines), Decimal(0)) != candidate.goods:
        unknown("CONFIRMATION_GOODS_DO_NOT_RECONCILE")
    if po.goods + po.carriage - po.discount + po.vat != po.gross:
        unknown("PO_TOTAL_DOES_NOT_RECONCILE")
    for name in ("carriage", "discount"):
        value = getattr(candidate, name)
        if value is None:
            unknown(name.upper() + "_UNSPECIFIED")
        elif identity_proven and po.currency == candidate.currency:
            compare(name.upper() + "_DIFFERENCE", getattr(po, name), value)
    if candidate.carriage is not None and candidate.discount is not None:
        if candidate.goods + candidate.carriage - candidate.discount + candidate.vat != candidate.gross:
            unknown("CONFIRMATION_TOTAL_DOES_NOT_RECONCILE")
    if identity_proven and po.currency == candidate.currency:
        for name in ("goods", "vat", "gross"):
            compare(name.upper() + "_DIFFERENCE", getattr(po, name), getattr(candidate, name))

    by_id = {line.line_id: line for line in po.lines}
    seen_variants: set[VariantKey] = set()
    seen_lines: set[str] = set()
    for line in candidate.lines:
        if line.variant in seen_variants:
            unknown("CONFIRMATION_VARIANT_AMBIGUOUS", variant=line.variant)
            continue
        seen_variants.add(line.variant)
        mapping = mappings.get(line.variant)
        if not identity_proven or mapping is None:
            unknown("LINE_MAPPING_REQUIRED", variant=line.variant)
            continue
        expected_line = by_id.get(mapping.po_line_id)
        if expected_line is None:
            unknown("UNEXPECTED_CONFIRMATION_LINE", mapping.po_line_id, line.variant)
            continue
        if mapping.po_line_id in seen_lines:
            unknown("PO_LINE_MAPPING_AMBIGUOUS", mapping.po_line_id, line.variant)
            continue
        seen_lines.add(mapping.po_line_id)
        factor = mapping.quantity_factor
        if factor is None or mapping.source_unit != line.unit or mapping.po_unit != expected_line.unit:
            unknown("UNIT_MAPPING_REQUIRED", mapping.po_line_id, line.variant)
        else:
            compare("LINE_QUANTITY_DIFFERENCE", expected_line.quantity,
                    line.quantity * factor, mapping.po_line_id, line.variant)
            if po.currency == candidate.currency:
                compare("LINE_PRICE_DIFFERENCE", expected_line.unit_price * factor,
                        line.unit_price, mapping.po_line_id, line.variant)
        required = expected_line.required_date
        if required is None or line.delivery_date is None:
            timing_unknown = True
            issues.append(Difference("DELIVERY_DATE_UNPROVEN", mapping.po_line_id, line.variant))
        elif line.delivery_date > required:
            timing_exception = True
            issues.append(Difference("DELIVERY_AFTER_REQUIRED", mapping.po_line_id,
                                     line.variant, str(required), str(line.delivery_date)))
        if required and line.stock_return_date and line.stock_return_date > required:
            timing_exception = True
            issues.append(Difference("STOCK_RETURN_AFTER_REQUIRED", mapping.po_line_id,
                                     line.variant, str(required), str(line.stock_return_date)))
        if required and candidate.despatch_date and candidate.despatch_date > required:
            timing_exception = True
            issues.append(Difference("DESPATCH_AFTER_REQUIRED", mapping.po_line_id,
                                     line.variant, str(required), str(candidate.despatch_date)))
    if identity_proven:
        for missing in sorted(by_id.keys() - seen_lines):
            unknown("PO_LINE_NOT_CONFIRMED", missing)
    if not identity_proven or len(seen_lines) != len(po.lines):
        timing_unknown = True

    commercial = "DIFFERENCES" if commercial_diff else "REVIEW_REQUIRED" if commercial_unknown else "MATCH"
    timing = "EXCEPTIONS" if timing_exception else "UNKNOWN" if timing_unknown else "MATCH"
    state = "MATCH" if commercial == timing == "MATCH" else "REVIEW_REQUIRED"
    return ValidationResult(state, commercial, timing, tuple(issues), VERSION,
                            mapping_version, po.revision, po.document_sha256,
                            candidate.document_sha256)
