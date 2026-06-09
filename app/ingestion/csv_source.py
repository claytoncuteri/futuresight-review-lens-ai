"""CSV source: decode, parse, validate, map to RawReview (ingestion.md §6, §9).

Per-row validation ingests the valid remainder; whole-file problems (decode
failure, missing required header, empty/header-only) reject the file with a named
cause. The 500-row cap is enforced at persist time (it depends on existing rows),
not here.
"""

from __future__ import annotations

import csv
import io

from .base import RawReview, RowError, SourceResult
from .normalize import coerce_rating, parse_date

REQUIRED_HEADERS = ("rating", "text")
OPTIONAL_HEADERS = ("author", "date", "language")
SOURCE = "csv"


class CsvError(Exception):
    """A whole-file rejection (decode failure, missing header, empty file)."""


def _decode(data: bytes) -> str:
    """Decode as UTF-8 (BOM-tolerant). Reject the whole file on failure."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvError(
            "Could not decode the file as UTF-8. Save it as UTF-8 CSV and re-upload."
        ) from exc


class CsvSource:
    """A ReviewSource over an uploaded CSV for one entity."""

    def __init__(self, data: bytes, entity_name: str, entity_id: str):
        self._data = data
        self._entity_name = entity_name
        self._entity_id = entity_id

    def produce(self) -> SourceResult:
        text = _decode(self._data)
        if not text.strip():
            raise CsvError("The file is empty.")

        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            raise CsvError("The file is empty.")

        # Normalize header names; map each required/optional column to its index.
        cols = {name.strip().lower(): idx for idx, name in enumerate(header)}
        missing = [h for h in REQUIRED_HEADERS if h not in cols]
        if missing:
            raise CsvError(
                "Missing required column(s): "
                + ", ".join(missing)
                + ". The template requires 'rating' and 'text'."
            )

        reviews: list[RawReview] = []
        rejections: list[RowError] = []
        warnings: list[RowError] = []
        data_rows = 0

        def cell(row: list[str], name: str) -> str | None:
            idx = cols.get(name)
            if idx is None or idx >= len(row):
                return None
            value = row[idx]
            return value.strip() if isinstance(value, str) else value

        # Source row numbers are 1-based with the header as row 1.
        for offset, row in enumerate(reader, start=2):
            if not any((c or "").strip() for c in row):
                continue  # skip fully-blank lines without counting them
            data_rows += 1

            text_val = cell(row, "text")
            rating_raw = cell(row, "rating")

            if not text_val or not rating_raw:
                rejections.append(
                    RowError(offset, "missing required field (rating and text are required)")
                )
                continue

            rating = coerce_rating(rating_raw)
            if rating is None:
                rejections.append(
                    RowError(offset, f"rating '{rating_raw}' is not an integer in 1-5")
                )
                continue

            date_raw = cell(row, "date")
            published_at = parse_date(date_raw) if date_raw else None
            if date_raw and published_at is None:
                warnings.append(RowError(offset, f"unparseable date '{date_raw}' (kept, date omitted)"))

            reviews.append(
                RawReview(
                    author=cell(row, "author"),
                    rating=rating,
                    text=text_val,
                    language=cell(row, "language"),
                    published_at=published_at,
                )
            )

        if data_rows == 0:
            raise CsvError("The file has a header but no data rows.")

        return SourceResult(
            entity_id=self._entity_id,
            entity_name=self._entity_name,
            source=SOURCE,
            reviews=reviews,
            rejections=rejections,
            warnings=warnings,
        )
