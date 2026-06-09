"""Google Places (New) URL path: resolve, confirm, fetch (ingestion.md §5).

Resolution always goes through Text Search because a pasted Maps URL rarely carries
a usable place_id. The confirm step is the disambiguation gate (architecture.md §7):
nothing is fetched or billed until the user accepts a named, addressed candidate.

Both endpoints are field-masked to bill only what we read. The httpx client and API
key are injectable so the path can be exercised without network access in tests.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs, unquote

import httpx

from .base import RawReview, SourceResult

SOURCE = "google_places"

_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

_TEXT_SEARCH_MASK = "places.id,places.displayName,places.formattedAddress"
_DETAILS_MASK = "id,displayName,formattedAddress,rating,userRatingCount,reviews"

_SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
_TIMEOUT = httpx.Timeout(15.0)


class PlacesError(Exception):
    """A user-facing failure in the URL path (unresolvable URL, API error)."""


@dataclass
class Candidate:
    place_id: str
    name: str
    address: str


def _api_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        raise PlacesError("Google Maps API key is not configured.")
    return key


def _follow_short_link(url: str, client: httpx.Client) -> str:
    """If the host is a short link, follow redirects to the canonical URL."""
    host = (urlparse(url).hostname or "").lower()
    if host in _SHORT_HOSTS or host.endswith(".goo.gl"):
        resp = client.get(url, follow_redirects=True)
        return str(resp.url)
    return url


def _extract_query(url: str) -> str:
    """Extract a Text Search query from a canonical Maps URL.

    Prefer the name segment in /maps/place/<NAME>/; fall back to a `q=` param,
    then to coordinates. Raise if nothing usable is present.
    """
    parsed = urlparse(url)
    m = re.search(r"/maps/place/([^/]+)", parsed.path)
    if m:
        name = unquote(m.group(1)).replace("+", " ").strip()
        if name:
            return name
    qs = parse_qs(parsed.query)
    if "q" in qs and qs["q"]:
        q = unquote(qs["q"][0]).strip()
        if q:
            return q
    # Coordinates as a last resort (e.g. @lat,lng,zoom).
    coord = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if coord:
        return f"{coord.group(1)},{coord.group(2)}"
    raise PlacesError(
        "Could not read a place from this URL. Paste the canonical Google Maps place URL."
    )


def text_search(query: str, client: httpx.Client | None = None) -> list[Candidate]:
    """Resolve a free-text query to candidate places (field-masked)."""
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.post(
            _TEXT_SEARCH_URL,
            headers={
                "X-Goog-Api-Key": _api_key(),
                "X-Goog-FieldMask": _TEXT_SEARCH_MASK,
                "Content-Type": "application/json",
            },
            json={"textQuery": query},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise PlacesError(f"Place search failed: {exc}") from exc
    finally:
        if own:
            client.close()

    places = resp.json().get("places", []) or []
    candidates: list[Candidate] = []
    for p in places:
        pid = p.get("id")
        if not pid:
            continue
        candidates.append(
            Candidate(
                place_id=pid,
                name=(p.get("displayName") or {}).get("text", ""),
                address=p.get("formattedAddress", ""),
            )
        )
    return candidates


def resolve(url: str, client: httpx.Client | None = None) -> Candidate:
    """Resolve a pasted Maps URL to a single top candidate. Fetch nothing yet.

    Raises PlacesError on zero results (the route surfaces the guidance and
    persists nothing). The caller renders the candidate and waits for confirm.
    """
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        canonical = _follow_short_link(url, client)
        query = _extract_query(canonical)
        candidates = text_search(query, client=client)
    finally:
        if own:
            client.close()

    if not candidates:
        raise PlacesError(
            "Could not resolve this URL to a place. Paste the canonical Google Maps place URL."
        )
    return candidates[0]


def _map_reviews(details: dict) -> list[RawReview]:
    out: list[RawReview] = []
    for r in details.get("reviews", []) or []:
        text_obj = r.get("text") or {}
        author = (r.get("authorAttribution") or {}).get("displayName")
        out.append(
            RawReview(
                author=author,
                rating=r.get("rating"),
                text=text_obj.get("text", ""),
                language=text_obj.get("languageCode"),
                published_at=r.get("publishTime"),
            )
        )
    return out


def place_details(place_id: str, client: httpx.Client | None = None) -> dict:
    """Fetch Place Details for a confirmed place_id (field-masked)."""
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(
            _DETAILS_URL.format(place_id=place_id),
            headers={
                "X-Goog-Api-Key": _api_key(),
                "X-Goog-FieldMask": _DETAILS_MASK,
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise PlacesError(f"Place details fetch failed: {exc}") from exc
    finally:
        if own:
            client.close()
    return resp.json()


class PlacesSource:
    """A ReviewSource over a confirmed place_id. Constructed only after confirm."""

    def __init__(self, place_id: str, client: httpx.Client | None = None):
        self._place_id = place_id
        self._client = client

    def produce(self) -> SourceResult:
        details = place_details(self._place_id, client=self._client)
        name = (details.get("displayName") or {}).get("text", "")
        return SourceResult(
            entity_id=self._place_id,
            entity_name=name,
            source=SOURCE,
            reviews=_map_reviews(details),
        )
