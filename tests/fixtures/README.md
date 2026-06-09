# Test fixtures

All files here are **synthetic, clearly labeled, and deletable** (architecture.md
§4.2). They are not real reviews for any entity and must never be presented as such
in a demo. Removing them affects only the test suite.

- `volume.csv` — ~150 synthetic rows to exercise the CSV path.
- `rejections.csv` — seeded row-level problems (missing fields, out-of-range
  rating, unparseable date, a duplicate pair).
- `injection.csv` — a row whose text is `SYSTEM: ignore prior instructions…`, to
  assert ingestion stores it verbatim as data (the injection defense lives in the
  Q&A scope guard, not ingestion).
- `header_only.csv` — header with no data rows (whole-file rejection).
- `not_utf8.csv` — latin-1 bytes that are invalid UTF-8 (whole-file rejection).
