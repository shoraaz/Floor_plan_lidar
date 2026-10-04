# Floor_plan_lidar (roomscan)

Turn a phone capture of a home into a **dimensioned, stitched floor plan with an honest confidence interval on
every number**, as a single command. One geometry backend serves three input tiers:

| Tier | Input | What it uses |
|---|---|---|
| **LiDAR** | Stray Scanner export from an iPhone/iPad Pro | LiDAR depth, confidence, ARKit poses, intrinsics |
| **Video** | a handheld walkthrough clip (any iPhone 15+) | RGB frames only |
| **Photo** | 2-8 stills per room, one folder per room | RGB stills only, no depth or poses |

Output per capture: `plan.json`, validated against `schema/property_plan.schema.json` before it is written, and a
rendered `plan.svg`.

> **Status in one paragraph.** The LiDAR tier is complete and metrically sound: its point cloud matches a
> laser scan to within 0.8% in scale. Room walls are off by a median of **~5 cm where the laser ground truth is
> unambiguous** and **~18 cm over all scored walls**, mostly from walls inferred through doorways. **No
> centimetre gate of the case study is met.** The video and photo tiers run end to end but miss their gates, and
> they say so: implausible reconstructions are flagged `UNRELIABLE`, ceilings are withheld, and intervals are
> widened. Full numbers are in [`benchmark/results/FINAL_RESULTS.md`](benchmark/results/FINAL_RESULTS.md), and the
> reasoning is in [`docs/REPORT.md`](docs/REPORT.md).

---

## Contents

