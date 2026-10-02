"""Overlay registered room polygons of two captures (A solid, B dashed) for repeatability diagnosis.
uv run python scripts/repeat_overlay.py <capA> <capB> <planA> <planB> <out.png>
"""
import sys, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from roomscan.bench.repeat import aligned_band, register, _apply

ca, cb, pa, pb, out = sys.argv[1:6]
A, B = aligned_band(Path(ca)), aligned_band(Path(cb))
M, diag = register(A, B)
PA, PB = json.loads(Path(pa).read_text()), json.loads(Path(pb).read_text())
fig, ax = plt.subplots(figsize=(14, 14))
ax.scatter(A[::20, 0], A[::20, 1], s=0.2, c="0.7")
for r in PA["rooms"]:
    p = np.array([w["start"] for w in r["walls"]] + [r["walls"][0]["start"]])
    ax.plot(p[:, 0], p[:, 1], "b-", lw=2)
    ax.text(p[:-1, 0].mean(), p[:-1, 1].mean(), "A:" + r["room_id"], color="b", fontsize=10)
    for w in r["walls"]:
        m = (np.array(w["start"]) + np.array(w["end"])) / 2
        ax.text(m[0], m[1], f"{w['length_m']['value']:.2f}", color="b", fontsize=7)
for r in PB["rooms"]:
    p = _apply(M, [w["start"] for w in r["walls"]] + [r["walls"][0]["start"]])
    ax.plot(p[:, 0], p[:, 1], "r--", lw=1.5)
    ax.text(p[:-1, 0].mean(), p[:-1, 1].mean() - 0.3, "B:" + r["room_id"], color="r", fontsize=10)
    for w in r["walls"]:
        m = _apply(M, [(np.array(w["start"]) + np.array(w["end"])) / 2])[0]
        ax.text(m[0], m[1] - 0.12, f"{w['length_m']['value']:.2f}", color="r", fontsize=7)
ax.set_aspect("equal"); plt.tight_layout(); plt.savefig(out, dpi=75)
print(diag)
