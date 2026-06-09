import { TEMPLATE_URL } from "../api.js";

// Summary surface (frontend.md §6). The factual core is the confidence-building
// screen; the theme layer is rendered visibly marked as generated, distinct from
// the factual core (the architecture.md §4.5 boundary must read on screen).
export default function Summary({ summary, onGoToChat }) {
  if (!summary) return <p className="muted">No summary loaded yet.</p>;

  const { entity_name, source, factual, themes, warnings } = summary;
  const dist = factual.rating_distribution;
  const c = factual.completeness;
  const tooSmall = warnings.some((w) => w.includes("too small") || w.includes("no reviews"));

  return (
    <div className="summary">
      <div className="row spread">
        <h2>{entity_name}</h2>
        <button onClick={onGoToChat}>Ask questions →</button>
      </div>
      <p className="muted">Source: {source}</p>

      {warnings.length > 0 && (
        <div className="warnings">
          {warnings.map((w, i) => (
            <p key={i} className="warning-line">
              ⚠ {w}
            </p>
          ))}
          {tooSmall && (
            <p className="muted">
              The corpus is small. <a href={TEMPLATE_URL}>Download the template</a> and
              upload more reviews to enable trend analysis.
            </p>
          )}
        </div>
      )}

      <section className="card">
        <h3>The data (computed, not generated)</h3>
        <p>
          <strong>{factual.review_count}</strong> reviews
        </p>

        <h4>Ratings</h4>
        <table className="dist">
          <tbody>
            {["5", "4", "3", "2", "1", "null"].map((star) => (
              <tr key={star}>
                <td>{star === "null" ? "no rating" : `${star}★`}</td>
                <td>{dist[star] ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h4>Date range</h4>
        <p>
          {factual.date_range.min || "—"} to {factual.date_range.max || "—"}
          {factual.date_range.missing > 0 && (
            <span className="muted"> ({factual.date_range.missing} without a date)</span>
          )}
        </p>

        <h4>Languages</h4>
        <p>
          {Object.entries(factual.language_mix)
            .map(([lang, n]) => `${lang}: ${n}`)
            .join(", ") || "—"}
        </p>

        <h4>Completeness</h4>
        <ul className="completeness">
          <li>with date: {pct(c.pct_with_date)}</li>
          <li>with author: {pct(c.pct_with_author)}</li>
          <li>with rating: {pct(c.pct_with_rating)}</li>
          <li>size band: {c.size_band}</li>
        </ul>
      </section>

      <section className="card generated">
        <h3>
          Themes <span className="badge">generated</span>
        </h3>
        {themes.items && themes.items.length > 0 ? (
          <ul className="themes">
            {themes.items.map((t, i) => (
              <li key={i}>
                <strong>{t.label}</strong> — {t.characterization}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{themes.note || "No themes available."}</p>
        )}
        <p className="muted small">
          This section is written by {themes.model} and is qualitative, not a source of
          counts.
        </p>
      </section>
    </div>
  );
}

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}
