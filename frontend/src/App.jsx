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
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const cursor = useRef(0);
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

  useEffect(() => { setJob(null); }, [selected]);

  useEffect(() => {
    if (!job?.job_id) return;
    let cancelled = false;
    const check = async () => {
      try {
        const next = await api("/explanations/" + job.job_id);
        if (!cancelled) setJob(next);
      } catch (e) { if (!cancelled) setError(e.message); }
    };
    check();
    const timer = setInterval(check, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [job?.job_id]);

  async function explain() {
    setBusy(true);
    try { setJob(await api("/incidents/" + selected + "/explanations", { method: "POST" })); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  if (loading) return <main className="loading">Opening ThreatScope…</main>;
  if (!user) return <main className="loading"><h1>ThreatScope unavailable</h1>
    <p className="error" role="alert">{error || "Start evaluation services and enroll demo organizations."}</p>
    <button onClick={() => location.reload()}>Retry</button>
  </main>;

  const counts = ["supported", "unresolved", "contradicted"].map((state) => incidents.filter((item) => item.outcome === state).length);
  return <div className="workspace">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">T</span><strong>ThreatScope</strong></div>
      <p className="eyebrow">OPERATIONS WORKSPACE</p>
      <div className="nav-active">â—ˆ &nbsp; Incident overview</div>
      <p className="sidebar-note">Evidence stays under source control. Conclusions show their limits.</p>
      <div className="sidebar-bottom"><Badge value={connected ? "connected" : "reconnecting"} />
        <small>Local evaluation session</small></div>
    </aside>
    <main className="main">
      <header><div><p className="eyebrow">EVIDENCE / CORRELATION / INTERPRETATION</p><h1>Incident overview</h1></div>
        <button className="secondary" onClick={refresh}>Refresh</button></header>
      {error && <div className="error" role="alert">{error}</div>}
      <section className="metrics" aria-label="Incident counts">
        {["Supported", "Unresolved", "Contradicted"].map((title, index) =>
          <div className="metric" key={title}><span>{title}</span><strong>{counts[index]}</strong><small>Declared rule outcome</small></div>)}
        <div className="metric"><span>Organizations</span><strong>{organizations.length}</strong><small>{status.pending_signals ?? "—"} reports awaiting correlation</small></div>
      </section>
      <div className="content-grid">
        <section className="panel incident-list">
          <div className="panel-heading"><h2>Investigations</h2><span>{incidents.length}</span></div>
          {incidents.length === 0 && <div className="empty">Waiting for organization reports.<p>New investigations appear when eligible anomaly signals arrive.</p></div>}
          {incidents.map((item) => <button className={"incident " + (selected === item.incident_id ? "selected" : "")}
            key={item.incident_id} onClick={() => setSelected(item.incident_id)}>
            <div><Badge value={item.outcome} /><small>{time(item.created_at)}</small></div>
            <strong>{label(item.family)}</strong><span>{label(item.reason)}</span><small>Revision {item.version} · {label(item.coverage)}</small>
          </button>)}
        </section>
        <section className="panel detail">
          <div className="panel-heading"><h2>Authorized evidence</h2>{current && <span>REV {current.version}</span>}</div>
          {!current ? <div className="empty">Select an investigation to inspect its evidence.</div> : <>
            <div className="incident-title"><h2>{label(current.family)}</h2><Badge value={current.outcome} /></div>
            <p className="muted">{label(current.reason)}. A supported rule does not establish successful compromise.</p>
            <div className="coverage">Coverage: <strong>{label(current.coverage)}</strong>
              {user.role !== "analyst" && <select aria-label="Investigation workflow" value={current.workflow} onChange={async (event) => {
                try { await api("/incidents/" + selected + "/workflow", { method: "PATCH", body: JSON.stringify({ status: event.target.value }) }); refresh(); }
                catch (e) { setError(e.message); }
              }}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option></select>}
            </div>
            <div className="evidence-table">
              {current.evidence.length === 0 ? <p className="muted">No refinements released yet.</p> : current.evidence.map((item) =>
                <div className="evidence-row" key={item.id}><div><strong>{label(item.entry)}</strong><small>{item.id.slice(0, 8)} · version {item.version}</small></div>
                  <Badge value={item.active ? item.value : "withdrawn"} /><small>{item.cost} policy units</small></div>)}
            </div>
            <h3>Disclosure decisions</h3>
            <div className="requests">{current.requests.length === 0 ? <p className="muted">No additional evidence requested.</p> :
              current.requests.map((item) => <div key={item.id}><span>{label(item.entry)}</span><Badge value={item.status} /></div>)}</div>
          </>}
        </section>
        <section className="panel organizations">
          <div className="panel-heading"><h2>Organizations</h2></div>
          {organizations.map((org) => <div className="org" key={org.id}><span className={"dot " + (org.active ? "online" : "")} />
            <div><strong>{org.name}</strong><small>{time(org.last_signal)}</small></div></div>)}
          <div className="boundary-note"><h3>Sharing boundary</h3><p>Only approved evidence appears here. Missing or denied evidence remains unknown.</p></div>
        </section>
      </div>
      <section className="panel explanation">
        <div className="panel-heading"><div><p className="eyebrow">LOCAL INTERPRETATION</p><h2>Explanation with evidence references</h2></div>
          <button onClick={explain} disabled={!selected || busy}>{busy ? "Requesting…" : "Explain selected incident"}</button></div>
        {!job && <p className="muted">Generate an explanation from this account’s authorized evidence.</p>}
        {job && <><Badge value={job.status} />
          {["queued", "running"].includes(job.status) && <p className="muted">Preparing explanation. Incident monitoring continues.</p>}
          {job.status === "stale" && <p className="notice">Evidence or permissions changed. Generate a new explanation before using its conclusions.</p>}
          {job.result && <><p className="muted">{job.result.mode === "template" ? "Structured fallback" : "Local model"} · Facts checked against the supported evidence contract</p>
            <ol>{job.result.claims.map((claim, index) => <li key={index}><Badge value={claim.kind} /><p>{claim.text}</p>
              {claim.evidence_id && <small>Evidence {claim.evidence_id.slice(0, 8)} · version {claim.evidence_version}</small>}</li>)}</ol></>}
        </>}
      </section>
      <footer>ThreatScope research prototype · Scenario demonstrations are labeled in the run manifest.</footer>
    </main>
  </div>;
}
