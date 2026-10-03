"""Recall-oriented signal triage. Rejected observations remain stored."""

from dataclasses import dataclass

from idea_hunter.processing.prefilter import PAIN_KEYWORDS


TRIAGE_TYPES = {"pain", "workaround", "willingness_to_pay", "contradiction", "noise"}


@dataclass(frozen=True)
class TriageResult:
    signal_type: str
    confidence: float
    reason: str


def heuristic_triage(text: str) -> TriageResult:
    value = (text or "").casefold()
    if any(term in value for term in ("would pay", "pay for", "paid for", "budget for")):
        return TriageResult("willingness_to_pay", 0.75, "pricing language")
    if any(term in value for term in ("workaround", "spreadsheet", "manually", "manual process", "copy and paste")):
        return TriageResult("workaround", 0.70, "workaround language")
    if any(term in value for term in ("actually works", "solved by", "not a problem", "disagree", "already solved")):
        return TriageResult("contradiction", 0.60, "contradiction language")
    hits = sum(keyword in value for keyword in PAIN_KEYWORDS)
    if hits:
        return TriageResult("pain", min(0.9, 0.45 + hits * 0.15), "pain language")
    return TriageResult("noise", 0.35, "no recognized signal")
