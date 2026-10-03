"""Evidence claims and deterministic quote verification."""

import re
from dataclasses import dataclass

from idea_hunter.db.models import Claim, ClaimEvidence, Observation


def _canonical(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def quote_is_verified(quote: str, observation_text: str) -> bool:
    """A citation is valid only when its exact normalized quote is in source text."""
    normalized_quote = _canonical(quote)
    return bool(normalized_quote and normalized_quote in _canonical(observation_text))


@dataclass(frozen=True)
class CitationInput:
    observation_id: int
    quote: str
    stance: str = "support"


def attach_claim_evidence(claim: Claim, observations: dict[int, Observation], citations: list[CitationInput]) -> list[ClaimEvidence]:
    rows = []
    for citation in citations:
        observation = observations.get(citation.observation_id)
        if not observation:
            continue
        rows.append(ClaimEvidence(
            claim=claim,
            observation_id=observation.id,
            quote=citation.quote,
            stance=citation.stance,
            verified=quote_is_verified(citation.quote, observation.normalized_text or observation.raw_text),
        ))
    return rows
