import unittest
from unittest.mock import patch

import caption_agent
from caption_playbook import build_caption_playbook


class CaptionAgentFrontierTests(unittest.TestCase):
    def test_call_model_json_payload_retries_without_response_format_when_provider_rejects_it(self):
        class FakeMessage:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMessage(content)

        class FakeResponse:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeCompletions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if "response_format" in kwargs:
                    raise ValueError("response_format is not supported for this model")
                return FakeResponse('{"hooks":[{"variant_id":"variant_1","hook_style":"contrast","hook_text":"Hook","rationale":"Why"}]}')

        fake_client = type("FakeClient", (), {"chat": type("FakeChat", (), {"completions": FakeCompletions()})()})()

        with patch.object(caption_agent, "_resolve_model_routes", return_value=[("groq", fake_client, "openai/gpt-oss-120b")]):
            payload, attempts, error = caption_agent._call_model_json_payload("system", "user", max_tokens=120)

        self.assertEqual(payload["hooks"][0]["hook_text"], "Hook")
        self.assertEqual(error, "")
        self.assertEqual(attempts[0]["status"], "success")
        self.assertFalse(attempts[0]["json_mode"])

    def test_call_model_json_payload_repairs_non_json_prose_response(self):
        class FakeMessage:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMessage(content)

        class FakeResponse:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            def create(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse("Here are your hooks in plain text with no JSON at all.")
                return FakeResponse('{"hooks":[{"variant_id":"variant_1","hook_style":"mood-led local","hook_text":"برد الكويت له مزاجه","rationale":"Native and local"}]}')

        fake_client = type("FakeClient", (), {"chat": type("FakeChat", (), {"completions": FakeCompletions()})()})()

        with patch.object(caption_agent, "_resolve_model_routes", return_value=[("groq", fake_client, "openai/gpt-oss-120b")]):
            payload, attempts, error = caption_agent._call_model_json_payload("system", "user", max_tokens=120)

        self.assertEqual(payload["hooks"][0]["hook_style"], "mood-led local")
        self.assertEqual(error, "")
        self.assertEqual(attempts[0]["status"], "repaired_success")

    def _brand_payload(self):
        return {
            "status": "success",
            "brand_data": {
                "business_name": "Cedar Roast",
                "main_language": "arabic",
                "city_market": "Kuwait City",
                "target_audience": "Young professionals and students in Kuwait",
                "services": ["iced chocolate", "cold brew", "specialty coffee"],
                "brand_voice": {"tone": "premium, local, sharp"},
                "brand_voice_examples": ["Short, premium, local copy."],
            },
        }

    def test_generate_caption_payload_returns_caption_single_pass(self):
        events: list[dict] = []
        single_caption = {
            "caption": "هل جرّبت آيسد شوكولاتة Cedar Roast في الكويت؟",
            "hashtags": ["#CedarRoast", "#IcedChocolate", "#KuwaitCity"],
            "seo_keyword_used": "iced chocolate",
            "hook_style": "mood-led local",
            "direction_label": "Iced chocolate summer push",
        }
        ranked = [
            {
                **single_caption,
                "variant_id": "variant_1",
                "client_name": "Cedar Roast",
                "selected_hook_family": "mood-led local",
                "hook_text": "",
                "rationale": "",
                "quality_gate": {
                    "score": 88.4,
                    "passed": True,
                    "threshold": 78.0,
                    "dimensions": {"visual_grounding": 90, "brand_voice_fidelity": 88, "audience_platform_fit": 84, "realism": 92, "hook_strength": 86, "trend_relevance": 79},
                    "dimension_weights": {},
                    "failures": [],
                    "verdict": "Approved",
                    "notes": {},
                },
            },
        ]

        with patch.object(caption_agent, "_load_brand_profile_payload", return_value=self._brand_payload()), patch.object(
            caption_agent,
            "get_client_trend_dossier",
            return_value={"topical_language": ["صيف الكويت"], "hook_patterns": ["سؤال قصير"], "trend_angles": ["Summer drinks"]},
        ), patch.object(
            caption_agent,
            "analyze_media_bundle",
            return_value={
                "analysis_summary": "Three images focused on iced drinks.",
                "product_signals": ["iced chocolate", "iced drinks"],
                "hook_opportunities": ["summer", "Kuwait heat"],
                "story_arc": "multi-frame product story",
            },
        ), patch.object(
            caption_agent,
            "_call_model_json_payload",
            return_value=(single_caption, [{"provider": "groq", "model": "gpt-oss-120b", "attempt": 1, "status": "success"}], ""),
        ), patch.object(
            caption_agent,
            "_call_anthropic_json_payload",
            return_value=({}, [], "Anthropic key not configured."),
        ), patch.object(
            caption_agent,
            "get_caption_technique_snapshot_payload",
            return_value={"headline_rules": ["Lead with a useful first line."]},
        ), patch.object(
            caption_agent,
            "list_client_drafts",
            return_value={"bundles": {}},
        ), patch.object(
            caption_agent,
            "rank_caption_variants",
            return_value=ranked,
        ):
            result = caption_agent.generate_caption_payload(
                "Cedar Roast",
                "WhatsApp Carousel 2026-04-16 09:05:31 Cedar Roast carousel concept",
                "carousel_post",
                recent_captions=["Old caption"],
                progress_callback=events.append,
                operator_brief="launch iced drinks for summer",
                media_type_context="image_carousel",
                media_assets=[{"filename": "hero.jpg", "kind": "image"}],
            )

        self.assertEqual(result["caption"], single_caption["caption"])
        self.assertIn("analysis_summary", result)
        self.assertEqual(result["generation_state"], "success")
        self.assertEqual(result["generation_source"], "model_generated")
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["hidden_variants"], [])
        # Quality gate is always advisory (passed=True)
        self.assertTrue(result["quality_gate"]["passed"])
        # Single-pass events: no scoring_started, no score_passed/score_failed
        event_names = [event["event"] for event in events]
        self.assertIn("media_analysis_started", event_names)
        self.assertIn("drafting_started", event_names)
        self.assertIn("finalized", event_names)

    def test_internal_workflow_labels_are_stripped_from_topic(self):
        self.assertEqual(
            caption_agent._strip_internal_workflow_labels("WhatsApp Carousel 2026-04-16 09:05:31 Cedar Roast carousel concept"),
            "Cedar Roast",
        )

    def test_normalize_caption_payload_strips_leading_punctuation(self):
        normalized = caption_agent.normalize_caption_payload(
            {
                "caption": ": مرحبا بك في Cedar Roast",
                "hashtags": ["#CedarRoast"],
            }
        )

        self.assertEqual(normalized["caption"], "مرحبا بك في Cedar Roast")
        self.assertEqual(normalized["hashtags"], ["#CedarRoast"])

    def test_fallback_variants_avoid_internal_labels(self):
        variants = caption_agent._build_fallback_variants(
            {
                "client_name": "Cedar Roast",
                "content_goal": "WhatsApp Carousel Cedar Roast carousel concept",
                "profile": {
                    "business_name": "Cedar Roast",
                    "market": "Kuwait City",
                    "offers": ["iced chocolate", "cold brew"],
                },
                "platform_strategy": {"language_mode": "arabic"},
                "media_analysis": {},
            }
        )
        joined = " ".join(item["caption"] for item in variants).lower()
        self.assertNotIn("whatsapp", joined)
        self.assertNotIn("concept", joined)
        self.assertNotIn("carousel", joined)

    def test_generate_mode_single_pass_does_not_reuse_hidden_variants(self):
        single_caption = {
            "caption": "Fresh regenerated caption.",
            "hashtags": ["#CedarRoast"],
            "seo_keyword_used": "iced chocolate",
            "hook_style": "contrast/selectivity",
            "direction_label": "Sharper retry",
        }
        ranked = [
            {
                **single_caption,
                "variant_id": "variant_1",
                "client_name": "Cedar Roast",
                "selected_hook_family": "contrast/selectivity",
                "hook_text": "",
                "rationale": "",
                "quality_gate": {
                    "score": 84.0,
                    "passed": True,
                    "threshold": 78.0,
                    "dimensions": {},
                    "dimension_weights": {},
                    "failures": [],
                    "verdict": "Approved",
                    "notes": {},
                },
            }
        ]

        with patch.object(caption_agent, "_load_brand_profile_payload", return_value=self._brand_payload()), patch.object(
            caption_agent,
            "get_client_trend_dossier",
            return_value={"topical_language": ["صيف الكويت"], "hook_patterns": ["سؤال قصير"], "trend_angles": ["Summer drinks"]},
        ), patch.object(
            caption_agent,
            "analyze_media_bundle",
            return_value={
                "analysis_summary": "Three images focused on iced drinks.",
                "product_signals": ["iced chocolate", "iced drinks"],
                "hook_opportunities": ["summer", "Kuwait heat"],
                "story_arc": "hero item with supporting frames",
            },
        ), patch.object(
            caption_agent,
            "_call_model_json_payload",
            return_value=(single_caption, [{"provider": "groq", "model": "gpt-oss-120b", "attempt": 1, "status": "success"}], ""),
        ), patch.object(
            caption_agent,
            "_call_anthropic_json_payload",
            return_value=({}, [], "Anthropic key not configured."),
        ), patch.object(
            caption_agent,
            "get_caption_technique_snapshot_payload",
            return_value={"headline_rules": ["Avoid brand-name openers."]},
        ), patch.object(
            caption_agent,
            "list_client_drafts",
            return_value={"bundles": {}},
        ), patch.object(
            caption_agent,
            "rank_caption_variants",
            return_value=ranked,
        ):
            result = caption_agent.generate_caption_payload(
                "Cedar Roast",
                "iced drinks push",
                "carousel_post",
                operator_brief="make it sharper",
                media_type_context="image_carousel",
                media_assets=[{"filename": "hero.jpg", "kind": "image"}],
                prior_hidden_variants=[
                    {
                        "caption": "SHOULD NOT BE REUSED",
                        "hashtags": ["#Hidden"],
                        "seo_keyword_used": "hidden",
                        "status": "success",
                        "direction_label": "Hidden",
                    }
                ],
                mode="generate",
                current_caption="Old weak caption",
                prior_best_caption="Old weak caption",
                avoid_repeat_failures=["Weak hook strength"],
            )

        self.assertEqual(result["caption"], "Fresh regenerated caption.")
        self.assertEqual(result["hidden_variants"], [])
        # Quality gate is always advisory
        self.assertTrue(result["quality_gate"]["passed"])

    def test_generation_unavailable_hides_fallback_copy_from_operator_payload(self):
        with patch.object(caption_agent, "_load_brand_profile_payload", return_value=self._brand_payload()), patch.object(
            caption_agent,
            "get_client_trend_dossier",
            return_value={"topical_language": ["صيف الكويت"], "hook_patterns": ["سؤال قصير"], "trend_angles": ["Summer drinks"]},
        ), patch.object(
            caption_agent,
            "analyze_media_bundle",
            return_value={
                "analysis_summary": "Three images focused on iced drinks.",
                "product_signals": ["iced chocolate", "iced drinks"],
                "hook_opportunities": ["summer", "Kuwait heat"],
                "story_arc": "hero item with supporting frames",
            },
        ), patch.object(
            caption_agent,
            "_call_model_json_payload",
            return_value=({}, [{"provider": "groq", "model": "gpt-oss-120b", "attempt": 1, "status": "error"}], "Provider failed"),
        ), patch.object(
            caption_agent,
            "_call_anthropic_json_payload",
            return_value=({}, [], "Anthropic key not configured."),
        ), patch.object(
            caption_agent,
            "get_caption_technique_snapshot_payload",
            return_value={"headline_rules": ["Avoid generic first lines."]},
        ), patch.object(
            caption_agent,
            "list_client_drafts",
            return_value={"bundles": {}},
        ):
            result = caption_agent.generate_caption_payload(
                "Cedar Roast",
                "iced drinks push",
                "carousel_post",
                operator_brief="make it sharper",
                media_type_context="image_carousel",
                media_assets=[{"filename": "hero.jpg", "kind": "image"}],
            )

        self.assertEqual(result["status"], "generation_unavailable")
        self.assertEqual(result["generation_state"], "generation_unavailable")
        self.assertEqual(result["caption"], "")
        self.assertTrue(result["used_fallback"])
        self.assertTrue(result["internal_fallback_variants"])

    def test_unified_prompt_differs_between_generate_and_revise_modes(self):
        base_context = {
            "client_name": "Cedar Roast",
            "content_goal": "iced drinks push",
            "operator_brief": "make it premium",
            "profile": {
                "business_name": "Cedar Roast",
                "market": "Kuwait City",
                "audience": "Young professionals",
                "offers": ["iced chocolate", "cold brew"],
                "voice_rules": ["premium", "local"],
            },
            "platform_strategy": {"language_mode": "arabic", "format": "carousel"},
            "media_analysis": {
                "analysis_summary": "Three-frame iced drinks story.",
                "hook_opportunities": ["your afternoon reset"],
                "story_arc": "hero item with supporting frames",
                "product_signals": ["iced chocolate"],
            },
            "recent_captions": ["Old opener"],
            "story_angles": ["Afternoon reset"],
            "hook_terms": ["your afternoon reset"],
            "trend_terms": ["kuwait summer"],
            "prompt_profile": {"business_name": "Cedar Roast"},
            "anchor_requirements": "Mention Cedar Roast clearly.",
            "current_caption": "Current weak caption",
            "prior_best_caption": "Previous caption",
            "avoid_repeat_failures": ["Weak hooks"],
            "playbook": {"variant_briefs": [{"hook_style": "contrast", "instruction": "Lead with tension"}]},
        }

        generate_system, generate_user = caption_agent._build_unified_caption_prompt(
            base_context, mode="generate",
        )
        revise_system, revise_user = caption_agent._build_unified_caption_prompt(
            {**base_context, "current_caption": "Current weak caption"}, mode="revise",
        )

        # Generate mode should not include REVISE directive
        self.assertNotIn("REVISE THIS DRAFT", generate_user)
        # Revise mode should include the current caption for revision
        self.assertIn("REVISE THIS DRAFT", revise_user)
        self.assertIn("Current weak caption", revise_user)
        # Both should include the brand name and content goal
        self.assertIn("Cedar Roast", generate_user)
        self.assertIn("Cedar Roast", revise_user)
        self.assertIn("iced drinks push", generate_user)

    def test_caption_playbook_builds_examples_and_variant_briefs_for_coffee(self):
        playbook = build_caption_playbook(
            profile={
                "industry": "food_beverage",
                "offer_summary": "iced chocolate, cold brew, specialty coffee",
                "seo_keywords": ["coffee"],
                "website_digest": {"service_terms": ["espresso", "latte"]},
            },
            language_mode="arabic",
            media_analysis={"hook_opportunities": ["your afternoon reset", "one mood three frames"]},
            attempt_label="hook-led punchier",
            variant_count=4,
        )

        self.assertEqual(playbook["industry_bucket"], "coffee")
        self.assertEqual(playbook["language_bucket"], "arabic")
        self.assertTrue(playbook["examples"])
        self.assertEqual(len(playbook["variant_briefs"]), 4)
        self.assertEqual(playbook["variant_briefs"][0]["variant_id"], "variant_1")
        self.assertTrue(playbook["variant_briefs"][0]["hook_style"])


    def test_auto_close_truncated_json_recovers_partial_hooks(self):
        truncated = '{"hooks":[{"variant_id":"v1","hook_style":"contrast","hook_text":"Hook","rationale":"Why"}],"extra":"val'
        result = caption_agent._auto_close_truncated_json(truncated)
        self.assertTrue(result)
        parsed = __import__("json").loads(result)
        self.assertEqual(parsed["hooks"][0]["hook_text"], "Hook")

    def test_auto_close_truncated_json_recovers_mid_array(self):
        truncated = '{"variants":[{"variant_id":"v1","caption":"Hello","hashtags":["#test"],"seo_keyword_used":"test","direction_label":"d","rationale":"r","selected_hook_family":"contrast","hook_text":"hook'
        result = caption_agent._auto_close_truncated_json(truncated)
        self.assertTrue(result)
        parsed = __import__("json").loads(result)
        self.assertIn("variants", parsed)
        self.assertEqual(parsed["variants"][0]["caption"], "Hello")

    def test_auto_close_returns_empty_for_no_json(self):
        result = caption_agent._auto_close_truncated_json("plain text with no braces")
        self.assertEqual(result, "")

    def test_auto_close_returns_empty_for_balanced_json(self):
        result = caption_agent._auto_close_truncated_json('{"key": "value"}')
        self.assertEqual(result, "")

    def test_extract_caption_json_recovers_truncated_output(self):
        truncated = '{"hooks":[{"variant_id":"v1","hook_style":"contrast","hook_text":"Hook","rationale":"Why'
        result = caption_agent._extract_caption_json(truncated)
        self.assertIn("hooks", result)
        self.assertEqual(result["hooks"][0]["hook_text"], "Hook")

    def test_extract_caption_json_still_raises_for_no_json(self):
        with self.assertRaises(ValueError):
            caption_agent._extract_caption_json("No JSON content at all")

    def test_call_model_json_payload_detects_truncation_and_auto_closes(self):
        class FakeMessage:
            def __init__(self, content):
                self.content = content
                self.finish_reason = "length"

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMessage(content)
                self.finish_reason = "length"

        class FakeResponse:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeCompletions:
            def create(self, **kwargs):
                if "response_format" in kwargs:
                    raise ValueError("response_format is not supported for this model")
                return FakeResponse('{"hooks":[{"variant_id":"v1","hook_style":"contrast","hook_text":"Truncated hook","rationale":"Why')

        fake_client = type("FakeClient", (), {"chat": type("FakeChat", (), {"completions": FakeCompletions()})()})()

        with patch.object(caption_agent, "_resolve_model_routes", return_value=[("groq", fake_client, "openai/gpt-oss-120b")]):
            payload, attempts, error = caption_agent._call_model_json_payload("system", "user", max_tokens=120)

        self.assertIn("hooks", payload)
        self.assertEqual(payload["hooks"][0]["hook_text"], "Truncated hook")
        self.assertEqual(error, "")
        # Auto-close happens inside _extract_caption_json before ValueError is raised,
        # so _call_model_json_payload sees a normal success with was_truncated=True
        self.assertEqual(attempts[0]["status"], "success")
        self.assertTrue(attempts[0]["was_truncated"])


if __name__ == "__main__":
    unittest.main()
