import copy
import unittest
from src.route66_ext.services.learning_access_policy import membership_delta


def member(user, ident=None, date="fixture"):
    return {"id": ident or user, "user_id": user, "creation_date": date}


def receipt(action, user, ident=None, date="fixture"):
    return {"action": action, **member(user, ident, date)}


class LearningAccessPolicyTests(unittest.TestCase):
    def test_additions_deduplicate_and_sort(self):
        self.assertEqual(membership_delta([3, 1, 1], [member(1)], []),
            {"add_user_ids": [3], "remove_members": [], "preserved_manual_count": 1})

    def test_never_remove_manual_members(self):
        self.assertEqual(membership_delta([], [member(2)], [])["remove_members"], [])

    def test_remove_only_owned_members(self):
        result = membership_delta([], [member(1), member(2)], [receipt("added", 2)])
        self.assertEqual(result["remove_members"], [member(2)])
        self.assertEqual(result["preserved_manual_count"], 1)

    def test_removed_receipt_ends_ownership(self):
        self.assertEqual(membership_delta([], [member(2)], [receipt("added", 2), receipt("removed", 2)])["remove_members"], [])

    def test_recreated_row_never_adopted(self):
        for row in [member(2, date="new"), member(2, ident=99)]:
            self.assertEqual(membership_delta([], [row], [receipt("added", 2)])["remove_members"], [])

    def test_duplicate_ids_or_users_are_not_arbitrarily_selected(self):
        for rows in [[member(1), member(1)], [member(1), member(2, ident=1)], [member(1), member(1, ident=9)]]:
            with self.assertRaises(ValueError):
                membership_delta([], rows, [])

    def test_invalid_server_inputs_fail_closed(self):
        for args in [(None, [], []), ([True], [], []), ([], [member(True)], []),
                     ([], [], [receipt("invalid", 1)]), ([], [{}], []),
                     ([], [member(1, date="")], []), ([], [], [None])]:
            with self.assertRaisesRegex(ValueError, "Learning access needs administrator review"):
                membership_delta(*args)

    def test_outputs_do_not_alias_nested_inputs(self):
        row = {**member(2), "metadata": {"value": 1}}
        before = copy.deepcopy(row)
        result = membership_delta([], [row], [receipt("added", 2)])
        result["remove_members"][0]["metadata"]["value"] = 9
        self.assertEqual(row, before)

    def test_eligible_users_keep_access_and_other_section_union_is_input(self):
        self.assertEqual(membership_delta([2], [member(2)], [receipt("added", 2)])["remove_members"], [])

    def test_idempotent_receipt_and_deterministic_delta(self):
        args = ([3, 1], [member(2)], [receipt("added", 2), receipt("added", 2)])
        before = copy.deepcopy(args)
        self.assertEqual(membership_delta(*args), membership_delta(*args))
        self.assertEqual(args, before)
