"""Offline synthetic boundary tests; no application, DB, network or credentials."""
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

from src.route66_ext.services.attendance_policy import CHECKIN_TOKEN_TTL, SessionPolicy, counts_as_completed_session, decide_checkin, missing_attendance_status, summarize_attendance, token_is_current


class AttendancePolicyTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 14, 2, tzinfo=timezone.utc)
        self.policy = SessionPolicy(self.start, self.start + timedelta(hours=2))

    def scan(self, minutes, **kwargs):
        return decide_checkin(self.policy, arrived_at=self.start + timedelta(minutes=minutes), **kwargs)

    def test_early_window_is_inclusive(self):
        self.assertEqual(self.scan(-30).outcome, "accepted")
        result = decide_checkin(self.policy, arrived_at=self.start - timedelta(minutes=30, microseconds=1))
        self.assertEqual((result.outcome, result.computed_status), ("not_open", None))

    def test_grace_is_not_the_entry_cutoff(self):
        for minutes, expected in ((-30, "present"), (0, "present"), (10, "present"), (10.00001, "late"), (20, "late")):
            with self.subTest(minutes=minutes):
                result = self.scan(minutes)
                self.assertEqual((result.outcome, result.computed_status), ("accepted", expected))

    def test_first_entry_after_cutoff_has_no_recordable_status(self):
        result = self.scan(20.00001)
        self.assertEqual((result.outcome, result.computed_status), ("entry_cutoff", None))

    def test_existing_entry_bypasses_only_first_entry_cutoff(self):
        self.assertEqual(self.scan(60, has_record=True).computed_status, "late")
        self.assertEqual(self.scan(121, has_record=True).outcome, "ended")
        self.assertEqual(self.scan(-31, has_record=True).outcome, "not_open")

    def test_heartbeat_can_be_first_evidence_after_entry_cutoff(self):
        self.assertEqual(self.scan(60, kind="heartbeat").computed_status, "late")
        self.assertEqual(self.scan(121, kind="heartbeat").outcome, "ended")

    def test_end_is_inclusive_for_scans_but_completed_for_reporting(self):
        self.assertEqual(self.scan(120, kind="heartbeat").outcome, "accepted")
        self.assertEqual(self.scan(120.00001, kind="heartbeat").outcome, "ended")
        self.assertEqual(missing_attendance_status(self.policy, now=self.policy.ends_at), "absent")
        self.assertTrue(counts_as_completed_session(self.policy, now=self.policy.ends_at))

    def test_no_class_blocks_every_scan_and_excludes_denominator(self):
        policy = replace(self.policy, state="no_class")
        for minutes in (-31, 0, 15, 60, 121):
            for kind in ("entry", "heartbeat"):
                for existing in (False, True):
                    with self.subTest(minutes=minutes, kind=kind, existing=existing):
                        at = self.start + timedelta(minutes=minutes)
                        result = decide_checkin(policy, arrived_at=at, kind=kind, has_record=existing)
                        self.assertEqual((result.outcome, result.computed_status), ("no_class", None))
                        self.assertEqual(missing_attendance_status(policy, now=at), "no_class")
                        self.assertFalse(counts_as_completed_session(policy, now=at))

    def test_policy_is_immutable_and_restoration_only_changes_projection(self):
        with self.assertRaises(FrozenInstanceError):
            self.policy.state = "no_class"
        no_class = replace(self.policy, state="no_class")
        restored = replace(no_class, state="scheduled")
        self.assertFalse(counts_as_completed_session(no_class, now=self.policy.ends_at))
        self.assertTrue(counts_as_completed_session(restored, now=self.policy.ends_at))
        self.assertEqual(self.policy.state, "scheduled")

    def test_server_arrival_not_lock_completion_determines_status(self):
        arrived = self.start + timedelta(minutes=10)
        lock_completed = arrived + timedelta(seconds=5)
        self.assertEqual(decide_checkin(self.policy, arrived_at=arrived).computed_status, "present")
        self.assertEqual(decide_checkin(self.policy, arrived_at=lock_completed).computed_status, "late")

    def test_timezone_offset_is_the_same_instant(self):
        bangkok = timezone(timedelta(hours=7))
        local = replace(self.policy, starts_at=self.start.astimezone(bangkok), ends_at=self.policy.ends_at.astimezone(bangkok))
        self.assertEqual(decide_checkin(local, arrived_at=self.start), decide_checkin(self.policy, arrived_at=self.start.astimezone(bangkok)))

    def test_dst_fold_uses_instants_not_wall_clock_subtraction(self):
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("America/New_York")
        start = datetime(2026, 11, 1, 1, 10, tzinfo=zone, fold=0)
        end = datetime(2026, 11, 1, 1, 50, tzinfo=zone, fold=1)
        policy = SessionPolicy(start, end)
        self.assertEqual(decide_checkin(policy, arrived_at=datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=0)).computed_status, "present")
        self.assertEqual(decide_checkin(policy, arrived_at=datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=1)).outcome, "entry_cutoff")

    def test_legacy_naive_timestamps_are_utc(self):
        naive = replace(self.policy, starts_at=self.start.replace(tzinfo=None), ends_at=self.policy.ends_at.replace(tzinfo=None))
        self.assertEqual(decide_checkin(naive, arrived_at=self.start.replace(tzinfo=None)), decide_checkin(self.policy, arrived_at=self.start))

    def test_equal_grace_and_cutoff_is_valid(self):
        policy = replace(self.policy, grace_minutes=0, late_threshold_minutes=0)
        self.assertEqual(decide_checkin(policy, arrived_at=self.start).computed_status, "present")
        self.assertEqual(decide_checkin(policy, arrived_at=self.start + timedelta(microseconds=1)).outcome, "entry_cutoff")

    def test_invalid_policy_fails_closed(self):
        for changes in ({"state": "cancelled"}, {"grace_minutes": -1}, {"grace_minutes": True}, {"late_threshold_minutes": 9}, {"late_threshold_minutes": 20.5}, {"ends_at": self.start}, {"ends_at": self.start - timedelta(seconds=1)}, {"starts_at": "2026-10-14"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.policy, **changes)

    def test_invalid_scan_context_fails_closed(self):
        for kwargs in ({"kind": "exit"}, {"has_record": 1}, {"has_record": "false"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.scan(0, **kwargs)
        with self.assertRaises(ValueError):
            decide_checkin(self.policy, arrived_at="now")

    def test_qr_expiry_is_exclusive(self):
        expiry = self.start + CHECKIN_TOKEN_TTL
        self.assertTrue(token_is_current(expires_at=expiry, arrived_at=expiry - timedelta(microseconds=1)))
        self.assertFalse(token_is_current(expires_at=expiry, arrived_at=expiry))
        self.assertFalse(token_is_current(expires_at=expiry, arrived_at=expiry + timedelta(microseconds=1)))
        self.assertEqual(CHECKIN_TOKEN_TTL.total_seconds(), 120)

    def test_absence_is_not_projected_before_completion(self):
        for minutes, expected in ((-1, "upcoming"), (0, "unrecorded"), (119, "unrecorded"), (120, "absent")):
            with self.subTest(minutes=minutes):
                self.assertEqual(missing_attendance_status(self.policy, now=self.start + timedelta(minutes=minutes)), expected)

    def test_future_session_excluded(self):
        self.assertFalse(counts_as_completed_session(self.policy, now=self.start))

    def test_withdrawal_boundary_is_inclusive(self):
        now = self.policy.ends_at
        self.assertTrue(counts_as_completed_session(self.policy, now=now, withdrawn_at=self.start))
        self.assertFalse(counts_as_completed_session(self.policy, now=now, withdrawn_at=self.start - timedelta(microseconds=1)))
        self.assertTrue(counts_as_completed_session(self.policy, now=now, withdrawn_at=self.start + timedelta(seconds=1)))

    def test_empty_denominator_has_no_percentage_or_risk(self):
        summary = summarize_attendance(0, [])
        self.assertIsNone(summary.percent)
        self.assertFalse(summary.at_risk)

    def test_missing_records_are_absent_and_excused_and_late_count(self):
        summary = summarize_attendance(5, iter(("present", "late", "excused", "absent")))
        self.assertEqual((summary.present, summary.late, summary.excused, summary.absent), (1, 1, 1, 2))
        self.assertEqual(summary.percent, 60.0)
        self.assertTrue(summary.at_risk)

    def test_risk_is_strictly_below_configured_threshold(self):
        records = ["present"] * 4
        self.assertFalse(summarize_attendance(5, records).at_risk)
        self.assertTrue(summarize_attendance(5, records, at_risk_threshold=81).at_risk)
        self.assertFalse(summarize_attendance(5, [], at_risk_threshold=0).at_risk)

    def test_two_decimal_rounding_precedes_risk_test(self):
        summary = summarize_attendance(3, ["present", "late"], at_risk_threshold=66.67)
        self.assertEqual(summary.percent, 66.67)
        self.assertFalse(summary.at_risk)

    def test_invalid_summary_fails_closed(self):
        for total, statuses in ((-1, []), (True, []), (1.0, []), (0, ["present"]), (1, ["no_class"]), (1, ["upcoming"]), (1, ["unknown"])):
            with self.subTest(total=total, statuses=statuses), self.assertRaises(ValueError):
                summarize_attendance(total, statuses)
        for threshold in (-1, 101, float("nan"), float("inf"), True, "80"):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                summarize_attendance(1, [], at_risk_threshold=threshold)

    def test_summary_does_not_mutate_records(self):
        records = ["present", "excused"]
        summarize_attendance(3, records)
        self.assertEqual(records, ["present", "excused"])


if __name__ == "__main__":
    unittest.main()

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
