import unittest
from datetime import date, datetime

from schedule_utils import normalize_schedule_request, parse_time_string, resolve_date_phrase, schedule_request_is_in_past


class ScheduleUtilsTests(unittest.TestCase):
    def test_parse_time_string_accepts_compact_meridiem_forms(self):
        self.assertEqual(parse_time_string("2:00AM").hour, 2)
        self.assertEqual(parse_time_string("2PM").hour, 14)
        self.assertEqual(parse_time_string("8:30 PM").minute, 30)

    def test_resolve_date_phrase_handles_relative_words(self):
        base = date(2026, 4, 8)
        self.assertEqual(resolve_date_phrase("today", base), date(2026, 4, 8))
        self.assertEqual(resolve_date_phrase("tonight", base), date(2026, 4, 8))
        self.assertEqual(resolve_date_phrase("tomorrow", base), date(2026, 4, 9))
        self.assertEqual(resolve_date_phrase("this tuesday", base), date(2026, 4, 14))

    def test_resolve_date_phrase_accepts_day_month_order(self):
        base = date(2026, 4, 8)
        self.assertEqual(resolve_date_phrase("24 april", base), date(2026, 4, 24))
        self.assertEqual(resolve_date_phrase("friday 24 april", base), date(2026, 4, 24))

    def test_scheduled_date_takes_priority_over_weekday_reinterpretation(self):
        base = datetime(2026, 4, 22, 14, 38)
        scheduled_date, days = normalize_schedule_request(["Wednesday"], scheduled_date="2026-04-23", base_dt=base)
        self.assertEqual(scheduled_date, "2026-04-23")
        self.assertEqual(days, ["Thursday"])

        self.assertFalse(
            schedule_request_is_in_past(
                "02:42 PM",
                scheduled_date="2026-04-23",
                raw_days=["Wednesday"],
                base_dt=base,
            )
        )


if __name__ == "__main__":
    unittest.main()
