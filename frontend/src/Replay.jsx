import { useEffect, useRef, useState } from "react";
import { init, use as registerCharts } from "echarts/core";
import { LineChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import "./replay.css";

registerCharts([LineChart, AriaComponent, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const words = (value = "") => value.replaceAll("_", " ");
const stageNames = ["Read local logs", "Check activity", "Accept signals", "Compare reports", "Check explanation"];
const evidenceNames = {
  auth_failure: "Rejected sign-ins", source_spread: "Spread across sources", failure_kind: "Reason for failure",
  request_rate: "Request pressure", service_errors: "Service errors", phishing_links: "Flagged links",
  malware_checkins: "Recurring outbound contacts", data_transfer: "Large outbound transfers",
};
const seen = new Intl.NumberFormat();
const stageDetail = [
  "Each node reads its own CSV. Raw rows never appear in the dashboard or go to the model.",
  "The detector counts flagged events within each 100-event window. Quiet windows stay local.",
  "The coordinator validates each qualifying signal with the enrolled node credential and stores it.",
  "Three enrolled groups must supply supporting evidence in the same 120-second bucket. The local release policy can approve, reduce, or refuse a request.",
  "A template or a local model proposes claims from approved evidence. The verifier checks the claims before you see them.",
];
const names = { idle: "Ready", playing: "Playing", paused: "Paused", starting: "Starting local model", error: "Stopped with error", complete: "Finished" };

function Activity({ replay, theme }) {
  const host = useRef(null);
  const chart = useRef(null);
  useEffect(() => {
    const instance = init(host.current);
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(host.current);
    return () => { observer.disconnect(); instance.dispose(); };
  }, []);
  useEffect(() => {
    const colors = theme === "dark" ? ["#ff926a", "#63cbc2", "#e5c16a"] : ["#a64025", "#217c72", "#82611c"];
    const text = theme === "dark" ? "#bed0d1" : "#4c504b";
    const line = theme === "dark" ? "#343d42" : "#e7dbcf";
    const last = Math.max(20, ...replay.points.map((p) => p.window));
    const context = replay.points.findLast((p) => p.window === last)?.family;
    chart.current.setOption({
      animation: false, color: colors, textStyle: { color: text },
      aria: { enabled: true, label: { description: "Flagged events per 100-event replay window by organization." } },
      tooltip: { trigger: "axis", confine: true },
      legend: { right: 14, top: 10, textStyle: { color: text } },
      grid: { top: 47, bottom: 48, left: 48, right: 23 },
      xAxis: { type: "value", min: 1, max: last, name: "Replay window", nameLocation: "middle", nameGap: 27, minInterval: 1,
        nameTextStyle: { color: text }, axisLabel: { color: text }, axisLine: { lineStyle: { color: line } }, splitLine: { show: false } },
      yAxis: { min: 0, max: 100, splitNumber: 4, axisLabel: { color: text }, splitLine: { lineStyle: { color: line } } },
      series: replay.nodes.map((node) => ({
        name: node, type: "line", data: replay.points.filter((point) => point.node === node)
          .map((point) => [point.window, point.count, replay.labels[point.family] || context]),
        showSymbol: true, symbol: "circle", symbolSize: 5, lineStyle: { width: 2 },
        encode: { x: 0, y: 1, tooltip: [1, 2] }, dimensions: ["Window", "Flagged events", "Scenario"],
      })),
    });
  }, [replay, theme]);
  return <div className="replay-chart" ref={host} role="img" aria-label="Line chart of flagged events per window by organization" />;
}

function Help({ dialog }) {
  return <dialog ref={dialog} className="replay-help" aria-labelledby="replay-help-title">
    <form method="dialog"><button className="button help-close" autoFocus>Close</button></form>
    <p className="eyebrow">FIELD GUIDE / EVALUATION</p><h2 id="replay-help-title">How the dashboard works</h2>
    <p>Both modes replay the same recorded test inputs. Demo uses a checked template. Local model mode starts your local GGUF server when you play and stops it when you pause or finish. It never calls a cloud service.</p>
    <ol>{stageNames.map((stage, i) => <li key={stage}><strong>{stage}.</strong> {stageDetail[i]}</li>)}</ol>
    <p><strong>Activity chart:</strong> Flags per 100 events in the selected sensor stream. The spikes are scheduled test inputs. The CSV activity is synthetic and is not a measure of detection accuracy.</p>
    <p><strong>Signal checks:</strong> The score is a fixed rule score (0–1). Baseline distance, shown as z, compares the flag count with the first four quiet windows; it is diagnostic and does not decide the outcome.</p>
    <p><strong>Case outcomes:</strong> Supported means the evidence met this scenario’s rule. It does not prove compromise. Unresolved means the required evidence is missing. Check the requests, shared values, and explanation separately.</p>
    <p><strong>Controls:</strong> Pause stops new input; the coordinator can finish processing already accepted signals. Reset clears the replay display. Previous coordinator incidents remain in Incident archive.</p>
  </dialog>;
}

const initial = { state: "idle", mode: "demo", scenario: "all", position: 0, total: 0, nodes: ["Orion", "Lyra", "Vega"],
  points: [], cases: [], rows: [], labels: {}, metrics: {}, events: [], model_configured: false };

export default function Replay({ api, theme }) {
  const [replay, setReplay] = useState(initial);
  const [options, setOptions] = useState(null);
  const [caseId, setCaseId] = useState(null);
  const [tab, setTab] = useState("evidence");
  const [signalsOnly, setSignalsOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [available, setAvailable] = useState(null);
  const stamp = useRef(0);
  const dialog = useRef(null);
  const mode = options?.mode || replay.mode;
  const scenario = options?.scenario || replay.scenario;
  const active = ["playing", "starting"].includes(replay.state);
  const pause = replay.state === "paused" && replay.mode === mode && replay.scenario === scenario;
  const current = replay.cases.find((item) => item.incident_id === caseId) || replay.cases[0];
  const latest = replay.rows[0];
  const visibleRows = signalsOnly ? replay.rows.filter((row) => row.signal_id) : replay.rows;
  const phase = replay.state === "complete" || current?.explanation_status ? 4 : latest?.state === "Used in case" ? 3 :
    latest?.state === "Accepted" || latest?.state === "Queued for delivery" ? 2 : latest ? 1 : 0;

  useEffect(() => {
    let stopped = false, timer;
    async function refresh() {
      const version = stamp.current;
      try {
        const data = await api("/replay");
        if (!stopped && version === stamp.current) { setReplay(data); setAvailable(true); }
      } catch (e) { if (!stopped && version === stamp.current) { setAvailable(false); setError(e.message); } }
      if (!stopped) timer = setTimeout(refresh, 450);
    }
    refresh();
    return () => { stopped = true; clearTimeout(timer); };
  }, [api]);

  async function control(action) {
    stamp.current++;
    setBusy(true);
    setError("");
    try {
      setReplay(await api("/replay", { method: "POST", body: JSON.stringify({ action, mode, scenario }) }));
      if (action === "reset") setCaseId(null);
    } catch (e) { setError(e.message); }
    finally { stamp.current++; setBusy(false); }
  }

  return <div className="replay">
    <section className="panel replay-control" aria-label="Replay controls">
      <div className="replay-modes" aria-label="Dashboard mode">
        {[["demo", "Demo simulation"], ["live", "Local model simulation"]].map(([key, name]) =>
          <button key={key} className="button" aria-pressed={mode === key} disabled={active || busy}
            onClick={() => setOptions({ mode: key, scenario })}>{name}</button>)}
      </div>
      <div className="replay-actions">
        <label>Scenario <select value={scenario} disabled={active || busy || !available}
          onChange={(e) => setOptions({ mode, scenario: e.target.value })}>
          <option value="all">All five scenarios</option>
          {Object.entries(replay.labels).map(([id, title]) => <option value={id} key={id}>{title}</option>)}
        </select></label>
        <button className="button primary" disabled={busy || !available || (!active && mode === "live" && !replay.model_configured)}
          onClick={() => control(active ? "pause" : "play")}>{active ? "Pause" : pause ? "Resume" : "Play"}</button>
        <button className="button" disabled={busy || !available || !replay.position} onClick={() => control("reset")}>Reset</button>
        <button className="button" onClick={() => dialog.current.showModal()}>System info</button>
      </div>
      <div className="replay-mode-note">
        <span className="mono" role="status">{names[replay.state]} · {replay.total ? replay.position + " / " + replay.total + " checks" : "30,000 input events"}</span>
        <span>{mode === "demo" ? "Checked template · no AI required" : replay.model_configured ?
          "Local llama-server · starts on Play, stops on Pause" : "Local model not configured. Launch with --llama-server and --model."}</span>
      </div>
    </section>
    {(error || replay.error) && <p className="error" role="alert">{replay.error || error}</p>}
    <ol className="replay-stages" aria-label="Signal workflow">
      {stageNames.map((label, i) => <li key={label} className={phase === i && replay.position ? "current" : ""}>
        <span>0{i + 1}</span><strong>{label}</strong>
      </li>)}
    </ol>

    <section className="panel replay-plot" aria-labelledby="activity-title">
      <header className="panel-heading"><h2 id="activity-title">Flagged activity by organization</h2>
        <span>{seen.format(replay.position * 100)} ROWS READ</span></header>
      <p className="replay-caption">Flagged events per 100 rows. {latest ? replay.metrics[latest.scenario] + " · " + replay.labels[latest.scenario] : "Play a scenario to see activity rise and fall."}</p>
      <Activity replay={replay} theme={theme} />
    </section>

    <div className="replay-grid">
      <section className="panel" aria-labelledby="checks-title">
        <header className="panel-heading"><h2 id="checks-title">Signal checks</h2><span>LATEST {replay.rows.length}</span></header>
        <p className="replay-caption">Quiet windows are checked locally. Only qualifying signals get an ID and reach the coordinator.</p>
        <label className="replay-filter"><input type="checkbox" checked={signalsOnly}
          onChange={(event) => setSignalsOnly(event.target.checked)} /> Sent signals only</label>
        <div className="replay-table"><table>
          <thead><tr>{["Replay time", "Signal ID", "Organization", "Sensor check", "Baseline z", "Rule score", "Status"].map((t) => <th key={t}>{t}</th>)}</tr></thead>
          <tbody>{visibleRows.map((row) => <tr key={row.id}>
            <td>+{row.replay_second}s</td><td title={row.signal_id || undefined}>{row.signal_id?.slice(0, 8) || "—"}</td>
            <td>{row.node}</td><td>{replay.metrics[row.scenario]}</td><td>{row.z == null ? "—" : row.z.toFixed(2)}</td>
            <td>{row.score.toFixed(2)}</td><td>{row.incident_id ? <button className="replay-link" onClick={() => {
              setCaseId(row.incident_id); setTab("evidence"); document.getElementById("replay-inspection").scrollIntoView({ block: "nearest" });
            }}>{row.state}</button> : row.state}</td>
          </tr>)}</tbody>
        </table>{!visibleRows.length && <p className="empty">{signalsOnly ? "No sent signals in the visible window." : "Signal checks will appear one at a time after you press Play."}</p>}</div>
      </section>
      <section className="panel" aria-labelledby="clusters-title">
        <header className="panel-heading"><h2 id="clusters-title">Cross-organization cases</h2><span>{replay.cases.length}</span></header>
        <div className="replay-cases">{!replay.cases.length && <p className="empty">Cases appear once the coordinator checks a qualifying signal.</p>}
          {replay.cases.map((item) => <button className="incident" aria-pressed={current?.incident_id === item.incident_id}
            key={item.incident_id} onClick={() => { setCaseId(item.incident_id); setTab("evidence"); }}>
            <div><small>CASE {item.incident_id.slice(0, 8).toUpperCase()}</small><span className={"badge " + item.outcome}>{item.outcome}</span></div>
            <strong>{replay.labels[item.family]}</strong>
            <small>{item.summary.independent_groups} reporting · {item.summary.supporting_groups} of 3 supporting</small>
            <small>{item.reporting_nodes?.join(" · ")}</small>
          </button>)}
        </div>
      </section>
    </div>
    <section className="panel replay-inspection" id="replay-inspection" aria-labelledby="inspection-title">
      <header className="panel-heading"><h2 id="inspection-title">Case inspection</h2>{current && <span>REV {current.version}</span>}</header>
      {!current ? <p className="empty">Select a case to see what the organizations shared and what the explanation can claim.</p> : <>
        <div className="replay-caption"><strong>{replay.labels[current.family]}</strong> · {words(current.reason)}</div>
        <div className="replay-tabs">{[["evidence", "Shared evidence"], ["requests", "Disclosure decisions"], ["explanation", "Checked explanation"]]
          .map(([key, title]) => <button className="button" aria-pressed={key === tab} key={key} onClick={() => setTab(key)}>{title}</button>)}</div>
        {tab === "evidence" && <ul className="replay-evidence">
          {current.evidence.map((item) => <li key={item.id}>{evidenceNames[item.entry] || words(item.entry)} · <strong>{words(item.value)}</strong> <small>Ref {item.id.slice(0, 8)} / v{item.version}</small></li>)}
          {!current.evidence.length && <li>No evidence has been released.</li>}
        </ul>}
        {tab === "requests" && <ul className="replay-evidence">
          {current.requests.map((item) => <li key={item.id}>{evidenceNames[item.entry] || words(item.entry)} · <strong>{words(item.status)}</strong></li>)}
          {!current.requests.length && <li>No disclosure requests. The coordinator first waits for three groups.</li>}
        </ul>}
        {tab === "explanation" && <div className="replay-explanation">
          <p>{current.explanation ? current.explanation.mode === "local_model" ? "Local model · claims verified" :
            replay.mode === "live" ? "Checked fallback · model did not produce acceptable claims" : "Checked template" :
            current.explanation_status || "Waiting for a supported or contradicted case."}</p>
          {current.explanation?.claims.map((claim, index) => <div className="replay-claim" key={index}>
            <span className="mono">{words(claim.kind)}</span><p>{claim.text}</p>
          </div>)}
        </div>}
      </>}
    </section>
    {replay.events.length > 0 && <details className="panel replay-history"><summary>Recent workflow decisions</summary>
      <ol>{replay.events.map((event) => <li key={event.id}><strong>{event.title}</strong> · {event.detail}</li>)}</ol>
    </details>}
    <Help dialog={dialog} />
  </div>;
}
