import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import webhook_server


class WebhookServerTests(unittest.TestCase):
    def setUp(self):
        webhook_server._recent_inbound_message_ids.clear()

    def test_should_skip_inbound_message_is_idempotent_for_same_message_id(self):
        self.assertFalse(webhook_server._should_skip_inbound_message("wamid-123"))
        self.assertTrue(webhook_server._should_skip_inbound_message("wamid-123"))
        self.assertFalse(webhook_server._should_skip_inbound_message("wamid-456"))

    def test_approval_states_are_not_counted_as_successful_release_statuses(self):
        self.assertFalse(webhook_server._is_successful_release_status("approval_ready"))
        self.assertFalse(webhook_server._is_successful_release_status("approval_sent_whatsapp"))
        self.assertTrue(webhook_server._is_successful_release_status("published"))

    def test_extract_connectable_meta_choices_filters_to_page_ig_pairs(self):
        choices = webhook_server._extract_connectable_meta_choices(
            [
                {
                    "id": "page-1",
                    "name": "Demo Agency",
                    "access_token": "page-token-1",
                    "instagram_business_account": {"id": "ig-1", "username": "demo.agency"},
                },
                {
                    "id": "page-2",
                    "name": "No Instagram",
                    "access_token": "page-token-2",
                    "instagram_business_account": {},
                },
            ]
        )

        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0]["page_id"], "page-1")
        self.assertEqual(choices[0]["instagram_account_id"], "ig-1")

    def test_owner_schedule_preview_reply_stays_out_of_reschedule_lane(self):
        with patch.object(
            webhook_server,
            "get_agency_config",
            return_value={"owner_phone": "96560396543"},
        ), patch.object(
            webhook_server,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "preview", "expected_reply": "schedule"}},
        ), patch.object(
            webhook_server,
            "load_reschedule_sessions",
            return_value={"96560396543": {"approval_id": "ABC123"}},
        ), patch.object(
            webhook_server,
            "parse_owner_reschedule_command",
            return_value=(None, "03:04 PM", ["Wednesday"], "2026-04-22"),
        ):
            self.assertFalse(webhook_server._owner_text_should_use_reschedule_lane("96560396543", "Today 3:04 PM"))

    def test_owner_reschedule_text_uses_reschedule_lane_when_not_in_preview_schedule(self):
        with patch.object(
            webhook_server,
            "get_agency_config",
            return_value={"owner_phone": "96560396543"},
        ), patch.object(
            webhook_server,
            "get_operator_session_state",
            return_value={"payload_json": {"mode": "idle"}},
        ), patch.object(
            webhook_server,
            "load_reschedule_sessions",
            return_value={"96560396543": {"approval_id": "ABC123"}},
        ), patch.object(
            webhook_server,
            "parse_owner_reschedule_command",
            return_value=(None, "03:04 PM", ["Wednesday"], "2026-04-22"),
        ):
            self.assertTrue(webhook_server._owner_text_should_use_reschedule_lane("96560396543", "Today 3:04 PM"))

    def test_handle_inbound_text_owner_falls_back_to_operator_when_no_pending_reschedule_target(self):
        forwarded: list[dict] = []

        async def fake_handle_operator_message(payload):
            forwarded.append(payload)
            return {"status": "success"}

        with patch.object(
            webhook_server,
            "get_agency_config",
            return_value={"owner_phone": "96560396543"},
        ), patch.object(
            webhook_server,
            "list_pending_approvals",
            return_value=[],
        ), patch.object(
            webhook_server,
            "load_reschedule_sessions",
            return_value={},
        ), patch.object(
            webhook_server,
            "parse_owner_reschedule_command",
            return_value=(None, "03:04 PM", ["Wednesday"], "2026-04-22"),
        ), patch.object(
            webhook_server,
            "handle_operator_message",
            side_effect=fake_handle_operator_message,
        ):
            asyncio.run(webhook_server.handle_inbound_text("96560396543", "Today 3:04 PM"))

        self.assertEqual(
            forwarded,
            [{"from": "96560396543", "type": "text", "text": "Today 3:04 PM"}],
        )

    def test_receive_message_routes_operator_document_to_operator_handler(self):
        handled: list[dict] = []

        async def fake_handle_operator_message(payload):
            handled.append(payload)
            return {"status": "success"}

        with patch.object(
            webhook_server,
            "_verify_meta_webhook_signature",
            return_value=True,
        ), patch.object(
            webhook_server,
            "is_operator_phone",
            return_value=True,
        ), patch.object(
            webhook_server,
            "handle_operator_message",
            side_effect=fake_handle_operator_message,
        ), patch.object(
            webhook_server,
            "record_whatsapp_inbound",
            return_value=None,
        ):
            client = TestClient(webhook_server.app)
            response = client.post(
                "/webhook",
                json={
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "messages": [
                                            {
                                                "id": "wamid-doc-1",
                                                "from": "96560396543",
                                                "timestamp": "1710000000",
                                                "type": "document",
                                                "document": {
                                                    "id": "media-1",
                                                    "filename": "clip.mp4",
                                                    "mime_type": "video/mp4",
                                                },
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(handled), 1)
        self.assertEqual(handled[0]["type"], "document")
        self.assertEqual(handled[0]["filename"], "clip.mp4")

    def test_receive_message_routes_non_operator_text_to_inbound_text(self):
        inbound_calls: list[tuple[str, str]] = []

        async def fake_handle_inbound_text(phone, text):
            inbound_calls.append((phone, text))

        with patch.object(
            webhook_server,
            "_verify_meta_webhook_signature",
            return_value=True,
        ), patch.object(
            webhook_server,
            "is_operator_phone",
            return_value=False,
        ), patch.object(
            webhook_server,
            "handle_inbound_text",
            side_effect=fake_handle_inbound_text,
        ), patch.object(
            webhook_server,
            "record_whatsapp_inbound",
            return_value=None,
        ):
            client = TestClient(webhook_server.app)
            response = client.post(
                "/webhook",
                json={
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "messages": [
                                            {
                                                "id": "wamid-text-1",
                                                "from": "1234567890",
                                                "timestamp": "1710000000",
                                                "type": "text",
                                                "text": {"body": "hello"},
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(inbound_calls, [("1234567890", "hello")])

    def test_synthesizer_candidate_models_include_provider_fallbacks(self):
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "groq-test",
                "OPENAI_API_KEY": "openai-test",
                "OPENROUTER_API_KEY": "openrouter-test",
            },
            clear=False,
        ), patch.object(webhook_server, "SYNTHESIZER_MODEL", "qwen/qwen3.6-plus-preview:free"):
            models = webhook_server._synthesizer_candidate_models(False)

        self.assertIn("qwen/qwen3.6-plus-preview:free", models)
        self.assertIn("groq:llama-3.3-70b-versatile", models)
        self.assertIn("openai:gpt-4.1-mini", models)

    def test_synthesize_client_profile_falls_back_after_openrouter_429(self):
        class Fake429Response:
            status_code = 429
            text = "rate limited"

            def json(self):
                return {}

        class FakeAgentResponse:
            def __init__(self, content: str):
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        async def run_test():
            with patch.dict(
                "os.environ",
                {
                    "OPENROUTER_API_KEY": "openrouter-test",
                    "GROQ_API_KEY": "groq-test",
                },
                clear=False,
            ), patch.object(
                webhook_server,
                "_prepare_synthesis_context",
                return_value=("Premium oud oils in Kuwait", [], {}),
            ), patch.object(
                webhook_server.requests,
                "post",
                return_value=Fake429Response(),
            ), patch.object(
                webhook_server.Agent,
                "chat",
                return_value=FakeAgentResponse(
                    '{"status":"success","missing_fields":[],"data":{"business_name":"Oudique","industry":"fragrance","language_profile":{"brief_language":"english","primary_language":"english","caption_output_language":"english","arabic_mode":""},"brand_voice":{"tone":"premium","style":"luxury","dialect":"","dialect_notes":""},"services":["oud oils"],"target_audience":"gift buyers","brand_voice_examples":["example"],"seo_keywords":["oud"],"hashtag_bank":["#oud"],"banned_words":[],"caption_defaults":{"min_length":150,"max_length":300,"hashtag_count_min":3,"hashtag_count_max":5},"identity":"premium fragrance brand","dos_and_donts":["Do sound premium"]}}'
                ),
            ), patch.object(
                webhook_server,
                "validate_synthesized_profile",
                return_value=[],
            ):
                return await webhook_server.synthesize_client_profile(
                    "Oudique",
                    raw_context="notes",
                    website_url="https://www.oudique.com",
                )

        result = asyncio.run(run_test())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["business_name"], "Oudique")


if __name__ == "__main__":
    unittest.main()
