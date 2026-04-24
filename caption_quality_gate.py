from __future__ import annotations

import logging
from typing import Any

from content_ops_caption_scorer import score_caption_with_content_ops

logger = logging.getLogger("CaptionQualityGate")


def score_caption_quality(
    caption_payload: dict[str, Any],
    brand_profile: dict[str, Any],
    *,
    language_mode: str,
    topic: str = "",
    media_type: str = "image_post",
) -> dict[str, Any]:
    try:
        return score_caption_with_content_ops(
            caption_payload,
            brand_profile,
            language_mode=language_mode,
            topic=topic,
            media_type=media_type,
        )
    except Exception as exc:
        logger.exception("Deterministic caption quality scoring failed: %s", exc)
        return {
            "score": 0,
            "passed": False,
            "threshold": 85,
            "dimensions": {},
            "dimension_weights": {},
            "failures": [f"Content Ops scorer failed: {type(exc).__name__}: {exc}"],
            "verdict": "Needs another pass",
            "notes": {"source": "caption_quality_gate_fallback"},
        }
