import unittest
from unittest.mock import patch

from publish_agent import PublishAgent


class PublishAgentTests(unittest.TestCase):
    def test_prepare_instagram_image_urls_keeps_supabase_host_direct_by_default(self):
        agent = PublishAgent()
        with patch.object(
            agent,
            "_mirror_instagram_image_to_catbox",
            side_effect=lambda path: f"https://files.example/{path.split('/')[-1]}",
        ):
            urls, error = agent._prepare_instagram_image_urls(
                ["assets/cedar_roast/hero.jpg"],
                ["https://gqlsdsprvjcqfycalgex.supabase.co/storage/v1/object/public/client-assets/cedar_roast/hero.jpg"],
                "gqlsdsprvjcqfycalgex.supabase.co",
            )

        self.assertEqual(error, "")
        self.assertEqual(
            urls,
            ["https://gqlsdsprvjcqfycalgex.supabase.co/storage/v1/object/public/client-assets/cedar_roast/hero.jpg"],
        )

    def test_prepare_instagram_video_urls_keeps_supabase_host_direct_by_default(self):
        agent = PublishAgent()
        with patch.object(
            agent,
            "_mirror_instagram_video_to_catbox",
            side_effect=lambda path: f"https://files.example/{path.split('/')[-1]}",
        ):
            urls, error = agent._prepare_instagram_video_urls(
                ["assets/cedar_roast/reel.mp4"],
                ["https://gqlsdsprvjcqfycalgex.supabase.co/storage/v1/object/public/client-assets/cedar_roast/reel.mp4"],
                "gqlsdsprvjcqfycalgex.supabase.co",
            )

        self.assertEqual(error, "")
        self.assertEqual(
            urls,
            ["https://gqlsdsprvjcqfycalgex.supabase.co/storage/v1/object/public/client-assets/cedar_roast/reel.mp4"],
        )

    def test_should_retry_instagram_with_mirror_for_supabase_fetch_failure(self):
        agent = PublishAgent()
        self.assertTrue(
            agent._should_retry_instagram_with_mirror(
                "gqlsdsprvjcqfycalgex.supabase.co",
                {
                    "status": "error",
                    "step": "create_video_container",
                    "error_message": "The media could not be fetched from this URI.",
                },
            )
        )

    def test_execute_requires_client_specific_meta_credentials(self):
        agent = PublishAgent()

        with patch("publish_agent.get_client_store") as store_mock, patch.object(
            agent,
            "_build_public_media_urls",
            return_value=(["https://assets.example/hero.jpg"], [], "https://assets.example"),
        ), patch(
            "publish_agent.os.getenv",
            side_effect=lambda key, default=None: {
                "META_ACCESS_TOKEN": "shared-env-token",
                "META_PAGE_ID": "shared-page",
                "META_IG_USER_ID": "shared-ig",
            }.get(key, default),
        ):
            store_mock.return_value.get_client.return_value = {
                "client_id": "cedar_roast",
                "facebook_page_id": "",
                "instagram_account_id": "",
                "meta_access_token": "",
            }
            result = agent.publish(
                {
                    "status": "success",
                    "client_name": "cedar_roast",
                    "caption": "Caption",
                    "hashtags": [],
                    "images": ["tmp/hero.jpg"],
                }
            )

        self.assertEqual(result["status"], "error")
        self.assertIn("No Meta Access Token configured for client", result["message"])


if __name__ == "__main__":
    unittest.main()
