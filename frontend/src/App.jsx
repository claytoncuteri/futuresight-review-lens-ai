import { useState } from "react";
import * as api from "./api.js";
import Ingest from "./views/Ingest.jsx";
import Summary from "./views/Summary.jsx";
import Chat from "./views/Chat.jsx";
import QuotaWarning from "./components/QuotaWarning.jsx";

// One top-level state object; view is a state value, not a URL (frontend.md §4).
const INITIAL = {
  view: "ingest",
  entityId: null,
  entityName: null,
  resolve: { candidate: null, status: "idle" },
  summary: null,
  chat: { messages: [], pending: false },
  quota: null,
};

export default function App() {
  const [state, setState] = useState(INITIAL);
  const patch = (p) => setState((s) => ({ ...s, ...p }));

  // Capture quota off any response body (qa.md §9), shared across surfaces.
  const captureQuota = (data) => {
    if (data && data.quota) patch({ quota: data.quota });
    return data;
  };

  async function loadSummary(entityId) {
    const summary = await api.getSummary(entityId);
    patch({ summary, view: "summary" });
  }

  async function doResolve(url) {
    patch({ resolve: { candidate: null, status: "resolving" } });
    try {
      const data = captureQuota(await api.resolveUrl(url));
      patch({ resolve: { candidate: data.candidate, status: "awaiting_confirm" } });
    } catch (err) {
      patch({ resolve: { candidate: null, status: "error" } });
      throw err;
    }
  }

  async function doConfirm() {
    const candidate = state.resolve.candidate;
    if (!candidate) return;
    const data = captureQuota(await api.confirmPlace(candidate.place_id));
    patch({
      entityId: data.entity_id,
      entityName: data.entity_name,
      resolve: { candidate: null, status: "idle" },
    });
    await loadSummary(data.entity_id);
  }

  function cancelResolve() {
    patch({ resolve: { candidate: null, status: "idle" } });
  }

  async function doUploadCsv(file, entityName, mode) {
    const data = captureQuota(await api.uploadCsv(file, entityName, mode));
    patch({ entityId: data.entity_id, entityName: data.entity_name });
    await loadSummary(data.entity_id);
    return data; // so Ingest can show rejected-row / duplicate report
  }

  async function doAsk(question) {
    setState((s) => ({ ...s, chat: { ...s.chat, pending: true } }));
    try {
      const data = captureQuota(await api.ask(state.entityId, question));
      setState((s) => ({
        ...s,
        chat: {
          pending: false,
          messages: [
            ...s.chat.messages,
            { role: "user", text: question },
            {
              role: "assistant",
              answer: data.answer,
              citations: data.citations,
              matchedReviews: data.matched_reviews,
              flagged: data.flagged,
            },
          ],
        },
      }));
    } catch (err) {
      setState((s) => ({ ...s, chat: { ...s.chat, pending: false } }));
      throw err;
    }
  }

  const navItems = [
    { key: "ingest", label: "Ingest" },
    { key: "summary", label: "Summary", disabled: !state.entityId },
    { key: "chat", label: "Chat", disabled: !state.entityId },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <h1>ReviewLens AI</h1>
        <nav>
          {navItems.map((n) => (
            <button
              key={n.key}
              className={state.view === n.key ? "nav active" : "nav"}
              disabled={n.disabled}
              onClick={() => patch({ view: n.key })}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </header>

      <QuotaWarning quota={state.quota} />

      <main className="content">
        {state.view === "ingest" && (
          <Ingest
            resolve={state.resolve}
            onResolve={doResolve}
            onConfirm={doConfirm}
            onCancelResolve={cancelResolve}
            onUploadCsv={doUploadCsv}
          />
        )}
        {state.view === "summary" && (
          <Summary
            summary={state.summary}
            onGoToChat={() => patch({ view: "chat" })}
          />
        )}
        {state.view === "chat" && (
          <Chat
            entityName={state.entityName}
            chat={state.chat}
            onAsk={doAsk}
          />
        )}
      </main>
    </div>
  );
}
