"""The Sonnet 4.6 call and JSON contract handling (qa.md §6).

The model returns a single JSON object {answer, citations[]}. On a parse failure
we retry once; on a second failure we return the raw prose with flagged=True and no
citations, rather than erroring the turn. The grounding gate (gate.py) runs over the
citations afterward and may raise the flag further.

Structured outputs (output_config.format) would harden this further; we keep the
documented parse-then-retry contract here so the degradation path is explicit and
testable, and leave structured outputs as a future hardening.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import citations as citations_mod

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1500


@dataclass
class ClientResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    flagged: bool = False  # True when the JSON contract could not be parsed


def _make_client():
    # Imported lazily so importing this module never requires the API key.
    import anthropic

    return anthropic.Anthropic()


def _extract_text(message) -> str:
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


def ask(system_prompt: str, question: str, client=None) -> ClientResult:
    """Call Sonnet 4.6, parse the JSON contract, retry once, else flag the prose.

    `client` is injectable so tests run without the API key or network.
    """
    client = client or _make_client()
    messages = [{"role": "user", "content": question}]

    last_text = ""
    for _attempt in range(2):  # initial try + one retry on parse failure
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        last_text = _extract_text(message)
        parsed = citations_mod.parse_response(last_text)
        if parsed is not None:
            return ClientResult(
                answer=parsed["answer"],
                citations=parsed["citations"],
                flagged=False,
            )

    # Second parse failure: serve the raw prose, flagged, with no citations.
    return ClientResult(answer=last_text, citations=[], flagged=True)
