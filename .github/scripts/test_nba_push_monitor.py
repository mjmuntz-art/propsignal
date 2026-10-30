import copy
import unittest
from nba_push_monitor import current_checkpoint, changes

class TestMonitor(unittest.TestCase):
    def setUp(self):
        self.card={"ok":True,"page":"card","today":"2026-10-30",
          "publication":{"status":"APPROVED_CURRENT"},
          "tonight":[{"key":"play1","date":"2026-10-30","player":"Sample Player",
             "stat":"PTS","direction":"Over","line":19.5,"proj":23.2,
             "odds":-110,"decision":"PLAY","locked":False}],
          "recent":[]}
    def test_first_run_sets_baseline_without_notification(self):
        now=current_checkpoint(self.card,None)
        self.assertEqual(changes(None,now)["projections"],0)
    def test_timestamp_and_odds_changes_are_ignored(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card)
        fresh["refreshedAt"]="10:30 AM"
        fresh["tonight"][0]["odds"]=-115
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["projections"],0)
    def test_material_projection(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card)
        fresh["tonight"][0]["proj"]=25.2
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["projections"],1)
    def test_new_lock_not_projection(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card);fresh["tonight"][0]["locked"]=True
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["locked"],1)
        self.assertEqual(changes(before,now)["projections"],0)
    def test_grade_only_once(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card)
        fresh["recent"]=[{"key":"play1","outcome":"HIT","actual":28,"units":0.9}]
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["results"],1)
        later=current_checkpoint(fresh,now)
        self.assertEqual(changes(now,later)["results"],0)
    def test_stale_slates_suppressed(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card)
        fresh["publication"]["status"]="CHECK"
        fresh["tonight"][0]["proj"]=30.4
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["projections"],0)
    def test_no_duplicate_on_repeated_run(self):
        before=current_checkpoint(self.card,None)
        after=current_checkpoint(self.card,before)
        self.assertEqual(changes(before,after)["projections"],0)
    def test_new_slate(self):
        before=current_checkpoint(self.card,None)
        fresh=copy.deepcopy(self.card)
        fresh["today"]="2026-10-31";fresh["tonight"][0]["date"]="2026-10-31"
        fresh["tonight"][0]["key"]="play2"
        now=current_checkpoint(fresh,before)
        self.assertEqual(changes(before,now)["projections"],1)

if __name__ == "__main__":
    unittest.main()
