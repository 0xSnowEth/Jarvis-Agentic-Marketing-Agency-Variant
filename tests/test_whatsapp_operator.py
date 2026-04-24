import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import whatsapp_operator
from schedule_utils import resolve_date_phrase


class WhatsAppOperatorTests(unittest.TestCase):
    def _stateful_operator_patches(self, initial_payload: dict[str, object] | None = None):
        state = dict(initial_payload or {})
        saved_payloads: list[dict[str, object]] = []
        sent_messages: list[str] = []
        spawned_coroutines: list[object] = []

        def fake_get_operator_session_state(_phone):
            return {"payload_json": dict(state)}

        def fake_save_operator_session_state(_phone, payload):
            state.clear()
            state.update(payload)
            saved_payloads.append(dict(payload))
            return payload

        def fake_send_text_message(_phone, text):
            sent_messages.append(text)
            return {"success": True}

        def fake_spawn_background(coro):
            spawned_coroutines.append(coro)
            coro.close()
            return coro

        return {
            "state": state,
            "saved_payloads": saved_payloads,
            "sent_messages": sent_messages,
            "spawned_coroutines": spawned_coroutines,
            "get_operator_session_state": fake_get_operator_session_state,
            "save_operator_session_state": fake_save_operator_session_state,
            "send_text_message": fake_send_text_message,
            "spawn_background": fake_spawn_background,
        }

    def _preview_session(self, **overrides):
        session = {
            "mode": "preview",
            "client_id": "cedar_roast",
            "bundle_name": "Draft 1",
            "draft_id": "draft-1",
            "topic": "Launch promo",
            "content_goal": "Launch promo",
            "media_kind": "image_carousel",
            "item_count": 3,
            "display_direction": "Kuwait premium pull",
            "operator_brief": "make it more premium and local",
            "caption_payload": {
                "caption": "Original caption",
                "hashtags": ["#CedarRoast"],
                "quality_gate": {"score": 61.0, "threshold": 65.0, "passed": False, "verdict": "Needs another pass"},
                "generation_state": "success",
                "generation_source": "model_generated",
            },
            "generation_state": "success",
            "requested_intent": {},
        }
        session.update(overrides)
        return session

    def _generated_caption_payload(self, **overrides):
        payload = {
            "caption": "Fresh regenerated caption",
            "hashtags": ["#CedarRoast"],
            "seo_keyword_used": "iced chocolate",
            "status": "success",
            "display_direction": "Sharper Kuwait pull",
            "hidden_variants": [{"caption": "Still hidden"}],
            "media_analysis": {"analysis_summary": "Three drinks across the carousel."},
            "ranking_summary": {"winner_score": 79.5, "failure_reasons": []},
            "retry_memory": {"failure_reasons": [], "last_hook_family": "mood-led local"},
            "quality_gate": {"score": 79.5, "threshold": 65.0, "passed": True, "verdict": "Approved"},
            "generation_state": "success",
            "generation_source": "model_generated",
            "provider_attempts": [{"provider": "groq", "status": "success"}],
            "model_failure_reason": "",
            "hook_candidates": [{"variant_id": "variant_1", "hook_style": "mood-led local", "hook_text": "برد الكويت له وقته"}],
            "selected_hook_family": "mood-led local",
            "client_memory_examples": [],
        }
        payload.update(overrides)
        return payload

    def test_help_reanchors_to_root_menu_during_client_pick(self):
        calls: dict[str, object] = {}

        def fake_send_button_message(to_phone, **kwargs):
            calls["to_phone"] = to_phone
            calls["kwargs"] = kwargs
            return {"success": True}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "client_pick", "selection_reason": "post_client"}},
        ), patch.object(whatsapp_operator, "_audit", return_value=None), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=fake_send_button_message,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "hey jarvis",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(calls["to_phone"], "96560396543")
        payload = calls["kwargs"]
        self.assertEqual(payload["header_text"], "Jarvis")
        self.assertIn("What would you like to do?", payload["body_text"])
        self.assertIn("client selection is still open", payload["body_text"].lower())
        self.assertEqual([button["title"] for button in payload["buttons"]], ["New Post", "Add Client", "More"])

    def test_addclient_opens_mode_picker(self):
        saved: dict[str, object] = {}
        calls: list[dict[str, object]] = []

        with patch.object(whatsapp_operator, "get_operator_session_state", return_value={"payload_json": {}}), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda phone, payload: saved.update({"phone": phone, "payload": payload}) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda to_phone, **kwargs: calls.append({"phone": to_phone, "kwargs": kwargs}) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "/addclient",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(saved["phone"], "96560396543")
        self.assertEqual(saved["payload"]["mode"], "add_client_mode_picker")
        self.assertEqual(calls[0]["phone"], "96560396543")
        payload = calls[0]["kwargs"]
        self.assertEqual(payload["header_text"], "New Client")
        self.assertEqual([button["title"] for button in payload["buttons"]], ["Quick Brief", "Import Brief", "Scan Website"])
        self.assertEqual(calls[1]["kwargs"]["header_text"], "Navigation")
        self.assertEqual([button["title"] for button in calls[1]["kwargs"]["buttons"]], ["Go Back"])

    def test_addclient_quick_mode_starts_structured_brief(self):
        saved: dict[str, object] = {}
        messages: list[str] = []
        button_calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "add_client_mode_picker"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda phone, payload: saved.update({"phone": phone, "payload": payload}) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda to_phone, **kwargs: button_calls.append({"phone": to_phone, "kwargs": kwargs}) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_ADD_CLIENT:QUICK",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(saved["payload"]["mode"], "onboarding_form")
        self.assertEqual(saved["payload"]["onboarding_mode"], "quick_brief")
        self.assertTrue(messages)
        self.assertIn("Send one structured brief", messages[0])
        self.assertIn("Language rule", messages[0])
        self.assertEqual([button["title"] for button in button_calls[0]["kwargs"]["buttons"]], ["Go Back"])

    def test_strategy_prompt_session_uses_selected_client_without_strategy_prefix(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "strategy_prompt", "client_id": "Cedar Roast"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "run_strategy_agent",
            return_value={"client_id": "Cedar Roast", "timeframe": "next 30 days", "summary": "Plan ready", "items": []},
        ), patch.object(
            whatsapp_operator,
            "summarize_strategy_plan_reply",
            return_value="Plan ready",
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=True,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "next month content strategy focused on premium iced coffee",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(any("Building strategy for Cedar Roast" in message for message in messages))
        self.assertTrue(any("Strategy ready" in message for message in messages))
        self.assertFalse(any("Strategy needs a client" in message for message in messages))

    def test_strategy_client_pick_opens_strategy_menu(self):
        button_calls: list[dict[str, object]] = []

        def fake_send_button_message(_phone, **kwargs):
            button_calls.append(kwargs)
            return {"success": True}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "client_pick", "selection_reason": "strategy_client"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=fake_send_button_message,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_CLIENT_PICK:Cedar Roast",
                        "text": "Cedar Roast",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(button_calls)
        self.assertIn("New Plan", [button["title"] for button in button_calls[0]["buttons"]])
        self.assertIn("Saved Plans", [button["title"] for button in button_calls[0]["buttons"]])

    def test_strategy_menu_view_saved_plans_sends_list(self):
        list_calls: list[dict[str, object]] = []

        def fake_send_list_message(_phone, **kwargs):
            list_calls.append(kwargs)
            return {"success": True}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "strategy_menu", "client_id": "Cedar Roast"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "list_strategy_plans",
            return_value=[
                {
                    "plan_id": "plan-1",
                    "client_id": "Cedar Roast",
                    "window": "next_30_days",
                    "summary": "Premium iced coffee push",
                    "updated_at": "2026-04-23T10:00:00+00:00",
                    "items": [{}, {}, {}],
                    "item_count": 3,
                }
            ],
        ), patch.object(
            whatsapp_operator,
            "send_list_message",
            side_effect=fake_send_list_message,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_STRATEGY:VIEW",
                        "text": "View Saved Plans",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(list_calls)
        rows = list_calls[0]["sections"][0]["rows"]
        self.assertEqual(rows[0]["id"], "OP_STRATEGY_PLAN:plan-1")
        self.assertIn("Premium iced coffee push", rows[0]["description"])

    def test_strategy_menu_view_saved_plans_dedupes_same_brief_rows(self):
        list_calls: list[dict[str, object]] = []

        def fake_send_list_message(_phone, **kwargs):
            list_calls.append(kwargs)
            return {"success": True}

        duplicated = [
            {
                "plan_id": "plan-2",
                "client_id": "Cedar Roast",
                "window": "next_30_days",
                "summary": "Premium iced coffee push",
                "goal": "Next month premium iced coffee strategy",
                "requested_prompt": "Next month premium iced coffee strategy",
                "updated_at": "2026-04-23T11:00:00+00:00",
                "items": [{}, {}, {}, {}, {}, {}],
                "item_count": 6,
            },
            {
                "plan_id": "plan-1",
                "client_id": "Cedar Roast",
                "window": "next_30_days",
                "summary": "Premium iced coffee push",
                "goal": "Next month premium iced coffee strategy",
                "requested_prompt": "Next month premium iced coffee strategy",
                "updated_at": "2026-04-23T10:00:00+00:00",
                "items": [{}, {}, {}, {}, {}, {}],
                "item_count": 6,
            },
        ]

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "strategy_menu", "client_id": "Cedar Roast"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "list_strategy_plans",
            return_value=duplicated,
        ), patch.object(
            whatsapp_operator,
            "send_list_message",
            side_effect=fake_send_list_message,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_STRATEGY:VIEW",
                        "text": "View Saved Plans",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(list_calls)
        rows = list_calls[0]["sections"][0]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "OP_STRATEGY_PLAN:plan-2")

    def test_strategy_plan_selection_renders_saved_plan_messages(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "strategy_plan_pick", "client_id": "Cedar Roast"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "get_strategy_plan",
            return_value={"plan_id": "plan-1", "client_id": "Cedar Roast", "items": []},
        ), patch.object(
            whatsapp_operator,
            "format_strategy_plan_messages",
            return_value=["message one", "message two"],
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_STRATEGY_PLAN:plan-1",
                        "text": "Open plan",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(messages, ["message one", "message two"])

    def test_handle_synthesized_candidate_surfaces_provider_pause_reason(self):
        patches = self._stateful_operator_patches({"mode": "onboarding_build"})
        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "delete_operator_session_state",
            return_value=True,
        ):
            asyncio.run(
                whatsapp_operator._handle_synthesized_candidate(
                    "96560396543",
                    {"status": "error", "reason": "Provider rejected the request: 429"},
                    provisional_name="Oudique",
                    source_mode="scan_website",
                )
            )

        self.assertTrue(any("Provider rejected the request: 429" in text for text in patches["sent_messages"]))

    def test_preview_text_hides_internal_bundle_name_and_shows_direction(self):
        text = whatsapp_operator._preview_text(
            "cedar_roast",
            "Iced chocolate summer push",
            {
                "caption": "Arabic caption here",
                "hashtags": ["#CedarRoast", "#IcedChocolate"],
                "quality_gate": {
                    "score": 91.5,
                    "threshold": 85,
                    "verdict": "Approved",
                    "dimensions": {
                        "visual_grounding": 93,
                        "brand_voice_fidelity": 95,
                        "audience_platform_fit": 88,
                        "realism": 100,
                        "hook_strength": 82,
                        "trend_relevance": 78,
                    },
                },
            },
            "image_carousel",
            3,
        )

        self.assertNotIn("Draft:", text)
        self.assertNotIn("WhatsApp Carousel", text)
        self.assertIn("Direction: Iced chocolate summer push", text)
        self.assertIn("Format: 3 image carousel", text)

    def test_preview_schedule_button_sets_expected_reply(self):
        saved_payloads: list[dict[str, object]] = []
        messages: list[str] = []
        button_calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={
                "payload_json": {
                    "mode": "preview",
                    "client_id": "cedar_roast",
                    "bundle_name": "Draft 1",
                }
            },
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda to_phone, **kwargs: button_calls.append({"phone": to_phone, "kwargs": kwargs}) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:SCHEDULE",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(saved_payloads)
        self.assertEqual(saved_payloads[-1]["expected_reply"], "schedule")
        self.assertTrue(messages)
        self.assertIn("today 2pm", messages[-1].lower())
        self.assertFalse(button_calls)

    def test_meta_account_pick_interactive_saves_specific_choice(self):
        saved_clients: list[tuple[str, dict]] = []
        messages: list[str] = []

        class FakeStore:
            def get_client(self, _client_id):
                return {"client_id": "Bakhourito", "profile_json": {"business_name": "Bakhoor Nights"}}

            def save_client(self, client_id, payload):
                saved_clients.append((client_id, dict(payload)))
                return payload

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={
                "payload_json": {
                    "mode": "meta_account_pick",
                    "client_id": "Bakhourito",
                    "pending_meta_choices": [
                        {
                            "page_id": "page-1",
                            "page_name": "Demo Agency",
                            "page_access_token": "page-token-1",
                            "instagram_account_id": "ig-1",
                            "instagram_username": "veloura.studio.kw",
                        }
                    ],
                }
            },
        ), patch.object(
            whatsapp_operator,
            "get_client_store",
            return_value=FakeStore(),
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "delete_operator_session_state",
            return_value=True,
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_META_PICK:page-1",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(saved_clients[0][0], "Bakhourito")
        self.assertEqual(saved_clients[0][1]["facebook_page_id"], "page-1")
        self.assertEqual(saved_clients[0][1]["instagram_account_id"], "ig-1")
        self.assertIn("This specific Page/Instagram pair is now bound to this client.", messages[-1])

    def test_navigation_back_to_root_from_add_client_picker(self):
        calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "add_client_mode_picker"}},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda to_phone, **kwargs: calls.append({"phone": to_phone, "kwargs": kwargs}) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_NAV:ROOT",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(calls[0]["kwargs"]["header_text"], "Jarvis")
        self.assertEqual([button["title"] for button in calls[0]["kwargs"]["buttons"]], ["New Post", "Add Client", "More"])

    def test_schedule_parser_accepts_bare_weekday_and_day_first(self):
        weekday_intent = whatsapp_operator._parse_release_intent("schedule monday 6am")
        self.assertEqual(weekday_intent["mode"], "schedule")
        self.assertEqual(weekday_intent["days"], ["Monday"])
        self.assertEqual(weekday_intent["time"], "06:00 AM")

        day_first_intent = whatsapp_operator._parse_release_intent("schedule 17 friday at 6am")
        self.assertEqual(day_first_intent["mode"], "schedule")
        self.assertEqual(day_first_intent["days"], ["Friday"])
        self.assertEqual(day_first_intent["time"], "06:00 AM")

        explicit_date_intent = whatsapp_operator._parse_release_intent("schedule friday 24 april 6:00PM")
        self.assertEqual(explicit_date_intent["mode"], "schedule")
        self.assertEqual(explicit_date_intent["scheduled_date"], "2026-04-24")
        self.assertEqual(explicit_date_intent["days"], ["Friday"])
        self.assertEqual(explicit_date_intent["time"], "06:00 PM")

        bare_clock_intent = whatsapp_operator._parse_release_intent("today 3:28")
        self.assertEqual(bare_clock_intent["mode"], "schedule")
        self.assertEqual(bare_clock_intent["scheduled_date"], resolve_date_phrase("today").isoformat())
        self.assertEqual(bare_clock_intent["time"], "03:28 AM")

    def test_schedule_button_keeps_waiting_after_missing_time(self):
        saved_payloads: list[dict[str, object]] = []
        messages: list[str] = []
        approval_calls: list[tuple] = []
        session = {
            "mode": "preview",
            "client_id": "cedar_roast",
            "bundle_name": "Draft 1",
            "topic": "Launch promo",
            "draft_id": "draft-1",
            "expected_reply": "schedule",
            "caption_payload": {
                "quality_gate": {"score": 89.0, "threshold": 85, "passed": True},
            },
        }

        class FakeApprovalTool:
            def execute(self, *args):
                approval_calls.append(args)
                return {"message": "Scheduled successfully."}

        with patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "RequestApprovalTool",
            return_value=FakeApprovalTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "_send_back_button",
            return_value={"success": True},
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "monday", session))
            self.assertEqual(session["expected_reply"], "schedule")
            self.assertTrue(any("today 2pm" in message.lower() for message in messages))

            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "today 2pm", session))

        self.assertTrue(approval_calls)
        self.assertEqual(approval_calls[-1][2], [resolve_date_phrase("today").strftime("%A")])
        self.assertEqual(approval_calls[-1][3], "02:00 PM")

    def test_schedule_follow_up_accepts_today_tomorrow_and_explicit_date(self):
        approval_calls: list[tuple] = []

        class FakeApprovalTool:
            def execute(self, *args):
                approval_calls.append(args)
                return {"message": "Scheduled successfully."}

        for reply in ("today at 2pm", "tommorow 7pm", "friday 24 april 6:00PM"):
            session = self._preview_session(expected_reply="schedule")
            with patch.object(
                whatsapp_operator,
                "send_text_message",
                return_value={"success": True},
            ), patch.object(
                whatsapp_operator,
                "RequestApprovalTool",
                return_value=FakeApprovalTool(),
            ), patch.object(
                whatsapp_operator,
                "_clear_session",
                return_value=None,
            ):
                asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", reply, session))

        self.assertEqual(len(approval_calls), 3)
        self.assertEqual(approval_calls[0][3], "02:00 PM")
        self.assertEqual(approval_calls[0][6], resolve_date_phrase("today").isoformat())
        self.assertEqual(approval_calls[1][3], "07:00 PM")
        self.assertEqual(approval_calls[1][6], resolve_date_phrase("tomorrow").isoformat())
        self.assertEqual(approval_calls[2][3], "06:00 PM")
        self.assertEqual(approval_calls[2][6], "2026-04-24")

    def test_schedule_follow_up_accepts_bare_clock_without_meridiem(self):
        approval_calls: list[tuple] = []

        class FakeApprovalTool:
            def execute(self, *args):
                approval_calls.append(args)
                return {"message": "Scheduled successfully."}

        session = self._preview_session(expected_reply="schedule")
        with patch.object(
            whatsapp_operator,
            "send_text_message",
            return_value={"success": True},
        ), patch.object(
            whatsapp_operator,
            "RequestApprovalTool",
            return_value=FakeApprovalTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "today 3:28", session))

        self.assertEqual(len(approval_calls), 1)
        self.assertEqual(approval_calls[0][3], "03:28 AM")
        self.assertEqual(approval_calls[0][6], resolve_date_phrase("today").isoformat())

    def test_connect_now_uses_saved_client_payload(self):
        messages: list[str] = []
        saved_payloads: list[dict[str, object]] = []

        class FakeStore:
            def get_client(self, client_id):
                if client_id == "cedar_roast_2":
                    return {
                        "client_id": "cedar_roast_2",
                        "profile_json": {"business_name": "Cedar Roast"},
                    }
                return None

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {}},
        ), patch.object(
            whatsapp_operator,
            "get_client_store",
            return_value=FakeStore(),
        ), patch.object(
            whatsapp_operator,
            "resolve_client_id",
            side_effect=lambda value: value,
        ), patch.object(
            whatsapp_operator,
            "build_meta_connect_link",
            return_value="https://example.com/connect",
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_CONNECT_NOW:cedar_roast_2",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(saved_payloads)
        self.assertEqual(saved_payloads[-1]["pending_connect_client_id"], "cedar_roast_2")
        self.assertTrue(messages)
        self.assertIn("Connect Meta for Cedar Roast", messages[-1])
        self.assertIn("https://example.com/connect", messages[-1])

    def test_client_picker_shows_meta_expired_status(self):
        class FakeStore:
            def list_clients(self):
                return [
                    {
                        "client_id": "cedar_roast",
                        "instagram_account_id": "ig-1",
                        "profile_json": {"business_name": "Cedar Roast"},
                    }
                ]

        with patch.object(
            whatsapp_operator,
            "get_client_store",
            return_value=FakeStore(),
        ), patch.object(
            whatsapp_operator,
            "_client_meta_health",
            return_value={"ok": False, "status": "expired_or_invalid", "detail": "Session has expired.", "probe_source": "live"},
        ):
            sections = whatsapp_operator._build_client_picker_sections()

        self.assertEqual(sections[0]["rows"][0]["description"], "Meta expired")

    def test_post_client_pick_blocks_before_upload_when_meta_expired(self):
        messages: list[str] = []
        button_calls: list[dict[str, object]] = []
        saved_payloads: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "client_pick", "selection_reason": "post_client", "source_text": ""}},
        ), patch.object(
            whatsapp_operator,
            "_get_client_row",
            return_value={
                "client_id": "cedar_roast",
                "display_name": "Cedar Roast",
                "profile": {"business_name": "Cedar Roast"},
                "meta_health": {"ok": False, "status": "expired_or_invalid", "detail": "Session has expired.", "probe_source": "live"},
            },
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda _phone, **kwargs: button_calls.append(kwargs) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_CLIENT_PICK:cedar_roast",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(saved_payloads[-1]["mode"], "meta_blocked")
        self.assertEqual(button_calls[-1]["header_text"], "Meta Needs Attention")
        self.assertIn("avoid wasting time on uploads", button_calls[-1]["body_text"].lower())
        self.assertEqual([button["title"] for button in button_calls[-1]["buttons"]], ["Connect Meta", "Go Back"])
        self.assertFalse(messages)

    def test_refresh_meta_status_clears_cache_and_sends_summary(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {}},
        ), patch.object(
            whatsapp_operator,
            "_clear_meta_health_cache",
            return_value=None,
        ) as clear_mock, patch.object(
            whatsapp_operator,
            "_build_status_summary",
            return_value="*Jarvis status* ✦\n• Connected Meta accounts: 1",
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_MORE:REFRESH_META",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        clear_mock.assert_called_once()
        self.assertIn("Meta status refreshed", messages[0])
        self.assertIn("Connected Meta accounts", messages[1])

    def test_build_schedules_summary_handles_empty_schedule_tuple_view(self):
        with patch.object(
            whatsapp_operator,
            "load_schedule",
            return_value=[],
        ):
            summary = whatsapp_operator._build_schedules_summary()

        self.assertIn("No schedules yet", summary)

    def test_more_menu_schedules_sends_empty_state_message(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": {}},
        ), patch.object(
            whatsapp_operator,
            "load_schedule",
            return_value=[],
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_MORE:SCHEDULES",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertIn("No schedules yet", messages[0])

    def test_first_document_starts_media_collect_session(self):
        patches = self._stateful_operator_patches()

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "_spawn_background",
            side_effect=patches["spawn_background"],
        ), patch.object(
            whatsapp_operator.uuid,
            "uuid4",
            return_value=SimpleNamespace(hex="token-first"),
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "document",
                        "mime_type": "image/jpeg",
                        "media_id": "media-1",
                        "filename": "first.jpg",
                        "caption": "launch @cedar_roast",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(patches["saved_payloads"][-1]["mode"], "media_collect")
        self.assertEqual(patches["saved_payloads"][-1]["collection_token"], "token-first")
        self.assertEqual(len(patches["saved_payloads"][-1]["media_refs"]), 1)
        self.assertEqual(patches["saved_payloads"][-1]["media_refs"][0]["kind"], "image")
        self.assertEqual(len(patches["spawned_coroutines"]), 1)
        self.assertTrue(patches["sent_messages"])
        self.assertIn("Image received", patches["sent_messages"][-1])

    def test_second_image_document_appends_into_existing_bundle(self):
        patches = self._stateful_operator_patches(
            {
                "mode": "media_collect",
                "collection_token": "token-shared",
                "client_id": "cedar_roast",
                "source_text": "launch teaser",
                "media_refs": [
                    {
                        "media_id": "media-1",
                        "filename": "first.jpg",
                        "mime_type": "image/jpeg",
                        "kind": "image",
                        "received_at": "2026-04-15T00:00:00+00:00",
                    }
                ],
                "updated_at": "2026-04-15T00:00:01+00:00",
            }
        )

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "_spawn_background",
            side_effect=patches["spawn_background"],
        ), patch.object(
            whatsapp_operator.uuid,
            "uuid4",
            return_value=SimpleNamespace(hex="token-second"),
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "document",
                        "mime_type": "image/png",
                        "media_id": "media-2",
                        "filename": "second.png",
                        "caption": "second angle",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(patches["saved_payloads"][-1]["mode"], "media_collect")
        self.assertEqual(patches["saved_payloads"][-1]["collection_token"], "token-second")
        self.assertEqual([ref["media_id"] for ref in patches["saved_payloads"][-1]["media_refs"]], ["media-1", "media-2"])
        self.assertEqual(len(patches["saved_payloads"][-1]["media_refs"]), 2)
        self.assertEqual(len(patches["spawned_coroutines"]), 1)
        self.assertIn("Carousel updated", patches["sent_messages"][-1])

    def test_single_video_document_stays_on_valid_bundle_path(self):
        patches = self._stateful_operator_patches()

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "_spawn_background",
            side_effect=patches["spawn_background"],
        ), patch.object(
            whatsapp_operator.uuid,
            "uuid4",
            return_value=SimpleNamespace(hex="token-video"),
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "document",
                        "mime_type": "video/mp4",
                        "media_id": "media-video",
                        "filename": "reel.mp4",
                        "caption": "single reel",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(patches["saved_payloads"][-1]["mode"], "media_collect")
        self.assertEqual(patches["saved_payloads"][-1]["collection_token"], "token-video")
        self.assertEqual(patches["saved_payloads"][-1]["media_refs"][0]["kind"], "video")
        media_kind, error = whatsapp_operator._infer_media_bundle(patches["saved_payloads"][-1]["media_refs"])
        self.assertEqual(media_kind, "video")
        self.assertEqual(error, "")
        self.assertEqual(len(patches["spawned_coroutines"]), 1)
        self.assertTrue(patches["sent_messages"])
        self.assertIn("Video received", patches["sent_messages"][-1])

    def test_text_during_media_collect_preserves_session(self):
        patches = self._stateful_operator_patches(
            {
                "mode": "media_collect",
                "collection_token": "token-notes",
                "client_id": "cedar_roast",
                "source_text": "launch teaser",
                "media_refs": [
                    {
                        "media_id": "media-1",
                        "filename": "first.jpg",
                        "mime_type": "image/jpeg",
                        "kind": "image",
                        "received_at": "2026-04-15T00:00:00+00:00",
                    }
                ],
                "updated_at": "2026-04-15T00:00:01+00:00",
            }
        )

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "_spawn_background",
            side_effect=patches["spawn_background"],
        ), patch.object(
            whatsapp_operator.uuid,
            "uuid4",
            return_value=SimpleNamespace(hex="token-notes-2"),
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "keep these notes and @cedar_roast in the bundle",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(patches["saved_payloads"][-1]["mode"], "media_collect")
        self.assertEqual(patches["state"]["mode"], "media_collect")
        self.assertEqual(patches["saved_payloads"][-1]["collection_token"], "token-notes-2")
        self.assertIn("keep these notes", patches["saved_payloads"][-1]["source_text"])
        self.assertEqual(len(patches["spawned_coroutines"]), 1)
        self.assertIn("wait 10 more seconds", patches["sent_messages"][-1])

    def test_document_during_preview_does_not_overwrite_preview_session(self):
        patches = self._stateful_operator_patches(
            {
                "mode": "preview",
                "client_id": "cedar_roast",
                "bundle_name": "Draft 1",
                "draft_id": "draft-1",
            }
        )

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "_audit",
            return_value=None,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "document",
                        "mime_type": "image/jpeg",
                        "media_id": "late-media",
                        "filename": "late.jpg",
                        "caption": "",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertFalse(patches["saved_payloads"])
        self.assertEqual(patches["state"]["mode"], "preview")
        self.assertIn("Preview still open", patches["sent_messages"][-1])

    def test_preview_text_uses_examples_label_and_quality_snapshot(self):
        preview = whatsapp_operator._preview_text(
            "cedar_roast",
            "WhatsApp Carousel 2026-04-15 21:15:08",
            {
                "caption": "هل جرّبت آيسد شوكولاتة Cedar Roast في الكويت؟",
                "hashtags": ["#CedarRoast", "#KuwaitCoffeeCulture"],
                "quality_gate": {
                    "score": 89.2,
                    "threshold": 85,
                    "verdict": "Approved",
                    "dimensions": {
                        "visual_grounding": 91,
                        "brand_voice_fidelity": 84,
                        "audience_platform_fit": 88,
                        "realism": 100,
                        "hook_strength": 87,
                        "trend_relevance": 76,
                    },
                },
            },
            "image_carousel",
            3,
        )

        self.assertIn("Reply with one of the examples below if you prefer typing:", preview)
        self.assertIn("Quality snapshot: Visual 91 · Voice 84 · Platform 88 · Realism 100 · Hooks 87 · Trend 76", preview)
        self.assertIn("Quality: 89.2/85 - Approved", preview)
        self.assertIn("• post now", preview)
        self.assertIn("• edit hashtags #kuwait #specialtycoffee", preview)
        self.assertIn("• append hashtags #icedcoffee", preview)

    def test_preview_text_keeps_release_examples_when_quality_is_low(self):
        preview = whatsapp_operator._preview_text(
            "cedar_roast",
            "WhatsApp Carousel 2026-04-15 21:58:24",
            {
                "caption": "Generic caption",
                "hashtags": ["#CedarRoast"],
                "quality_gate": {
                    "score": 45.5,
                    "threshold": 85,
                    "passed": False,
                    "verdict": "Needs another pass",
                    "dimensions": {
                        "visual_grounding": 25,
                        "brand_voice_fidelity": 6,
                        "audience_platform_fit": 78,
                        "realism": 93,
                        "hook_strength": 66,
                        "trend_relevance": 40,
                    },
                },
            },
            "image_carousel",
            3,
        )

        self.assertIn("• post now", preview)
        self.assertIn("• schedule friday 17 at 6am", preview)
        self.assertIn("• try again", preview)
        self.assertIn("Needs another pass", preview)

    def test_caption_progress_callback_only_announces_drafting_once(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ):
            callback = whatsapp_operator._build_caption_progress_callback("96560396543", "cedar_roast")
            callback({"event": "drafting_started"})
            callback({"event": "drafting_started"})
            callback({"event": "scoring_started"})
            callback({"event": "score_failed"})

        self.assertEqual(len(messages), 1)
        self.assertIn("Writing caption", messages[0])

    def test_send_preview_card_keeps_release_actions_when_quality_is_low(self):
        text_messages: list[str] = []
        button_calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: text_messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_send_button_card",
            side_effect=lambda phone, **kwargs: button_calls.append({"phone": phone, "kwargs": kwargs}) or {"success": True},
        ):
            whatsapp_operator._send_preview_card(
                "96560396543",
                self._preview_session(
                    caption_payload={
                        "caption": "Generic",
                        "hashtags": ["#CedarRoast"],
                        "quality_gate": {"score": 45.5, "threshold": 65, "passed": False, "verdict": "Needs another pass"},
                        "generation_state": "success",
                    }
                ),
            )

        self.assertTrue(text_messages)
        self.assertEqual(button_calls[0]["kwargs"]["header_text"], "Next Move")
        self.assertEqual([button["title"] for button in button_calls[0]["kwargs"]["buttons"]], ["Publish Now", "Schedule", "Revise"])

    def test_preview_post_now_button_publishes_immediately(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        session = self._preview_session()

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": session},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:POST_NOW",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(publish_calls)
        self.assertEqual(publish_calls[-1][0], "cedar_roast")
        self.assertEqual(publish_calls[-1][3], "Draft 1")
        self.assertIn("Published", messages[-1])

    def test_preview_revise_button_sets_expected_reply(self):
        saved_payloads: list[dict[str, object]] = []
        messages: list[str] = []
        button_calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": self._preview_session()},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "send_button_message",
            side_effect=lambda to_phone, **kwargs: button_calls.append({"phone": to_phone, "kwargs": kwargs}) or {"success": True},
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:REVISE",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(saved_payloads[-1]["expected_reply"], "revise")
        self.assertIn("Tell Jarvis what to change", messages[-1])
        self.assertFalse(button_calls)

    def test_preview_try_again_button_triggers_fresh_regeneration(self):
        messages: list[str] = []
        preview_calls: list[dict[str, object]] = []
        saved_payloads: list[dict[str, object]] = []
        session = self._preview_session(
            hidden_variants=[{"caption": "Old hidden variant"}],
            caption_payload={
                "caption": "Old blocked caption",
                "hashtags": ["#CedarRoast"],
                "quality_gate": {
                    "score": 61.0,
                    "threshold": 65.0,
                    "passed": False,
                    "failures": ["Hooks need more pull.", "Trend relevance is light."],
                },
                "generation_state": "success",
            },
        )

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": session},
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}]}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            side_effect=lambda _client_id, _bundle_name, payload: saved_payloads.append(payload) or {"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:TRY_AGAIN",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(generate_mock.called)
        self.assertEqual(generate_mock.call_args.kwargs["mode"], "generate")
        self.assertTrue(preview_calls)
        self.assertTrue(saved_payloads)
        self.assertIn("Regenerating caption", messages[0])

    def test_preview_cancel_button_clears_preview_state(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": self._preview_session()},
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ) as clear_mock:
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:CANCEL",
                        "text": "",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        clear_mock.assert_called_once()
        self.assertIn("Preview dismissed", messages[-1])

    def test_cancel_text_clears_preview_state(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ) as clear_mock:
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "cancel", self._preview_session()))

        clear_mock.assert_called_once()
        self.assertIn("Preview dismissed", messages[-1])

    def test_yes_now_publishes_immediately(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        session = self._preview_session()

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "yes now", session))

        self.assertTrue(publish_calls)
        self.assertIn("Published", messages[-1])

    def test_post_now_text_publishes_immediately(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        session = self._preview_session()

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", session))

        self.assertTrue(publish_calls)
        self.assertIn("Published", messages[-1])

    def test_post_now_partial_success_keeps_preview_session_open(self):
        messages: list[str] = []
        saved_payloads: list[dict[str, object]] = []
        session = self._preview_session()

        class FakePublishTool:
            def execute(self, *args):
                return {"status": "partial_success", "message": "Facebook posted, Instagram failed."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            side_effect=AssertionError("preview should stay open on partial success"),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", session))

        self.assertTrue(saved_payloads)
        self.assertIn("Published", messages[-1])

    def test_post_now_error_keeps_preview_session_open(self):
        messages: list[str] = []
        saved_payloads: list[dict[str, object]] = []
        session = self._preview_session()

        class FakePublishTool:
            def execute(self, *args):
                return {"status": "error", "message": "Instagram failed."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            side_effect=AssertionError("preview should stay open on error"),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", session))

        self.assertTrue(saved_payloads)
        self.assertIn("Published", messages[-1])

    def test_schedule_text_schedules_in_one_shot(self):
        messages: list[str] = []
        approval_calls: list[tuple] = []
        session = self._preview_session()

        class FakeApprovalTool:
            def execute(self, *args):
                approval_calls.append(args)
                return {"message": "Scheduled successfully."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "RequestApprovalTool",
            return_value=FakeApprovalTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "schedule friday 17 at 6am", session))

        self.assertTrue(approval_calls)
        self.assertEqual(approval_calls[-1][0], "cedar_roast")
        self.assertEqual(approval_calls[-1][3], "06:00 AM")
        self.assertIn("Scheduled", messages[-1])

    def test_schedule_error_keeps_preview_session_open(self):
        messages: list[str] = []
        saved_payloads: list[dict[str, object]] = []
        session = self._preview_session()

        class FakeApprovalTool:
            def execute(self, *args):
                return {"error": "Meta credentials invalid."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "RequestApprovalTool",
            return_value=FakeApprovalTool(),
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: saved_payloads.append(dict(payload)) or payload,
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            side_effect=AssertionError("preview should stay open on schedule failure"),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "schedule friday 17 at 6am", session))

        self.assertTrue(saved_payloads)
        self.assertIn("Scheduled", messages[-1])

    def test_hey_jarvis_resets_preview_session_to_root_menu(self):
        messages: list[str] = []

        with patch.object(
            whatsapp_operator,
            "_session_payload",
            return_value={"mode": "preview", "expected_reply": "schedule"},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=True,
        ) as clear_session, patch.object(
            whatsapp_operator,
            "_send_root_menu",
            side_effect=lambda _phone: messages.append("ROOT"),
        ), patch.object(
            whatsapp_operator,
            "_handle_preview_reply",
            side_effect=AssertionError("preview should not handle hey jarvis"),
        ):
            asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "hey jarvis",
                    }
                )
            )

        clear_session.assert_called_once()
        self.assertEqual(messages, ["ROOT"])

    def test_edit_command_updates_caption_and_keeps_preview_usable(self):
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session()

        with patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"caption_metadata": {}, "items": []}}},
        ), patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "edit A tighter premium caption", session))

        self.assertEqual(session["caption_payload"]["caption"], "A tighter premium caption")
        self.assertEqual(session["caption_payload"]["generation_source"], "operator_edited")
        self.assertEqual(session["generation_state"], "success")
        self.assertTrue(preview_calls)

    def test_edit_hashtags_replaces_hashtags_and_keeps_preview_usable(self):
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session()

        with patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"caption_metadata": {}, "items": []}}},
        ), patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(
                whatsapp_operator._handle_preview_reply(
                    "96560396543",
                    "edit hashtags #kuwait #specialtycoffee #iceddrinks",
                    session,
                )
            )

        self.assertEqual(session["caption_payload"]["hashtags"], ["#kuwait", "#specialtycoffee", "#iceddrinks"])
        self.assertEqual(session["caption_payload"]["generation_source"], "operator_edited")
        self.assertTrue(preview_calls)

    def test_append_hashtags_merges_without_duplicates(self):
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session(
            caption_payload={
                "caption": "Original caption",
                "hashtags": ["#CedarRoast", "#Kuwait"],
                "quality_gate": {"score": 61.0, "threshold": 65.0, "passed": False, "verdict": "Needs another pass"},
                "generation_state": "success",
                "generation_source": "model_generated",
            }
        )

        with patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"caption_metadata": {}, "items": []}}},
        ), patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(
                whatsapp_operator._handle_preview_reply(
                    "96560396543",
                    "append hashtags #IcedCoffee #Kuwait #LateNight",
                    session,
                )
            )

        self.assertEqual(session["caption_payload"]["hashtags"], ["#CedarRoast", "#Kuwait", "#IcedCoffee", "#LateNight"])
        self.assertEqual(session["caption_payload"]["generation_source"], "operator_edited")
        self.assertTrue(preview_calls)

    def test_change_command_triggers_revise_flow(self):
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session()

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            return_value={"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}]}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(
                whatsapp_operator._handle_preview_reply(
                    "96560396543",
                    "change make it sharper, more premium, and more local to Kuwait",
                    session,
                )
            )

        self.assertTrue(generate_mock.called)
        self.assertEqual(generate_mock.call_args.kwargs["mode"], "revise")
        self.assertEqual(generate_mock.call_args.kwargs["operator_brief"], "make it sharper, more premium, and more local to Kuwait")
        self.assertTrue(preview_calls)

    def test_plain_revision_text_after_revise_prompt_triggers_revise_flow(self):
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session(expected_reply="revise")

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            return_value={"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}]}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "make it sharper and shorter", session))

        self.assertTrue(generate_mock.called)
        self.assertEqual(generate_mock.call_args.kwargs["mode"], "revise")
        self.assertEqual(generate_mock.call_args.kwargs["operator_brief"], "make it sharper and shorter")
        self.assertTrue(preview_calls)

    def test_try_again_generates_fresh_batch_instead_of_promoting_hidden_variant(self):
        messages: list[str] = []
        preview_calls: list[dict[str, object]] = []
        saved_payloads: list[dict[str, object]] = []
        session = self._preview_session(
            hidden_variants=[{"caption": "Old hidden variant"}],
            caption_payload={
                "caption": "Old blocked caption",
                "hashtags": ["#CedarRoast"],
                "quality_gate": {
                    "score": 61.0,
                    "threshold": 65.0,
                    "passed": False,
                    "failures": ["Hooks need more pull.", "Trend relevance is light."],
                },
                "generation_state": "success",
            },
        )

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}]}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            side_effect=lambda _client_id, _bundle_name, payload: saved_payloads.append(payload) or {"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "try again", session))

        self.assertTrue(generate_mock.called)
        self.assertEqual(generate_mock.call_args.kwargs["mode"], "generate")
        self.assertEqual(generate_mock.call_args.kwargs["current_caption"], "Old blocked caption")
        self.assertIn("Hooks need more pull.", generate_mock.call_args.kwargs["avoid_repeat_failures"])
        self.assertEqual(session["caption_payload"]["caption"], "Fresh regenerated caption")
        self.assertEqual(session["display_direction"], "Sharper Kuwait pull")
        self.assertTrue(preview_calls)
        self.assertTrue(saved_payloads)
        self.assertIn("Regenerating caption", messages[0])
        self.assertFalse(any("Alternate direction loaded" in message for message in messages))

    def test_send_preview_card_generation_unavailable_hides_caption_preview(self):
        text_messages: list[str] = []
        button_calls: list[dict[str, object]] = []

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: text_messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_send_button_card",
            side_effect=lambda phone, **kwargs: button_calls.append({"phone": phone, "kwargs": kwargs}) or {"success": True},
        ):
            whatsapp_operator._send_preview_card(
                "96560396543",
                {
                    "client_id": "cedar_roast",
                    "bundle_name": "Draft 1",
                    "media_kind": "image_carousel",
                    "item_count": 3,
                    "generation_state": "generation_unavailable",
                    "caption_payload": {
                        "status": "generation_unavailable",
                        "generation_state": "generation_unavailable",
                        "reason": "Provider failed to return valid JSON.",
                        "internal_fallback_variants": [{"caption": "Hidden fallback"}],
                    },
                },
            )

        self.assertEqual(len(text_messages), 1)
        self.assertIn("Caption generation failed", text_messages[0])
        self.assertNotIn("Hidden fallback", text_messages[0])
        self.assertEqual(button_calls[0]["kwargs"]["header_text"], "Caption Blocked")
        self.assertEqual([button["title"] for button in button_calls[0]["kwargs"]["buttons"]], ["Try Again", "Revise", "Cancel"])

    def test_change_after_generation_unavailable_uses_generate_mode(self):
        messages: list[str] = []
        preview_calls: list[dict[str, object]] = []
        session = self._preview_session(
            generation_state="generation_unavailable",
            caption_payload={
                "status": "generation_unavailable",
                "generation_state": "generation_unavailable",
                "caption": "",
                "reason": "Provider failed.",
                "quality_gate": {},
            },
        )

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}]}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: session.update(payload) or payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "change make it more premium", session))

        self.assertTrue(generate_mock.called)
        self.assertEqual(generate_mock.call_args.kwargs["mode"], "generate")
        self.assertEqual(generate_mock.call_args.kwargs["current_caption"], "")
        self.assertEqual(generate_mock.call_args.kwargs["prior_best_caption"], "")
        self.assertTrue(preview_calls)
        self.assertEqual(session["generation_state"], "success")

    def test_generation_unavailable_blocks_post_now_and_schedule(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        approval_calls: list[tuple] = []
        base_session = self._preview_session(
            generation_state="generation_unavailable",
            caption_payload={"generation_state": "generation_unavailable", "status": "generation_unavailable"},
        )

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        class FakeApprovalTool:
            def execute(self, *args):
                approval_calls.append(args)
                return {"message": "Scheduled successfully."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "RequestApprovalTool",
            return_value=FakeApprovalTool(),
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", dict(base_session)))
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "schedule friday 17 at 6am", dict(base_session)))

        self.assertFalse(publish_calls)
        self.assertFalse(approval_calls)
        self.assertTrue(all("Release blocked" in message for message in messages[-2:]))

    def test_generation_unavailable_allows_try_again_revise_edit_and_cancel(self):
        messages: list[str] = []
        preview_calls: list[dict[str, object]] = []
        cleared = []
        base_session = self._preview_session(
            generation_state="generation_unavailable",
            caption_payload={
                "status": "generation_unavailable",
                "generation_state": "generation_unavailable",
                "caption": "",
                "reason": "Provider failed.",
                "quality_gate": {},
            },
        )

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_build_caption_progress_callback",
            return_value=lambda _event: None,
        ), patch.object(
            whatsapp_operator,
            "_recent_client_captions",
            return_value=["Older caption"],
        ), patch.object(
            whatsapp_operator,
            "list_client_drafts",
            return_value={"bundles": {"Draft 1": {"items": [{"filename": "hero.jpg", "kind": "image"}], "caption_metadata": {}}}},
        ), patch.object(
            whatsapp_operator,
            "generate_caption_payload",
            return_value=self._generated_caption_payload(),
        ) as generate_mock, patch.object(
            whatsapp_operator,
            "save_draft_payload",
            return_value={"draft_id": "draft-1"},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: payload,
        ), patch.object(
            whatsapp_operator,
            "_send_preview_card",
            side_effect=lambda _phone, payload: preview_calls.append(dict(payload)),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            side_effect=lambda _phone: cleared.append(True),
        ):
            try_again_session = dict(base_session)
            revise_session = dict(base_session)
            edit_session = dict(base_session)
            cancel_session = dict(base_session)
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "try again", try_again_session))
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "revise", revise_session))
            self.assertEqual(revise_session["expected_reply"], "revise")
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "edit Manual operator caption", edit_session))
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "cancel", cancel_session))

        self.assertTrue(generate_mock.called)
        self.assertTrue(preview_calls)
        self.assertTrue(cleared)
        self.assertEqual(edit_session["caption_payload"]["generation_source"], "operator_edited")

    def test_post_now_is_allowed_when_quality_is_low(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        session = self._preview_session(
            caption_payload={
                "caption": "Low-score caption",
                "hashtags": ["#CedarRoast"],
                "quality_gate": {"score": 45.5, "threshold": 65.0, "passed": False, "verdict": "Needs another pass"},
                "generation_state": "success",
            }
        )

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", session))

        self.assertTrue(publish_calls)
        self.assertIn("Published", messages[-1])

    def test_post_now_button_and_text_reach_same_publish_backend_action(self):
        button_publish_calls: list[tuple] = []
        text_publish_calls: list[tuple] = []
        button_messages: list[str] = []
        text_messages: list[str] = []

        class FakeButtonPublishTool:
            def execute(self, *args):
                button_publish_calls.append(args)
                return {"message": "Posted now."}

        class FakeTextPublishTool:
            def execute(self, *args):
                text_publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": self._preview_session()},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakeButtonPublishTool(),
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: button_messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "OP_PREVIEW:POST_NOW",
                        "text": "",
                    }
                )
            )

        with patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakeTextPublishTool(),
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: text_messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", self._preview_session()))

        self.assertEqual(button_publish_calls, text_publish_calls)
        self.assertIn("Published", button_messages[-1])
        self.assertIn("Published", text_messages[-1])

    def test_post_now_overrides_stale_schedule_requested_intent(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []
        session = self._preview_session(
            requested_intent={
                "mode": "schedule",
                "scheduled_date": "2026-04-25",
                "days": ["Friday"],
                "time": "06:00 AM",
            }
        )

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(whatsapp_operator._handle_preview_reply("96560396543", "post now", session))

        self.assertTrue(publish_calls)
        self.assertIn("Published", messages[-1])

    def test_title_only_interactive_post_now_falls_back_to_text_parser(self):
        messages: list[str] = []
        publish_calls: list[tuple] = []

        class FakePublishTool:
            def execute(self, *args):
                publish_calls.append(args)
                return {"message": "Posted now."}

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            return_value={"payload_json": self._preview_session()},
        ), patch.object(
            whatsapp_operator,
            "TriggerPipelineNowTool",
            return_value=FakePublishTool(),
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_clear_session",
            return_value=None,
        ):
            asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "interactive",
                        "interactive_reply_id": "",
                        "text": "Post Now",
                    }
                )
            )

        self.assertTrue(publish_calls)
        self.assertIn("Published", messages[-1])

    def test_schedule_prompt_no_longer_sends_preview_back_button(self):
        messages: list[str] = []
        session = self._preview_session()
        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: payload,
        ), patch.object(
            whatsapp_operator,
            "_send_back_button",
            side_effect=AssertionError("preview back button should not be sent"),
        ):
            whatsapp_operator._prompt_preview_schedule("96560396543", session)

        self.assertEqual(session["expected_reply"], "schedule")
        self.assertTrue(messages and "Schedule this draft" in messages[-1])

    def test_revise_prompt_no_longer_sends_preview_back_button(self):
        messages: list[str] = []
        session = self._preview_session()
        with patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=lambda _phone, text: messages.append(text) or {"success": True},
        ), patch.object(
            whatsapp_operator,
            "_save_session",
            side_effect=lambda _phone, payload: payload,
        ), patch.object(
            whatsapp_operator,
            "_send_back_button",
            side_effect=AssertionError("preview back button should not be sent"),
        ):
            whatsapp_operator._prompt_preview_revise("96560396543", session)

        self.assertEqual(session["expected_reply"], "revise")
        self.assertTrue(messages and "Revise this draft" in messages[-1])

    def test_parse_missing_field_submission_accepts_single_freeform_answer(self):
        answers, unresolved = whatsapp_operator._parse_missing_field_submission(
            "Target audiences will be teenagers and adults, mostly older people.",
            ["Target audience"],
        )

        self.assertEqual(unresolved, [])
        self.assertIn("Target audience", answers)
        self.assertIn("teenagers and adults", answers["Target audience"])

    def test_parse_missing_field_submission_accepts_labeled_line_without_numbering(self):
        answers, unresolved = whatsapp_operator._parse_missing_field_submission(
            "Target audience: premium car buyers in Kuwait",
            ["Target audience"],
        )

        self.assertEqual(unresolved, [])
        self.assertEqual(answers["Target audience"], "premium car buyers in Kuwait")

    def test_missing_field_reply_saves_freeform_single_field_answer(self):
        patches = self._stateful_operator_patches(
            {
                "mode": "onboarding_missing_fields",
                "provisional_client_name": "Oudique",
                "source_mode": "scan_website",
                "missing_fields": ["Target audience"],
                "candidate_profile": {"business_name": "Oudique"},
            }
        )

        with patch.object(
            whatsapp_operator,
            "get_operator_session_state",
            side_effect=patches["get_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "save_operator_session_state",
            side_effect=patches["save_operator_session_state"],
        ), patch.object(
            whatsapp_operator,
            "send_text_message",
            side_effect=patches["send_text_message"],
        ), patch.object(
            whatsapp_operator,
            "_spawn_background",
            side_effect=patches["spawn_background"],
        ):
            result = asyncio.run(
                whatsapp_operator.handle_operator_message(
                    {
                        "from": "96560396543",
                        "type": "text",
                        "text": "Target audiences will be teenagers and adults, mostly older people.",
                    }
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(any("Missing details received for Oudique" in message for message in patches["sent_messages"]))
        self.assertEqual(patches["state"]["mode"], "onboarding_build")
        self.assertEqual(len(patches["spawned_coroutines"]), 1)


if __name__ == "__main__":
    unittest.main()
