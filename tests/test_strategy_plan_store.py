import importlib
import os
import tempfile
import unittest


class StrategyPlanStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prev_backend = os.environ.get("JARVIS_DATA_BACKEND")
        self.prev_cwd = os.getcwd()
        os.environ["JARVIS_DATA_BACKEND"] = "json"
        os.chdir(self.temp_dir.name)

        import strategy_plan_store
        import strategy_agent

        self.strategy_plan_store = importlib.reload(strategy_plan_store)
        self.strategy_agent = importlib.reload(strategy_agent)
        self.strategy_plan_store._store = None

    def tearDown(self):
        os.chdir(self.prev_cwd)
        if self.prev_backend is None:
            os.environ.pop("JARVIS_DATA_BACKEND", None)
        else:
            os.environ["JARVIS_DATA_BACKEND"] = self.prev_backend
        self.temp_dir.cleanup()

    def test_save_and_list_strategy_plan(self):
        saved = self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Veloura_Studio",
                "window": "next_7_days",
                "summary": "Weekly launch plan",
                "items": [
                    {
                        "topic": "Launch story",
                        "format": "carousel",
                        "platforms": ["facebook", "instagram"],
                        "recommended_time": "Tuesday 7:00 PM",
                    }
                ],
            }
        )
        self.assertEqual(saved["client_id"], "Veloura_Studio")
        self.assertEqual(len(self.strategy_plan_store.list_strategy_plans("Veloura_Studio")), 1)
        loaded = self.strategy_plan_store.get_strategy_plan(saved["plan_id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["summary"], "Weekly launch plan")

    def test_materialize_marks_items_as_suggested(self):
        saved = self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Stack_District",
                "window": "next_30_days",
                "summary": "Monthly menu push",
                "items": [
                    {"item_id": "item-1", "topic": "Menu spotlight", "format": "reel"},
                    {"item_id": "item-2", "topic": "Combo offer", "format": "carousel"},
                ],
            }
        )
        updated = self.strategy_agent.materialize_strategy_plan(saved["plan_id"], ["item-1"])
        item_statuses = {item["item_id"]: item["status"] for item in updated["items"]}
        self.assertEqual(updated["status"], "materialized")
        self.assertEqual(item_statuses["item-1"], "suggested")
        self.assertEqual(item_statuses["item-2"], "planned")

    def test_delete_single_strategy_plan(self):
        first = self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Northline_Dental",
                "summary": "First plan",
                "items": [{"topic": "Case study", "format": "carousel"}],
            }
        )
        second = self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Northline_Dental",
                "summary": "Second plan",
                "items": [{"topic": "Clinic tour", "format": "reel"}],
            }
        )
        removed = self.strategy_plan_store.delete_strategy_plan(first["plan_id"])
        remaining = self.strategy_plan_store.list_strategy_plans("Northline_Dental")
        self.assertTrue(removed)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["plan_id"], second["plan_id"])

    def test_delete_client_strategy_plans(self):
        self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Harbor_Pilates",
                "summary": "Week one",
                "items": [{"topic": "Mobility routine", "format": "reel"}],
            }
        )
        self.strategy_plan_store.save_strategy_plan(
            {
                "client_id": "Harbor_Pilates",
                "summary": "Week two",
                "items": [{"topic": "Instructor intro", "format": "story"}],
            }
        )
        removed = self.strategy_plan_store.delete_client_strategy_plans("Harbor_Pilates")
        self.assertEqual(removed, 2)
        self.assertEqual(self.strategy_plan_store.list_strategy_plans("Harbor_Pilates"), [])


if __name__ == "__main__":
    unittest.main()
