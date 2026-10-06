"""Inspect a local PDF candidate; private documents/output must stay outside Git.

Uses optional pdfplumber 0.11.9, tested with the bundled Codex PDF runtime. This
is a local bounded candidate tool, not the production mail attachment worker.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.communication.castle_confirmation import Word, parse_confirmation


def serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("unsupported candidate value")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--supplier-ref", required=True, help="candidate supplier; remains unverified")
    parser.add_argument("--output", required=True, type=Path, help="private candidate path outside the repository")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(repo):
        raise ValueError("private output must be outside repository")
    if args.pdf.stat().st_size > 5_000_000:
        raise ValueError("document size exceeds local candidate budget")
    import pdfplumber
    with pdfplumber.open(args.pdf) as pdf:
        if len(pdf.pages) > 10:
            raise ValueError("document page budget exceeded")
        words = [[Word(w["text"], w["x0"], w["top"]) for w in page.extract_words()] for page in pdf.pages]
    candidate = parse_confirmation(words, document_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                                   supplier_ref=args.supplier_ref)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(asdict(candidate), stream, default=serialize, indent=2)
        stream.write("\n")
    # Summary only; no addresses, message text, credentials or commercial lines.
    print(json.dumps({"state":"CANDIDATE_REVIEW_REQUIRED", "variants":len(candidate.lines),
                      "stock_date_variants":sum(x.stock_return_date is not None for x in candidate.lines)}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ImportError, TypeError):
        print("confirmation_candidate_extraction_failed", file=sys.stderr)
        raise SystemExit(1)
