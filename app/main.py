"""FastAPI app: lifespan bootstrap, API router, static frontend with SPA fallback.

One process serves the API and the built React app (qa.md §2, §8). In dev the Vite
server proxies /api here; in prod this serves frontend/dist/ at / with an SPA
fallback so a client-side view change does not 404 on refresh. Secrets
(ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY) are read from the environment by the
clients that need them, never committed (architecture.md §4.7).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api.routes import router

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_INDEX = _DIST / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.bootstrap()  # idempotent schema creation on startup
    yield


app = FastAPI(title="ReviewLens AI", lifespan=lifespan)
app.include_router(router)

# Serve built static assets when present (after a frontend build). The API router
# is registered first, so /api/* always resolves to a handler, not the SPA fallback.
if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """Return index.html for any non-/api path (SPA fallback, qa.md §8)."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    # Serve a real static file if one matches (e.g. /favicon.ico), else index.html.
    candidate = _DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    if _INDEX.is_file():
        return FileResponse(_INDEX)
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run `npm run build` in frontend/.",
    )
