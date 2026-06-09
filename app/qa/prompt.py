"""Prompt assembly (qa.md §5, §6).

Loads scope-guard-prompt.md verbatim (the text between the markers, nothing else),
substitutes {{ENTITY_NAME}}, appends the <reviews> data block, then appends an
output-format directive. The guard rules are never paraphrased in code — the file
under review is the file that runs.
"""

from __future__ import annotations

from pathlib import Path

_PROMPT_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "docs" / "plans" / "scope-guard-prompt.md"
)
_START = "<!-- SYSTEM PROMPT START -->"
_END = "<!-- SYSTEM PROMPT END -->"

# Output-format directive (qa.md §6). A format instruction, not a rule change.
# Crucially, every citation quote must be a verbatim span copied from the cited
# review text so the deterministic grounding gate (qa.md §7) does not drop valid
# citations as unverifiable.
FORMAT_DIRECTIVE = """
<output_format>
Return your reply as a single JSON object and nothing else. No prose before or
after it, no markdown code fences. The object has exactly two keys:

{
  "answer": "<your reply, written exactly as the guidance above describes, with
             citations inline in the (rating, date, author, \\"quote\\") style>",
  "citations": [
    {"review_id": "<the review_id of the cited review>",
     "rating": <its rating as an integer, or null>,
     "date": "<its date, or null>",
     "author": "<its author, or null>",
     "quote": "<a short span copied VERBATIM, character for character, from that
                review's text>"}
  ]
}

Rules for the JSON:
- "answer" carries the full reply the analyst reads, including the inline
  citations, exactly in the style the examples above show.
- Every object in "citations" must mirror a citation you made inline, and its
  "quote" must be an exact substring of the cited review's text — copy it, do not
  paraphrase, reword, translate, or fix typos. Quote only from a review that
  actually appears in the <reviews> block, using its real review_id.
- For a decline or an in-scope-but-ungrounded answer, "citations" is an empty list
  ([]); the prose still carries the reason and redirect.
</output_format>
""".strip()


def load_guard_prompt() -> str:
    """Return the literal prompt text between the markers in scope-guard-prompt.md."""
    raw = _PROMPT_FILE.read_text(encoding="utf-8")
    start = raw.index(_START) + len(_START)
    end = raw.index(_END)
    return raw[start:end].strip()


def _review_element(review) -> str:
    rating = "N/A" if review.rating is None else str(review.rating)
    date = review.published_at or "N/A"
    author = review.author or "Anonymous"
    # Text is inserted verbatim (not escaped) so the model sees, and can quote,
    # exactly the stored text — the grounding gate matches quotes against it.
    return (
        f'<review review_id="{review.id}" rating="{rating}" '
        f'date="{date}" author="{author}">{review.text}</review>'
    )


def build_reviews_block(reviews) -> str:
    """One <review> element per row, each carrying its review_id (qa.md §5)."""
    elements = "\n".join(_review_element(r) for r in reviews)
    return f"<reviews>\n{elements}\n</reviews>"


def assemble(entity_name: str, reviews) -> str:
    """Full system prompt: guard (entity substituted) + format directive + <reviews>."""
    guard = load_guard_prompt().replace("{{ENTITY_NAME}}", entity_name)
    return "\n\n".join([guard, FORMAT_DIRECTIVE, build_reviews_block(reviews)])
