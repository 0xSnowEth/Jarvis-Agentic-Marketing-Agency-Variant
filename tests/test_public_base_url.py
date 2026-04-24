import unittest
from types import SimpleNamespace
from unittest.mock import patch

import public_base_url
import whatsapp_operator


class PublicBaseUrlTests(unittest.TestCase):
    def tearDown(self):
        public_base_url.reset_observed_public_base_url()

    def test_build_meta_connect_link_prefers_observed_public_base(self):
        with patch.dict(
            "os.environ",
            {
                "META_APP_ID": "app-id",
                "META_APP_SECRET": "app-secret",
                "META_OAUTH_PUBLIC_BASE_URL": "https://old-session.trycloudflare.com",
                "WEBHOOK_PROXY_URL": "https://old-webhook.trycloudflare.com",
            },
            clear=False,
        ):
            public_base_url.remember_public_base_url("https://fresh-session.trycloudflare.com")
            link = whatsapp_operator.build_meta_connect_link("cedar_roast", "96560396543")

        self.assertTrue(link.startswith("https://fresh-session.trycloudflare.com/api/meta-oauth/start"))

    def test_redirect_uri_prefers_observed_public_base_over_stale_ephemeral_env(self):
        with patch.dict(
            "os.environ",
            {
                "META_OAUTH_REDIRECT_URI": "https://old-session.trycloudflare.com/api/meta-oauth-callback",
                "META_OAUTH_PUBLIC_BASE_URL": "https://old-session.trycloudflare.com",
                "WEBHOOK_PROXY_URL": "https://old-webhook.trycloudflare.com",
            },
            clear=False,
        ):
            public_base_url.remember_public_base_url("https://fresh-session.trycloudflare.com")
            redirect_uri = public_base_url.get_meta_oauth_redirect_uri()

        self.assertEqual(redirect_uri, "https://fresh-session.trycloudflare.com/api/meta-oauth-callback")

    def test_remember_public_base_from_request_ignores_localhost(self):
        request = SimpleNamespace(
            headers={"host": "localhost:8000"},
            url=SimpleNamespace(scheme="http"),
        )

        remembered = public_base_url.remember_public_base_from_request(request)

        self.assertEqual(remembered, "")
        self.assertEqual(public_base_url.get_observed_public_base_url(), "")

    def test_remember_public_base_from_request_uses_public_host(self):
        request = SimpleNamespace(
            headers={"host": "fresh-session.trycloudflare.com"},
            url=SimpleNamespace(scheme="https"),
        )

        remembered = public_base_url.remember_public_base_from_request(request)

        self.assertEqual(remembered, "https://fresh-session.trycloudflare.com")
        self.assertEqual(public_base_url.get_observed_public_base_url(), "https://fresh-session.trycloudflare.com")


if __name__ == "__main__":
    unittest.main()
