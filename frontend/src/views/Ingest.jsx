import { useState } from "react";
import { TEMPLATE_URL } from "../api.js";

// Ingest surface (frontend.md §5): URL resolve→confirm→fetch, CSV upload, template.
export default function Ingest({ resolve, onResolve, onConfirm, onCancelResolve, onUploadCsv }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState(null);

  const [file, setFile] = useState(null);
  const [entityName, setEntityName] = useState("");
  const [mode, setMode] = useState("replace");
  const [csvReport, setCsvReport] = useState(null);
  const [csvError, setCsvError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submitUrl(e) {
    e.preventDefault();
    setError(null);
    try {
      await onResolve(url.trim());
    } catch (err) {
      setError(err.message);
    }
  }

  async function confirm() {
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitCsv(e) {
    e.preventDefault();
    setCsvError(null);
    setCsvReport(null);
    if (!file || !entityName.trim()) {
      setCsvError("Choose a CSV file and enter an entity name.");
      return;
    }
    setBusy(true);
    try {
      const data = await onUploadCsv(file, entityName.trim(), mode);
      setCsvReport(data);
    } catch (err) {
      setCsvError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ingest">
      <section className="card">
        <h2>Ingest from a Google Maps URL</h2>
        <form onSubmit={submitUrl}>
          <input
            type="text"
            placeholder="Paste a Google Maps place URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button type="submit" disabled={resolve.status === "resolving" || !url.trim()}>
            {resolve.status === "resolving" ? "Resolving…" : "Resolve"}
          </button>
        </form>

        {resolve.status === "awaiting_confirm" && resolve.candidate && (
          <div className="candidate">
            <p className="muted">
              Nothing has been fetched or billed yet. Confirm this is the right place.
            </p>
            <p>
              <strong>{resolve.candidate.name}</strong>
              <br />
              <span className="muted">{resolve.candidate.address}</span>
            </p>
            <div className="row">
              <button onClick={confirm}>Confirm &amp; fetch reviews</button>
              <button className="secondary" onClick={onCancelResolve}>
                Not this one
              </button>
            </div>
          </div>
        )}

        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h2>Upload reviews as CSV</h2>
        <p className="muted">
          Columns: <code>rating</code> (1–5, required), <code>text</code> (required),{" "}
          <code>author</code>, <code>date</code>, <code>language</code> (optional).{" "}
          <a href={TEMPLATE_URL}>Download the template</a>.
        </p>
        <form onSubmit={submitCsv}>
          <input
            type="text"
            placeholder="Entity name (e.g. Joe's Cafe)"
            value={entityName}
            onChange={(e) => setEntityName(e.target.value)}
          />
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
          <label className="mode">
            On existing entity:
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="replace">replace</option>
              <option value="append">append</option>
              <option value="new-entity">new entity</option>
            </select>
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>

        {csvError && <p className="error">{csvError}</p>}

        {csvReport && (
          <div className="report">
            <p>
              Ingested <strong>{csvReport.review_count}</strong> reviews.
              {csvReport.skipped_duplicates > 0 &&
                ` Skipped ${csvReport.skipped_duplicates} duplicate(s).`}
            </p>
            {csvReport.rejections && csvReport.rejections.length > 0 && (
              <details open>
                <summary>{csvReport.rejections.length} rejected row(s)</summary>
                <ul>
                  {csvReport.rejections.map((r, i) => (
                    <li key={i}>
                      Row {r.row}: {r.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {csvReport.warnings && csvReport.warnings.length > 0 && (
              <details>
                <summary>{csvReport.warnings.length} warning(s)</summary>
                <ul>
                  {csvReport.warnings.map((r, i) => (
                    <li key={i}>
                      Row {r.row}: {r.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
