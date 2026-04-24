import unittest

from caption_quality_gate import score_caption_quality


class CaptionQualityGateTests(unittest.TestCase):
    def _brand_profile(self):
        return {
            "business_name": "Cedar Roast",
            "city_market": "Kuwait",
            "offer_summary": "iced chocolate, cold brew, specialty coffee",
            "seo_keywords": ["iced chocolate", "Kuwait coffee culture"],
            "website_digest": {
                "service_terms": ["cold brew", "specialty coffee", "iced chocolate"],
                "brand_keywords": ["cedar roast", "summer drinks"],
            },
            "trend_dossier": {
                "topical_language": ["summer drinks", "Kuwait", "coffee culture"],
            },
        }

    def test_strong_caption_scores_higher_than_generic_ai_caption(self):
        brand_profile = self._brand_profile()
        strong_quality = score_caption_quality(
            {
                "caption": "هل جرّبت آيسد شوكولاتة Cedar Roast في الكويت؟ هذا المشروب يجمع بين القهوة المختصة والكاكاو البارد بطريقة أخفّ وأوضح للصيف.",
                "hashtags": ["#CedarRoast", "#KuwaitCoffeeCulture", "#IcedChocolate", "#SpecialtyCoffee"],
            },
            brand_profile,
            language_mode="arabic",
            topic="Iced chocolate launch",
            media_type="carousel_post",
        )
        generic_quality = score_caption_quality(
            {
                "caption": "Discover the next level coffee experience with a seamless and innovative drink that elevates your day. Don't miss out and visit us today!",
                "hashtags": ["#coffee", "#summer", "#goodvibes", "#innovation", "#discover"],
            },
            brand_profile,
            language_mode="english",
            topic="Iced chocolate launch",
            media_type="carousel_post",
        )

        self.assertGreater(strong_quality["score"], generic_quality["score"])
        self.assertIn("dimensions", strong_quality)
        self.assertIn("humanizer", strong_quality["dimensions"])
        self.assertLess(generic_quality["dimensions"]["humanizer"], strong_quality["dimensions"]["humanizer"])
        self.assertTrue(generic_quality["failures"])

    def test_quality_payload_keeps_expected_contract_and_source_assets(self):
        quality = score_caption_quality(
            {
                "caption": "Have you tried Cedar Roast cold brew in Kuwait yet? One clean pour, one bold finish, and a much sharper coffee break.",
                "hashtags": ["#CedarRoast", "#KuwaitCoffeeCulture", "#ColdBrew", "#SpecialtyCoffee"],
            },
            self._brand_profile(),
            language_mode="english",
            topic="Cold brew launch",
            media_type="image_post",
        )

        self.assertIn("score", quality)
        self.assertIn("passed", quality)
        self.assertIn("threshold", quality)
        self.assertIn("failures", quality)
        self.assertIn("dimensions", quality)
        self.assertIn("dimension_weights", quality)
        self.assertIn("verdict", quality)
        self.assertIn("notes", quality)
        self.assertIn("source_assets", quality["notes"])
        self.assertIn("humanizer_rubric", quality["notes"]["source_assets"])


if __name__ == "__main__":
    unittest.main()
