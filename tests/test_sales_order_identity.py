"""Synthetic identity regressions for observed V1 migration failure modes."""
from dataclasses import replace
import unittest

from packages.contracts.sales_order_identity import (
    DeliveryLineIdentity,
    SalesLineIdentity,
    SalesOrderKey,
    SourceScope,
    delivery_snapshot_observation_key,
    resolve_delivery_line,
    validate_delivery_capture,
    validate_sales_revision,
)


class SalesOrderIdentityTests(unittest.TestCase):
    def setUp(self):
        self.scope = SourceScope("synthetic-erp", "synthetic-company")
        self.order = SalesOrderKey(self.scope, "SYN001", 10001)
        self.delivery = DeliveryLineIdentity(self.order, 20001, 0, "", 3, "", 6)

    def test_renumbering_preserves_logical_reference_and_changes_native_position(self):
        before = SalesLineIdentity(self.order, 3, 6)
        after = SalesLineIdentity(self.order, 8, 6)
        self.assertEqual(before.logical_key, after.logical_key)
        self.assertNotEqual(before.native_key, after.native_key)
        validate_sales_revision(self.order, [before])
        validate_sales_revision(self.order, [after])

    def test_reused_native_slot_does_not_merge_logical_lines(self):
        before = SalesLineIdentity(self.order, 3, 6)
        after = SalesLineIdentity(self.order, 3, 7)
        self.assertEqual(before.native_key, after.native_key)
        self.assertNotEqual(before.logical_key, after.logical_key)

    def test_same_revision_cannot_use_one_logical_reference_twice(self):
        with self.assertRaisesRegex(ValueError, "ambiguous logical"):
            validate_sales_revision(self.order, [
                SalesLineIdentity(self.order, 3, 6),
                SalesLineIdentity(self.order, 8, 6),
            ])

    def test_same_revision_cannot_reuse_one_native_slot(self):
        with self.assertRaisesRegex(ValueError, "duplicate native"):
            validate_sales_revision(self.order, [
                SalesLineIdentity(self.order, 3, 6),
                SalesLineIdentity(self.order, 3, 7),
            ])

    def test_snapshot_cannot_join_another_customer_by_order_number(self):
        another_order = replace(self.order, customer_reference="SYN002")
        with self.assertRaisesRegex(ValueError, "ownership differs"):
            validate_sales_revision(self.order, [
                SalesLineIdentity(another_order, 3, 6),
            ])

    def test_delivery_uses_logical_reference_when_native_positions_differ(self):
        correct = SalesLineIdentity(self.order, 8, 6)
        incorrect_naive_match = SalesLineIdentity(self.order, 6, 9)
        self.assertEqual(correct, resolve_delivery_line(
            self.delivery, self.order, [incorrect_naive_match, correct]
        ))

    def test_missing_logical_reference_does_not_fall_back_to_matching_item(self):
        matching_position_wrong_line = SalesLineIdentity(self.order, 3, 7)
        self.assertIsNone(resolve_delivery_line(
            self.delivery, self.order, [matching_position_wrong_line]
        ))

    def test_delivery_does_not_fall_back_across_customer_references(self):
        another_order = replace(self.order, customer_reference="SYN002")
        self.assertIsNone(resolve_delivery_line(
            self.delivery, another_order, [SalesLineIdentity(another_order, 3, 6)]
        ))

    def test_registered_source_and_company_scopes_remain_distinct(self):
        for scope in [
            replace(self.scope, source_instance="another-erp"),
            replace(self.scope, company_scope="another-company"),
        ]:
            other_order = replace(self.order, scope=scope)
            self.assertNotEqual(
                SalesLineIdentity(self.order, 3, 6).logical_key,
                SalesLineIdentity(other_order, 3, 6).logical_key,
            )
            self.assertIsNone(resolve_delivery_line(
                self.delivery, other_order, [SalesLineIdentity(other_order, 3, 6)]
            ))

    def test_customer_reference_case_is_preserved(self):
        lower_case = replace(self.order, customer_reference="syn001")
        self.assertNotEqual(self.order, lower_case)

    def test_delivery_unique_number_is_an_attribute_of_its_native_row(self):
        changed_reference = replace(self.delivery, unique_number=7)
        self.assertEqual(self.delivery.native_key, changed_reference.native_key)
        self.assertNotEqual(
            self.delivery.representation_key, changed_reference.representation_key
        )
        with self.assertRaisesRegex(ValueError, "duplicate native delivery"):
            validate_delivery_capture([self.delivery, changed_reference])

    def test_delivery_amendment_is_valid_in_a_separate_capture(self):
        validate_delivery_capture([self.delivery])
        validate_delivery_capture([replace(self.delivery, unique_number=7)])

    def test_header_print_state_is_retained_without_changing_native_line_key(self):
        another_print = replace(self.delivery, print_indicator="R")
        self.assertEqual(self.delivery.native_key, another_print.native_key)
        self.assertNotEqual(self.delivery.capture_row_key, another_print.capture_row_key)
        validate_delivery_capture([self.delivery, another_print])

    def test_delivery_suffix_and_kit_indicator_are_never_dropped(self):
        for another in [
            replace(self.delivery, delivery_suffix=1),
            replace(self.delivery, kit_indicator="K"),
        ]:
            self.assertNotEqual(self.delivery.native_key, another.native_key)
            self.assertNotEqual(
                self.delivery.representation_key, another.representation_key
            )

    def test_business_keys_survive_reused_legacy_projection_row_positions(self):
        another_delivery = replace(self.delivery, delivery_number=20002)
        # Both synthetic source rows may have the same V1 (sync_run_id,row_no).
        # Their original document identities must still produce distinct IDs.
        first_key = delivery_snapshot_observation_key("synthetic-export-1", self.delivery)
        second_key = delivery_snapshot_observation_key("synthetic-export-1", another_delivery)
        self.assertNotEqual(first_key, second_key)
        self.assertEqual(len({first_key, second_key, first_key, second_key}), 2)
        self.assertNotEqual(
            delivery_snapshot_observation_key("synthetic-export-1", self.delivery),
            delivery_snapshot_observation_key("synthetic-export-2", self.delivery),
        )

    def test_invalid_logical_reference_is_not_an_unassigned_zero(self):
        for value in [0, None, True, -1, 65536]:
            with self.assertRaises(ValueError):
                SalesLineIdentity(self.order, 3, value)

    def test_physical_unsigned_key_ranges_are_enforced(self):
        for updates in [
            {"delivery_suffix": 256},
            {"delivery_number": 0},
            {"item_number": 65536},
            {"kit_indicator": "KK"},
            {"kit_indicator": "🐈"},
            {"print_indicator": "\n"},
        ]:
            with self.assertRaises(ValueError):
                replace(self.delivery, **updates)

    def test_empty_revision_proves_no_missing_line_or_completion(self):
        self.assertEqual(validate_sales_revision(self.order, []), ())
        self.assertIsNone(resolve_delivery_line(self.delivery, self.order, []))


if __name__ == "__main__":
    unittest.main()
