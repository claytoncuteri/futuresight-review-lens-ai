// Proximity warning banner (frontend.md §8). Renders when either bucket's remaining
// count is at or below the threshold the backend exposes, naming the bucket and the
// window reset. The UI warns as the limit approaches rather than blocking silently.
const THRESHOLD = 5;

export default function QuotaWarning({ quota }) {
  if (!quota) return null;

  const low = [];
  if (quota.questions_remaining <= THRESHOLD) {
    low.push(`${quota.questions_remaining} question(s)`);
  }
  if (quota.ingests_remaining <= THRESHOLD) {
    low.push(`${quota.ingests_remaining} ingest(s)`);
  }
  if (low.length === 0) return null;

  return (
    <div className="quota-warning">
      ⚠ Approaching the rate limit: {low.join(" and ")} remaining this hour. Resets at{" "}
      {formatReset(quota.window_reset)}.
    </div>
  );
}

function formatReset(iso) {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}
