import { useEffect, useState } from "react";
import { api, useOnce } from "../api.js";
import { LANGS, useLang } from "../i18n.js";

export default function ScenarioBar({ live }) {
  const scenarios = useOnce("/scenarios") || [];
  const { lang, setLang } = useLang();
  const llm = useOnce("/llm", [live.status]);
  const [choice, setChoice] = useState("morning_peak");
  const [speed, setSpeed] = useState(4);
  const [controller, setController] = useState("traffix");
  useEffect(() => { if (live.scenario) setChoice(live.scenario); }, [live.scenario]);
  const start = () => api(`/start?scenario=${choice}&speed=${speed}&controller=${controller}`, { method: "POST" });
  const stop = () => api("/stop", { method: "POST" });
  const status = live.status;
  return (
    <div className="bar">
      <select value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Scenario">
        {scenarios.map((s) => <option key={s.id} value={s.id}>{s.id.replaceAll("_", " ")}</option>)}
      </select>
      <select value={speed} onChange={(e) => setSpeed(e.target.value)} aria-label="Speed">
        {[1, 2, 4, 8, 16].map((s) => <option key={s} value={s}>{s}× speed</option>)}
      </select>
      <select value={controller} onChange={(e) => setController(e.target.value)} aria-label="Traffic light agent">
        <option value="traffix">Max-pressure agent</option>
        <option value="traffix_predictive">Predictive agent (MPC)</option>
        <option value="traffix_rl">Reinforcement learning agent</option>
        <option value="traffix_rules">Rules only (no models)</option>
        <option value="junction_only">No supermaster</option>
      </select>
      <button className="primary" onClick={start}>Start</button>
      <button onClick={stop}>Stop</button>
      <span style={{ display: "inline-flex", gap: 4 }} role="group" aria-label="Language">
        {LANGS.map((l) => (
          <button key={l.id} onClick={() => setLang(l.id)} className={lang === l.id ? "primary" : ""}
                  style={{ padding: "4px 10px" }}>{l.label}</button>
        ))}
      </span>
      {llm && <span className={`pill ${llm.available ? "ok" : "info"}`}
                    title={llm.available ? `${llm.provider} writes alerts, answers and copilot text` : "Built-in templates (set ANTHROPIC_API_KEY or GROQ_API_KEY)"}>
        {llm.available ? `LLM on · ${llm.provider}` : "templates"}</span>}
      <span style={{ flex: 1 }} />
      {status === "running" && <>
        <span className="muted">{live.scenario?.replaceAll("_", " ")} · {
          { traffix: "max-pressure", traffix_predictive: "predictive", traffix_rl: "RL",
            traffix_rules: "rules only", junction_only: "no supermaster" }[live.controller] || live.controller}</span>
        <span className="clock">{live.clock}</span>
        <span className="pill ok">live</span>
      </>}
      {status === "finished" && <span className="pill info">finished</span>}
      {status === "idle" && <span className="muted">No simulation running</span>}
      {status === "offline" && <span className="pill bad">backend offline: run python scripts/run_live.py</span>}
    </div>
  );
}
