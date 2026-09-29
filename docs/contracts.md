# Versioned contracts

The authoritative typed wire definitions are `common/contracts.py`. `/openapi.json` exposes the HTTP request schemas. Version 1 rejects unknown input fields, nonfinite numbers, raw dictionaries, and out-of-catalogue values. Bodies above 16 KiB are rejected without echoing input. Validation errors omit submitted values.

| Interface | Contract and authorization |
|---|---|
| `POST /api/v1/signals` | Enrolled `X-Api-Key`; schema version, stable signal and snapshot UUIDs, observation interval, family, score, detector version, model state, policy version. HTTP 202 only after commit; identical retry acknowledged; conflicting reuse returns 409. |
| `GET /api/v1/agent/requests` | Enrolled node; only that organization's pending, unexpired finite-catalogue requests. |
| `POST /api/v1/agent/responses` | Exact request/snapshot/entry binding; approved, coarsened, or denied; immutable response on retry. Foreign request returns 404. |
| `POST /api/v1/agent/evidence/{id}/revise` | Owning organization, expected current version, correction or withdrawal. Competing versions return 409. |
| `/api/v1/auth/login`, `/auth/me`, `/auth/logout` | Origin-bound login; persisted opaque cookie; logout and other writes require CSRF. No browser token storage. |
| `GET /api/v1/incidents` and `/{id}` | Authorized snapshots with evidence revisions, disclosure decisions, coverage, workflow, and digest. Unrelated organizations receive 404. |
| `PATCH /api/v1/incidents/{id}/workflow` | Administrator/coordinator only; does not overwrite evidential outcome. |
| `POST /api/v1/incidents/{id}/explanations` | Queued job for the requesting account's current snapshot. Per-user quota; detection does not wait. |
| `GET /api/v1/explanations/{id}` | Creator only; current permissions and digest rechecked; stale output returns no explanation. |
| `WS /api/v1/events?cursor=N` | Allowed origin and browser session; scoped snapshots, monotonic recovery cursor, heartbeat, bounded queue. Reconnect with the last received cursor. |
| `POST /api/v1/admin/credentials/{id}/revoke` | Administrator revokes a node enrollment. |
| `POST /api/v1/admin/users/{id}/disable` | Another administrator disables an account, its sessions, and dependent explanations. |

Credential renewal and provenance enrollment are operator-controlled administrative operations. A credential ID is not secret. API keys, passwords, raw source addresses, and local logs must never be included in incident snapshots or notification payloads. Evidence UUIDs provide reference identity, not cryptographic integrity against a malicious enrolled source.
