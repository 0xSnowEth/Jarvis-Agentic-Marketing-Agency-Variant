import importlib
import os
import tempfile
import unittest
from unittest import mock


class CaptionTechniqueServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prev_backend = os.environ.get("JARVIS_DATA_BACKEND")
        self.prev_cwd = os.getcwd()
        os.environ["JARVIS_DATA_BACKEND"] = "json"
        os.chdir(self.temp_dir.name)

        import caption_technique_store
        import caption_technique_service

        self.caption_technique_store = importlib.reload(caption_technique_store)
        self.caption_technique_service = importlib.reload(caption_technique_service)
        self.caption_technique_store._store = None

    def tearDown(self):
        os.chdir(self.prev_cwd)
        if self.prev_backend is None:
            os.environ.pop("JARVIS_DATA_BACKEND", None)
        else:
            os.environ["JARVIS_DATA_BACKEND"] = self.prev_backend
        self.temp_dir.cleanup()

    def test_get_snapshot_payload_seeds_local_store(self):
        payload = self.caption_technique_service.get_caption_technique_snapshot_payload(force_refresh=False)

        self.assertEqual(payload["snapshot_key"], self.caption_technique_service.CAPTION_TECHNIQUE_SNAPSHOT_KEY)
        self.assertEqual(payload["refresh_status"], "seed")
        self.assertTrue(payload["source_links"])
        self.assertIn("hook_types", payload["techniques"])
        self.assertIn("search_rules", payload["techniques"])
        self.assertIn("carousel_rules", payload["techniques"])

        persisted = self.caption_technique_store.get_caption_technique_snapshot(
            self.caption_technique_service.CAPTION_TECHNIQUE_SNAPSHOT_KEY
        )
        self.assertEqual(persisted["snapshot_key"], payload["snapshot_key"])

    def test_refresh_snapshot_writes_last_good_when_sources_fetch(self):
        fake_sources = [
            {"title": "Meta Carousel Ads", "headings": ["Lead with one idea", "Use progression"], "url": "https://example.com/carousel"},
            {"title": "Meta Creative", "headings": ["Keep the opener compressed"], "url": "https://example.com/creative"},
        ]

        with mock.patch.object(
            self.caption_technique_service,
            "_fetch_source_snapshot",
            side_effect=fake_sources,
        ):
            payload = self.caption_technique_service.refresh_caption_technique_snapshot(force=True)

        self.assertEqual(payload["refresh_status"], "ok")
        self.assertTrue(payload["refreshed_at"])
        self.assertEqual(payload["last_good_refresh_at"], payload["refreshed_at"])
        self.assertEqual(payload["source_links"][0]["url"], "https://example.com/carousel")
        self.assertIn("Lead with one idea", payload["source_summary"])


if __name__ == "__main__":
    unittest.main()
