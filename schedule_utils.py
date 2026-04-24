import calendar
import re
from datetime import date, datetime, timedelta
from typing import Iterable

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
WEEKDAY_INDEX = {name.lower(): index for index, name in enumerate(WEEKDAY_NAMES)}
MONTH_INDEX = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
MONTH_INDEX.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})
MONTH_INDEX["sept"] = 9

DAY_ALIASES = {
    "today": "today",
    "tdy": "today",
    "tonight": "tonight",
    "tonite": "tonight",
    "later tonight": "tonight",
    "this evening": "tonight",
    "evening": "tonight",
    "later this evening": "tonight",
    "this afternoon": "today",
    "this morning": "today",
    "tomorrow": "tomorrow",
    "tommorow": "tomorrow",
    "tmrw": "tomorrow",
    "tmr": "tomorrow",
}


def normalize_prompt_date_typos(text: str | None) -> str:
    raw = str(text or "")
    normalized = raw
    for alias, canonical in DAY_ALIASES.items():
        if alias == canonical:
            continue
        normalized = re.sub(rf"\b{re.escape(alias)}\b", canonical, normalized, flags=re.IGNORECASE)
    return normalized


def coerce_days(value: Iterable | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_iso_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_time_string(time_str: str) -> datetime.time:
    cleaned = str(time_str or "").strip().upper()
    cleaned = re.sub(r"(?<=\d)(AM|PM)\b", r" \1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"time data '{time_str}' does not match supported formats")


def format_display_date(date_value: str | date | None) -> str:
    if isinstance(date_value, str):
        parsed = parse_iso_date(date_value)
    else:
        parsed = date_value
    if not parsed:
        return ""
    return f"{parsed.strftime('%A')}, {parsed.strftime('%B')} {parsed.day}"


def format_schedule_label(time_str: str, scheduled_date: str | None = None, days: list[str] | None = None) -> str:
    parsed_date = parse_iso_date(scheduled_date)
    if parsed_date:
        return f"{format_display_date(parsed_date)} at {time_str}"

    day_values = [str(day).title() for day in coerce_days(days)]
    if day_values:
        return f"{', '.join(day_values)} at {time_str}"
    return time_str


def past_time_error_message(time_str: str, scheduled_date: str | None = None, days: list[str] | None = None) -> str:
    release_window = format_schedule_label(time_str, scheduled_date=scheduled_date, days=days)
    return (
        f"The requested release window ({release_window}) is already in the past. "
        "Choose a later time or a future date."
    )


def normalize_weekday_token(token: str, base_date: date | None = None) -> str:
    base = base_date or datetime.now().date()
    lowered = DAY_ALIASES.get(str(token or "").strip().lower(), str(token or "").strip().lower())
    if not lowered:
        return ""
    if lowered == "today":
        return base.strftime("%A")
    if lowered == "tonight":
        return base.strftime("%A")
    if lowered == "tomorrow":
        return (base + timedelta(days=1)).strftime("%A")
    if lowered == "everyday":
        return "Everyday"
    return str(token).strip().title()


def _next_or_same_weekday(base_date: date, target_weekday: int) -> date:
    delta = (target_weekday - base_date.weekday()) % 7
    return base_date + timedelta(days=delta)


def _resolve_relative_weekday(base_date: date, modifier: str, weekday_name: str) -> date | None:
    target = WEEKDAY_INDEX.get(weekday_name.lower())
    if target is None:
        return None

    next_or_same = _next_or_same_weekday(base_date, target)
    if modifier == "this":
        return next_or_same
    if modifier == "next":
        if next_or_same == base_date:
            return base_date + timedelta(days=7)
        return next_or_same + timedelta(days=7)
    return None


def _candidate_from_month_day(base_date: date, month: int, day_num: int, year: int | None = None) -> date | None:
    years = [year] if year else [base_date.year, base_date.year + 1]
    for target_year in years:
        try:
            candidate = date(target_year, month, day_num)
        except ValueError:
            continue
        if candidate >= base_date:
            return candidate
    return None


def _candidate_from_day_of_month(base_date: date, day_num: int, weekday_name: str | None = None, year: int | None = None) -> date | None:
    month_cursor = base_date.month
    year_cursor = year or base_date.year

    for _ in range(0, 18):
        try:
            candidate = date(year_cursor, month_cursor, day_num)
        except ValueError:
            candidate = None

        if candidate and candidate >= base_date:
            if weekday_name:
                if candidate.strftime("%A").lower() == weekday_name.lower():
                    return candidate
            else:
                return candidate

        month_cursor += 1
        if month_cursor > 12:
            month_cursor = 1
            year_cursor += 1
        if year and year_cursor > year:
            break
    return None


def resolve_date_phrase(text: str | None, base_date: date | None = None) -> date | None:
    base = base_date or datetime.now().date()
    raw = str(text or "").strip()
    if not raw:
        return None

    parsed_iso = parse_iso_date(raw)
    if parsed_iso:
        return parsed_iso

    cleaned = re.sub(r"\s+", " ", raw.replace(",", " ")).strip().lower()
    cleaned = DAY_ALIASES.get(cleaned, cleaned)
    if cleaned == "today":
        return base
    if cleaned == "tonight":
        return base
    if cleaned == "tomorrow":
        return base + timedelta(days=1)

    relative = re.match(r"^(this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", cleaned)
    if relative:
        return _resolve_relative_weekday(base, relative.group(1), relative.group(2))

    bare_weekday = re.match(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", cleaned)
    if bare_weekday:
        target = WEEKDAY_INDEX.get(bare_weekday.group(1))
        if target is not None:
            return _next_or_same_weekday(base, target)

    month_day = re.match(
        r"^(?:(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+)?"
        r"(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:\s+(\d{4}))?$",
        cleaned,
    )
    if month_day:
        weekday_name, month_name, day_num, year_num = month_day.groups()
        month = MONTH_INDEX.get(month_name)
        candidate = _candidate_from_month_day(base, month, int(day_num), int(year_num) if year_num else None)
        if candidate and weekday_name and candidate.strftime("%A").lower() != weekday_name.lower():
            return None
        return candidate

    day_month = re.match(
        r"^(?:(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+)?"
        r"(\d{1,2})\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)(?:\s+(\d{4}))?$",
        cleaned,
    )
    if day_month:
        weekday_name, day_num, month_name, year_num = day_month.groups()
        month = MONTH_INDEX.get(month_name)
        candidate = _candidate_from_month_day(base, month, int(day_num), int(year_num) if year_num else None)
        if candidate and weekday_name and candidate.strftime("%A").lower() != weekday_name.lower():
            return None
        return candidate

    numeric_date = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", cleaned)
    if numeric_date:
        month_num, day_num, year_num = numeric_date.groups()
        year = int(year_num) if year_num else None
        if year and year < 100:
            year += 2000
        return _candidate_from_month_day(base, int(month_num), int(day_num), year)

    weekday_and_day = re.match(
        r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(\d{1,2})(?:\s+(\d{4}))?$",
        cleaned,
    )
    if weekday_and_day:
        weekday_name, day_num, year_num = weekday_and_day.groups()
        return _candidate_from_day_of_month(base, int(day_num), weekday_name=weekday_name, year=int(year_num) if year_num else None)

    day_and_weekday = re.match(
        r"^(\d{1,2})\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(\d{4}))?$",
        cleaned,
    )
    if day_and_weekday:
        day_num, weekday_name, year_num = day_and_weekday.groups()
        return _candidate_from_day_of_month(base, int(day_num), weekday_name=weekday_name, year=int(year_num) if year_num else None)

    return None


def normalize_schedule_request(days: list[str], scheduled_date: str | None = None, base_dt: datetime | None = None) -> tuple[str | None, list[str]]:
    base = base_dt or datetime.now()
    raw_days = coerce_days(days)

    resolved_from_scheduled = resolve_date_phrase(scheduled_date, base.date()) if scheduled_date else None
    resolved_from_days = resolve_date_phrase(raw_days[0], base.date()) if len(raw_days) == 1 else None
    resolved_date = resolved_from_scheduled or resolved_from_days

    if resolved_date:
        return resolved_date.isoformat(), [resolved_date.strftime("%A")]

    normalized_days = [normalize_weekday_token(day, base.date()) for day in raw_days]
    normalized_days = [day for day in normalized_days if day]
    return None, normalized_days


def schedule_request_is_in_past(
    time_str: str,
    scheduled_date: str | None = None,
    raw_days: list[str] | None = None,
    base_dt: datetime | None = None,
) -> bool:
    base = base_dt or datetime.now()
    scheduled_time = parse_time_string(time_str)
    raw_day_values = coerce_days(raw_days)
    resolved_from_scheduled = resolve_date_phrase(scheduled_date, base.date()) if scheduled_date else None
    resolved_from_days = resolve_date_phrase(raw_day_values[0], base.date()) if len(raw_day_values) == 1 else None
    resolved_date = resolved_from_scheduled or resolved_from_days

    if resolved_date:
        scheduled_dt = datetime.combine(resolved_date, scheduled_time)
        return scheduled_dt <= base

    if len(raw_day_values) == 1 and raw_day_values[0].strip().lower() == "today":
        return scheduled_time <= base.time()
    return False
