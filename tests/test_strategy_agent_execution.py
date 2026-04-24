import importlib
import unittest
from unittest.mock import Mock, patch


class StrategyAgentExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import strategy_agent

        cls.strategy_agent = importlib.reload(strategy_agent)

    def _store(self):
        store = Mock()
        store.get_client = Mock(
            side_effect=lambda client_id: {"client_id": client_id, "profile_json": {"business_name": client_id}}
            if client_id == "Cedar Roast"
            else None
        )
        store.get_brand_profile = Mock(return_value={"business_name": "Cedar Roast", "city_market": "Kuwait City"})
        store.list_client_ids = Mock(return_value=["Cedar Roast"])
        return store

    def test_run_strategy_agent_hard_fails_when_live_research_is_insufficient(self):
        with patch.object(self.strategy_agent, "get_client_store", return_value=self._store()), patch.object(
            self.strategy_agent.StrategyWebSearchTool,
            "execute",
            side_effect=lambda *args, **kwargs: {
                "query": "cedar roast premium iced coffee",
                "provider": "tavily",
                "status": "insufficient_recent_sources",
                "results": [
                    {
                        "title": "Only one source",
                        "url": "https://example.com/article",
                        "published_at": "2026-04-22T00:00:00+00:00",
                        "snippet": "single weak source",
                    }
                ],
                "total": 1,
                "last_error": "",
            },
        ):
            result = self.strategy_agent.run_strategy_agent(
                "Cedar Roast",
                "next_30_days",
                "Premium iced coffee content plan",
                "",
                "next month plan",
            )

        self.assertIn("error", result)
        self.assertIn("live web research", result["error"].lower())

    def test_build_strategy_search_queries_broadens_brand_market_goal_inputs(self):
        queries = self.strategy_agent._build_strategy_search_queries(
            "Cedar Roast",
            {
                "business_name": "Cedar Roast",
                "industry": "specialty coffee",
                "city_market": "Kuwait City",
                "target_audience": "after-work professionals",
                "services": ["iced coffee", "pastries"],
            },
            "premium iced coffee content strategy",
            "next_30_days",
        )

        self.assertGreaterEqual(len(queries), 3)
        self.assertTrue(any("last 30 days" in query.lower() for query in queries))
        self.assertTrue(any("kuwait city" in query.lower() for query in queries))
        self.assertTrue(any("after-work professionals" in query.lower() for query in queries))

    def test_build_research_snapshot_from_multiple_queries_merges_domains(self):
        snapshot = self.strategy_agent._build_research_snapshot_from_search(
            [
                {
                    "query": "coffee kuwait demand",
                    "provider": "tavily",
                    "status": "success",
                    "results": [
                        {
                            "title": "Demand report",
                            "url": "https://one.example.com/a",
                            "published_at": "2026-04-22T00:00:00+00:00",
                            "snippet": "afternoon demand is climbing",
                        }
                    ],
                },
                {
                    "query": "coffee instagram trends kuwait",
                    "provider": "ddgs",
                    "status": "success",
                    "results": [
                        {
                            "title": "Instagram cafe trends",
                            "url": "https://two.example.org/b",
                            "published_at": "2026-04-21T00:00:00+00:00",
                            "snippet": "iced drinks are outperforming",
                        }
                    ],
                },
            ]
        )

        quality = self.strategy_agent._research_quality_report(snapshot)
        self.assertEqual(snapshot["status"], "success")
        self.assertIn("tavily", snapshot["provider"])
        self.assertIn("ddgs", snapshot["provider"])
        self.assertEqual(quality["domain_count"], 2)

    def test_run_strategy_agent_reuses_existing_matching_plan_id(self):
        store = self._store()
        existing_plan = {
            "plan_id": "plan-existing",
            "client_id": "Cedar Roast",
            "window": "next_30_days",
            "goal": "Premium iced coffee content plan",
            "requested_prompt": "Premium iced coffee content plan",
            "created_at": "2026-04-23T00:00:00+00:00",
            "updated_at": "2026-04-23T00:00:00+00:00",
            "items": [],
        }
        response_payload = {
            "summary": "Premium iced coffee push",
            "objective": "Sell more premium iced coffee",
            "timeframe": "next_30_days",
            "items": [
                {
                    "topic": f"Topic {idx}",
                    "format": "reel",
                    "platforms": ["instagram"],
                    "recommended_time": "Weekday 5:00 PM",
                    "hook_direction": "Lead with the payoff.",
                    "rationale": "Fresh demand signal.",
                    "source_signals": ["Signal"],
                    "source_links": [{"title": "Source", "url": f"https://example{idx}.com", "published_at": "2026-04-22T00:00:00+00:00"}],
                    "needs_review": False,
                    "confidence": 0.8,
                }
                for idx in range(1, 7)
            ],
        }
        saved_payloads: list[dict[str, object]] = []

        class FakeResponse:
            def __init__(self, content: str):
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        def fake_search(*_args, **_kwargs):
            return {
                "query": "q",
                "provider": "tavily",
                "status": "success",
                "results": [
                    {"title": "One", "url": "https://one.example.com/a", "published_at": "2026-04-22T00:00:00+00:00", "snippet": "one"},
                    {"title": "Two", "url": "https://two.example.com/b", "published_at": "2026-04-21T00:00:00+00:00", "snippet": "two"},
                    {"title": "Three", "url": "https://three.example.org/c", "published_at": "2026-04-20T00:00:00+00:00", "snippet": "three"},
                ],
            }

        with patch.object(self.strategy_agent, "get_client_store", return_value=store), patch.object(
            self.strategy_agent, "list_strategy_plans", return_value=[existing_plan]
        ), patch.object(
            self.strategy_agent.StrategyWebSearchTool,
            "execute",
            side_effect=fake_search,
        ), patch.object(
            self.strategy_agent, "get_trend_research_health", return_value={}
        ), patch.object(
            self.strategy_agent.StrategyAgent,
            "chat",
            return_value=FakeResponse(importlib.import_module("json").dumps(response_payload)),
        ), patch.object(
            self.strategy_agent, "save_strategy_plan", side_effect=lambda payload: saved_payloads.append(payload) or payload
        ):
            result = self.strategy_agent.run_strategy_agent(
                "Cedar Roast",
                "next_30_days",
                "Premium iced coffee content plan",
                "",
                "Premium iced coffee content plan",
            )

        self.assertEqual(result["plan_id"], "plan-existing")
        self.assertEqual(saved_payloads[0]["plan_id"], "plan-existing")

    def test_format_strategy_plan_messages_include_sources_and_opportunities(self):
        plan = {
            "plan_id": "plan-1",
            "client_id": "Cedar Roast",
            "window": "next_30_days",
            "summary": "Research shows strong afternoon iced coffee demand.",
            "objective": "Turn summer traffic into repeat iced drink visits.",
            "research_snapshot": {
                "status": "success",
                "provider": "tavily",
                "source_link_details": [
                    {
                        "title": "Kuwait summer drinks report",
                        "url": "https://news.example.com/kuwait-drinks",
                        "published_at": "2026-04-21T00:00:00+00:00",
                    },
                    {
                        "title": "Cafe trend report",
                        "url": "https://insights.example.org/cafe-trends",
                        "published_at": "2026-04-20T00:00:00+00:00",
                    },
                    {
                        "title": "After work food traffic",
                        "url": "https://market.example.net/after-work",
                        "published_at": "2026-04-19T00:00:00+00:00",
                    },
                ],
                "trend_angles": ["Afternoon cooldown ritual", "Premium iced coffee moments"],
                "source_signals": ["After-work search interest is climbing", "Cold drink content is outperforming"],
                "hook_patterns": ["Lead with the first sip payoff"],
            },
            "items": [
                {
                    "item_id": "item-1",
                    "topic": "After-work iced coffee reset",
                    "format": "reel",
                    "platforms": ["instagram", "facebook"],
                    "recommended_time": "Weekday 5:30 PM",
                    "hook_direction": "Open on the relief of the first cold sip after work.",
                    "rationale": "Matches the strongest recent summer signal.",
                    "source_signals": ["After-work search interest is climbing"],
                    "source_links": [
                        {
                            "title": "After work food traffic",
                            "url": "https://market.example.net/after-work",
                            "published_at": "2026-04-19T00:00:00+00:00",
                        }
                    ],
                    "needs_review": False,
                    "confidence": 0.84,
                },
                {
                    "item_id": "item-2",
                    "topic": "Premium iced latte comparison",
                    "format": "carousel",
                    "platforms": ["instagram"],
                    "recommended_time": "Weekend 1:00 PM",
                    "hook_direction": "Contrast the boring default order with the premium upgrade.",
                    "rationale": "Connects product education to the premium positioning.",
                    "source_signals": ["Cold drink content is outperforming"],
                    "source_links": [
                        {
                            "title": "Kuwait summer drinks report",
                            "url": "https://news.example.com/kuwait-drinks",
                            "published_at": "2026-04-21T00:00:00+00:00",
                        }
                    ],
                    "needs_review": False,
                    "confidence": 0.8,
                },
                {
                    "item_id": "item-3",
                    "topic": "Evening takeaway order push",
                    "format": "single_image",
                    "platforms": ["facebook"],
                    "recommended_time": "Thursday 7:00 PM",
                    "hook_direction": "Frame it as the easiest premium pickup before the night starts.",
                    "rationale": "Supports the after-work and evening ordering window.",
                    "source_signals": ["After-work search interest is climbing"],
                    "source_links": [
                        {
                            "title": "Cafe trend report",
                            "url": "https://insights.example.org/cafe-trends",
                            "published_at": "2026-04-20T00:00:00+00:00",
                        }
                    ],
                    "needs_review": True,
                    "confidence": 0.67,
                },
                {
                    "item_id": "item-4",
                    "topic": "Summer signature drink story",
                    "format": "reel",
                    "platforms": ["instagram", "facebook"],
                    "recommended_time": "Sunday 6:30 PM",
                    "hook_direction": "Tell the story of why this drink exists in Kuwait summer.",
                    "rationale": "Creates repeatable brand memory, not just one-off product hype.",
                    "source_signals": ["Cold drink content is outperforming"],
                    "source_links": [
                        {
                            "title": "Kuwait summer drinks report",
                            "url": "https://news.example.com/kuwait-drinks",
                            "published_at": "2026-04-21T00:00:00+00:00",
                        }
                    ],
                    "needs_review": False,
                    "confidence": 0.79,
                },
                {
                    "item_id": "item-5",
                    "topic": "Dessert pairing with iced coffee",
                    "format": "carousel",
                    "platforms": ["instagram"],
                    "recommended_time": "Monday 2:00 PM",
                    "hook_direction": "Make the pairing feel like a smarter summer order.",
                    "rationale": "Raises ticket value while staying relevant to the seasonal demand.",
                    "source_signals": ["Cold drink content is outperforming"],
                    "source_links": [
                        {
                            "title": "Cafe trend report",
                            "url": "https://insights.example.org/cafe-trends",
                            "published_at": "2026-04-20T00:00:00+00:00",
                        }
                    ],
                    "needs_review": False,
                    "confidence": 0.76,
                },
                {
                    "item_id": "item-6",
                    "topic": "Office order tray angle",
                    "format": "single_image",
                    "platforms": ["facebook", "instagram"],
                    "recommended_time": "Tuesday 11:30 AM",
                    "hook_direction": "Frame it as the easiest office save before the afternoon dip.",
                    "rationale": "Maps to a clear weekday office use case.",
                    "source_signals": ["After-work search interest is climbing"],
                    "source_links": [
                        {
                            "title": "After work food traffic",
                            "url": "https://market.example.net/after-work",
                            "published_at": "2026-04-19T00:00:00+00:00",
                        }
                    ],
                    "needs_review": False,
                    "confidence": 0.75,
                },
            ],
        }

        messages = self.strategy_agent.format_strategy_plan_messages(plan)

        self.assertGreaterEqual(len(messages), 4)
        self.assertIn("*What the research says*", messages[1])
        self.assertTrue(any("https://news.example.com/kuwait-drinks" in message for message in messages))
        self.assertTrue(any("Plan items" in message for message in messages))

    def test_resolve_strategy_model_name_prefixes_gpt_oss_to_groq(self):
        self.assertEqual(
            self.strategy_agent._resolve_strategy_model_name("openai/gpt-oss-120b"),
            "groq:openai/gpt-oss-120b",
        )

    def test_resolve_strategy_model_name_defaults_to_groq_llama(self):
        self.assertEqual(
            self.strategy_agent._resolve_strategy_model_name(""),
            "groq:llama-3.3-70b-versatile",
        )


if __name__ == "__main__":
    unittest.main()
