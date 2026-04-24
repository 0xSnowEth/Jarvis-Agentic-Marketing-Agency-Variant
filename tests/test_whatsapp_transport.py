import unittest

from whatsapp_transport import normalize_inbound_message


class WhatsAppTransportTests(unittest.TestCase):
    def test_interactive_title_without_id_keeps_text_fallback(self):
        normalized = normalize_inbound_message(
            {
                "id": "wamid-1",
                "from": "96560396543",
                "timestamp": "1710000000",
                "type": "interactive",
                "interactive": {
                    "button_reply": {
                        "title": "Post Now",
                    }
                },
            }
        )

        self.assertEqual(normalized["interactive_reply_id"], "")
        self.assertEqual(normalized["interactive_reply_title"], "Post Now")
        self.assertEqual(normalized["text"], "Post Now")

    def test_button_payload_maps_to_interactive_fields(self):
        normalized = normalize_inbound_message(
            {
                "id": "wamid-2",
                "from": "96560396543",
                "timestamp": "1710000001",
                "type": "button",
                "button": {
                    "payload": "OP_PREVIEW:POST_NOW",
                    "text": "Post Now",
                },
            }
        )

        self.assertEqual(normalized["interactive_reply_id"], "OP_PREVIEW:POST_NOW")
        self.assertEqual(normalized["interactive_reply_title"], "Post Now")
        self.assertEqual(normalized["text"], "Post Now")


if __name__ == "__main__":
    unittest.main()