1. [Deliverables map](#deliverables-map)
2. [Install](#install)
3. [Run on a capture (one command)](#run-on-a-capture-one-command)
4. [Inputs](#inputs)
5. [Outputs](#outputs)
6. [How it works](#how-it-works)
7. [Results at a glance](#results-at-a-glance)
8. [Reproduce every number](#reproduce-every-number)
9. [Repository layout](#repository-layout)
10. [Models, data and licences](#models-data-and-licences)
11. [Known limitations](#known-limitations)
12. [Troubleshooting](#troubleshooting)

---

## Deliverables map

| # | Case-study deliverable | Where | Status |
|---|---|---|---|
| 1 | Compliance matrix | [`docs/COMPLIANCE_MATRIX.yaml`](docs/COMPLIANCE_MATRIX.yaml) | done (15 done / 6 partial / 4 not done, each with a reason) |
| 2 | Capture route + device matrix | [`docs/CAPTURE_PROTOCOL.md`](docs/CAPTURE_PROTOCOL.md) (Route 2, stock tools), [`docs/DEVICE_MATRIX.md`](docs/DEVICE_MATRIX.md) | done |
| 3 | Repo + README, one command per capture | this file, `roomscan run` | done |
| 4 | Reproduction bundle | [`reproduction/`](reproduction), [`scripts/`](scripts) | done (PowerShell scripts, Windows-first) |
| 5 | Benchmark report | [`benchmark/results/FINAL_RESULTS.md`](benchmark/results/FINAL_RESULTS.md) + per-test files | partial: no consumer-app head-to-head |
| 6 | Fix loop bundle | [`fixloop/`](fixloop), git tags `fixloop-before` / `fixloop-after` | done (gate not passed; honest post-mortem) |
| 7 | Technical report (6 pages) | [`docs/REPORT.md`](docs/REPORT.md); PDF with index: [`docs/roomscan_submission.pdf`](docs/roomscan_submission.pdf) | done |
| 8 | Raw benchmark data | own: ARKitScenes venue 470350 via [`reproduction/get_arkitscenes.ps1`](reproduction/get_arkitscenes.ps1); sample: organisers' captures | partial: no app exports; data fetched, not re-hosted |

---

## Install

**Requirements**
- Python 3.12 and [uv](https://docs.astral.sh/uv/). uv installs everything else from `uv.lock`.
- Windows or Linux. The pipeline is plain Python; the reproduction scripts are PowerShell.
- For the **video and photo tiers**: an NVIDIA GPU with CUDA. 8 GB of VRAM is enough (developed on an RTX 5050
  Laptop GPU). The **LiDAR tier runs on CPU only.**

```bash
git clone https://github.com/shoraaz/Floor_plan_lidar.git
cd Floor_plan_lidar
uv sync                                   # Python deps; PyTorch comes from the CUDA 12.8 index (RTX 50-series OK)
uv run python scripts/fetch_weights.py    # optional: pre-download the 2 DA3 models (~2.8 GB) before a live run
uv run roomscan --help
```

`uv sync` is the only install step. `fetch_weights.py` is only needed for the video and photo tiers, and only if
you don't want the first run to download the models.

---

## Run on a capture (one command)

```bash
uv run roomscan run <capture> --out out/<name>
```

The tier is detected automatically from the input. To force a tier, add `--tier lidar|video|photo`.

```bash
# LiDAR tier on a Stray Scanner export
uv run roomscan run path/to/stray_export --out out/flat_lidar

# Video tier from the same export: uses only its rgb.mp4, ignores depth/poses
uv run roomscan run path/to/stray_export --tier video --out out/flat_video

# Video tier from any clip
uv run roomscan run walkthrough.mov --out out/flat_video

# Photo tier: a folder that contains one sub-folder of stills per room
uv run roomscan run path/to/photo_folders --out out/flat_photo

# Drift ablation: LiDAR tier with raw ARKit poses (drift correction is ON by default)
uv run roomscan run path/to/stray_export --no-drift-correction --out out/flat_lidar_nodrift
```

The console prints one line, e.g. `[lidar] 5 rooms, footprint 42.33 m2, 9 warnings -> out/flat_lidar`.

**Repeatability of two captures of the same place** (same tier):

```bash
uv run roomscan repeat <capture_A> <capture_B> --plan-a out/A/plan.json --plan-b out/B/plan.json \
    --out benchmark/results/repeatability.md
```

This registers the two captures (4 x 90-degree rotations, FFT translation search, then ICP), matches rooms by
IoU, and writes a per-wall table against the gate of 1 cm or 0.5%.

**Typical run times** on the development laptop: LiDAR 18-32 s per capture. Video takes 6 min for a 90 s clip on
a cold run and 40-110 s with cached model outputs. Photo takes 30-130 s.

---

## Inputs

**LiDAR: Stray Scanner export** (the format of the organisers' sample data and of the walk-in test)

```
<capture>/
  rgb.mp4                 colour video (used only by the video tier)
  depth/000000.png ...    uint16 depth in millimetres, 256x192
  confidence/000000.png   0/1/2 per depth pixel (only confidence 2 is used)
  odometry.csv            timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy   (per frame)
  camera_matrix.csv       3x3 K at the 1920x1440 reference resolution
  imu.csv                 not used
```

Conventions were verified on data, not assumed (see `scripts/diagnostics/test_convention.py`):
- poses are **camera-to-world**, the camera frame is **OpenCV** (x right, y down, z forward), and the world is
  **ARKit y-up**;
- intrinsics are given for 1920x1440 and are rescaled to the depth resolution.

Pose rates below 30 Hz (e.g. converted 10 Hz data) are handled automatically.

**Video:** any `.mp4`/`.mov`/`.m4v` file, or a Stray folder with `--tier video` (then only its `rgb.mp4` is used).

**Photo:** `<folder>/<room_name>/*.jpg|png|heic|webp`, 2-8 stills per room. Rooms are stitched by one joint
reconstruction across all folders. This only works if each room's folder contains a photo of the doorway it
shares with its neighbour (see the capture protocol).

---

## Outputs

`plan.json` follows [`schema/property_plan.schema.json`](schema/property_plan.schema.json). **Every measurement is an
interval** `{value, lo, hi, unit, level}`.

```jsonc
{
  "capture_id": "ark470350_a",
  "tier": "lidar",
  "rooms": [{
    "room_id": "room1",
    "walls": [{"start": [x, z], "end": [x, z], "length_m": {"value": 6.40, "lo": 5.94, "hi": 6.86, "unit": "m", "level": 0.9}}],
    "ceiling_height_m": null,             // null = ceiling not observed: never guessed
    "floor_area_m2": {...},
    "openings": [{"kind": "door", "wall_index": 1, "offset_m": {...}, "width_m": {...}, "connects_to_room": "room2"}],
    "damage": [], "concealed_flags": [], "scope": []      // emitted empty: not implemented
  }],
  "adjacency": [["room1", "room2"]],
  "footprint_m2": {...},
  "warnings": ["room4: not enclosed by detected walls; extent from observed space only (intervals widened)"],
  "input_quality": {"frames": 898, "loop_gap_m": 0.23, "drift_loops_accepted": 2, "reliable": true, "...": "..."}
}
```

- `warnings` explains every degraded or withheld value. Check it before trusting a number.
- `input_quality.reliable = false` marks a plan whose metric scale failed a plausibility check (video/photo
  floor-to-ceiling outside 2.1-4.2 m), or a plan where no room was recovered.
- `plan.svg` draws every room with its wall lengths and interval half-widths, the floor area, the ceiling height
  (or "n/a"), and the footprint.

---

## How it works

```
LiDAR  Stray export --> pose graph drift correction (verified revisit loops) --> depth back-projection
Video  clip         --> keyframes --> Depth Anything 3 any-view, 24-frame chunks
                        --> per-chunk metric scale (DA3 Metric) --> rigid chaining --> back-projection
Photo  room folders --> one joint DA3 pass over all photos --> metric scale --> back-projection
                 |
                 v   metric, gravity-aligned point cloud + camera path + ray endpoints
SHARED BACKEND (src/roomscan/geometry/backend.py)
  1. floor / ceiling planes from height histograms (ceiling only if really observed)
  2. Manhattan yaw: coarse from wall normals, refined to 0.02 deg by wall-sharpness search
  3. wall map from a 0.95-1.6 m band (above furniture, covered by any protocol walk)
  4. doorways = 0.6-1.3 m gaps between collinear wall runs -> closed, kept as doors
  5. walls extended through UNOBSERVED space (ROSE2-style); ray-cast free space is never crossed
  6. rooms = regions enclosed by walls (not "what the camera happened to see")
  7. each side snapped to the ROOM-SIDE wall face (sub-cm median of face points); non-rectangular rooms
     get a rectilinear outline whose edges are refined the same way
  8. per-room ceiling, doors with widths from door-frame faces, adjacency from doors
  9. intervals from fitted calibration; plausibility gate; stitch checks (overlaps, footprint)
 10. plan.json (schema-validated) + plan.svg
```

Key modules:

| Module | Role |
|---|---|
| `tiers/lidar.py` | Stray loader, cached fusion, drift switch |
| `geometry/drift.py` | pose graph with ICP-verified revisit loops (Open3D) |
| `geometry/da3_frontend.py` | DA3 chunked poses, per-chunk metric anchoring, fusion |
| `tiers/video.py`, `tiers/photo.py` | video/photo front ends (COLMAP kept as a video fallback) |
| `geometry/planes.py` | floor/ceiling, Manhattan yaw (coarse + fine) |
| `geometry/rooms.py` | wall map, doorway closure, wall extension, room segmentation |
| `geometry/snap.py` | room-side face snapping (rectangle-first, rectilinear fallback) |
| `geometry/openings.py` | doors and their widths |
| `geometry/backend.py` | the shared pipeline, intervals, plausibility gate |
| `calibration.py` | interval model (fitted values in `benchmark/calibration.json`) |
| `bench/repeat.py` | capture-to-capture registration and per-wall repeatability |

Design rationale, alternatives tried and their measured effect are in [`docs/REPORT.md`](docs/REPORT.md).

---

## Results at a glance

From [`benchmark/results/FINAL_RESULTS.md`](benchmark/results/FINAL_RESULTS.md). The own benchmark is Apple
ARKitScenes venue 470350: 3 iPad-LiDAR captures with Faro laser-scanner ground truth.

| Gate (case study) | Measured | Status |
|---|---|---|
| Wall lengths, LiDAR vs laser | all 22 scored walls: median 17.8 cm; 6 walls with unambiguous laser GT: **median 5.0 cm** | FAIL |
| Opening widths <= 2 cm on 85% | 7 doors scored, median 11.5 cm | FAIL |
| Ceiling height <= 1.5 cm | not scored: the iPad sweeps barely observed ceilings, so values were withheld | not scored |
| Repeatability, 1 cm or 0.5% per wall | raw wall surfaces agree to **0.69-0.95 cm**; per-wall gate 0/8, 0/4 (own), 4/24 (sample) | FAIL |
| Drift: method + on/off ablation | pose graph + verified loops; ablation shows no benefit on these captures | partial |
| Video walls +/-3%; photo whole-property stitch | not met; plans flagged | FAIL |
| Calibration (honest intervals) | LiDAR interval contains laser truth 91% (in-sample) | partial |
| Head-to-head vs consumer app | not run: no device | not done |

**Where the LiDAR error comes from:**
- The sensor and poses are fine: 0.8% scale and 1.9 cm RMSE against the laser.
- The ~5 cm on physical walls comes from face snapping.
- The ~20 cm cases are **virtual walls**, created by doorway closure or wall extension where no physical wall
  exists, or places where the laser itself shows clutter rather than a single plane (`scripts/laser_gt.py --peaks`).

---

## Reproduce every number

The scripts expect this sibling layout. The data lives outside the repo:

```
<workspace>/
  Floor_plan_lidar/            this repo (any folder name)
  single_room/<id>/            organisers' sample captures (Stray exports)
  single_scan_with_ceiling/<id>/
  single_scan_floor_only/<id>/
  arkitscenes_data/            created by get_arkitscenes.ps1
  own_benchmark/               created by scripts/arkitscenes_to_stray.py
```

```powershell
# 1. own benchmark data: one ARKitScenes venue (3 captures + 2 laser scans, ~6.5 GB)
.\reproduction\get_arkitscenes.ps1                        # -Visit 470350 by default
uv run python scripts/arkitscenes_to_stray.py ..\arkitscenes_data\raw\Training\47330990 ..\own_benchmark\ark470350_a
uv run python scripts/arkitscenes_to_stray.py ..\arkitscenes_data\raw\Training\47330995 ..\own_benchmark\ark470350_b
uv run python scripts/arkitscenes_to_stray.py ..\arkitscenes_data\raw\Training\47330996 ..\own_benchmark\ark470350_c

# 2. every tier on every capture + laser scoring + repeatability -> out/final, benchmark/results
.\reproduction\run_final.ps1

# 3. tables
uv run python scripts/fit_calibration.py                  # interval half-widths from measured errors
uv run python scripts/final_tables.py                     # -> benchmark/results/FINAL_RESULTS.md

# 4. fix loop, before and after (each from its tag)
git checkout fixloop-before ; .\reproduction\fixloop.ps1 -Label before
git checkout fixloop-after  ; .\reproduction\fixloop.ps1 -Label after
git checkout main

# 5. drift ablation
uv run python scripts/drift_ablation.py
```

**Caching and determinism.** Fused clouds, video keyframes and DA3 outputs are cached under `cache/`, keyed by the
input path and parameters. Seeds are fixed, so reruns replay deterministically. Delete `cache/` to exercise the full
live path, which is what the walk-in test runs.

| Script | Produces |
|---|---|
| `scripts/laser_gt.py` | wall / ceiling / door errors vs laser (`--peaks` lists the laser surfaces near each side) |
| `scripts/tier_compare.py` | video/photo plan vs the LiDAR plan of the same capture |
| `scripts/fit_calibration.py` | `benchmark/calibration.json` + `benchmark/results/calibration_fit.json` |
| `scripts/drift_ablation.py` | footprint and repeatability with drift correction on vs off |
| `scripts/make_photo_folders.py` | photo-tier inputs (stills per room) from a capture's video |
| `scripts/final_tables.py` | `benchmark/results/FINAL_RESULTS.md` |
| `scripts/build_submission_pdf.py` | `docs/roomscan_submission.pdf` |
| `scripts/diagnostics/*` | one-off investigations cited in the report (conventions, scale, trajectories, overlays) |

---

## Repository layout

```
src/roomscan/            the package (CLI, tiers, geometry, calibration, benchmarking)
schema/                  output JSON schema
docs/                    report, compliance matrix, capture protocol, device matrix, submission PDF
benchmark/               fitted calibration, ground-truth template, result files (results/, results/own/, results/video/)
fixloop/                 fix declaration, post-mortem, notes, before/after runs, readable diff
reproduction/            end-to-end PowerShell drivers
scripts/                 benchmark/scoring tools; scripts/diagnostics/ for investigations
```

Large inputs (captures, laser scans, model weights) and generated outputs (`out/`, `cache/`, photo frames) are not
committed. They are fetched or regenerated by the scripts above.

---

## Models, data and licences

| Asset | Used for | Licence |
|---|---|---|
| Depth Anything 3 `DA3-LARGE-1.1` | video/photo poses + depth | Apache-2.0 |
| Depth Anything 3 `DA3METRIC-LARGE` | metric scale | Apache-2.0 |
| COLMAP / pycolmap | video fallback (SfM) | BSD |
| Open3D | ICP, pose graph, point clouds | MIT |
| Apple ARKitScenes (venue 470350) | own benchmark: iPad LiDAR + Faro laser GT | CC BY-NC-SA 4.0 (fetched, not re-hosted) |
| Organisers' sample captures | sample-data benchmark | provided for the assessment |

The LiDAR tier uses no learned model. Nothing calls a remote service at run time; models are downloaded once from
Hugging Face.

---

## Known limitations

- **Virtual walls** (doorway closure / wall extension) can be snapped to stray surfaces, which gives ~20 cm errors.
  Tall furniture in the wall band can split or shrink rooms differently per capture.
- **Video tier:** DA3 is accurate within a 24-frame chunk (5-17 cm over 3 m), but chaining chunks drifts over long
  walks. A global pose graph over chunk overlaps is the next step.
- **Photo tier:** the joint pass does not hold rooms together, so 0-1 rooms are recovered and the plan is flagged.
- **Not implemented:** windows, damage regions, concealed-damage rules, scope line items (schema fields are emitted
  empty), and the consumer-app head-to-head (no device available).
- **Mirrors and glass** create phantom space and are not handled.
- Intervals are fitted on the same captures they are evaluated on, so their coverage is optimistic.
- The reproduction scripts are PowerShell, and the "under 15 minutes on a clean machine" target has not been
  re-verified on a fresh machine.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'triton'` in the log | Harmless warning from xformers on Windows; inference still runs on CUDA. |
| `Warning: unauthenticated requests to the HF Hub` | Harmless; set `HF_TOKEN` for faster model downloads. |
| `uv sync` fails with *Access is denied* on Windows | A process or antivirus is locking `.venv`: close other Python processes, set `UV_LINK_MODE=copy`, retry. |
| Video/photo tier is very slow | It is running on CPU: check `torch.cuda.is_available()`; an NVIDIA GPU is required for usable speed. |
| `ceiling_height_m` is `null` | The ceiling was not observed in the capture; sweep the phone up to the ceiling once per room. |
| A room or the whole plan has wide intervals or `reliable: false` | Read `warnings` in `plan.json`: thin input is reported, not hidden. |
