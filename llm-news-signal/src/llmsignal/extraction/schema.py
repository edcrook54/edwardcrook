"""The extraction output contract: what the LLM must return per statement."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Sentiment = Literal["hawkish", "dovish", "neutral"]


class ExtractionResult(BaseModel):
    hawkish_dovish_score: float = Field(
        ge=-1.0, le=1.0, description="-1 maximally dovish, +1 maximally hawkish, 0 neutral"
    )
    surprise_magnitude: float = Field(
        ge=0.0, le=1.0, description="0 = fully expected given prior guidance, 1 = major surprise"
    )
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(
        max_length=500, description="one or two sentences, for human spot-checking"
    )


EXTRACTION_TOOL_SCHEMA: dict[str, Any] = {
    "name": "record_fomc_sentiment",
    "description": "Record the extracted sentiment/surprise assessment of an FOMC statement.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hawkish_dovish_score": {
                "type": "number",
                "minimum": -1,
                "maximum": 1,
                "description": "-1 maximally dovish, +1 maximally hawkish, 0 neutral",
            },
            "surprise_magnitude": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0 = fully expected given prior guidance, 1 = major surprise",
            },
            "sentiment": {"type": "string", "enum": ["hawkish", "dovish", "neutral"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string", "description": "one or two sentences"},
        },
        "required": [
            "hawkish_dovish_score",
            "surprise_magnitude",
            "sentiment",
            "confidence",
            "rationale",
        ],
    },
}
