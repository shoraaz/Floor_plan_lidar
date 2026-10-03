"""Build the benchmark report table for the sample data: every tier vs the LiDAR plan, plus timing.
uv run python scripts/bench_table.py  -> benchmark/results/benchmark_sample.md (+ .json)
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tier_compare import main as compare

B = Path("out/bench")
caps = ["single_room", "with_ceiling", "floor_only"]
timing = {}
if (B / "timing.csv").exists():
    for t, k, s in csv.reader(open(B / "timing.csv")):
        try:
            timing[(t, k)] = float(s)
        except ValueError:
            pass
rows, details = [], {}
for k in caps:
    ref = B / "lidar" / k / "plan.json"
    if not ref.exists():
        continue
    lp = json.loads(ref.read_text())
    ceil = [r["ceiling_height_m"]["value"] for r in lp["rooms"] if r["ceiling_height_m"]]
    rows.append({"tier": "lidar", "capture": k, "rooms": len(lp["rooms"]), "footprint_m2": round(lp["footprint_m2"]["value"], 2),
                 "footprint_err_pct": 0.0, "matched_dims": "ref", "median_abs_err_pct": "ref", "within_3pct": "ref",
                 "within_8pct": "ref", "interval_coverage": "ref",
                 "ceiling_m": f"{min(ceil):.3f}-{max(ceil):.3f}" if ceil else "not observed",
                 "seconds": timing.get(("lidar", k))})
    for t in ["video", "photo"]:
        p = B / t / k / "plan.json"
        if not p.exists():
            continue
        s, det = compare(str(ref), str(p))
        tp = json.loads(p.read_text())
        ceil = [r["ceiling_height_m"]["value"] for r in tp["rooms"] if r["ceiling_height_m"]]
        rows.append({"tier": t, "capture": k, "rooms": s["rooms_tier"], "footprint_m2": s["footprint_tier_m2"],
                     "footprint_err_pct": s["footprint_err_pct"], "matched_dims": s["matched_dims"],
                     "median_abs_err_pct": s["median_abs_err_pct"], "within_3pct": s["within_3pct"],
                     "within_8pct": s["within_8pct"], "interval_coverage": s["interval_coverage"],
                     "ceiling_m": f"{min(ceil):.3f}-{max(ceil):.3f}" if ceil else "not observed",
                     "seconds": timing.get((t, k))})
        details[f"{t}/{k}"] = det
cols = list(rows[0].keys())
md = ["# Sample-data benchmark (reference = LiDAR plan; no tape ground truth supplied with sample data)", "",
      "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
out = Path("benchmark/results"); out.mkdir(parents=True, exist_ok=True)
(out / "benchmark_sample.md").write_text("\n".join(md))
(out / "benchmark_sample.json").write_text(json.dumps({"rows": rows, "details": details}, indent=1))
print("\n".join(md))
