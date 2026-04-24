import unittest
from datetime import datetime

from schedule_store import is_past_due_one_off_job, split_schedule_views


class ScheduleStoreTests(unittest.TestCase):
    def test_same_day_past_one_off_is_purged(self):
        job = {
            "job_id": "job-1",
            "client": "cedar_roast",
            "status": "approved",
            "scheduled_date": "2026-04-23",
            "time": "06:00 AM",
            "days": [],
        }

        self.assertTrue(is_past_due_one_off_job(job, now=datetime(2026, 4, 23, 13, 30)))
        active, history = split_schedule_views([job], now=datetime(2026, 4, 23, 13, 30))
        self.assertEqual(active, [])
        self.assertEqual(history, [])

    def test_scheduled_date_takes_priority_even_when_days_are_present(self):
        job = {
            "job_id": "job-2",
            "client": "cedar_roast",
            "status": "approved",
            "scheduled_date": "2026-04-23",
            "time": "06:00 AM",
            "days": ["Thursday"],
        }

        self.assertTrue(is_past_due_one_off_job(job, now=datetime(2026, 4, 23, 13, 30)))
        active, history = split_schedule_views([job], now=datetime(2026, 4, 23, 13, 30))
        self.assertEqual(active, [])
        self.assertEqual(history, [])


if __name__ == "__main__":
    unittest.main()
