import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from asset_store import JsonAssetStore
from webhook_server import _asset_preview_payload


def _make_image_bytes(size=(860, 640), color=(180, 120, 80)):
    handle = BytesIO()
    image = Image.new("RGB", size, color)
    image.save(handle, format="PNG")
    return handle.getvalue()


class AssetPreviewDeliveryTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = tempfile.TemporaryDirectory()
        os.chdir(self._tmpdir.name)
        self.store = JsonAssetStore()

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmpdir.cleanup()

    def test_json_store_generates_thumbnail_and_metadata_sidecars(self):
        asset = self.store.save_asset("Preview Client", "hero.png", _make_image_bytes())

        client_dir = Path(self._tmpdir.name) / "assets" / "Preview Client"
        self.assertTrue((client_dir / "hero.jpg").exists())
        self.assertTrue((client_dir / "hero.jpg.thumb.jpg").exists())
        self.assertTrue((client_dir / "hero.jpg.meta.json").exists())

        listed = self.store.list_assets("Preview Client")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["filename"], "hero.jpg")
        self.assertTrue(str(listed[0]["metadata"].get("preview_version") or "").strip())
        self.assertIn("/assets/Preview%20Client/hero.jpg.thumb.jpg", self.store.preview_asset_url("Preview Client", asset))

    def test_asset_preview_payload_prefers_thumbnail_contract(self):
        asset = self.store.save_asset("Preview Client", "catalog.png", _make_image_bytes())

        with patch("webhook_server.get_asset_store", return_value=self.store):
            payload = _asset_preview_payload("Preview Client", asset)

        self.assertEqual(payload["preview_url"], payload["thumb_url"])
        self.assertIn("/assets/Preview%20Client/catalog.jpg.thumb.jpg", payload["thumb_url"])
        self.assertIn("/assets/Preview%20Client/catalog.jpg", payload["full_url"])
        self.assertIn("?v=", payload["thumb_url"])
        self.assertEqual(payload["version_token"], asset["metadata"]["preview_version"])


if __name__ == "__main__":
    unittest.main()
