"""Build the single submission PDF for the Google Form: deliverables index + gate summary + technical report.
uv run --with markdown python scripts/build_submission_pdf.py   -> docs/roomscan_submission.pdf
Renders Markdown -> HTML (python-markdown) -> PDF with headless Microsoft Edge (installed on Windows).
"""
import re, subprocess, sys
from pathlib import Path
import markdown

REPO = "https://github.com/shoraaz/Floor_plan_lidar"
root = Path(__file__).resolve().parents[1]
report = (root / "docs/REPORT.md").read_text(encoding="utf-8")
final = (root / "benchmark/results/FINAL_RESULTS.md").read_text(encoding="utf-8")
gate = final[final.index("## Gate table"):final.index("## Tier agreement")] if "## Tier agreement" in final else final

index = f"""
# roomscan: submission summary

**Repository:** [{REPO}]({REPO}) - one command per capture: `uv run roomscan run <capture> --out <dir>`

## Deliverables

| # | Deliverable | Location in repo | Status |
|---|---|---|---|
| 1 | Compliance matrix | `docs/COMPLIANCE_MATRIX.yaml` | done (15 done / 6 partial / 4 not done, each with reason) |
| 2 | Capture route + device matrix | `docs/CAPTURE_PROTOCOL.md` (Route 2, stock tools), `docs/DEVICE_MATRIX.md` | done |
| 3 | Repo, README, one command per capture | `README.md`, `src/roomscan/cli.py` | done; uv-based install |
| 4 | Reproduction bundle | `reproduction/run_final.ps1`, `get_arkitscenes.ps1`, `fixloop.ps1`; deterministic caches; live path runs | done (Windows PowerShell scripts) |
| 5 | Benchmark report | `benchmark/results/FINAL_RESULTS.md` (gates, repeatability, tier tables, timing) | partial: no head-to-head (no device) |
| 6 | Fix loop bundle | `fixloop/` (declaration, before/after, diff, post-mortem), tags `fixloop-before` / `fixloop-after` | done (gate not passed, honest post-mortem) |
| 7 | Technical report (6 pages) | `docs/REPORT.md` (reproduced below) | done |
| 8 | Raw benchmark data | own: ARKitScenes venue 470350 (fetched by script, licence prevents re-hosting); sample: organisers' captures | partial: no app exports |

**Data note.** No LiDAR phone or room was available, so the own benchmark uses Apple ARKitScenes (CC BY-NC-SA 4.0):
three iPad-LiDAR captures of one venue with Faro laser-scanner ground truth, converted to the Stray Scanner format
so the unchanged pipeline runs on them. All numbers are also reported on the organisers' sample data.

**Headline (honest).** LiDAR tier: metric point cloud (0.8% scale vs laser); wall lengths median 5.0 cm on walls with
unambiguous laser ground truth, 17.8 cm over all scored walls; no centimetre gate passes. Video and photo tiers run end
to end but fail their gates and flag themselves UNRELIABLE rather than emit confident garbage.

{gate}
"""

css = """
<style>
 @page { size: A4; margin: 14mm 13mm; }
 body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.6pt; line-height: 1.38; color: #1d1d1f; }
 h1 { font-size: 17pt; margin: 0 0 6px; } h2 { font-size: 12.5pt; margin: 14px 0 5px; border-bottom: 1px solid #ddd; }
 table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 8.4pt; }
 th, td { border: 1px solid #cfcfcf; padding: 3px 5px; vertical-align: top; text-align: left; }
 th { background: #f2f2f2; } code { font-family: Consolas, monospace; font-size: 8.4pt; background: #f5f5f5; padding: 0 2px; }
 pre { background: #f6f6f6; padding: 6px 8px; font-size: 7.8pt; white-space: pre-wrap; border-radius: 3px; }
 .pb { page-break-before: always; } a { color: #1a4f8b; }
</style>
"""
md = lambda t: markdown.markdown(t, extensions=["tables", "fenced_code"])
html = f"<html><head><meta charset='utf-8'>{css}</head><body>{md(index)}<div class='pb'></div>{md(report)}</body></html>"
out_html = root / "docs/_submission.html"; out_pdf = root / "docs/roomscan_submission.pdf"
out_html.write_text(html, encoding="utf-8")
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={out_pdf}", out_html.as_uri()], check=True, timeout=120)
out_html.unlink()
print(out_pdf, round(out_pdf.stat().st_size / 1024), "KB")
