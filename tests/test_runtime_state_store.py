import importlib
import os
import tempfile
import unittest


class StubRuntimeStore:
    backend_name = "stub"

    def __init__(self, *, get_run=None, save_run=None, list_runs=None, fail_methods=None):
        self.get_run = get_run
        self.save_run = save_run
        self.list_runs = list_runs
        self.fail_methods = set(fail_methods or [])
        self.saved_payloads = []

    def _maybe_fail(self, method_name):
        if method_name in self.fail_methods:
            raise RuntimeError(f"{method_name} failed")

    def get_orchestrator_run(self, run_id):
        self._maybe_fail("get_orchestrator_run")
        if callable(self.get_run):
            return self.get_run(run_id)
        return self.get_run

    def save_orchestrator_run(self, payload):
        self._maybe_fail("save_orchestrator_run")
        self.saved_payloads.append(dict(payload))
        if callable(self.save_run):
            return self.save_run(payload)
        return self.save_run

    def list_orchestrator_runs(self, limit=100):
        self._maybe_fail("list_orchestrator_runs")
        if callable(self.list_runs):
            return self.list_runs(limit)
        return list(self.list_runs or [])

    def get_auth_session(self, token):
        return None

    def save_auth_session(self, token, expires_at, payload=None):
        return {}

    def delete_auth_session(self, token):
        return False

    def delete_expired_auth_sessions(self, now_iso=None):
        return 0

    def touch_auth_session(self, token, seen_at=None):
        return None

    def replace_reschedule_sessions(self, sessions):
        return sessions

    def load_reschedule_sessions(self):
        return {}

    def record_audit_event(self, event_type, payload=None, actor=None, request_id=None):
        return {}


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

    def test_fallback_run_save_prefers_newer_payload_over_stale_primary_read(self):
        rss = self.runtime_state_store
        stale_primary = {
            "run_id": "run-merge-1",
            "status": "completed",
            "updated_at": "2026-04-11T07:54:58+00:00",
            "completed_at": "2026-04-11T07:56:01+00:00",
            "items": [{"status": "queued", "draft_name": "Launch"}],
        }
        newest_payload = {
            "run_id": "run-merge-1",
            "status": "completed",
            "updated_at": "2026-04-11T07:56:10+00:00",
            "completed_at": "2026-04-11T07:56:10+00:00",
            "items": [{"status": "published", "draft_name": "Launch"}],
        }
        primary = StubRuntimeStore(save_run=stale_primary)
        fallback = StubRuntimeStore(save_run=None)
        store = rss.FallbackRuntimeStateStore(primary, fallback)

        saved = store.save_orchestrator_run(newest_payload)

        self.assertEqual(saved["items"][0]["status"], "published")
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(primary.saved_payloads[0]["items"][0]["status"], "published")
        self.assertEqual(fallback.saved_payloads[0]["items"][0]["status"], "published")

    def test_fallback_run_reads_prefer_more_complete_record(self):
        rss = self.runtime_state_store
        primary = StubRuntimeStore(
            get_run={
                "run_id": "run-merge-2",
                "status": "completed",
                "updated_at": "2026-04-11T07:55:00+00:00",
                "items": [{"status": "queued", "draft_name": "Launch"}],
            },
            list_runs=[
                {
                    "run_id": "run-merge-2",
                    "status": "completed",
                    "updated_at": "2026-04-11T07:55:00+00:00",
                    "items": [{"status": "queued", "draft_name": "Launch"}],
                }
            ],
        )
        fallback = StubRuntimeStore(
            get_run={
                "run_id": "run-merge-2",
                "status": "completed",
                "updated_at": "2026-04-11T07:56:00+00:00",
                "completed_at": "2026-04-11T07:56:00+00:00",
                "items": [{"status": "published", "draft_name": "Launch"}],
            },
            list_runs=[
                {
                    "run_id": "run-merge-2",
                    "status": "completed",
                    "updated_at": "2026-04-11T07:56:00+00:00",
                    "completed_at": "2026-04-11T07:56:00+00:00",
                    "items": [{"status": "published", "draft_name": "Launch"}],
                }
            ],
        )
        store = rss.FallbackRuntimeStateStore(primary, fallback)

        loaded = store.get_orchestrator_run("run-merge-2")
        self.assertEqual(loaded["items"][0]["status"], "published")

        listed = store.list_orchestrator_runs(limit=5)
        self.assertEqual(listed[0]["items"][0]["status"], "published")


if __name__ == "__main__":
    unittest.main()
