"""The source seam (ingestion.md §3).

The seam future sources plug into is "produce normalized rows for one entity from
one source." `PlacesSource` and `CsvSource` both implement `ReviewSource.produce`;
a managed scraper would be a third implementation. Nothing downstream of the seam
knows the source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawReview:
    """One review as produced by a source, pre-normalization."""

    author: str | None
    rating: int | None
    text: str
    language: str | None          # declared (csv) or from Places; else None
    published_at: str | None      # raw, pre-normalization


@dataclass
class RowError:
    """A rejected source row (or a non-row error when row == -1)."""

    row: int                      # 1-based source row; -1 for non-row errors
    reason: str


@dataclass
class SourceResult:
    """The output of a source for one entity."""

    entity_id: str
    entity_name: str
    source: str                   # 'google_places' | 'csv'
    reviews: list[RawReview]
    rejections: list[RowError] = field(default_factory=list)
    warnings: list[RowError] = field(default_factory=list)  # non-fatal (e.g. bad date)


class ReviewSource(Protocol):
    """Produces normalized rows for one entity from one source."""

    def produce(self) -> SourceResult: ...


@dataclass
class Review:
    """A committed, normalized review row (ingestion.md §4).

    This is what Q&A and summary read out of SQLite. `Review` is the type the
    Q&A retrieval seam returns (qa.md §4). The frozen schema lives in db.py.
    """

    id: str
    entity_id: str
    source: str
    author: str | None
    rating: int | None
    text: str
    language: str
    published_at: str | None
    ingested_at: str
    dedup_key: str

    @classmethod
    def from_row(cls, row) -> "Review":
        """Build from a sqlite3.Row (or any mapping with the column names)."""
        return cls(
            id=row["id"],
            entity_id=row["entity_id"],
            source=row["source"],
            author=row["author"],
            rating=row["rating"],
            text=row["text"],
            language=row["language"],
            published_at=row["published_at"],
            ingested_at=row["ingested_at"],
            dedup_key=row["dedup_key"],
        )
