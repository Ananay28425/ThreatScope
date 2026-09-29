# Architecture and limits

## Trust and deployment

Three separately enrolled organizations run local detection and independent SQLite release ledgers. Enrollment maps a hashed random credential to an organization; the credential record is the node enrollment identity. Provenance groups are assigned by the operator and copied into accepted signals. They are not cryptographic proof of independence. Multiple credentials or reports from one group do not create independent corroboration. Compromised organizations can lie about their own observations; this prototype is not Byzantine consensus.

FastAPI authenticates and commits a durable signal inbox. PostgreSQL is authoritative for incidents, participation, requests, evidence revisions, browser sessions, explanation jobs, audit events, and notification history. One correlation worker owns an advisory lock. One explanation worker owns another lock and performs model calls outside database transactions. The React dashboard receives scoped snapshots through authenticated HTTP and a recoverable WebSocket stream.

The design chooses durable acceptance and consistent incident updates over accepting data during a database outage. Agents retain pending signals for later retry. A lost acknowledgement may cause a resend, but organization-scoped signal and snapshot identities prevent duplicate acceptance. Conflicting identity reuse returns HTTP 409. A database restart is recoverable; it is not high availability. A single database and correlation worker remain failure domains.

## Disclosure mechanism

The catalogue is finite and versioned with the wire schema. Authentication scenarios use authentication-failure level, source spread, and failure kind. Traffic scenarios use request-rate category, source spread, and service-error level. Raw log export, arbitrary queries, and unrestricted metric maps are absent.

An initial signal costs one policy unit. Authentication refinements cost 1, 2, and 2 units; traffic refinements cost 1, 2, and 1 units. An organization defaults to a six-unit snapshot ceiling and 2,400 units across all snapshots released to the coordinator in the preceding hour. These are administrative limits, not epsilon or formal leakage bounds. New requests and policy version numbers do not reset accumulated costs.

For an unresolved rule, the coordinator requests the cheapest missing predicate, using its catalogue name to break ties. It never requests another predicate after that source's rule is decided. The source can approve, coarsen to unknown, or deny. SQLite commits an immutable release and its debit before transmission. Retries reuse the representation and evidence identity without charging twice. Policy tightening can deny reuse; it cannot erase evidence already received elsewhere.

One denial terminates further requests to that source in that investigation. All useful requests exhausted, insufficient sources, conflicting corroboration, budget exhaustion, and deadlines leave an explicit unresolved outcome. Missing evidence does not become benign evidence. An incident's supported/contradicted/unresolved outcome is separate from the analyst's open/investigating/resolved workflow.

## Correlation semantics

The current catalogue addresses two declared scenarios, not every coordinated threat. A 120-second tumbling window selects the first eligible snapshot from each organization for a family. At least three enrolled provenance groups must agree. Reports from one group must agree internally to contribute a group vote. Unknown fingerprints do not join unrelated anomalies. Signals can arrive up to 24 hours late and 60 seconds ahead; late data still uses its observation bucket, while requests have a receipt-time deadline. Boundary-split campaigns and changing conditions within a window remain limitations.

Authentication support requires high failure rate, wide source spread, and rejected credentials. Service-unavailable failures supply a benign alternative. Traffic support requires a spike, wide sources, and high service errors; normal rate or low errors contradict that rule. These predicates are interpretable assumptions, not universal attack definitions. Local detector warmup cannot suppress a rule score. Model readiness describes training progress and is not detection confidence.

## Local explanation boundary

Only recipient-authorized snapshots enter generation. The model selects claims in a finite language separating observation, inference, unknown, and advice. Admission checks each predicate/value pair, exact evidence identity and version, active status, and the authorized snapshot. Fixed prose renders admitted slots. This deliberately restricts expressive power; it does not solve unrestricted natural-language factuality.

Evidence corrections, withdrawal, expiry, or changed authorization invalidate dependent views. Evidence expires after 24 hours; retrieval masks expired evidence immediately, and the worker persists expiry revisions. The model has no tools, raw-log access, or cloud fallback. One repair is allowed before deterministic fallback. The call budget is 512 output tokens, at most four requested claims, one concurrent generation, and a bounded timeout. Oversized prompts fall back before inference. Detection continues while inference is slow or unavailable.

## Security and operational costs

Random node credentials are stored as SHA-256 hashes; browser passwords use Argon2. Browser sessions use HttpOnly, SameSite cookies, origin checks, and CSRF tokens. Administrator/coordinator access covers shared evidence; organization analysts see only their own refinements within participating incidents. Every stream subscription rechecks the session. Slow viewers receive bounded buffering and disconnect without blocking ingestion.

Loopback HTTP is for the single-PC demo. Production browser access requires TLS and secure cookies. A second-laptop inference endpoint requires authenticated HTTPS and certificate verification. Source-local snapshots and database evidence remain sensitive at rest; disk encryption and operating-system access control belong to deployment. No credential is a metric label. Logs use resource identities, not secret keys.

PostgreSQL indexes cover pending ingestion, observation windows, scoped evidence, request ownership, sessions, and notification cursors. The coordinator stores historical versions and notifications indefinitely in this prototype. Plan retention and disk alerts before long-running deployment. Agent pending queues are bounded to 1,000 signals; rejected production attempts increment a visible gap counter. A full or unavailable database fails visibly. No partitioning, multi-region replication, distributed query engine, or automatic failover is claimed.
