"""HTTP handlers (qa.md §3, §8). Thin: delegate to qa / ingestion / summary.

Routes carry no business logic. The limiter sits as a dependency in front of the
ask endpoint (questions bucket) and the three ingest endpoints (ingests bucket).
GET /api/template and GET /api/summary are not limited (no external bill).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from . import schemas
from .limiter import INGESTS, QUESTIONS, RateLimitExceeded, limiter
from ..ingestion import persist
from ..ingestion.csv_source import CsvError, CsvSource
from ..ingestion.places import PlacesError, PlacesSource, resolve as places_resolve
from ..qa import client as qa_client
from ..qa import context, gate, prompt
from ..summary import payload as summary_payload

router = APIRouter(prefix="/api")


# --- limiter wiring ------------------------------------------------------------

def client_ip(request: Request) -> str:
    """Client IP from Replit's proxy-forwarded header, else the socket peer.

    Replit sets `X-Forwarded-For` (client first in the comma list). Falls back to
    the direct socket peer when the header is absent (local dev).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _guard(request: Request, bucket: str) -> None:
    try:
        limiter.consume(client_ip(request), bucket)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "bucket": exc.bucket,
                "window_reset": exc.window_reset,
            },
        )


def question_guard(request: Request) -> None:
    _guard(request, QUESTIONS)


def ingest_guard(request: Request) -> None:
    _guard(request, INGESTS)


def _quota(request: Request) -> schemas.Quota:
    return schemas.Quota(**limiter.quota(client_ip(request)))


# --- Q&A -----------------------------------------------------------------------

@router.post("/ask", response_model=schemas.AskResponse, dependencies=[Depends(question_guard)])
def ask(request: Request, body: schemas.AskRequest) -> schemas.AskResponse:
    entity_name = context.get_entity_name(body.entity_id)
    if entity_name is None:
        raise HTTPException(status_code=404, detail="Unknown entity; ingest reviews first.")

    reviews = context.get_context(body.entity_id, body.question)
    system_prompt = prompt.assemble(entity_name, reviews)

    result = qa_client.ask(system_prompt, body.question)
    validated, gate_flagged = gate.apply_gate(result.citations, reviews)

    return schemas.AskResponse(
        answer=result.answer,
        citations=[schemas.Citation(**_citation_fields(c)) for c in validated],
        matched_reviews=[],  # v1: matched-review browser not built (next step)
        flagged=result.flagged or gate_flagged,
        quota=_quota(request),
    )


def _citation_fields(c: dict) -> dict:
    return {
        "review_id": c.get("review_id"),
        "rating": c.get("rating"),
        "date": c.get("date"),
        "author": c.get("author"),
        "quote": c.get("quote", ""),
    }


# --- Ingestion: URL path -------------------------------------------------------

@router.post(
    "/ingest/resolve",
    response_model=schemas.ResolveResponse,
    dependencies=[Depends(ingest_guard)],
)
def ingest_resolve(request: Request, body: schemas.ResolveRequest) -> schemas.ResolveResponse:
    try:
        candidate = places_resolve(body.url)
    except PlacesError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return schemas.ResolveResponse(
        candidate=schemas.CandidateModel(
            place_id=candidate.place_id, name=candidate.name, address=candidate.address
        ),
        quota=_quota(request),
    )


@router.post(
    "/ingest/confirm",
    response_model=schemas.IngestResult,
    dependencies=[Depends(ingest_guard)],
)
def ingest_confirm(request: Request, body: schemas.ConfirmRequest) -> schemas.IngestResult:
    from .. import db

    try:
        result = PlacesSource(body.place_id).produce()
    except PlacesError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    conn = db.get_connection()
    try:
        pr = persist.persist(conn, result, mode=persist.REPLACE)
    finally:
        conn.close()

    return schemas.IngestResult(
        entity_id=pr.entity_id,
        entity_name=pr.entity_name,
        source=pr.source,
        review_count=pr.review_count,
        skipped_duplicates=pr.skipped_duplicates,
        quota=_quota(request),
    )


# --- Ingestion: CSV path -------------------------------------------------------

@router.post(
    "/ingest/csv",
    response_model=schemas.IngestResult,
    dependencies=[Depends(ingest_guard)],
)
async def ingest_csv(
    request: Request,
    file: UploadFile = File(...),
    entity_name: str = Form(...),
    mode: str = Form(persist.REPLACE),
) -> schemas.IngestResult:
    from .. import db

    if mode not in (persist.REPLACE, persist.APPEND, persist.NEW_ENTITY):
        raise HTTPException(status_code=400, detail=f"Unknown mode '{mode}'.")

    data = await file.read()
    entity_id = persist.csv_entity_id(entity_name)
    try:
        result = CsvSource(data, entity_name, entity_id).produce()
    except CsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    conn = db.get_connection()
    try:
        pr = persist.persist(conn, result, mode=mode)
    except persist.RowCapExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()

    return schemas.IngestResult(
        entity_id=pr.entity_id,
        entity_name=pr.entity_name,
        source=pr.source,
        review_count=pr.review_count,
        skipped_duplicates=pr.skipped_duplicates,
        rejections=[{"row": e.row, "reason": e.reason} for e in result.rejections],
        warnings=[{"row": e.row, "reason": e.reason} for e in result.warnings],
        quota=_quota(request),
    )


# --- Template (unlimited) ------------------------------------------------------

_TEMPLATE = (
    "rating,text,author,date,language\n"
    "5,\"Great food and friendly staff\",Dana P.,2024-03-02,en\n"
    "2,\"Slow service on the weekend\",,2024-03-14,en\n"
)


@router.get("/summary/{entity_id:path}")
def summary(entity_id: str) -> dict:
    """Return the summary payload (summary.md §4). Unlimited (idempotent read)."""
    payload = summary_payload.build_payload(entity_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Unknown entity; ingest reviews first.")
    return payload


@router.get("/template")
def template() -> PlainTextResponse:
    return PlainTextResponse(
        _TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reviewlens_template.csv"},
    )
