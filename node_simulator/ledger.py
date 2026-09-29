"""Organization-local durable outbox and transactionally enforced disclosure limits."""
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from common.contracts import CATALOGUE, EvidenceResponse, SignalIn, aware, utcnow


@dataclass(frozen=True)
class Policy:
    version: int = 1
    snapshot_cap: int = 6
    rolling_hour_cap: int = 2400
    denied: frozenset[str] = field(default_factory=frozenset)
    coarsened: frozenset[str] = field(default_factory=frozenset)


class Ledger:
    """SQLite belongs to one enrolled organization; no network I/O occurs inside a transaction."""
    def __init__(self, path: Path, policy: Policy | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = policy or Policy()
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, signal TEXT NOT NULL, values_json TEXT NOT NULL,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS releases (
                    snapshot TEXT NOT NULL, recipient TEXT NOT NULL, entry TEXT NOT NULL,
                    payload TEXT NOT NULL, cost INTEGER NOT NULL CHECK(cost >= 0),
                    created REAL NOT NULL, PRIMARY KEY(snapshot,recipient,entry)
                );
                CREATE INDEX IF NOT EXISTS release_time ON releases(recipient,created);
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE TABLE IF NOT EXISTS gaps (
                    reason TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0
                );
            """)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _fits(self, db, snapshot: str, cost: int) -> bool:
        used = db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM releases WHERE snapshot=? AND recipient='coordinator'",
            (snapshot,),
        ).fetchone()[0]
        rolling = db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM releases WHERE recipient='coordinator' AND created>=?",
            (utcnow().timestamp() - 3600,),
        ).fetchone()[0]
        return used + cost <= self.policy.snapshot_cap and rolling + cost <= self.policy.rolling_hour_cap

    def queue_signal(self, signal: SignalIn, values: dict[str, str]) -> bool:
        """Persist approved initial disclosure and its charge before any bytes can leave."""
        if any(k not in CATALOGUE or v not in CATALOGUE[k]["values"] for k, v in values.items()):
            raise ValueError("invalid_private_catalogue_snapshot")
        payload = signal.model_dump_json()
        snapshot = str(signal.snapshot_id)
        with self.transaction() as db:
            prior = db.execute("SELECT signal,values_json FROM snapshots WHERE id=?", (snapshot,)).fetchone()
            if prior:
                if prior["signal"] != payload or json.loads(prior["values_json"]) != values:
                    raise ValueError("snapshot_identity_conflict")
                return True
            count = db.execute("SELECT COUNT(*) FROM outbox WHERE state='pending'").fetchone()[0]
            reason = "outbox_capacity" if count >= 1000 else None
            if not self._fits(db, snapshot, 1):
                reason = "initial_release_budget"
            if reason:
                db.execute(
                    "INSERT INTO gaps(reason,count) VALUES (?,1) ON CONFLICT(reason) DO UPDATE SET count=count+1",
                    (reason,),
                )
                return False
            now = utcnow().timestamp()
            db.execute("INSERT INTO snapshots VALUES (?,?,?,?)", (snapshot, payload, json.dumps(values), now))
            db.execute("INSERT INTO releases VALUES (?,?,?,?,?,?)",
                       (snapshot, "coordinator", "_initial", payload, 1, now))
            db.execute("INSERT INTO outbox(id,payload) VALUES (?,?)", (str(signal.signal_id), payload))
        return True

    def respond(self, request: dict) -> EvidenceResponse:
        """Recheck current policy, then reuse or atomically commit the exact released representation."""
        required = {"schema_version", "request_id", "snapshot_id", "entry", "recipient", "deadline"}
        if set(request) != required or request["schema_version"] != 1:
            raise ValueError("invalid_request_contract")
        entry, snapshot = request["entry"], request["snapshot_id"]
        if entry not in CATALOGUE or request["recipient"] != "coordinator":
            raise ValueError("unauthorized_catalogue_request")
        deadline = datetime.fromisoformat(request["deadline"])
        if deadline.tzinfo is None:
            raise ValueError("request_timezone_required")

        def deny(reason):
            return EvidenceResponse(
                request_id=request["request_id"], snapshot_id=snapshot, entry=entry,
                status="denied", reason=reason, cost=0, policy_version=self.policy.version,
            )

        with self.transaction() as db:
            if aware(deadline) <= utcnow():
                return deny("expired")
            if entry in self.policy.denied:
                return deny("policy")
            row = db.execute("SELECT * FROM snapshots WHERE id=?", (snapshot,)).fetchone()
            if not row:
                return deny("missing")
            if row["created"] < utcnow().timestamp() - 86400:
                return deny("expired")
            prior = db.execute(
                "SELECT payload FROM releases WHERE snapshot=? AND recipient=? AND entry=?",
                (snapshot, request["recipient"], entry),
            ).fetchone()
            if prior:
                response = EvidenceResponse.model_validate_json(prior["payload"])
                # A policy tightening may deny reuse; an earlier fine response is never replayed as coarse.
                if entry in self.policy.coarsened and response.status != "coarsened":
                    return deny("policy")
                return response.model_copy(update={"request_id": UUID(request["request_id"])})
            values = json.loads(row["values_json"])
            if entry not in values:
                return deny("missing")
            coarse = entry in self.policy.coarsened
            cost = 0 if coarse else CATALOGUE[entry]["cost"]
            if not self._fits(db, snapshot, cost):
                return deny("budget")
            response = EvidenceResponse(
                request_id=request["request_id"], snapshot_id=snapshot, entry=entry,
                status="coarsened" if coarse else "approved", value="unknown" if coarse else values[entry],
                evidence_id=uuid4(), policy_version=self.policy.version, cost=cost,
            )
            db.execute("INSERT INTO releases VALUES (?,?,?,?,?,?)", (
                snapshot, request["recipient"], entry, response.model_dump_json(), cost, utcnow().timestamp(),
            ))
            return response

    def pending(self) -> list[dict]:
        with self.transaction() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM outbox WHERE state='pending' AND next_attempt<=? ORDER BY rowid LIMIT 32",
                (utcnow().timestamp(),),
            )]

    def finish(self, signal_id: str, accepted: bool, permanent: bool = False) -> None:
        with self.transaction() as db:
            if accepted or permanent:
                state = "accepted" if accepted else "rejected"
                db.execute("UPDATE outbox SET state=? WHERE id=?", (state, signal_id))
                if permanent:
                    db.execute("INSERT INTO gaps VALUES ('permanent_rejection',1) "
                               "ON CONFLICT(reason) DO UPDATE SET count=count+1")
            else:
                row = db.execute("SELECT attempts FROM outbox WHERE id=?", (signal_id,)).fetchone()
                delay = min(60, 2 ** min(row["attempts"], 6))
                # Stable per-ID jitter avoids synchronization without changing experiment reproducibility.
                jitter = int(signal_id.replace("-", "")[-4:], 16) / 65535
                db.execute("UPDATE outbox SET attempts=attempts+1,next_attempt=? WHERE id=?",
                           (utcnow().timestamp() + delay + jitter, signal_id))

    def stats(self) -> dict:
        with self.transaction() as db:
            return {
                "pending": db.execute("SELECT COUNT(*) FROM outbox WHERE state='pending'").fetchone()[0],
                "released_units": db.execute("SELECT COALESCE(SUM(cost),0) FROM releases").fetchone()[0],
                "gaps": {r["reason"]: r["count"] for r in db.execute("SELECT * FROM gaps")},
            }
