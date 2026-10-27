import { useEffect, useState } from "react";
import { api, useOnce } from "../api.js";
import { Waiting } from "../components/Feed.jsx";
import { EXAMPLES, dirOf, t, useLang } from "../i18n.js";

export default function Analyst({ live }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const metrics = useOnce("/models");
  const { lang } = useLang();
  const hasEmergency = ["emergency", "combined"].includes(live.scenario);
  const examples = EXAMPLES[hasEmergency ? "emergency" : "general"][lang];
  const [lastIdx, setLastIdx] = useState(0);          // which example (or -1 = typed) was asked
  useEffect(() => { setQuestion(examples[0]); setLastIdx(0); setAnswer(null); }, [live.scenario]);
  useEffect(() => {                                    // switching language translates the answer too
    if (lastIdx >= 0) { const q = examples[lastIdx]; setQuestion(q); if (answer) ask(q); }
    else if (answer) ask(question);
  }, [lang]);
  useEffect(() => {
    if (live.status !== "running" && live.status !== "finished") return;
    const id = setTimeout(() => api(`/decisions?limit=150&q=${encodeURIComponent(q)}`).then(setRows).catch(() => {}), 300);
    return () => clearTimeout(id);
  }, [q, live.counts?.decisions]);
  const ask = async (q = question) => {
    if (!q.trim()) { setError(t("typeFirst", lang)); return; }
    setError("");
    try { setAnswer(await api("/ask", { method: "POST", headers: { "Content-Type": "application/json" },
                                         body: JSON.stringify({ question: q, lang }) })); }
    catch (e) { setError(String(e)); }
  };
  return (
    <>
      <div dir={dirOf(lang)}><h1>{t("analystTitle", lang)}</h1>
        <p className="muted">{t("analystSub", lang)}</p></div>
      <Waiting live={live} />
      <div className="card">
        <h2 dir={dirOf(lang)}>{t("askSynapse", lang)}</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <input style={{ flex: 1 }} dir={dirOf(lang)} value={question}
                 onChange={(e) => { setQuestion(e.target.value); setLastIdx(-1); setError(""); }}
                 onKeyDown={(e) => { if (e.key === "Enter") ask(); }} />
          <button className="primary" onClick={() => ask()}>{t("ask", lang)}</button>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {examples.map((x, i) => (
            <button key={x} dir={dirOf(lang)} style={{ fontSize: 12, padding: "3px 10px" }}
                    onClick={() => { setQuestion(x); setLastIdx(i); }}>{x}</button>
          ))}
        </div>
        {error && <span style={{ color: "#f4a497", fontSize: 13 }}>{error}</span>}
        {answer && <div className="answer" dir={dirOf(lang)}>
          <span className={`pill ${answer.abstained ? "warn" : "ok"}`}>{answer.abstained ? t("abstained", lang) : `${answer.citations.length} ${t("citations", lang)}`}</span>
          <span className="muted" style={{ fontSize: 12, marginInlineStart: 8 }}>{answer.engine === "llm-agent"
            ? `LLM agent · ${answer.tool_calls?.length || 0} tool calls`
            : answer.engine === "template (LLM unavailable)" ? "templates (LLM unavailable: see terminal)" : "templates"}</span>{"\n"}{answer.answer}</div>}
      </div>
      <div className="split">
        <div className="card">
          <h2 dir={dirOf(lang)}>{t("log", lang)}</h2>
          <input dir={dirOf(lang)} placeholder={t("filter", lang)} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="feed">
            <table><tbody>
              {rows.map((e) => (
                <tr key={e.id}>
                  <td className="mono muted" style={{ whiteSpace: "nowrap" }}>{e.clock || `${Math.round(e.t)}s`}</td>
                  <td>
                    <div dir={dirOf(lang)}>{e.texts?.[lang] || e.text || e.reason}</div>
                    <details style={{ marginTop: 3 }}>
                      <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>#{e.id} · {e.agent} · {e.reason}</summary>
                      <span className="muted mono" style={{ fontSize: 12, wordBreak: "break-all" }}>{JSON.stringify(e.details)}</span>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody></table>
          </div>
        </div>
        <div className="card">
          <h2 dir={dirOf(lang)}>{t("models", lang)}</h2>
          {!metrics || !Object.keys(metrics).length ? <span className="muted">Run python scripts/train.py</span> :
            <table><tbody>
              {Object.entries(metrics).filter(([k]) => !k.startsWith("_")).map(([k, v]) => (
                <tr key={k}><td><b>{k.replaceAll("_", " ")}</b></td>
                  <td className="mono">{Object.entries(v).filter(([, x]) => typeof x !== "object").slice(0, 4)
                    .map(([a, b]) => `${a}: ${b}`).join(" · ")}</td></tr>
              ))}
            </tbody></table>}
        </div>
      </div>
    </>
  );
}
