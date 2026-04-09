import importlib
import os
import tempfile
import unittest


class DraftResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prev_backend = os.environ.get("JARVIS_DATA_BACKEND")
        self.prev_cwd = os.getcwd()
        os.environ["JARVIS_DATA_BACKEND"] = "json"
        os.chdir(self.temp_dir.name)

        import draft_store

        self.draft_store = importlib.reload(draft_store)
        self.draft_store._store = None

    def tearDown(self):
        os.chdir(self.prev_cwd)
        if self.prev_backend is None:
            os.environ.pop("JARVIS_DATA_BACKEND", None)
        else:
            os.environ["JARVIS_DATA_BACKEND"] = self.prev_backend
        self.temp_dir.cleanup()

    def _save_minimal_draft(self, client_id: str, name: str, draft_id: str | None = None):
        payload = {
            "bundle_type": "image_post",
            "items": [{"asset_path": f"assets/{client_id}/{name}.jpg"}],
            "caption_mode": "ai",
            "caption_status": "ready",
            "caption_text": "Test caption",
            "hashtags": ["#jarvis"],
            "seo_keyword_used": "",
            "topic_hint": "",
        }
        if draft_id:
            payload["draft_id"] = draft_id
        self.draft_store.save_draft_payload(client_id, name, payload)

    def test_resolve_draft_payload_matches_normalized_name(self):
        self._save_minimal_draft("Stack_District", "burger squad", draft_id="draft-1")
        resolved = self.draft_store.resolve_draft_payload("Stack_District", draft_name="burger-squad")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["bundle_name"], "burger squad")

    def test_resolve_draft_payload_falls_back_to_only_saved_draft(self):
        self._save_minimal_draft("Veloura_Studio", "Fashionista", draft_id="draft-2")
        resolved = self.draft_store.resolve_draft_payload("Veloura_Studio", draft_name="fashion girl")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["bundle_name"], "Fashionista")


if __name__ == "__main__":
    unittest.main()
