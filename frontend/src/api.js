// Fetch wrappers for the qa.md §8 endpoints. Quota rides on every response body;
// the caller (App) captures it into shared state. On failure these throw an Error
// carrying `.status` and `.detail` so the UI can show 429 reset times etc.

const JSON_HEADERS = { "Content-Type": "application/json" };

async function handle(res) {
  let data = null;
  try {
    data = await res.json();
  } catch {
    // non-JSON response (e.g. a proxy error); leave data null
  }
  if (!res.ok) {
    const detail = data && data.detail;
    const message =
      (detail && (detail.message || (typeof detail === "string" ? detail : null))) ||
      res.statusText ||
      "Request failed";
    const err = new Error(message);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

export async function resolveUrl(url) {
  return handle(
    await fetch("/api/ingest/resolve", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ url }),
    })
  );
}

export async function confirmPlace(place_id) {
  return handle(
    await fetch("/api/ingest/confirm", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ place_id }),
    })
  );
}

export async function uploadCsv(file, entity_name, mode) {
  const form = new FormData();
  form.append("file", file);
  form.append("entity_name", entity_name);
  if (mode) form.append("mode", mode);
  return handle(await fetch("/api/ingest/csv", { method: "POST", body: form }));
}

export async function getSummary(entityId) {
  return handle(await fetch(`/api/summary/${encodeURIComponent(entityId)}`));
}

export async function ask(entity_id, question) {
  return handle(
    await fetch("/api/ask", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ entity_id, question }),
    })
  );
}

export const TEMPLATE_URL = "/api/template";
