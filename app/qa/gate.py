"""The deterministic grounding gate (qa.md §7).

A post-hoc verifier, not a second classifier — it runs after the model returns so
the prompt stays primary. For each citation it confirms (1) the review_id is in the
corpus passed to this turn and (2) the normalized quote is a substring of that
review's normalized text. Unverifiable citations are dropped and `flagged` is set.
The gate never rewrites prose and never fabricates.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Strip, collapse internal whitespace, casefold (matches dedup normalization)."""
    return _WHITESPACE.sub(" ", (text or "").strip()).casefold()


def apply_gate(citations: list[dict], reviews) -> tuple[list[dict], bool]:
    """Validate citations against the turn's corpus.

    Returns (validated_citations, flagged). `flagged` is True if any citation was
    dropped. A flagged answer is still served with the surviving citations.
    """
    by_id = {r.id: _normalize(r.text) for r in reviews}

    validated: list[dict] = []
    dropped = False

    for c in citations:
        if not isinstance(c, dict):
            dropped = True
            continue
        review_id = c.get("review_id")
        quote = c.get("quote")
        if review_id not in by_id or not isinstance(quote, str) or not quote.strip():
            dropped = True
            continue
        if _normalize(quote) not in by_id[review_id]:
            dropped = True
            continue
        validated.append(c)

    return validated, dropped
