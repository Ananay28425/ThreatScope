"""
Local Anomaly Detector — runs entirely within the node boundary.

Uses a two-layer approach:
  1. Rule-based fast path (flags configured patterns immediately)
  2. Isolation Forest (unsupervised ML for deviations from its local baseline)

The Isolation Forest is trained on local "normal" baseline data collected
during the first N windows after startup. This is the only ML training in
the system — it happens locally, per-node, with private data.
Nothing from the training data is ever shared externally.

Output:
  anomaly_score ∈ [0.0, 1.0]   (0 = normal, 1 = highly anomalous)
  fingerprint: str | None       (attack pattern label if detected by rules)
  model_readiness: float             (0.0–1.0, higher when more data is available)
"""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from node_simulator.feature_extractor import FeatureVector

# ── Attack fingerprint constants ──────────────────────────────────────────────

FP_AUTH_FAIL_BURST = "AUTH_FAIL_BURST"
FP_TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
FP_PORT_SCAN_LIKE = "PORT_SCAN_LIKE"
FP_HIGH_ERROR_RATE = "HIGH_ERROR_RATE"


@dataclass
class DetectionResult:
    anomaly_score: float     # 0.0 – 1.0
    fingerprint: str | None  # attack pattern or None
    model_readiness: float        # 0.0 – 1.0 based on model warmup state
    is_anomalous: bool       # convenience flag (score ≥ threshold)
    rule_triggered: bool     # True if rule-based detection fired


class LocalDetector:
    """
    Stateful per-node anomaly detector.

    Lifecycle:
      WARMUP → collect baseline_size windows of normal data → FIT → ACTIVE

    In WARMUP mode, only rule-based detection runs.
    In ACTIVE mode, both rule-based and Isolation Forest scores are blended.
    """

    SCORE_THRESHOLD = 0.75    # score above this = anomalous
    BASELINE_SIZE = 50        # number of windows to collect before fitting the model
    CONTAMINATION = 0.05      # expected fraction of anomalies in training data

    def __init__(self) -> None:
        self._model = IsolationForest(
            n_estimators=100,
            contamination=self.CONTAMINATION,
            random_state=42,
            n_jobs=1,
        )
        self._baseline: list[list[float]] = []
        self._fitted = False

    @property
    def model_readiness(self) -> float:
        """Readiness tracks training progress; it is not calibrated detection confidence."""
        if self._fitted:
            return 1.0
        return min(len(self._baseline) / self.BASELINE_SIZE, 0.99)

    def _rule_based_score(self, fv: FeatureVector) -> tuple[float, str | None]:
        """
        Fast rule-based detection. Returns (score, fingerprint | None).
        Rules flag candidate patterns; benign outages can satisfy the same conditions.
        """
        # Distributed brute force / credential stuffing
        if fv.failed_login_rate > 0.5 and fv.request_rate > 100:
            return 0.92, FP_AUTH_FAIL_BURST

        # DDoS / traffic flood
        if fv.request_rate > 500:
            return 0.88, FP_TRAFFIC_SPIKE

        # High IP diversity + low unique endpoints (port scan pattern)
        if fv.unique_ip_count > 400 and fv.ip_entropy > 4.5:
            return 0.82, FP_PORT_SCAN_LIKE

        # Application layer errors (potential exploit attempt)
        if fv.error_rate_5xx > 0.3:
            return 0.78, FP_HIGH_ERROR_RATE

        return 0.0, None

    def _ml_score(self, fv: FeatureVector) -> float:
        """
        Isolation Forest anomaly score, normalized to [0, 1].
        sklearn's decision_function returns negative scores for anomalies,
        so we flip and normalize.
        """
        if not self._fitted:
            return 0.0
        raw = self._model.decision_function([fv.to_array()])[0]
        # decision_function: more negative = more anomalous
        # Map to [0, 1]: typical range is roughly [-0.5, 0.5]
        normalized = max(0.0, min(1.0, (0.5 - raw)))
        return normalized

    def detect(self, fv: FeatureVector) -> DetectionResult:
        """
        Main detection entry point. Called once per feature window.
        """
        rule_score, fingerprint = self._rule_based_score(fv)
        rule_triggered = rule_score > 0.0

        # Warm up only on windows not flagged by the local rule layer.
        if not self._fitted and not rule_triggered:
            self._baseline.append(fv.to_array())
            if len(self._baseline) >= self.BASELINE_SIZE:
                X = np.array(self._baseline)
                self._model.fit(X)
                self._fitted = True

        ml_score = self._ml_score(fv)

        if rule_triggered:
            # An unfitted model must not suppress an already triggered rule.
            blended = max(rule_score, ml_score)
        else:
            blended = ml_score

        final_score = min(1.0, blended)

        return DetectionResult(
            anomaly_score=round(final_score, 4),
            fingerprint=fingerprint,
            model_readiness=self.model_readiness,
            is_anomalous=final_score >= self.SCORE_THRESHOLD,
            rule_triggered=rule_triggered,
        )
