from __future__ import annotations

from typing import Any


CAPTION_PLAYBOOKS: dict[str, dict[str, dict[str, Any]]] = {
    "arabic": {
        "coffee": {
            "examples": [
                {
                    "hook_style": "curiosity gap",
                    "caption": "حر الكويت ما يحتاج وصف كثير. يحتاج رشفة تفهم الجو من أول ثانية.",
                    "why": "Starts with a compressed hook and creates a gap before revealing the payoff.",
                },
                {
                    "hook_style": "contrarian",
                    "caption": "مو كل آيسد كوفي يستاهل اللقطة. هذا النوع يثبت نفسه قبل ما يخلص الكوب.",
                    "why": "Uses a confident contrast hook and keeps the brand name out of the opening line.",
                },
                {
                    "hook_style": "story",
                    "caption": "من أول رشفة، بدأ اليوم يخف. وبعدها صار كل شيء أهدأ وأكثر ترتيبًا.",
                    "why": "Opens mid-action and turns the caption into a small narrative instead of a feature list.",
                },
                {
                    "hook_style": "how-to",
                    "caption": "إذا تبي قهوة تضبط مع طلعات الكويت، ابدأ باختيار شيء يبرد الجو قبل ما يرفع الازدحام.",
                    "why": "Promises a specific useful takeaway that feels practical and searchable.",
                },
            ],
            "hook_families": [
                {"label": "curiosity gap", "instruction": "Open with a compressed hook that teases the payoff before revealing it."},
                {"label": "contrarian", "instruction": "Challenge a common coffee assumption in a brand-safe way."},
                {"label": "story", "instruction": "Open mid-action so the caption feels like a real moment, not a template."},
                {"label": "how-to", "instruction": "Promise a specific useful outcome or choice the audience can use."},
                {"label": "social proof", "instruction": "Lead with a result, repeat purchase signal, or customer reaction."},
            ],
        },
        "general": {
            "examples": [
                {
                    "hook_style": "curiosity gap",
                    "caption": "أحيانًا أول سطر هو الفرق بين تمريرة عادية وتوقف فعلي.",
                    "why": "Keeps the opener short and worth reading before the rest of the caption appears.",
                },
                {
                    "hook_style": "social proof",
                    "caption": "الشيء الذي يعود له الناس عادة ليس الأكثر صخبًا، بل الأكثر وضوحًا وفائدة.",
                    "why": "Starts from a result or repeated behavior instead of a feature dump.",
                },
            ],
            "hook_families": [
                {"label": "curiosity gap", "instruction": "Start with the gap, not the answer."},
                {"label": "contrarian", "instruction": "Challenge a common assumption cleanly."},
                {"label": "story", "instruction": "Open in the middle of a real moment or change."},
                {"label": "how-to", "instruction": "Promise a specific practical outcome."},
                {"label": "social proof", "instruction": "Lead with a credible result or proof point."},
            ],
        },
    },
    "english": {
        "coffee": {
            "examples": [
                {
                    "hook_style": "curiosity gap",
                    "caption": "Your 3pm slump deserves a better opening line than another generic coffee post.",
                    "why": "Uses a short hook that earns the tap before the product reveal.",
                },
                {
                    "hook_style": "contrarian",
                    "caption": "Not every iced coffee deserves the hype. This one actually earns it.",
                    "why": "A clear, brand-safe hot take that signals selectivity.",
                },
                {
                    "hook_style": "story",
                    "caption": "The day was going sideways until one clean pour changed the pace.",
                    "why": "Drops the viewer into motion and makes the caption feel like a scene.",
                },
                {
                    "hook_style": "how-to",
                    "caption": "How to turn a hot afternoon into a better coffee moment in one pour.",
                    "why": "Promises a concrete, useful outcome that reads naturally in search.",
                },
            ],
            "hook_families": [
                {"label": "curiosity gap", "instruction": "Open with a line that creates tension before the payoff."},
                {"label": "contrarian", "instruction": "Use a confident take that feels selective, not clickbaity."},
                {"label": "story", "instruction": "Open mid-action so the caption feels like a real moment."},
                {"label": "how-to", "instruction": "Promise a specific practical outcome the audience can use."},
                {"label": "social proof", "instruction": "Lead with a credible result, repeat behavior, or proof point."},
            ],
        },
        "general": {
            "examples": [
                {
                    "hook_style": "curiosity gap",
                    "caption": "The strongest opener is usually the one that makes people pause for half a second.",
                    "why": "Short, direct, and built around the tap before the reveal.",
                },
                {
                    "hook_style": "social proof",
                    "caption": "What people keep saving is rarely the loudest post. It is the one that feels useful.",
                    "why": "Leads with a result and points toward value and save-worthiness.",
                },
            ],
            "hook_families": [
                {"label": "curiosity gap", "instruction": "Start with the gap before the answer."},
                {"label": "contrarian", "instruction": "Challenge a common assumption cleanly."},
                {"label": "story", "instruction": "Open in the middle of a real moment."},
                {"label": "how-to", "instruction": "Promise a specific useful outcome."},
                {"label": "social proof", "instruction": "Lead with a credible result or proof point."},
            ],
        },
    },
}


def _resolve_industry_bucket(profile: dict[str, Any]) -> str:
    raw = " ".join(
        str(value or "")
        for value in [
            profile.get("industry"),
            profile.get("offer_summary"),
            *(profile.get("seo_keywords") or []),
            *(profile.get("website_digest", {}).get("service_terms") or []),
        ]
    ).lower()
    if any(term in raw for term in ["coffee", "cafe", "espresso", "cold brew", "latte", "matcha"]):
        return "coffee"
    if "food" in raw or "beverage" in raw:
        return "coffee"
    return "general"


def build_caption_playbook(
    *,
    profile: dict[str, Any],
    language_mode: str,
    media_analysis: dict[str, Any],
    attempt_label: str,
    variant_count: int,
) -> dict[str, Any]:
    language_bucket = "arabic" if str(language_mode or "").lower() == "arabic" else "english"
    industry_bucket = _resolve_industry_bucket(profile)
    selected = CAPTION_PLAYBOOKS.get(language_bucket, {}).get(industry_bucket) or CAPTION_PLAYBOOKS[language_bucket]["general"]
    hook_families = list(selected.get("hook_families") or [])
    if not hook_families:
        hook_families = list(CAPTION_PLAYBOOKS[language_bucket]["general"].get("hook_families") or [])
    import random as _rng
    _rng.shuffle(hook_families)
    variant_briefs: list[dict[str, str]] = []
    hook_opportunities = [str(item).strip() for item in (media_analysis.get("hook_opportunities") or []) if str(item).strip()]
    for index in range(max(1, variant_count)):
        family = hook_families[index % len(hook_families)]
        angle_hint = hook_opportunities[index % len(hook_opportunities)] if hook_opportunities else attempt_label
        variant_briefs.append(
            {
                "variant_id": f"variant_{index + 1}",
                "hook_style": str(family.get("label") or "").strip(),
                "instruction": str(family.get("instruction") or "").strip(),
                "angle_hint": str(angle_hint or "").strip(),
            }
        )
    return {
        "industry_bucket": industry_bucket,
        "language_bucket": language_bucket,
        "examples": list(selected.get("examples") or [])[:3],
        "variant_briefs": variant_briefs,
    }
