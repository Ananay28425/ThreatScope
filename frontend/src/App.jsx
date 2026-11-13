/** Purpose: an evaluation workspace with automatic local demo access. */
import { useCallback, useEffect, useRef, useState } from "react";
import "./styles.css";

let csrf = "";
async function api(path, options = {}) {
  const response = await fetch("/api/v1" + path, {
    credentials: "same-origin",
    cache: "no-store",
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
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshResult, setRefreshResult] = useState("");
  const cursor = useRef(0);
  const job = requestedJob?.incidentId === selected ? requestedJob : null;
  const current = incidents.find((item) => item.incident_id === selected);
  const [view, setView] = useState("dashboard");
  const [detail, setDetail] = useState("evidence");

  const refresh = useCallback(async () => {
    try {
      const [items, nodes, health] = await Promise.all([api("/incidents"), api("/organizations"), api("/status")]);
      setIncidents(items.incidents);
      setOrganizations(nodes.organizations);
      setStatus(health);
      setLastUpdated(new Date());
      setSelected((old) => items.incidents.some((item) => item.incident_id === old) ? old : items.incidents[0]?.incident_id ?? null);
      setError("");
      return items.incidents;
    } catch (e) { setError(e.message); throw e; }
  }, []);

  async function refreshManually() {
    setRefreshing(true);
    setRefreshResult("");
    try {
      const before = new Map(incidents.map((item) => [item.incident_id, item.version]));
      const items = await refresh();
      const changes = items.filter((item) => before.get(item.incident_id) !== item.version).length;
      setRefreshResult(changes ? `${changes} new or updated incident${changes === 1 ? "" : "s"}.` : "No new incidents. Data is current.");
    } catch (e) { setRefreshResult(`Refresh failed: ${e.message}`); }
    finally { setRefreshing(false); }
  }

  useEffect(() => {
    api("/auth/me").catch(() => api("/auth/demo", { method: "POST" }))
      .then((data) => { csrf = data.csrf; setUser(data.user); setError(""); })
      .catch((e) => setError("Demo access unavailable: " + e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    refresh().catch(() => {});
    const timer = setInterval(() => refresh().catch(() => {}), 5000);
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
    setDetail("explanation");
    setBusy(true);
    try { setJob({ ...await api("/incidents/" + selected + "/explanations", { method: "POST" }), incidentId: selected }); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const outcomes = ["supported", "unresolved", "contradicted"];
  const counts = outcomes.map((state) => incidents.filter((item) => item.outcome === state).length);
  const store = { sqlite: "SQLite", postgresql: "PostgreSQL" }[status.coordinator_store];
  const model = status.inference_configured ? "Hosted API" : "Checked template";
  const ready = Boolean(user && status.service === "ready");
  const stream = connected ? "Live updates" : ready ? "Polling API" : loading ? "Connecting" : "Awaiting API";

  return (
    <div className="workspace">
      <a className="skip-link" href="#main">Skip to workspace</a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">T<span>/</span>S</span>
          <div><strong>THREATSCOPE<span>.</span></strong><small>ANALYST CONSOLE</small></div>
        </div>
        <nav aria-label="Workspace navigation">
          <p className="side-title">WORKSPACE</p>
          {[["dashboard", "Dashboard"], ["architecture", "Architecture"]].map(([key, title], index) =>
            <button key={key} className="nav-item" aria-current={view === key ? "page" : undefined}
              onClick={() => setView(key)}><span>0{index + 1}</span>{title}</button>)}
        </nav>
        <section className="nodes" aria-labelledby="nodes-title">
          <h2 id="nodes-title" className="side-title">ENROLLED NODES <span>{ready ? organizations.length : "–"}</span></h2>
          {organizations.map((org) => <div className="node" key={org.id}>
            <i className={org.active ? "lamp live" : "lamp"} aria-hidden="true" />
            <div><strong>{org.name}</strong><small>{org.active ? time(org.last_signal) : "Inactive"}</small></div>
          </div>)}
          {!organizations.length && <p className="muted">{loading ? "Connecting…" : "No nodes to show."}</p>}
        </section>
        <div className="sidebar-bottom">
          <span className="mono">EVALUATION SESSION</span>
          <strong><i className={connected ? "lamp live" : "lamp"} aria-hidden="true" />{stream}</strong>
          {store && <small>{store} coordinator · {model}</small>}
        </div>
      </aside>

      <main id="main" className="main">
        <header className="page-heading">
          <div><p className="eyebrow">THREATSCOPE / {view === "dashboard" ? "OPERATIONS" : "SYSTEM"}</p>
            <h1>{view === "dashboard" ? "Incident dashboard" : "System architecture"}</h1>
            <p className="heading-copy">{view === "dashboard" ? "Cross-organization findings and authorized evidence." : "How local signals become evidence-backed findings."}</p>
          </div>
          {view === "dashboard" && user && <div className="refresh-control">
            <button className="button" onClick={refreshManually} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh data"}
            </button>
            <small role="status">{lastUpdated ? `API checked at ${lastUpdated.toLocaleTimeString()}` : "Waiting for API"}</small>
            {refreshResult && <small role="status">{refreshResult}</small>}
          </div>}
        </header>

        {view === "architecture" ? <Architecture /> : <>
          {error && <p className="error" role="alert">{error}</p>}
          {loading ? <p className="panel empty" role="status">Opening dashboard…</p> : !user ?
            <div className="panel empty"><p>Start the local demo launcher to open a session.</p>
              <button className="button" onClick={() => location.reload()}>Retry</button></div> : <>
              <section className="metrics" aria-label="Dashboard totals">
                {["Supported", "Unresolved", "Contradicted", "Enrolled nodes"].map((name, index) =>
                  <div className="metric" key={name}>
                    <span>{name}</span>
                    <strong>{ready ? String(index === 3 ? organizations.length : counts[index]).padStart(2, "0") : "–"}</strong>
                    <small>{index === 3 ? "REPORTING ORGANIZATIONS" : "INCIDENTS IN FEED"}</small>
                  </div>)}
              </section>

              <div className="work-grid">
                <section className="panel" aria-labelledby="feed-title">
                  <header className="panel-heading"><h2 id="feed-title">Incident feed</h2><span>{incidents.length} RECORDS</span></header>
                  <div className="incident-list">
                    {!incidents.length && <div className="empty">
                      <strong>{ready ? "No incidents yet" : "Waiting for data"}</strong>
                      {ready && <p>Use <code>scripts.demo_check</code> to generate a sample incident.</p>}
                    </div>}
                    {incidents.map((item) =>
                      <button className="incident" key={item.incident_id} aria-pressed={selected === item.incident_id}
                        onClick={() => { setSelected(item.incident_id); setDetail("evidence"); }}>
                        <div><Badge value={item.outcome} /><small>{time(item.created_at)}</small></div>
                        <strong>{label(item.family)}</strong>
                        <small>REV {item.version} / {item.incident_id.slice(0, 8)}</small>
                      </button>)}
                  </div>
                </section>

                <section className="panel" aria-labelledby="inspector-title">
                  <header className="panel-heading"><h2 id="inspector-title">Incident inspector</h2>{current && <span>REV {current.version}</span>}</header>
                  {!current ? <p className="empty">Select an incident to inspect its evidence.</p> : <>
                    <div className="case-summary">
                      <div className="case-heading">
                        <div><h3>{label(current.family)}</h3><p className="muted">{label(current.reason)}</p></div>
                        <Badge value={current.outcome} />
                      </div>
                      <dl className="case-meta">
                        {current.summary && <>
                          <div><dt>Independent groups</dt><dd>{current.summary.independent_groups}</dd></div>
                          <div><dt>Supporting groups</dt><dd>{current.summary.supporting_groups}</dd></div>
                        </>}
                        <div><dt>Coverage</dt><dd>{label(current.coverage)}</dd></div>
                      </dl>
                      <div className="case-actions">
                        {user.role !== "analyst" && <label className="workflow">Workflow <select value={current.workflow} onChange={async (event) => {
                          try { await api("/incidents/" + selected + "/workflow", { method: "PATCH", body: JSON.stringify({ status: event.target.value }) }); refresh(); }
                          catch (e) { setError(e.message); }
                        }}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select></label>}
                        <button className="button primary" onClick={explain} disabled={busy || ["queued", "running"].includes(job?.status)}>
                          {busy ? "Requesting…" : "Generate explanation"}
                        </button>
                      </div>
                    </div>

                    <div className="detail-nav" role="group" aria-label="Inspector sections">
                      {[
                        ["evidence", "Evidence", current.evidence.length],
                        ["decisions", "Disclosure decisions", current.requests.length],
                        ["explanation", "Explanation", null],
                      ].map(([key, title, count]) =>
                        <button key={key} aria-pressed={detail === key} onClick={() => setDetail(key)}>
                          {title}{count !== null && <span>{count}</span>}
                        </button>)}
                    </div>
                    {detail === "evidence" && <Evidence items={current.evidence} />}
                    {detail === "decisions" && <Decisions items={current.requests} />}
                    {detail === "explanation" && <Explanation job={job} model={model} busy={busy} />}
                  </>}
                </section>
              </div>
              <p className="footer-note">Synthetic evaluation. A supported rule is evidence for investigation, not proof of compromise.</p>
            </>}
        </>}
      </main>
    </div>
  );
}

function Evidence({ items }) {
  if (!items.length) return <p className="empty">No evidence has been released.</p>;
  return <div className="table-wrap"><table>
    <thead><tr><th scope="col">Evidence</th><th scope="col">Value</th><th scope="col" className="numeric">Policy units</th></tr></thead>
    <tbody>{items.map((item) => <tr key={item.id}>
      <td><strong>{label(item.entry)}</strong><small>{item.id.slice(0, 8)} · v{item.version}</small></td>
      <td><Badge value={item.active ? item.value : "withdrawn"} /></td>
      <td className="numeric">{item.cost}</td>
    </tr>)}</tbody>
  </table></div>;
}

function Decisions({ items }) {
  if (!items.length) return <p className="empty">No refinements requested.</p>;
  return <div className="table-wrap"><table>
    <thead><tr><th scope="col">Requested refinement</th><th scope="col">Decision</th></tr></thead>
    <tbody>{items.map((item) => <tr key={item.id}>
      <td><strong>{label(item.entry)}</strong><small>{item.id.slice(0, 8)}</small></td>
      <td><Badge value={item.status} /></td>
    </tr>)}</tbody>
  </table></div>;
}

function Explanation({ job, model, busy }) {
  if (!job) return <p className="empty" role="status">{busy ? "Requesting explanation…" : `No explanation requested. Available mode: ${model}.`}</p>;
  return <div className="explanation">
    <div className="explanation-status" role="status">
      <Badge value={job.status} />
      {["queued", "running"].includes(job.status) && <span>Checking authorized evidence…</span>}
      {job.status === "stale" && <span>Evidence or access changed. Generate a new explanation.</span>}
      {job.result && job.status !== "stale" && <span>{job.result.mode === "template" ? "Checked template" : "Verified model claims"}</span>}
    </div>
    {job.result && job.status !== "stale" && <ul className="claims">{job.result.claims.map((claim, index) =>
      <li key={index}><Badge value={claim.kind} /><p>{claim.text}</p>
        {claim.evidence_id && <small>Evidence {claim.evidence_id.slice(0, 8)} · v{claim.evidence_version}</small>}
      </li>)}</ul>}
  </div>;
}

const systemFlow = [
  ["F1", "Local detection", "Orion, Lyra and Vega detect authentication or traffic bursts independently. Raw logs stay with each organization."],
  ["F2", "Signal ingestion", "FastAPI validates signals and stores them before acknowledging. The laptop demo uses SQLite; the reference deployment uses PostgreSQL."],
  ["F3", "Correlation and disclosure", "The worker compares independent provenance groups across a 120-second window. Local policy can approve, coarsen or deny requests for evidence."],
  ["F4", "Explanation verification", "The verifier checks claims against authorized evidence. A hosted model is optional; the demo can use a checked template."],
  ["F5", "Analyst dashboard", "The incident feed updates over a live event stream and shows authorized evidence, disclosure decisions and checked explanations."],
];

function Architecture() {
  return <section className="panel architecture" aria-labelledby="flow-title">
    <header className="panel-heading"><h2 id="flow-title">Signal flow</h2><span>5 STAGES</span></header>
    <ol>{systemFlow.map(([code, title, description]) => <li key={code}>
      <span className="flow-code">{code}</span><div><h3>{title}</h3><p className="muted">{description}</p></div>
    </li>)}</ol>
  </section>;
}
