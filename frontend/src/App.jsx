/** Purpose: an evaluation workspace with automatic local demo access. */
import { useCallback, useEffect, useRef, useState } from "react";
import "./styles.css";

let csrf = "";
async function api(path, options = {}) {
  const response = await fetch("/api/v1" + path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, ...options.headers },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(readable(body.detail));
  return body;
}
const readable = (value) => typeof value === "string" ? value.replaceAll("_", " ") : "Request could not be completed.";
const label = (value = "") => value.replaceAll("_", " ");
const time = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "No reports yet";
const Badge = ({ value }) => <span className={"badge " + value}>{label(value)}</span>;

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [incidents, setIncidents] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [status, setStatus] = useState({});
  const [selected, setSelected] = useState(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");
  const [requestedJob, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const cursor = useRef(0);
  const job = requestedJob?.incidentId === selected ? requestedJob : null;
  const current = incidents.find((item) => item.incident_id === selected);

  const refresh = useCallback(async () => {
    try {
      const [items, nodes, health] = await Promise.all([api("/incidents"), api("/organizations"), api("/status")]);
      setIncidents(items.incidents);
      setOrganizations(nodes.organizations);
      setStatus(health);
      setSelected((old) => old || items.incidents[0]?.incident_id || null);
      setError("");
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => {
    api("/auth/me").catch(() => api("/auth/demo", { method: "POST" }))
      .then((data) => { csrf = data.csrf; setUser(data.user); setError(""); })
      .catch((e) => setError("Demo access unavailable: " + e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    refresh();
    const timer = setInterval(refresh, 5000);
    let socket, reconnect, stopped = false;
    function connect() {
      if (stopped) return;
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(protocol + "//" + location.host + "/api/v1/events?cursor=" + cursor.current);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.cursor) cursor.current = message.cursor;
        if (message.incident) {
          setIncidents((previous) => {
            const old = previous.find((item) => item.incident_id === message.incident.incident_id);
            if (old && old.version > message.incident.version) return previous;
            return [message.incident, ...previous.filter((item) => item.incident_id !== message.incident.incident_id)].slice(0, 100);
          });
          setSelected((old) => old || message.incident.incident_id);
        }
      };
      socket.onclose = () => { setConnected(false); if (!stopped) reconnect = setTimeout(connect, 3000); };
    }
    connect();
    return () => { stopped = true; clearInterval(timer); clearTimeout(reconnect); socket?.close(); };
  }, [user, refresh]);

  useEffect(() => {
    if (!job?.job_id) return;
    let cancelled = false;
    const check = async () => {
      try {
        const next = await api("/explanations/" + job.job_id);
        if (!cancelled) setJob((previous) => previous?.job_id === next.job_id ? { ...previous, ...next } : previous);
      } catch (e) { if (!cancelled) setError(e.message); }
    };
    check();
    const timer = setInterval(check, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [job?.job_id]);

  async function explain() {
    setBusy(true);
    try { setJob({ ...await api("/incidents/" + selected + "/explanations", { method: "POST" }), incidentId: selected }); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const counts = ["supported", "unresolved", "contradicted"].map((state) =>
    incidents.filter((item) => item.outcome === state).length);
  const [layer, setLayer] = useState(0);
  const store = status.coordinator_store === "sqlite" ? "SQLite" : status.coordinator_store === "postgresql" ? "PostgreSQL" : null;
  const infer = status.inference_configured ? "Hosted model API" : "Checked template";
  const stages = [
    { title: "Organization nodes", tag: "PRIVATE BOUNDARY", detail: "Orion, Lyra and Vega detect authentication and traffic bursts on their own event streams. Each node has a SQLite release ledger. Raw events stay inside the node." },
    { title: "FastAPI + durable store", tag: "COORDINATOR", detail: "FastAPI authenticates enrolled nodes, validates versioned signals and commits them before acknowledging. PostgreSQL is the reference store; this single-process laptop demo uses SQLite." },
    { title: "Correlation + explanation", tag: "TWO WORKERS", detail: "Correlation evaluates three provenance groups in a 120-second window and requests the cheapest useful missing evidence. The explanation worker builds a scoped snapshot, checks model claims and invalidates results when evidence changes." },
    { title: "Analyst dashboard", tag: "SCOPED ACCESS", detail: "The React dashboard shows incidents, evidence and disclosure decisions permitted for the current session. A recoverable event stream updates the view as workers commit changes." },
  ];

  return <>
    <a className="skip" href="#workspace">Skip to investigations</a>
    <header className="site-header" id="overview">
      <nav className="nav wrap" aria-label="Main navigation">
        <a className="brand" href="#overview"><span className="brand-mark">T<span>/</span>S</span>ThreatScope</a>
        <div className="nav-links"><a href="#architecture">Architecture</a><a href="#features">Features</a><a href="#workspace">Investigations</a></div>
        <a className="button nav-action" href="#workspace">Open workspace</a>
      </nav>
    </header>
    <main>
      <section className="hero wrap" aria-labelledby="hero-title">
        <p className="tag"><i /> Distributed threat intelligence</p>
        <h1 id="hero-title">Connect threat signals.<br /><em>Keep raw logs private.</em></h1>
        <p className="lede">See how three organizations detect anomalies, share bounded evidence and investigate a coordinated threat.</p>
        <div className="hero-actions">
          <a className="button primary" href="#workspace">Explore investigations</a>
          <a className="button secondary" href="#architecture">See how it works</a>
        </div>
      </section>

      <section className="architecture wrap" id="architecture" aria-labelledby="arch-title">
        <div className="frame">
          <header className="frame-head">
            <div><p className="eyebrow">01 / SYSTEM ARCHITECTURE</p><h2 id="arch-title">From local event to shared incident</h2></div>
            <span className="tag subtle"><i /> {store ? `${store} demo` : "Single-PC topology"}</span>
          </header>
          <div className="topology" aria-label="Architecture components">
            {stages.map((stage, index) => <button type="button" className="stage" aria-pressed={layer === index}
              key={stage.title} onClick={() => setLayer(index)}>
              <span className="stage-kicker"><b>0{index + 1}</b>{stage.tag}</span>
              <strong>{stage.title}</strong>
              <span className="stage-items">
                {[
                  ["Orion", "Lyra", "Vega"],
                  ["Authenticated signals", "Durable inbox"],
                  ["120 s · 3 groups", "Claim verifier"],
                  ["Incident + evidence", "Recoverable stream"],
                ][index].map((name) => <span key={name}>{name}</span>)}
              </span>
            </button>)}
          </div>
          <div className="stage-detail" aria-live="polite"><span className="eyebrow">0{layer + 1} / {stages[layer].tag}</span><p>{stages[layer].detail}</p></div>
          <div className="frame-foot">
            <span><b>Model boundary</b> · Optional HTTPS API receives approved categories with temporary evidence references. The verifier checks returned claims before display.</span>
            <span className="mono">{status.inference_configured === undefined ? "API OR TEMPLATE" : infer}</span>
          </div>
        </div>
      </section>

      <section className="section wrap" id="features" aria-labelledby="features-title">
        <p className="eyebrow">02 / FUNCTIONAL SPECIFICATIONS</p>
        <h2 id="features-title">What ThreatScope does</h2>
        <div className="features">
          {[
            ["F1", "Detect anomalies locally", "Each node processes its own events and flags authentication or traffic bursts."],
            ["F2", "Share signals securely", "Enrolled credentials identify the source. Stable signal IDs make retries safe; the coordinator stores the signal before replying."],
            ["F3", "Correlate and request evidence", "Compare independent reports. Local policy approves, coarsens or denies refinements and records release costs."],
            ["F4", "Verify explanation claims", "Check evidence IDs, versions, values and access before rendering. Use a checked template when inference is unavailable."],
            ["F5", "Investigate in one workspace", "Track incident outcomes, inspect authorized evidence and request an explanation as findings change."],
          ].map(([id, title, description]) => <article className="feature" key={id}>
            <span className="eyebrow">{id}</span><h3>{title}</h3><p>{description}</p>
          </article>)}
        </div>
        <p className="boundary">The evaluation uses synthetic data. A supported rule does not prove compromise. Policy units track disclosure cost and do not provide formal differential privacy.</p>
      </section>

      <section className="section wrap" id="workspace" aria-labelledby="workspace-title">
        <header className="section-heading">
          <div><p className="eyebrow">03 / ANALYST WORKSPACE</p><h2 id="workspace-title">Investigations</h2></div>
          {user && <div className="workspace-actions"><span className="tag subtle"><i className={connected ? "online" : ""} />{connected ? "Live updates" : "Polling API"}</span><button className="button secondary" onClick={refresh}>Refresh</button></div>}
        </header>
        {error && <p className="error" role="alert">{error}</p>}
        {loading ? <p className="empty">Opening the demo workspace…</p> : !user ?
          <div className="empty"><p>Start ThreatScope with the demo launcher to open a local session.</p><button className="button secondary" onClick={() => location.reload()}>Retry</button></div> : <>
          <div className="stats">
            {["Supported", "Unresolved", "Contradicted", "Organizations"].map((name, index) =>
              <div key={name}><span>{name}</span><strong>{index === 3 ? organizations.length : counts[index]}</strong></div>)}
          </div>
          <div className="work-grid">
            <div className="panel incident-list">
              <div className="panel-heading"><h3>Incident feed</h3><span className="mono">{incidents.length} RECORDS</span></div>
              {!incidents.length && <p className="empty">No incident reports yet. Run <code>uv run python -m scripts.demo_check</code> to generate a synthetic incident.</p>}
              {incidents.map((item) => <button className="incident" aria-pressed={selected === item.incident_id}
                key={item.incident_id} onClick={() => setSelected(item.incident_id)}>
                <strong>{label(item.family)}</strong><span><Badge value={item.outcome} /><small>{time(item.created_at)}</small></span>
              </button>)}
              <div className="panel-heading node-head"><h3>Enrolled nodes</h3></div>
              {organizations.map((org) => <div className="org" key={org.id}><i className={org.active ? "online" : ""} /><span>{org.name}</span><small>{time(org.last_signal)}</small></div>)}
            </div>
            <div className="panel incident-detail">
              <div className="panel-heading"><h3>Authorized evidence</h3>{current && <span className="mono">REV {current.version}</span>}</div>
              {!current ? <p className="empty">Select an incident to inspect its evidence and disclosure decisions.</p> :
                <div className="panel-body">
                  <div className="incident-title"><h3>{label(current.family)}</h3><Badge value={current.outcome} /></div>
                  <p className="muted">{label(current.reason)} · {label(current.coverage)}</p>
                  <div className="incident-meta">
                    {current.summary && <span>{current.summary.independent_groups} independent groups · {current.summary.supporting_groups} supporting</span>}
                    {user.role !== "analyst" && <label>Workflow <select aria-label="Investigation workflow" value={current.workflow} onChange={async (event) => {
                      try { await api("/incidents/" + selected + "/workflow", { method: "PATCH", body: JSON.stringify({ status: event.target.value }) }); refresh(); }
                      catch (e) { setError(e.message); }
                    }}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label>}
                  </div>
                  <h4>Evidence releases</h4>
                  {!current.evidence.length ? <p className="muted">No refinements released.</p> : current.evidence.map((item) =>
                    <div className="evidence-row" key={item.id}><span>{label(item.entry)} <small>v{item.version}</small></span>
                      <Badge value={item.active ? item.value : "withdrawn"} /><small>{item.cost} policy units</small></div>)}
                  <h4>Disclosure decisions</h4>
                  {!current.requests.length ? <p className="muted">No refinements requested.</p> : current.requests.map((item) =>
                    <div className="evidence-row" key={item.id}><span>{label(item.entry)}</span><Badge value={item.status} /></div>)}
                </div>}
              <div className="panel-heading explanation-head">
                <h3>Checked explanation</h3>
                <button className="button primary" onClick={explain} disabled={!current || busy || ["queued", "running"].includes(job?.status)}>
                  {busy ? "Requesting…" : "Generate explanation"}</button>
              </div>
              <div className="panel-body">
                {!job && <p className="muted">{status.inference_configured ? "The hosted API receives a minimized, authorized evidence snapshot." : "The demo uses a checked template when no model API is configured."}</p>}
                {job && <><Badge value={job.status} />
                  {["queued", "running"].includes(job.status) && <p className="muted">Checking evidence. Incident monitoring continues.</p>}
                  {job.status === "stale" && <p className="muted">Evidence or access changed. Generate a new explanation.</p>}
                  {job.result && job.status !== "stale" && <>
                    <p className="muted">{job.result.mode === "template" ? "Checked template" : job.result.mode === "api_model" ? "Hosted API · verified claims" : "Model · verified claims"}</p>
                    <ul className="claims">{job.result.claims.map((claim, index) =>
                      <li key={index}><Badge value={claim.kind} /><p>{claim.text}</p>
                        {claim.evidence_id && <small>Evidence {claim.evidence_id.slice(0, 8)} · v{claim.evidence_version}</small>}</li>)}</ul>
                  </>}
                </>}
              </div>
            </div>
          </div>
        </>}
      </section>
    </main>
    <footer className="footer"><div className="wrap"><strong>ThreatScope</strong><span>Research prototype · Synthetic evaluation</span><a href="#overview">Back to top ↑</a></div></footer>
  </>;
}
