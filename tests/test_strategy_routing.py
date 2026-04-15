import importlib
import unittest


class StrategyRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import strategy_agent

        cls.strategy_agent = importlib.reload(strategy_agent)

    def test_strategy_prompt_detection_positive_cases(self):
        positive_cases = [
            "plan next month for @Veloura_Studio",
            "build a content calendar for @Stack_District",
            "what should we post next week for @Torque_District",
            "need content ideas for @Veloura_Studio",
            "give me a campaign plan for @Stack District",
            "what do you recommend for @Torque_District next month",
            "strategy for @Veloura_Studio",
            "competitor and trend ideas for @Stack_District",
            "monthly plan for @Torque_District",
            "weekly plan for @Veloura_Studio",
            "content strategy for @Stack District",
            "posting ideas for @Torque_District",
            "plan content pillars for @Veloura_Studio",
            "what should I post for @Stack_District this week",
            "next month content ideas for @Torque_District",
            "campaign ideas for @Veloura_Studio",
            "trend strategy for @Stack District",
            "build a social strategy for @Torque_District",
            "content plan for @Veloura_Studio",
            "plan next week of content for @Stack_District",
        ]
        for prompt in positive_cases:
            with self.subTest(prompt=prompt):
                self.assertTrue(self.strategy_agent.prompt_requests_strategy(prompt))

    def test_strategy_prompt_detection_negative_cases(self):
        negative_cases = [
            "post @Veloura_Studio . Fashionista now",
            "schedule @Stack_District . burger squad tomorrow at 7:00 PM",
            "send @Torque_District . Carso for approval tomorrow at 4:30 PM",
            "run it",
            "approve this draft",
            "publish the loaded draft now",
            "post @Veloura_Studio draft fashion now",
            "schedule this for tomorrow",
            "send this to whatsapp approval",
            "delete @Stack_District . burger squad",
        ]
        for prompt in negative_cases:
            with self.subTest(prompt=prompt):
                self.assertFalse(self.strategy_agent.prompt_requests_strategy(prompt))

    def test_strategy_window_derivation(self):
        cases = [
            ("plan next month for @Veloura_Studio", "next_30_days"),
            ("what should we post this week for @Stack_District", "next_7_days"),
            ("weekly content ideas for @Torque_District", "next_7_days"),
            ("build a content calendar for @Veloura_Studio", "next_30_days"),
        ]
        for prompt, expected in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(self.strategy_agent.derive_strategy_window(prompt), expected)


if __name__ == "__main__":
    unittest.main()
