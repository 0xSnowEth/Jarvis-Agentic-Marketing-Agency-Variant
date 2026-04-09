import unittest
from datetime import date

from schedule_utils import parse_time_string, resolve_date_phrase


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


if __name__ == "__main__":
    unittest.main()
