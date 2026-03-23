"""Utilities for extracting strict JSON from LLM output."""

from __future__ import annotations

from json import JSONDecodeError
import json
import re
from typing import Any


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first valid JSON object from text."""

    candidates: list[str] = []
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    block_match = JSON_BLOCK_RE.search(text)
    if block_match:
        candidates.append(block_match.group(1).strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1].strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError(f"Model response did not contain a valid JSON object:\n{text}")
