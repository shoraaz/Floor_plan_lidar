"""Door-width repeatability between two LiDAR captures of the same flat (registered with bench.repeat)."""
import sys, json
from pathlib import Path
import numpy as np
from roomscan.bench.repeat import aligned_band, register, _apply
ca, cb, pa, pb = sys.argv[1:5]
M, _ = register(aligned_band(Path(ca)), aligned_band(Path(cb)))
def doors(plan, T=None):
    out = []
    for r in plan["rooms"]:
        for o in r["openings"]:
            w = r["walls"][o["wall_index"]]
            s, e = np.array(w["start"]), np.array(w["end"]); d = (e - s) / max(np.linalg.norm(e - s), 1e-9)
            c = s + d * (o["offset_m"]["value"] + o["width_m"]["value"] / 2)
            if T is not None: c = _apply(T, [c])[0]
            out.append((c, o["width_m"]["value"], r["room_id"]))
    return out
A = doors(json.loads(Path(pa).read_text())); B = doors(json.loads(Path(pb).read_text()), M)
seen, rows = set(), []
for c, w, rid in A:
    key = tuple(np.round(c, 1))
    if key in seen: continue
    seen.add(key)
    best = min(B, key=lambda t: np.linalg.norm(t[0] - c)) if B else None
    if best is not None and np.linalg.norm(best[0] - c) < 0.5:
        rows.append((rid, w, best[1], abs(w - best[1])))
    else:
        rows.append((rid, w, None, None))
for r in rows:
    print(f"{r[0]:7s} A={r[1]:.3f}  B={'-' if r[2] is None else f'{r[2]:.3f}'}  diff={'-' if r[3] is None else f'{r[3]*100:.1f} cm'}")
m = [r[3] for r in rows if r[3] is not None]
print(f"matched {len(m)}/{len(rows)} doors; within 2 cm: {sum(x <= 0.02 for x in m)}/{len(m)}")
