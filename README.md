# roomscan

Phone capture -> dimensioned, stitched whole-property floor plan + damage report.
Three input tiers (photos, video, LiDAR), one output contract, calibrated intervals everywhere.
Fully free stack. Everything runs locally.

## Quickstart (target: < 15 min on a clean machine)

```powershell
# Use Python 3.11 or 3.12 (Open3D / PyTorch wheels lag behind 3.14)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python scripts/fetch_weights.py          # pretrained weights, fetched not committed

# One command per capture
roomscan run <capture_path> --out out/<name>
```

`<capture_path>` is auto-detected:

| Input | Detected as |
|---|---|
| Folder with `rgb.mp4`, `depth/`, `odometry.csv`, `camera_matrix.csv` (Stray Scanner export) | `lidar` |
| A single video file (`.mov`/`.mp4`) | `video` |
| Folder of subfolders, one per room, each containing 2-8 stills | `photo` |

Override with `--tier lidar|video|photo`.

## Outputs (per capture)

- `plan.json` - validates against `schema/property_plan.schema.json`
- `plan.svg` - rendered whole-property floor plan
- `report.md` - human-readable summary incl. flags and warnings

## Layout

```
src/roomscan/
  models.py        Interval + plan dataclasses (every number carries an interval)
  calibration.py   split-conformal intervals, coverage checks
  cli.py           `roomscan run`
  tiers/           lidar.py, video.py, photo.py -> all emit RoomGeometry
  geometry/        planes.py, drift.py, stitch.py
  damage.py        damage regions + metric extent
  rules.py         concealed-damage rules + scope line items
  render.py        SVG plan
docs/              capture protocol, device matrix, compliance matrix, roadmap
benchmark/         ground truth, raw data, results
fixloop/           fix declaration, before/after bundle
```

See `docs/PLAN.md` for the build order and `docs/COMPLIANCE_MATRIX.yaml` for requirement tracking.
