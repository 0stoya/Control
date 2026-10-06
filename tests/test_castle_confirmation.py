from dataclasses import replace
from datetime import date
from decimal import Decimal
import unittest

from services.communication.castle_confirmation import Word, parse_confirmation


def fixture():
    # Synthetic coordinate grid. No supplier/user PDF or production payload.
    return [[Word("ORDER CONFIRMATION", 10, 10),
             Word("CUST1 900001 GBP - Pounds 777 01/01/2030 02/01/2030", 10, 20),
             Word("901 - SAMPLE ITEM (PIECES) Price: 2.00 Quantity: 3 Total Value: 6.00", 10, 40),
             Word("SIZE", 10, 50), Word("M", 100, 50), Word("L", 140, 50),
             Word("BLUE", 10, 60), Word("1", 100, 60), Word("2", 140, 60),
             Word("*21/01/30", 100, 69), Word("DPD 0.00", 10, 80)],
            [Word("TOTAL VALUE 6.00", 10, 10), Word("VAT 1.20", 10, 20),
             Word("TOTAL DUE (GBP) 7.20", 10, 30), Word("DELIVERY CHGS -", 10, 40)]]


def parse(pages):
    return parse_confirmation(pages, document_sha256="a" * 64, supplier_ref="SYN001")


class MatrixExtractionTests(unittest.TestCase):
    def test_customer_reference_supplier_order_and_aligned_stock_date_are_distinct(self):
        value = parse(fixture())
        self.assertEqual((value.our_po_reference, value.supplier_order_number), ("900001", "777"))
        self.assertEqual(value.lines[0].variant.size, "M")
        self.assertEqual(value.lines[0].stock_return_date, date(2030, 1, 21))
        self.assertIsNone(value.lines[1].stock_return_date)
        self.assertIn("stock:page-1:x-100.0", value.lines[0].evidence_ref)
        self.assertEqual(value.goods, Decimal(6))
        self.assertFalse(value.supplier_link_verified)
        self.assertIsNone(value.carriage)  # Printed dash is not zero.
        self.assertIsNone(value.discount)
        self.assertIsNone(value.lines[0].delivery_date)

    def test_misaligned_date_is_rejected_instead_of_assigned_to_nearest_size(self):
        pages = fixture()
        pages[0][-2] = replace(pages[0][-2], x0=120)
        with self.assertRaisesRegex(ValueError, "alignment"):
            parse(pages)

    def test_matrix_quantity_loss_and_duplicate_columns_fail_closed(self):
        for alteration in ("missing", "duplicate"):
            pages = fixture()
            if alteration == "missing":
                del pages[0][8]
            else:
                pages[0][8] = replace(pages[0][8], x0=100)
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                parse(pages)

    def test_group_quantity_and_value_must_reconcile(self):
        pages = fixture()
        pages[0][2] = replace(pages[0][2], text=pages[0][2].text.replace("Quantity: 3", "Quantity: 4"))
        with self.assertRaisesRegex(ValueError, "reconcile"):
            parse(pages)

    def test_document_total_and_group_layout_are_checked_independently(self):
        pages = fixture()
        pages[1][0] = replace(pages[1][0], text="TOTAL VALUE 7.00")
        with self.assertRaisesRegex(ValueError, "document goods"):
            parse(pages)
        pages = fixture()
        pages[0][2] = replace(pages[0][2], text=pages[0][2].text.replace("Price:", "Unit Price:"))
        with self.assertRaisesRegex(ValueError, "product group layout"):
            parse(pages)

    def test_changed_layout_missing_totals_and_duplicate_dates_require_review(self):
        for alteration in ("layout", "total", "date"):
            pages = fixture()
            if alteration == "layout":
                pages[0].insert(-1, Word("Unrecognised amendment note", 10, 75))
            elif alteration == "total":
                pages[1] = pages[1][1:]
            else:
                pages[0].insert(-1, Word("*22/01/30", 100, 73))
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                parse(pages)


if __name__ == "__main__":
    unittest.main()
