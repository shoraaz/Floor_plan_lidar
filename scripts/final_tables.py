"""Collect every final number into benchmark/results/FINAL_RESULTS.md (gate table first).
uv run python scripts/final_tables.py
"""
import json, csv, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from tier_compare import main as compare

O = Path("out/final"); R = Path("benchmark/results")
md = ["# Final results", "",
      "Sample data = organisers' 3 Stray Scanner captures (no ground truth supplied). Own benchmark = ARKitScenes venue",
      "470350 (Apple, CC BY-NC-SA 4.0): 3 iPad-LiDAR captures of the same space, Faro laser-scanner ground truth,",
      "converted to Stray format (`scripts/arkitscenes_to_stray.py`). Substitution disclosed: no own phone/room was",
      "available. Regenerate: `reproduction/get_arkitscenes.ps1`, `reproduction/run_final.ps1`, this script.", ""]

# ---- laser GT (own, LiDAR tier) ----
gt = {}
for p in sorted((R / "own").glob("laser_gt_ark*.json")):
    gt[p.stem.replace("laser_gt_", "")] = json.loads(p.read_text())
walls = [w for g in gt.values() for w in g["walls"] if w.get("gt_m")]
werr = np.array([abs(w["err_cm"]) for w in walls]) if walls else np.array([])
cerr = np.array([abs(w["err_cm"]) for w in walls if w.get("clean_gt")])
doors = [d for g in gt.values() for d in g["doors"] if d.get("gt_m")]
derr = np.array([abs(d["err_cm"]) for d in doors]) if doors else np.array([])
ceils = [c for g in gt.values() for c in g["ceilings"]]
ceil_scored = [c for c in ceils if c.get("err_cm") is not None]

def rep(path):
    if not Path(path).exists():
        return None
    t = Path(path).read_text()
    m = re.search(r"(\d+)/(\d+) walls pass", t); f = re.search(r"diff ([\d.]+)%\)", t)
    return (int(m.group(1)), int(m.group(2)), float(f.group(1)) if f else None) if m else None
ra, rc, rs = rep(R / "own/repeatability_ab.md"), rep(R / "own/repeatability_ac.md"), rep(R / "repeatability_sample.md")

def drift_row():
    p = R / "drift_ablation_strict05.log"
    return "pose graph + ICP-verified revisit loops, ON by default; ablation in `drift_ablation_*.log` (no measured benefit on sample data)" if p.exists() else "-"

gates = [
    ("Wall lengths (LiDAR) vs laser", "<= 1 cm or 0.5% (repeat gate used as accuracy proxy)",
     (f"{len(walls)} walls scored; median |err| {np.median(werr):.1f} cm; within 2 cm: {int((werr <= 2).sum())}. "
      f"Clean-GT subset (one sharp laser surface on both bounding walls): {len(cerr)} walls, median {np.median(cerr):.1f} cm, within 2 cm: {int((cerr <= 2).sum())}")
     if len(werr) and len(cerr) else (f"{len(walls)} walls scored; median |err| {np.median(werr):.1f} cm" if len(werr) else "not scored"), "FAIL"),
    ("Opening widths", "<= 2 cm on >= 85%, missed/phantom = miss",
     f"{len(doors)} doors scored; median |err| {np.median(derr):.1f} cm; within 2 cm: {int((derr <= 2).sum())}/{len(doors)}" if len(derr) else "no door scorable", "FAIL"),
    ("Ceiling height", "<= 1.5 cm; spread <= 1 cm",
     f"laser GT {', '.join(f'{c['gt_m']:.3f}' for c in ceils[:4])} m; ours reported in {len(ceil_scored)} rooms (ceiling not observed by the iPad sweeps -> withheld)", "NOT SCORED"),
    ("Repeatability (LiDAR)", "<= 1 cm or 0.5% per wall",
     f"own a/b {ra[0]}/{ra[1]}, own a/c {rc[0]}/{rc[1]}, sample {rs[0]}/{rs[1]}" if ra and rc and rs else "see files", "FAIL"),
    ("Drift accountability", "method + on/off footprint ablation", drift_row(), "PARTIAL"),
    ("Photo-tier whole-property stitch", "one stitched plan, correct adjacency, footprint +/-8%", "see tier table: collapses / flagged UNRELIABLE", "FAIL"),
    ("Video tier", "walls +/-3%", "see tier table", "FAIL"),
    ("Calibration / no confident garbage", "intervals honest at every tier",
     f"LiDAR interval coverage vs laser: {np.mean([w['covered'] for w in walls]):.0%}" if walls else "-", "PARTIAL"),
]
md += ["## Gate table", "", "| gate | target | measured | status |", "|---|---|---|---|"]
md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in gates]

md += ["", "## Own benchmark: LiDAR tier vs Faro laser ground truth", "", "| capture | walls scored | median abs err (cm) | within 2 cm | within 5 cm | doors scored |", "|---|---|---|---|---|---|"]
for k, g in gt.items():
    s = g["summary"]; nd = sum(1 for d in g["doors"] if d.get("gt_m"))
    md.append(f"| {k} | {s['walls_scored']}/{s['walls_total']} | {s['median_abs_err_cm']} | {s['within_2cm']} | {s['within_5cm']} | {nd} |")

md += ["", "## Tier agreement vs LiDAR plan (same capture)", "", "| set | tier | capture | rooms | footprint m2 | footprint err | median dim err | interval coverage | reliable |", "|---|---|---|---|---|---|---|---|---|"]
for st in ("sample", "own"):
    for tier in ("video", "photo"):
        for p in sorted((O / st / tier).glob("*/plan.json")) if (O / st / tier).exists() else []:
            ref = O / st / "lidar" / p.parent.name / "plan.json"
            if not ref.exists():
                continue
            tp = json.loads(p.read_text())
            if not tp["rooms"]:
                md.append(f"| {st} | {tier} | {p.parent.name} | 0 rooms (empty plan, flagged) | 0 | -100% | - | - | False |"); continue
            s, _ = compare(str(ref), str(p))
            md.append(f"| {st} | {tier} | {p.parent.name} | {s['rooms_tier']} vs {s['rooms_lidar']} | {s['footprint_tier_m2']} | "
                      f"{s['footprint_err_pct']}% | {s['median_abs_err_pct']}% | {s['interval_coverage']} | {tp['input_quality'].get('reliable')} |")

md += ["", "## Timing (seconds, this laptop: RTX 5050 8 GB; video/photo include DA3 inference, cold where not cached)", "", "| set | tier | capture | s |", "|---|---|---|---|"]
if (O / "timing.csv").exists():
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in csv.reader(open(O / "timing.csv"))]
(R / "FINAL_RESULTS.md").write_text("\n".join(md))
print("\n".join(md))
