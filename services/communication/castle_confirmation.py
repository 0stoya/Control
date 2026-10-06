"""Narrow coordinate-aware candidate extractor; unsupported layouts fail closed.

Input words are supplied by a PDF text extractor. No OCR, unit/colour/size alias
inference or acceptance takes place here. Each value retains a page/position ref.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
import re
from typing import Sequence

from services.communication.confirmation import Confirmation, ConfirmationLine, VariantKey

PARSER_VERSION = "castle_matrix_candidate_v1"
GROUP = re.compile(r"^(\d+) - .+ \((PIECES|PAIRS)\) Price: (\d+\.\d{2}) Quantity: (\d+) Total Value: (\d+\.\d{2})$")
HEADER = re.compile(r"^\S+ (\d+) ([A-Z]{3}) - .+ (\d+) (\d{2}/\d{2}/\d{4}) (\d{2}/\d{2}/\d{4})$")


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    top: float


def rows(words: Sequence[Word]) -> list[list[Word]]:
    result: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        if not result or abs(word.top - result[-1][0].top) > 2:
            result.append([word])
        else:
            result[-1].append(word)
    return [sorted(row, key=lambda w: w.x0) for row in result]


def parse_confirmation(
    pages: Sequence[Sequence[Word]], *, document_sha256: str, supplier_ref: str,
    supplier_link_verified: bool = False,
) -> Confirmation:
    if not pages or len(pages) > 10:
        raise ValueError("unsupported confirmation page budget")
    page_rows = [rows(page) for page in pages]
    texts = [" ".join(w.text for w in row) for page in page_rows for row in page]
    if "ORDER CONFIRMATION" not in texts:
        raise ValueError("unsupported document type")
    headers = [match for text in texts if (match := HEADER.fullmatch(text))]
    if len(headers) != 1:
        raise ValueError("ambiguous confirmation header")
    header = headers[0]
    received = datetime.strptime(header[4], "%d/%m/%Y").date()
    despatch = datetime.strptime(header[5], "%d/%m/%Y").date()
    lines: list[ConfirmationLine] = []
    group = None
    group_lines: list[int] = []
    sizes: list[Word] = []
    latest_colour: dict[str, int] = {}

    def finish_group():
        nonlocal group, group_lines, sizes, latest_colour
        if group is not None:
            captured = [lines[i] for i in group_lines]
            if not captured or sum((x.quantity for x in captured), Decimal(0)) != Decimal(group[4]):
                raise ValueError("matrix quantity does not reconcile")
            if sum((x.quantity * x.unit_price for x in captured), Decimal(0)) != Decimal(group[5]):
                raise ValueError("matrix value does not reconcile")
        group, group_lines, sizes, latest_colour = None, [], [], {}

    def column(word):
        if not sizes:
            raise ValueError("matrix columns missing")
        near = sorted(sizes, key=lambda size: abs(size.x0 - word.x0))
        if abs(near[0].x0 - word.x0) > 3:
            raise ValueError("ambiguous matrix column alignment")
        return near[0].text

    for page_no, page in enumerate(page_rows, 1):
        for row in page:
            text = " ".join(w.text for w in row)
            found = GROUP.fullmatch(text)
            if found:
                finish_group()
                group = found
                continue
            if "Price:" in text or "Total Value:" in text:
                raise ValueError("unsupported product group layout")
            if group is None:
                continue
            if row[0].text == "SIZE":
                sizes = row[1:]
                if not sizes or len({w.text for w in sizes}) != len(sizes):
                    raise ValueError("ambiguous sizes")
                latest_colour = {}
                continue
            if text.startswith("DPD ") or text.startswith("Page "):
                finish_group()
                continue
            if all(re.fullmatch(r"\*\d{2}/\d{2}/\d{2}", w.text) for w in row):
                for word in row:
                    size = column(word)
                    if size not in latest_colour:
                        raise ValueError("stock date without quantity evidence")
                    index = latest_colour[size]
                    if lines[index].stock_return_date is not None:
                        raise ValueError("duplicate stock date")
                    day, month, year = map(int, word.text[1:].split("/"))
                    stock = date(day=day, month=month, year=(received.year // 100) * 100 + year)
                    if abs(stock.year - received.year) > 5:
                        raise ValueError("ambiguous stock-date century")
                    ref = lines[index].evidence_ref + f";stock:page-{page_no}:x-{word.x0:.1f}:y-{word.top:.1f}"
                    lines[index] = replace(lines[index], stock_return_date=stock, evidence_ref=ref)
                continue
            if not sizes:
                raise ValueError("unsupported matrix layout")
            labels = [w.text for w in row if w.x0 < sizes[0].x0 - 10]
            cells = [w for w in row if w.x0 >= sizes[0].x0 - 10]
            if not labels or not cells or not all(re.fullmatch(r"\d+", w.text) for w in cells):
                raise ValueError("unsupported matrix row")
            assignments = {column(word): word for word in cells}
            if len(assignments) != len(cells) or set(assignments) != {w.text for w in sizes}:
                raise ValueError("missing or ambiguous quantity cells")
            latest_colour = {}
            for size, word in assignments.items():
                key = VariantKey(group[1], " ".join(labels), size)
                latest_colour[size] = len(lines)
                group_lines.append(len(lines))
                lines.append(ConfirmationLine(key, Decimal(word.text), Decimal(group[3]), group[2],
                                             f"page-{page_no}:x-{word.x0:.1f}:y-{word.top:.1f}"))
        finish_group()
    if not lines or len({line.variant for line in lines}) != len(lines):
        raise ValueError("empty or ambiguous confirmation line set")

    def amount(label: str, optional=False):
        matches = [re.fullmatch(re.escape(label) + r" (\d+\.\d{2}|-)", text) for text in texts]
        values = [match[1] for match in matches if match]
        if not values and optional:
            return None
        if len(values) != 1:
            raise ValueError("missing or ambiguous document total")
        if values[0] == "-":
            if optional:
                return None
            raise ValueError("unspecified required document total")
        return Decimal(values[0])

    goods = amount("TOTAL VALUE")
    if sum((line.quantity * line.unit_price for line in lines), Decimal(0)) != goods:
        raise ValueError("document goods do not reconcile with extracted variants")
    return Confirmation(
        supplier_ref, header[1], header[3], document_sha256, PARSER_VERSION, header[2],
        tuple(lines), goods, amount("VAT"), amount(f"TOTAL DUE ({header[2]})"),
        amount("DELIVERY CHGS", optional=True), amount("DISCOUNT", optional=True),
        despatch, supplier_link_verified, True,
    )
