import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest import mock


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload or {}
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class TrendResearchServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prev_backend = os.environ.get("JARVIS_DATA_BACKEND")
        self.prev_tavily_key = os.environ.get("TAVILY_API_KEY")
        self.prev_cwd = os.getcwd()
        os.environ["JARVIS_DATA_BACKEND"] = "json"
        os.environ["TAVILY_API_KEY"] = "test-key"
        os.chdir(self.temp_dir.name)

        import client_store
        import trend_research_service
        import caption_agent

        self.client_store = importlib.reload(client_store)
        self.trend_research_service = importlib.reload(trend_research_service)
        self.caption_agent = importlib.reload(caption_agent)
        self.trend_research_service._HEALTH.update(
            {
                "provider": "unknown",
                "available": False,
                "degraded": False,
                "last_success_at": "",
                "last_error": "",
            }
        )

    def tearDown(self):
        os.chdir(self.prev_cwd)
        if self.prev_backend is None:
            os.environ.pop("JARVIS_DATA_BACKEND", None)
        else:
            os.environ["JARVIS_DATA_BACKEND"] = self.prev_backend
        if self.prev_tavily_key is None:
            os.environ.pop("TAVILY_API_KEY", None)
        else:
            os.environ["TAVILY_API_KEY"] = self.prev_tavily_key
        self.temp_dir.cleanup()

    def test_search_recent_filters_old_results(self):
        now = datetime.now(timezone.utc)
        recent = now.isoformat()
        old = (now - timedelta(days=60)).isoformat()

        self.trend_research_service.TAVILY_API_KEY = "test-key"
        fake_tavily = ModuleType("tavily")

        class FakeTavilyClient:
            def __init__(self, api_key):
                self.api_key = api_key

            def search(self, **kwargs):
                return {
                    "results": [
                        {"title": "Recent post", "url": "https://example.com/recent", "snippet": "New trend", "published_at": recent},
                        {"title": "Old post", "url": "https://example.com/old", "snippet": "Old trend", "published_at": old},
                    ]
                }

        fake_tavily.TavilyClient = FakeTavilyClient

        with mock.patch.dict(sys.modules, {"tavily": fake_tavily}):
            pack = self.trend_research_service.search_recent("burger trends", max_results=5, recency_days=30)

        self.assertEqual(pack["provider"], "tavily")
        self.assertEqual(pack["total_results"], 1)
        self.assertTrue(pack["insufficient_recent_sources"])
        self.assertEqual(len(pack["results"]), 1)
        self.assertEqual(pack["results"][0]["title"], "Recent post")
        health = self.trend_research_service.get_trend_research_health()
        self.assertTrue(health["available"])
        self.assertEqual(health["provider"], "tavily")

    def test_extract_website_digest_parses_core_markers(self):
        html = """
        <html>
          <head>
            <title>Bakhourito | Premium Burger House</title>
            <meta name="description" content="Premium burgers and fast delivery." />
          </head>
          <body>
            <h1>Loaded burgers</h1>
            <h2>Late night delivery</h2>
            <p>Custom sauces, smash burgers, and premium combos.</p>
          </body>
        </html>
        """
        with mock.patch.object(
            self.trend_research_service.requests,
            "get",
            return_value=FakeResponse(text=html, status_code=200),
        ):
            digest = self.trend_research_service.extract_website_digest("https://example.com")

        self.assertEqual(digest["status"], "success")
        self.assertIn("Premium Burger House", digest["title"])
        self.assertIn("Premium burgers and fast delivery.", digest["meta_description"])
        self.assertIn("Loaded burgers", digest["h1"])
        self.assertIn("Late night delivery", digest["h2"])
        self.assertIn("burgers", " ".join(digest["brand_keywords"]))

    def test_trend_dossier_is_cached_and_persisted(self):
        class FakeStore:
            def __init__(self):
                self.brand = {
                    "business_name": "Bakhourito",
                    "industry": "food_beverage",
                    "target_audience": "late night burger fans",
                    "services": ["burgers", "combos"],
                    "seo_keywords": ["burger", "combo"],
                    "website_digest": {"brand_keywords": ["burgers"], "service_terms": ["combos"]},
                }
                self.client = {"profile_json": dict(self.brand)}
                self.saved = None
                self.trend_dossier = None

            def get_client(self, client_id):
                return dict(self.client)

            def get_brand_profile(self, client_id):
                return dict(self.brand)

            def save_client(self, client_id, payload):
                self.client = dict(payload)
                return payload

            def save_brand_profile(self, client_id, payload):
                self.saved = dict(payload)
                self.brand = dict(payload)
                return payload

            def get_trend_dossier(self, client_id):
                return dict(self.trend_dossier) if isinstance(self.trend_dossier, dict) else None

            def save_trend_dossier(self, client_id, payload):
                self.trend_dossier = dict(payload)
                return payload

        fake_store = FakeStore()
        snapshot_calls = []

        def fake_search_recent(query, max_results=None, recency_days=None, force_refresh=False):
            snapshot_calls.append((query, max_results, recency_days, force_refresh))
            return {
                "query": query,
                "provider": "tavily",
                "degraded": False,
                "results": [
                    {
                        "title": "Recent burger trend",
                        "url": "https://example.com/a",
                        "snippet": "Burger cravings are rising.",
                        "domain": "example.com",
                        "published_at": datetime.now(timezone.utc).isoformat(),
                        "provider": "tavily",
                    }
                ],
                "total_results": 1,
                "insufficient_recent_sources": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        with mock.patch.object(self.trend_research_service, "get_client_store", return_value=fake_store), \
            mock.patch.object(self.trend_research_service, "search_recent", side_effect=fake_search_recent):
            first = self.trend_research_service.get_client_trend_dossier("Bakhourito", force_refresh=False)
            first_call_count = len(snapshot_calls)
            second = self.trend_research_service.get_client_trend_dossier("Bakhourito", force_refresh=False)

        self.assertGreater(first_call_count, 0)
        self.assertEqual(len(snapshot_calls), first_call_count)
        self.assertEqual(first["client_id"], "Bakhourito")
        self.assertEqual(second["client_id"], "Bakhourito")
        self.assertEqual(fake_store.trend_dossier["source_links"][0], "https://example.com/a")




    def test_caption_generation_uses_trend_dossier(self):
        fake_brand_data = {
            "business_name": "Bakhourito",
            "industry": "food_beverage",
            "target_audience": "late night burger fans",
            "services": ["burgers", "combos"],
            "brand_voice": {"tone": "bold", "style": "energetic", "dialect": "english"},
            "brand_voice_examples": ["Fresh, loaded, and craveable."],
            "seo_keywords": ["burger", "combo"],
            "language_profile": {"caption_output_language": "english", "primary_language": "english"},
            "caption_defaults": {},
        }
        fake_dossier = {
            "status": "ok",
            "provider": "tavily",
            "recency_days": 30,
            "source_links": [{"title": "Trend", "url": "https://example.com/trend", "published_at": ""}],
            "recent_signals": ["burger", "combo"],
            "source_signals": ["burger", "combo"],
            "trend_angles": ["Late night cravings"],
            "hook_patterns": ["Lead with the late-night craving angle."],
            "topical_language": ["burger", "combo"],
            "anti_cliche_guidance": ["Avoid generic hype."],
            "source_coverage": "1 recent signal",
            "fetched_at": "2026-04-11T00:00:00+00:00",
            "expires_at": "2026-04-12T00:00:00+00:00",
        }

        captured = {}

        def fake_model_json_payload(system_prompt, user_prompt, *, max_tokens, response_schema=None):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            return (
                {
                    "caption": "Fresh burger caption",
                    "hashtags": ["#burger"],
                    "seo_keyword_used": "burger",
                    "direction_label": "Late night cravings",
                    "hook_style": "relatable problem",
                },
                [{"provider": "test", "model": "test-model", "attempt": 1, "status": "success"}],
                "",
            )

        with mock.patch.object(
            self.caption_agent,
            "_load_brand_profile_payload",
            return_value={"status": "success", "brand_data": fake_brand_data},
        ), mock.patch.object(
            self.caption_agent,
            "get_client_trend_dossier",
            return_value=fake_dossier,
        ), mock.patch.object(
            self.caption_agent,
            "analyze_media_bundle",
            return_value={
                "analysis_summary": "Single-frame product feature.",
                "visual_narrative": "Burger hero shot.",
                "emotional_tone": "craveable",
                "product_signals": ["burger"],
                "hook_opportunities": ["late night"],
                "cta_opportunities": ["order now"],
                "platform_fit_hints": ["strong first line"],
                "story_arc": "single-frame product feature",
            },
        ), mock.patch.object(
            self.caption_agent,
            "_call_model_json_payload",
            side_effect=fake_model_json_payload,
        ), mock.patch.object(
            self.caption_agent,
            "get_caption_technique_snapshot_payload",
            return_value={"headline_rules": ["Lead with a specific use case."]},
        ), mock.patch.object(
            self.caption_agent,
            "list_client_drafts",
            return_value={"bundles": {}},
        ):
            result = self.caption_agent.generate_caption_payload(
                "Bakhourito",
                "Burger launch",
                "image_post",
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["caption"], "Fresh burger caption")
        self.assertIn("Write one UNIQUE caption for Bakhourito.", captured["user_prompt"])
        self.assertIn("Brand: Bakhourito", captured["system_prompt"])
        self.assertIn("burger", f"{captured['system_prompt']} {captured['user_prompt']}".lower())


if __name__ == "__main__":
    unittest.main()
