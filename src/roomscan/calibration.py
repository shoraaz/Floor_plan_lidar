"""Split-conformal calibration of intervals, fit per (tier, measurement kind)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

# Fallback relative half-widths before any benchmark residuals exist.
# Deliberately conservative: better wide-and-honest than confident garbage.
DEFAULT_REL = {
    "lidar": {"wall": 0.01, "ceiling": 0.008, "opening": 0.03, "area": 0.02},
    "video": {"wall": 0.04, "ceiling": 0.04, "opening": 0.08, "area": 0.06},
    "photo": {"wall": 0.10, "ceiling": 0.06, "opening": 0.15, "area": 0.14},
}


def conformal_quantile(rel_residuals: np.ndarray, level: float = 0.90) -> float:
    """Finite-sample-corrected quantile of |pred - truth| / truth."""
    r = np.sort(np.abs(np.asarray(rel_residuals, dtype=float)))
    n = len(r)
    if n == 0:
        raise ValueError("no residuals")
    k = int(np.ceil((n + 1) * level))
    return float(r[min(k, n) - 1])


def fit(residuals: dict[str, dict[str, list[float]]], level: float = 0.90) -> dict:
    """residuals[tier][kind] = list of relative errors from the benchmark."""
    out: dict = {}
    for tier, kinds in residuals.items():
        out[tier] = {}
        for kind, r in kinds.items():
            out[tier][kind] = conformal_quantile(np.array(r), level) if len(r) >= 5 else DEFAULT_REL[tier][kind]
    return out


def load(path: str | Path = "benchmark/calibration.json") -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else DEFAULT_REL


def inflate(rel: float, quality: float) -> float:
    """quality in (0,1]; thin or degraded input widens the interval instead of lying."""
    return rel / max(quality, 0.15)


def coverage(pred, lo, hi, truth) -> float:
    pred, lo, hi, truth = map(np.asarray, (pred, lo, hi, truth))
    return float(np.mean((truth >= lo) & (truth <= hi)))
