# Floor_plan_lidar (roomscan)

Phone capture -> dimensioned, stitched floor plan with an interval on every number.
Three input tiers (LiDAR, video, photos) share one geometry backend and one output contract
(`schema/property_plan.schema.json`). Everything runs locally; no external services.

## Quickstart (clean Windows/Linux machine, ~10 min + model download)

```bash
# 1. Python 3.12 + uv (https://docs.astral.sh/uv/)
uv sync                                   # installs deps incl. CUDA 12.8 PyTorch (RTX 50-series OK)
# 2. One command per capture (tier auto-detected)
uv run roomscan run <capture> --out out/<name>
```

| `<capture>` | Detected tier | What is used |
|---|---|---|
| Stray Scanner folder (`rgb.mp4`, `depth/`, `confidence/`, `odometry.csv`, `camera_matrix.csv`) | `lidar` | depth + ARKit poses + intrinsics |
| A video file (`.mp4`/`.mov`), or a Stray folder with `--tier video` | `video` | the RGB clip only |
| A folder of per-room photo folders | `photo` | the photos only (no depth, poses, intrinsics) |

Outputs in `--out`: `plan.json` (schema-validated before writing), `plan.svg` (rendered plan).
First run of the video/photo tiers downloads two Apache-2.0 models from Hugging Face
(`depth-anything/DA3-LARGE-1.1`, `depth-anything/DA3METRIC-LARGE`, ~2.8 GB). A CUDA GPU is strongly
recommended for video/photo (8 GB is enough); the LiDAR tier is CPU-only.

## Reproduce every reported number

```powershell
.\reproduction\run_all.ps1                     # all tiers on all sample captures -> out/bench/, timing.csv
.\reproduction\fixloop.ps1 -Label after        # fix-loop run (checkout tag fixloop-before / fixloop-after)
uv run python scripts/make_photo_folders.py ...   # rebuild photo-tier inputs from the sample clips
uv run python scripts/tier_compare.py <lidar_plan> <tier_plan>
uv run roomscan repeat <capA> <capB> --plan-a ... --plan-b ...
```
Intermediate results are cached under `cache/` keyed by input path, so reruns are deterministic;
deleting `cache/` re-runs the live path.

## How it works (one paragraph per stage)

- **LiDAR front end** (`tiers/lidar.py`, `geometry/pointcloud.py`): back-projects confidence-filtered depth with
  ARKit poses. Stray Scanner stores poses camera->world with an OpenCV camera frame in an ARKit y-up world
  (verified: `scripts/diagnostics/test_convention.py`).
- **Video front end** (`tiers/video.py`, `geometry/da3_frontend.py`): keyframes -> Depth Anything 3 any-view model
  in overlapping 24-frame chunks (poses + depth), chained by depth ratios on shared frames, metric scale from
  DA3METRIC (units verified against LiDAR on the same frames). COLMAP SfM is kept as `frontend="colmap"`
  (registered only 13-21% of keyframes on low-texture walls).
- **Photo front end** (`tiers/photo.py`): one joint DA3 pass over all room folders puts every room in one frame
  (stitching), metric scale as above.
- **Shared backend** (`geometry/backend.py`): floor/ceiling planes -> Manhattan yaw (coarse normals + 0.02 deg
  sharpness search) -> wall map in a 0.95-1.6 m band -> doorway closure -> wall extension through unobserved
  space -> rooms = wall-enclosed regions -> rectangle-first snapping of each side to the room-side wall face ->
  per-room ceiling -> intervals (`calibration.py`) -> stitch checks (`geometry/stitch.py`) -> JSON + SVG.

## Known limits (see report)

Opening detection, damage detection, concealed-damage rules and scope items are not implemented in this
submission; the schema fields exist and are emitted empty. No ground truth was supplied with the sample data,
so accuracy is reported as cross-tier agreement against LiDAR and capture-to-capture repeatability.
