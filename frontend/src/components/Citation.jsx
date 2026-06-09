// One gate-validated citation chip (frontend.md §7). Shows only what the service
// confirmed: rating, date, author, and the verbatim quote.
export default function Citation({ citation }) {
  const meta = [
    citation.rating != null ? `${citation.rating}★` : null,
    citation.date || null,
    citation.author || null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <span className="citation" title={meta}>
      {meta && <span className="citation-meta">{meta}</span>}
      <span className="citation-quote">“{citation.quote}”</span>
    </span>
  );
}
