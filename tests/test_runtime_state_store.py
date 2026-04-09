import importlib
import os
import tempfile
import unittest


class RuntimeStateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prev_runtime_dir = os.environ.get("JARVIS_RUNTIME_STATE_DIR")
        self.prev_backend = os.environ.get("JARVIS_DATA_BACKEND")
        os.environ["JARVIS_RUNTIME_STATE_DIR"] = self.temp_dir.name
        os.environ["JARVIS_DATA_BACKEND"] = "json"

        import runtime_state_store

        self.runtime_state_store = importlib.reload(runtime_state_store)

    def tearDown(self):
        if self.prev_runtime_dir is None:
            os.environ.pop("JARVIS_RUNTIME_STATE_DIR", None)
        else:
            os.environ["JARVIS_RUNTIME_STATE_DIR"] = self.prev_runtime_dir
        if self.prev_backend is None:
            os.environ.pop("JARVIS_DATA_BACKEND", None)
        else:
            os.environ["JARVIS_DATA_BACKEND"] = self.prev_backend
        self.temp_dir.cleanup()

    def test_auth_session_persists_and_expires(self):
        rss = self.runtime_state_store
        record = rss.save_auth_session("token-1", "2030-01-01T00:00:00+00:00", {"role": "admin"})
        self.assertEqual(record["session_token"], "token-1")
        self.assertEqual(rss.get_auth_session("token-1")["payload_json"]["role"], "admin")

        touched = rss.touch_auth_session("token-1", "2026-04-08T12:00:00+00:00")
        self.assertEqual(touched["last_seen_at"], "2026-04-08T12:00:00+00:00")

        rss.save_auth_session("token-expired", "2020-01-01T00:00:00+00:00")
        removed = rss.delete_expired_auth_sessions(now_iso="2026-04-08T12:00:00+00:00")
        self.assertEqual(removed, 1)
        self.assertIsNone(rss.get_auth_session("token-expired"))

    def test_orchestrator_runs_and_reschedule_sessions_persist(self):
        rss = self.runtime_state_store
        saved = rss.save_orchestrator_run_state(
            {
                "run_id": "run-123",
                "status": "queued",
                "items": [{"draft_name": "Launch"}],
            }
        )
        self.assertEqual(saved["run_id"], "run-123")
        self.assertEqual(rss.get_orchestrator_run_state("run-123")["status"], "queued")
        self.assertEqual(rss.list_orchestrator_run_states(limit=5)[0]["run_id"], "run-123")

        sessions = rss.save_reschedule_session_map(
            {
                "+639171234567": {"approval_id": "APP-1", "client": "Veloura_Studio"},
            }
        )
        self.assertIn("+639171234567", sessions)
        loaded = rss.load_reschedule_session_map()
        self.assertEqual(loaded["+639171234567"]["approval_id"], "APP-1")

    def test_audit_event_is_written(self):
        rss = self.runtime_state_store
        event = rss.record_operator_audit_event(
            "auth.login_succeeded",
            {"ip": "127.0.0.1"},
            actor="operator",
            request_id="req-1",
        )
        self.assertEqual(event["event_type"], "auth.login_succeeded")
        self.assertEqual(event["request_id"], "req-1")


if __name__ == "__main__":
    unittest.main()
