"""
Pre-filter: runs BEFORE any LLM or embedding calls.
Drops obvious noise using cheap keyword/regex + engagement heuristics.
"""
import re
from dataclasses import dataclass

# High-signal complaint phrases
PAIN_KEYWORDS = [
    "frustrated", "frustrating", "annoying", "annoyed", "hate", "hated",
    "terrible", "horrible", "awful", "broken", "doesn't work", "can't",
    "impossible", "no way to", "wish there was", "why isn't there",
    "no tool", "no app", "nobody solves", "would pay", "pay for",
    "manual", "tedious", "time-consuming", "slow", "painful",
    "spent hours", "wasted", "workaround", "hack", "jury-rigged",
    "legacy", "outdated", "neglected", "abandoned", "no support",
    "missing feature", "feature request", "please add",
]

NOISE_PATTERNS = [
    r"^(lol|lmao|rofl|haha|ha ha)",
    r"^\s*[>\|]",                     # quoted/forwarded text only
    r"http\S+\s*$",                   # post is just a URL
    r"^\s*\[deleted\]\s*$",
    r"^\s*\[removed\]\s*$",
]

_compiled_noise = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]


@dataclass
class PrefilterResult:
    passed: bool
    reason: str
    score: float   # 0.0 – 1.0, rough signal strength


def prefilter(text: str, engagement: int = 0, min_engagement: int = 0) -> PrefilterResult:
    """
    Returns a PrefilterResult.
    Passed observations move on to embeddings + LLM. 
    Failed ones are logged and discarded.
    """
    if not text or len(text.strip()) < 30:
        return PrefilterResult(False, "too_short", 0.0)

    # Noise pattern check
    for pattern in _compiled_noise:
        if pattern.search(text[:200]):
            return PrefilterResult(False, "noise_pattern", 0.0)

    # Engagement gate
    if engagement < min_engagement:
        return PrefilterResult(False, f"low_engagement:{engagement}", 0.0)

    # Keyword signal
    text_lower = text.lower()
    matched = [kw for kw in PAIN_KEYWORDS if kw in text_lower]
    score = min(1.0, len(matched) / 3.0)   # 3+ matches = full score

    if not matched:
        return PrefilterResult(False, "no_pain_keywords", 0.0)

    return PrefilterResult(True, f"matched:{','.join(matched[:3])}", score)
