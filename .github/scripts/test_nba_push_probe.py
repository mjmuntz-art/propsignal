"""Offline event tests, no network or notification credentials."""
import copy
import unittest
from nba_push_probe import stable_snapshot, compare_snapshots

class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.card = {
            "ok": True, "page": "card", "today": "2026-10-30",
            "publication": {"status": "APPROVED_CURRENT"},
            "refreshedAt": "9:00 AM",
            "tonight": [{"key": "g1-p1-pts-over", "player": "Example Player",
                "stat": "PTS", "date": "2026-10-30", "direction": "Over",
                "line": 19.5, "odds": -110, "book": "DK", "proj": 23.2,
                "grade": "A", "decision": "PLAY", "locked": False}],
            "recent": []
        }
    def test_first_snapshot_no_alert(self):
        self.assertEqual(compare_snapshots(None, stable_snapshot(self.card))["projections"], 0)
    def test_timestamp_refresh_no_alert(self):
        old = stable_snapshot(self.card)
        new = copy.deepcopy(self.card)
        new["refreshedAt"] = "9:30 AM"
        self.assertEqual(compare_snapshots(old, stable_snapshot(new))["projections"], 0)
    def test_changed_projection(self):
        old = stable_snapshot(self.card)
        new = copy.deepcopy(self.card)
        new["tonight"][0]["proj"] = 24.2
        self.assertEqual(compare_snapshots(old, stable_snapshot(new))["projections"], 1)
    def test_locked_play_without_duplicate_projection_alert(self):
        old = stable_snapshot(self.card)
        new = copy.deepcopy(self.card)
        new["tonight"][0]["locked"] = True
        changes = compare_snapshots(old, stable_snapshot(new))
        self.assertEqual(changes["locked"], 1)
        self.assertEqual(changes["projections"], 0)
    def test_new_grade(self):
        old = stable_snapshot(self.card)
        new = copy.deepcopy(self.card)
        new["recent"] = [{"key": "g1-p1-pts-over", "outcome": "HIT", "actual": 29, "units": 0.9}]
        self.assertEqual(compare_snapshots(old, stable_snapshot(new))["results"], 1)
    def test_stale_publication_does_not_alert(self):
        old = stable_snapshot(self.card)
        new = copy.deepcopy(self.card)
        new["publication"]["status"] = "CHECK"
        new["tonight"][0]["proj"] = 24.5
        self.assertEqual(compare_snapshots(old, stable_snapshot(new))["projections"], 0)
    def test_error_payload_rejected(self):
        with self.assertRaises(ValueError):
            stable_snapshot({"ok": False})

if __name__ == "__main__":
    unittest.main()
