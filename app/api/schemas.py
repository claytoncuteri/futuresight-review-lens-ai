"""Pydantic request/response models (qa.md §6, §8).

These align with the ingestion dataclasses so request/response shapes and the
normalized schema share one type vocabulary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Quota(BaseModel):
    """Remaining quota for the current window; rides on every response (qa.md §9)."""

    questions_remaining: int
    ingests_remaining: int
    window_reset: str  # ISO datetime of the window boundary


class Citation(BaseModel):
    """A gate-validated citation rendered as a chip in the UI."""

    review_id: str
    rating: int | None = None
    date: str | None = None
    author: str | None = None
    quote: str


class MatchedReview(BaseModel):
    """An element of the matched-review set (empty list in v1)."""

    review_id: str
    rating: int | None = None
    date: str | None = None
    author: str | None = None
    text: str


# --- Q&A -----------------------------------------------------------------------

class AskRequest(BaseModel):
    entity_id: str
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    matched_reviews: list[MatchedReview]
    flagged: bool
    quota: Quota


# --- Ingestion (URL path) ------------------------------------------------------

class ResolveRequest(BaseModel):
    url: str = Field(min_length=1)


class CandidateModel(BaseModel):
    place_id: str
    name: str
    address: str


class ResolveResponse(BaseModel):
    candidate: CandidateModel
    quota: Quota


class ConfirmRequest(BaseModel):
    place_id: str = Field(min_length=1)


class IngestResult(BaseModel):
    """Returned by confirm and CSV upload; the UI then loads the summary."""

    entity_id: str
    entity_name: str
    source: str
    review_count: int
    skipped_duplicates: int = 0
    rejections: list[dict] = []
    warnings: list[dict] = []
    quota: Quota
