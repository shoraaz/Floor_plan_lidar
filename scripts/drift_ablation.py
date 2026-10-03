"""Drift ablation (PDF row "drift accountability"): stitched footprint and repeatability with loop closure ON vs OFF.
uv run python scripts/drift_ablation.py  -> benchmark/results/drift_ablation.md
"""
import json
from pathlib import Path
from roomscan.tiers import lidar
from roomscan.geometry.stitch import finalize
from roomscan.bench.repeat import aligned_band, register, compare

root = Path("..")
caps = {"with_ceiling": root / "single_scan_with_ceiling/c7d28f72c6",
        "floor_only": root / "single_scan_floor_only/1a8384c3f6",
        "single_room": root / "single_room/c00a170fe1"}
plans, rows = {}, []
for mode in (False, True):
    for k, c in caps.items():
        p = finalize(lidar.run(c, drift_correction=mode))
        d = json.loads(json.dumps(p.to_dict()))
        plans[(k, mode)] = d
        iq = d["input_quality"]
        rows.append({"capture": k, "drift": "ON" if mode else "OFF", "rooms": len(d["rooms"]),
                     "footprint_m2": round(d["footprint_m2"]["value"], 2), "floor_spread_cm": round(iq["floor_spread_m"] * 100, 2),
                     "loop": iq.get("drift_loop", "-"), "loops_acc": f"{iq.get('drift_loops_accepted', 0)}/{iq.get('drift_loops_tested', 0)}" if mode else "-",
                     "max_shift_cm": iq.get("drift_max_node_shift_cm", 0) if mode else "-"})
rep = []
for mode in (False, True):
    A = aligned_band(caps["with_ceiling"], drift=mode); B = aligned_band(caps["floor_only"], drift=mode)
    M, diag = register(A, B)
    rr, walls = compare(plans[("with_ceiling", mode)], plans[("floor_only", mode)], M)
    rep.append({"drift": "ON" if mode else "OFF", "icp_rmse_cm": round(diag["icp_rmse_m"] * 100, 2),
                "walls_pass": f"{sum(w['pass'] for w in walls)}/{len(walls)}",
                "footprint_diff_pct": round(abs(plans[("with_ceiling", mode)]["footprint_m2"]["value"] -
                                                plans[("floor_only", mode)]["footprint_m2"]["value"]) /
                                            plans[("with_ceiling", mode)]["footprint_m2"]["value"] * 100, 2)})
cols = list(rows[0]); cols2 = list(rep[0])
md = ["# Drift ablation: start-end loop closure ON vs OFF (LiDAR tier, sample data)", "",
      "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
md += ["", "## Repeatability with_ceiling vs floor_only", "", "| " + " | ".join(cols2) + " |", "|" + "---|" * len(cols2)]
md += ["| " + " | ".join(str(r[c]) for c in cols2) + " |" for r in rep]
Path("benchmark/results/drift_ablation.md").write_text("\n".join(md))
print("\n".join(md))
