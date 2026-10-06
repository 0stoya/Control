from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import unittest

from services.communication.confirmation import (
    ApprovedLineMapping, Confirmation, ConfirmationLine, PoBaseline, PoLine,
    VariantKey, validate_confirmation,
)


def fixture():
    # Entirely synthetic identities, variants, money and dates.
    key = VariantKey("STYLE-A", "BLUE", "L")
    po = PoBaseline("SYN001", "900001", 3, "a" * 64, "GBP",
                    (PoLine("line-1", D(4), D("2.50"), "Each", date(2030, 1, 7)),),
                    D(10), D(0), D(0), D(2), D(12), True, True)
    line = ConfirmationLine(key, D(4), D("2.50"), "PIECES", "synthetic:page-1:box-1",
                            delivery_date=date(2030, 1, 7))
    confirmation = Confirmation("SYN001", "900001", "SUP-999", "b" * 64,
                                "synthetic-v1", "GBP", (line,), D(10), D(2), D(12),
                                D(0), D(0), date(2030, 1, 6), True, True)
    mapping = {key: ApprovedLineMapping("line-1", "PIECES", "Each", D(1), "review-1")}
    return po, confirmation, mapping


def assess(po, candidate, mappings):
    return validate_confirmation(po, candidate, mappings, mapping_version="approved-v1")


def codes(result):
    return {difference.code for difference in result.differences}


class ConfirmationTests(unittest.TestCase):
    def test_complete_approved_match_retains_exact_versions(self):
        result = assess(*fixture())
        self.assertEqual(result.state, "MATCH")
        self.assertEqual(result.po_revision, 3)
        self.assertEqual(result.po_document_sha256, "a" * 64)
        self.assertEqual(result.confirmation_document_sha256, "b" * 64)
        self.assertEqual(result.mapping_version, "approved-v1")

    def test_despatch_is_not_delivery_and_money_does_not_hide_stock_delay(self):
        po, candidate, mappings = fixture()
        line = replace(candidate.lines[0], delivery_date=None, stock_return_date=date(2030, 1, 21))
        result = assess(po, replace(candidate, lines=(line,)), mappings)
        self.assertEqual(result.commercial_state, "MATCH")
        self.assertEqual((result.timing_state, result.state), ("EXCEPTIONS", "REVIEW_REQUIRED"))
        self.assertIn("STOCK_RETURN_AFTER_REQUIRED", codes(result))
        self.assertIn("DELIVERY_DATE_UNPROVEN", codes(result))

    def test_subject_supplier_order_number_cannot_replace_customer_reference(self):
        po, candidate, mappings = fixture()
        result = assess(po, replace(candidate, our_po_reference=candidate.supplier_order_number), mappings)
        self.assertIn("PO_REFERENCE_MISMATCH", codes(result))
        self.assertNotEqual(result.commercial_state, "MATCH")

    def test_unapproved_alias_and_unapproved_unit_remain_unknown(self):
        po, candidate, mappings = fixture()
        self.assertIn("LINE_MAPPING_REQUIRED", codes(assess(po, candidate, {})))
        key = candidate.lines[0].variant
        mappings[key] = replace(mappings[key], quantity_factor=None)
        self.assertIn("UNIT_MAPPING_REQUIRED", codes(assess(po, candidate, mappings)))

    def test_same_money_with_changed_quantities_and_prices_is_flagged(self):
        po, candidate, mappings = fixture()
        changed = replace(candidate.lines[0], quantity=D(2), unit_price=D(5))
        result = assess(po, replace(candidate, lines=(changed,)), mappings)
        self.assertEqual(result.commercial_state, "DIFFERENCES")
        self.assertTrue({"LINE_PRICE_DIFFERENCE", "LINE_QUANTITY_DIFFERENCE"} <= codes(result))

    def test_explicit_pack_conversion_compares_same_unit_basis(self):
        po, candidate, mappings = fixture()
        changed = replace(candidate.lines[0], quantity=D(2), unit_price=D(5), unit="PACK-2")
        key = changed.variant
        mappings[key] = ApprovedLineMapping("line-1", "PACK-2", "Each", D(2), "review-pack")
        self.assertEqual(assess(po, replace(candidate, lines=(changed,)), mappings).state, "MATCH")
        mappings[key] = replace(mappings[key], source_unit="OLD-PACK")
        self.assertIn("UNIT_MAPPING_REQUIRED", codes(assess(po, replace(candidate, lines=(changed,)), mappings)))

    def test_missing_and_extra_variants_are_not_a_complete_match(self):
        po, candidate, mappings = fixture()
        extra = replace(candidate.lines[0], variant=VariantKey("STYLE-X", "BLUE", "L"))
        result = assess(po, replace(candidate, lines=(extra,)), mappings)
        self.assertIn("PO_LINE_NOT_CONFIRMED", codes(result))
        self.assertNotEqual(result.commercial_state, "MATCH")

    def test_duplicate_variant_and_multiple_aliases_to_one_line_fail_closed(self):
        po, candidate, mappings = fixture()
        result = assess(po, replace(candidate, lines=candidate.lines * 2), mappings)
        self.assertIn("CONFIRMATION_VARIANT_AMBIGUOUS", codes(result))
        extra = replace(candidate.lines[0], variant=VariantKey("STYLE-A", "BLUE", "XL"))
        mappings[extra.variant] = mappings[candidate.lines[0].variant]
        result = assess(po, replace(candidate, lines=candidate.lines + (extra,)), mappings)
        self.assertIn("PO_LINE_MAPPING_AMBIGUOUS", codes(result))

    def test_missing_charges_and_incomplete_evidence_stay_unknown(self):
        po, candidate, mappings = fixture()
        for changed, code in ((replace(candidate, carriage=None), "CARRIAGE_UNSPECIFIED"),
                              (replace(candidate, extraction_complete=False), "EXTRACTION_INCOMPLETE"),
                              (replace(candidate, supplier_link_verified=False), "SUPPLIER_LINK_UNVERIFIED")):
            with self.subTest(code=code):
                result = assess(po, changed, mappings)
                self.assertIn(code, codes(result))
                self.assertNotEqual(result.state, "MATCH")
        self.assertIn("ISSUED_REVISION_UNVERIFIED", codes(assess(replace(po, issued_revision_verified=False), candidate, mappings)))

    def test_currency_and_internal_total_conflicts_cannot_validate(self):
        po, candidate, mappings = fixture()
        self.assertIn("CURRENCY_DIFFERENCE", codes(assess(po, replace(candidate, currency="EUR"), mappings)))
        result = assess(po, replace(candidate, goods=D(11)), mappings)
        self.assertIn("CONFIRMATION_GOODS_DO_NOT_RECONCILE", codes(result))
        self.assertIn("CONFIRMATION_TOTAL_DOES_NOT_RECONCILE", codes(result))

    def test_float_nan_negative_and_ambiguous_po_identity_are_rejected(self):
        po, candidate, mappings = fixture()
        for value in (2.5, D("NaN"), D("Infinity"), D(-1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(candidate.lines[0], quantity=value)
        with self.assertRaises(ValueError):
            replace(po, lines=po.lines * 2)

    def test_repeatable_replay_and_input_order_do_not_change_matching(self):
        po, candidate, mappings = fixture()
        self.assertEqual(assess(po, candidate, mappings), assess(po, candidate, mappings))


if __name__ == "__main__":
    unittest.main()
