import { useState } from "react";

// Matched-review browser (frontend.md §7): a dropdown + search over the full
// matched_reviews set for a count question. The model does not enumerate matches;
// the UI does. Renders nothing when matched_reviews is empty — so in v1, where the
// backend always returns [], this never appears.
export default function MatchedReviews({ matchedReviews }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  if (!matchedReviews || matchedReviews.length === 0) return null;

  const filtered = matchedReviews.filter((r) =>
    (r.text || "").toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="matched">
      <button className="secondary" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Show"} {matchedReviews.length} matched review(s)
      </button>
      {open && (
        <div className="matched-body">
          <input
            type="text"
            placeholder="Search matched reviews"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <ul>
            {filtered.map((r) => (
              <li key={r.review_id}>
                <span className="muted">
                  {r.rating != null ? `${r.rating}★` : "—"} · {r.date || "—"} ·{" "}
                  {r.author || "Anonymous"}
                </span>
                <div>{r.text}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
