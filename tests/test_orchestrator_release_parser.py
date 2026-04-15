import unittest

from orchestrator_agent import parse_multi_clause_release_request


class OrchestratorReleaseParserTests(unittest.TestCase):
    def test_post_this_now_stays_immediate(self):
        parsed = parse_multi_clause_release_request(
            '@[Bakhourito] draft_id:"32039ae7-e76d-4806-8901-98f9f9bc54ca" draft:"Oudie badoduie" post this now'
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed["tasks"]), 1)
        task = parsed["tasks"][0]
        self.assertEqual(task["status"], "ready")
        self.assertEqual(task["action"], "post_now")
        self.assertEqual(task["warning"], "")
        self.assertEqual(task["scheduled_date"], "")
        self.assertEqual(task["time"], "")

    def test_scheduled_clause_still_requires_release_window(self):
        parsed = parse_multi_clause_release_request(
            '@[Bakhourito] draft_id:"32039ae7-e76d-4806-8901-98f9f9bc54ca" draft:"Oudie badoduie" schedule this friday'
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed["tasks"]), 1)
        task = parsed["tasks"][0]
        self.assertEqual(task["status"], "ambiguous")
        self.assertEqual(task["action"], "")
        self.assertIn("exact release time", task["warning"].lower())


if __name__ == "__main__":
    unittest.main()
