import unittest
from types import SimpleNamespace
from unittest.mock import patch

from orchestrator_agent import RequestApprovalTool


class RequestApprovalToolTests(unittest.TestCase):
    def test_request_approval_blocks_when_meta_preflight_fails(self):
        tool = RequestApprovalTool()

        with patch("orchestrator_agent.resolve_client_id", return_value="cedar_roast"), patch(
            "orchestrator_agent.get_client_store",
            return_value=SimpleNamespace(get_client=lambda _client_id: {"client_id": "cedar_roast"}),
        ), patch(
            "webhook_server._validate_demo_meta_client",
            return_value={"ok": False, "detail": "Meta page is not connected."},
        ), patch(
            "orchestrator_agent.save_pending_approval"
        ) as save_mock, patch(
            "webhook_server.send_pending_approval_to_whatsapp"
        ) as send_mock:
            result = tool.execute(
                "cedar_roast",
                "Launch promo",
                ["Friday"],
                "06:00 AM",
                bundle_name="Draft 1",
            )

        self.assertIn("error", result)
        self.assertIn("Meta approval preflight failed", result["error"])
        save_mock.assert_not_called()
        send_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
