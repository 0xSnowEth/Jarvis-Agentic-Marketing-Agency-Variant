import re
from typing import Any


_SUSPICIOUS_LINE_PATTERNS = (
    re.compile(r"\bignore (?:all|any|the|previous|prior|earlier) instructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard (?:all|any|the|previous|prior|earlier) instructions\b", re.IGNORECASE),
    re.compile(r"\boverride (?:the )?(?:system|developer|assistant|prior) prompt\b", re.IGNORECASE),
    re.compile(r"\bsystem prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper message\b", re.IGNORECASE),
    re.compile(r"\breturn (?:only|just) (?:valid )?(?:json|xml|yaml)\b", re.IGNORECASE),
    re.compile(r"\boutput (?:only|just) (?:valid )?(?:json|xml|yaml)\b", re.IGNORECASE),
    re.compile(r"\bcall (?:the )?tool\b", re.IGNORECASE),
    re.compile(r"\buse (?:the )?tool\b", re.IGNORECASE),
    re.compile(r"\bexecute (?:the )?(?:tool|command|function)\b", re.IGNORECASE),
    re.compile(r"\bact as\b", re.IGNORECASE),
    re.compile(r"\byou are (?:chatgpt|an ai|a helpful assistant|jarvis)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:system|assistant|developer|tool)\s*:", re.IGNORECASE),
)


def _normalize_whitespace(text: str) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _looks_instruction_like(line: str) -> bool:
    raw = str(line or "").strip()
    if not raw:
        return False
    return any(pattern.search(raw) for pattern in _SUSPICIOUS_LINE_PATTERNS)


def sanitize_external_text(text: str) -> tuple[str, dict[str, Any]]:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return "", {"removed_line_count": 0, "removed_examples": []}

    kept: list[str] = []
    removed: list[str] = []
    for line in normalized.split("\n"):
        stripped = line.strip()
        if _looks_instruction_like(stripped):
            removed.append(stripped)
            continue
        kept.append(line)

    cleaned = _normalize_whitespace("\n".join(kept))
    return cleaned, {
        "removed_line_count": len(removed),
        "removed_examples": removed[:3],
    }


def sanitize_operator_brief(text: str) -> tuple[str, dict[str, Any]]:
    cleaned, report = sanitize_external_text(text)
    return cleaned, report


def sanitize_website_digest(digest: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(digest or {})
    removed_total = 0
    removed_examples: list[str] = []

    for key in ("title", "meta_description", "excerpt"):
        value, report = sanitize_external_text(str(payload.get(key) or ""))
        payload[key] = value
        removed_total += int(report.get("removed_line_count") or 0)
        removed_examples.extend(report.get("removed_examples") or [])

    for key in ("h1", "h2", "headings", "service_terms", "brand_keywords"):
        values = payload.get(key) or []
        if not isinstance(values, list):
            values = []
        cleaned_items: list[str] = []
        for item in values:
            cleaned, report = sanitize_external_text(str(item or ""))
            if cleaned:
                cleaned_items.append(cleaned)
            removed_total += int(report.get("removed_line_count") or 0)
            removed_examples.extend(report.get("removed_examples") or [])
        payload[key] = cleaned_items

    return payload, {
        "removed_line_count": removed_total,
        "removed_examples": removed_examples[:3],
    }
