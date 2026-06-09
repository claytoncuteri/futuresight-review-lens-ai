import { useState } from "react";
import Citation from "../components/Citation.jsx";
import MatchedReviews from "../components/MatchedReviews.jsx";

// Chat surface (frontend.md §7). A decline or ungrounded answer arrives with empty
// citations: render the prose, no chips, no error styling — declining is a correct
// outcome. `flagged` renders a low-confidence marker; the answer still shows.
export default function Chat({ entityName, chat, onAsk }) {
  const [question, setQuestion] = useState("");
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || chat.pending) return;
    setError(null);
    setQuestion("");
    try {
      await onAsk(q);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="chat">
      <p className="muted">
        Ask about the reviews for <strong>{entityName}</strong>. Answers come only from
        those reviews.
      </p>

      <div className="messages">
        {chat.messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="msg user">
              {m.text}
            </div>
          ) : (
            <div key={i} className="msg assistant">
              {m.flagged && (
                <div className="flag" title="The service could not verify a cited source.">
                  low confidence
                </div>
              )}
              <div className="answer">{m.answer}</div>
              {m.citations && m.citations.length > 0 && (
                <div className="citations">
                  {m.citations.map((c, j) => (
                    <Citation key={j} citation={c} />
                  ))}
                </div>
              )}
              <MatchedReviews matchedReviews={m.matchedReviews} />
            </div>
          )
        )}
        {chat.pending && <div className="msg assistant muted">Thinking…</div>}
      </div>

      {error && <p className="error">{error}</p>}

      <form className="ask" onSubmit={submit}>
        <input
          type="text"
          placeholder="e.g. What do people say about parking?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={chat.pending || !question.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
