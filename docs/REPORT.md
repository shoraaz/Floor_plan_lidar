# roomscan: technical report

Applied AI Engineer case study. Every number here is regenerable: `reproduction/get_arkitscenes.ps1` (own
benchmark data), `reproduction/run_final.ps1` (all tiers, all captures, scoring), `scripts/final_tables.py`
(`benchmark/results/FINAL_RESULTS.md`), `reproduction/fixloop.ps1` (fix loop). Short version: the LiDAR tier is
a complete, metrically sound pipeline that **does not yet meet the centimetre gates**; the video and photo tiers
run end to end but are far from their gates and say so in their output. All gate results are in sec. 4.

## 1. Data and the one substitution

- **Sample data** (organisers): 3 Stray Scanner LiDAR captures, two of the same flat. No ground truth supplied.
- **Own benchmark**: no LiDAR phone or room was available to me, so I used **Apple ARKitScenes** venue 470350
  (CC BY-NC-SA 4.0): three iPad-LiDAR captures of the same space plus **Faro laser-scanner point clouds** as
  ground truth. `scripts/arkitscenes_to_stray.py` converts each capture to the exact Stray export format, so the
  unchanged `roomscan run` processes it (also a rehearsal of the walk-in format). Two conventions were verified
  on data, not assumed: ARKitScenes trajectories are world-to-camera in a **z-up** world (camera height std
  0.30 m along z; floor peak along z), rotated to the y-up frame Stray uses. Not covered by this substitution:
  staged damage, a 3+-room-plus-connector layout, my own capture protocol, the consumer-app head-to-head.

## 2. Architecture

```
LiDAR  (Stray: depth + confidence + ARKit poses + K)  -> pose-graph drift correction -> fuse
Video  (RGB clip only)   -> DA3-LARGE-1.1 chunks, per-chunk metric scale (DA3METRIC) -> fuse
Photo  (room folders)    -> one joint DA3 pass over all photos + metric scale         -> fuse
        all three -> metric, y-up point cloud + camera path + ray endpoints
shared backend: floor/ceiling planes -> Manhattan yaw (normals + 0.02 deg wall-sharpness search)
  -> wall map in a 0.95-1.6 m band -> doorway closure -> wall extension through unobserved space
  -> rooms = wall-enclosed regions -> each side snapped to the room-side wall face -> ceiling per room
  -> doors (doorways joining two rooms; width from door-frame faces) -> intervals -> plausibility gate
  -> stitch checks -> plan.json (schema-validated before writing) + plan.svg
```

Design decisions I would defend live:
- **One backend, three front ends.** Room logic exists once; tiers differ only in how a metric cloud is made and
  in interval width. Cost: a weak front end cannot be rescued downstream (that is what happened to video/photo).
- **Structure, not coverage, defines rooms.** Rooms are wall-enclosed regions, with walls extended through
  unobserved space (ROSE2-style); using observed space made room extent depend on where the phone pointed.
- **Wall band 0.95-1.6 m.** Above tables, beds and counters, and covered by any protocol-following walk. One
  sample walk was aimed low (~5% of points above 1.6 m); a 1.1-2.0 m band broke its walls entirely.
- **Never guess.** Ceiling is `null` when not observed; empty reconstructions produce a valid, empty, flagged plan;
  non-LiDAR plans with an implausible floor-to-ceiling distance (outside 2.1-4.2 m) are marked UNRELIABLE.
- **Verify conventions on data.** Stray poses are camera-to-world, OpenCV camera, ARKit y-up world (floor peak
  1.4 m below the camera only under this reading). DA3 extrinsics are world-to-camera (5-17 cm ATE per chunk vs
  21-26 cm the other way). DA3METRIC depth in metres = output x focal / 300 (LiDAR ratio 1.37-1.59 vs 1.40).

## 3. Tiers and device matrix

| Tier | Input | Runs on (processing) | Honest accuracy on our data |
|---|---|---|---|
| LiDAR | Stray Scanner export (iPhone/iPad Pro) | CPU; 18-32 s per capture | metric cloud (0.8% scale vs laser); room walls median 20.5 cm vs laser |
| Video | any clip (iPhone 15+) | CUDA GPU, 8 GB; 6 min cold for 90 s of video | footprint -3% to -90%; trajectory error ~5% of path |
| Photo | 2-8 stills per room folder | CUDA GPU; 30-130 s | collapses to 0-1 rooms; flagged UNRELIABLE |

## 4. Results

**Gate table** (`benchmark/results/FINAL_RESULTS.md`):

| Gate | Target | Measured | Status |
|---|---|---|---|
| Walls (LiDAR) vs laser | 1 cm / 0.5% | 22 walls: median 20.5 cm; 2 within 2 cm; best capture (c) median 5.1 cm | FAIL |
| Opening widths | <= 2 cm on >= 85% | 7 doors scored: median 11.5 cm; 0 within 2 cm | FAIL |
| Ceiling height | <= 1.5 cm | laser 2.27-2.31 m; iPad sweeps rarely saw the ceiling -> withheld in most rooms | NOT SCORED |
| Repeatability | 1 cm / 0.5% per wall | own a/b 0/8, a/c 0/4, sample 4/24; raw surfaces agree to 0.69-0.95 cm | FAIL |
| Drift | method + ablation | pose graph with verified loops, ablated (sec. 5) | PARTIAL |
| Photo whole-property stitch | +/-8%, correct adjacency | does not stitch | FAIL |
| Video walls | +/-3% | not met | FAIL |
| Calibration | honest intervals | LiDAR 91% coverage vs laser, video/photo 100% vs LiDAR (in-sample) | PARTIAL |
| Head-to-head vs consumer app | beat/tie >= 70% | not run: no device | NOT DONE |

**Where the LiDAR error comes from** (laser, `scripts/laser_gt.py`, `scripts/diagnostics/scale_check.py`). The fused cloud is
metrically right: similarity ICP onto the laser scan gives scale 1.008 and 1.9 cm RMSE. The error is in which
surface a room side snaps to. Per-side comparison against laser wall faces (measured above furniture height):
several sides land within 1 cm (-0.6, -0.7, -0.9, -1.2 cm), many land **18-24 cm outside, i.e. on the far face of
the wall**. A fix for one cause (rectilinear outlines including the wall thickness) moved room1's worst sides from
+23.8/+22.7 cm to -6.7/+2.2 cm; the remaining far-face picks are the main open problem. The scorer itself is
limited to rectangular rooms and mis-measured one tiny room on capture b.

**Repeatability.** Raw wall surfaces of two captures agree to 0.69 cm (own) and 0.95 cm (sample) after
registration; footprints to 1.4% (own a/b). Per-wall agreement fails because the same space is partitioned or
snapped differently per capture (sec. 6).

**Video and photo** (`benchmark/results/video/`). Within one 24-frame chunk DA3 is good to 5-17 cm over 3 m.
Chaining chunks is the weak link: v1 chained relative scale and compounded it (scale off 86-91% after 54-60 m);
v2 anchors each chunk to metric depth independently, which removed the blow-up but not the shape error
(1.5-4.5 m jumps at chunk joins, ATE ~3 m on 98 m). COLMAP SfM registered only 13-21% of keyframes on these
low-texture walls and is kept only as a fallback. The photo tier's joint pass does not hold rooms together;
on the own capture it recovered no rooms and emits an empty, flagged plan instead of a guess.

**Timing** (RTX 5050 laptop): LiDAR 18-32 s; video 39-109 s with cached DA3, 380 s cold for a 90 s clip; photo
32-132 s.

## 5. Drift handling and ablation

Pose graph (`geometry/drift.py`): ARKit odometry edges between consecutive keyframes, plus loop edges at revisits
(>= 100 keyframes apart, < 0.6 m, < 25 deg viewing difference), each verified by coarse-to-fine point-to-plane ICP
of local submaps and accepted only if fitness > 0.5, RMSE < 1.5 cm, correction < 0.3 m and < 3 deg; Open3D global
optimisation with line-process pruning. ON by default; `--no-drift-correction` is the ablation switch. A first
version (start-end loop only) was rejected by its own checks on every sample (start and end views do not overlap).

| Setting (sample with_ceiling) | loops used | max pose shift | floor spread | footprint diff vs repeat capture |
|---|---|---|---|---|
| OFF (ARKit poses) | - | - | 1.40 cm | 6.4% |
| ON, strict (shipped) | 1/5 | 16.6 cm | 1.49 cm | 12.0% |
| ON, loose (fitness > 0.35) | 5/5 | 19.4 cm | 1.80 cm | 16.2% |

On ARKitScenes capture a it accepted 2/3 loops (max shift 9.1 cm). **No measured benefit on these captures**:
ARKit already relocalises on revisits, and partial-overlap loop edges add more error than they remove. Shipped
strict so that genuinely drifting captures are corrected; this row is not a pass.

## 6. Fix loop (25%)

Declared before any fix code (tag `fixloop-before`): worst measured gate = LiDAR repeatability, 0/22 walls;
hypothesis: room segmentation (not sensing, drift or snapping); prediction >= 70% after structure-only
segmentation. Shipped (tag `fixloop-after`): structure-only segmentation, protocol-covered wall band, wall
extension, fine yaw, rectangle-first snapping. Result **2/20 walls; matched-room extents median 50 -> 19 cm; best
room 2.3/2.6 cm. Gate not passed; prediction badly wrong.** Root cause partly right: segmentation was the dominant
cause, but snapping was wrongly excluded and a 0.75 deg orientation error was missed. The laser ground truth found
later confirms the snapping half: wrong-face picks of ~20 cm. Full post-mortem: `fixloop/POSTMORTEM.md`.

## 7. Error budget and calibration

| Source (LiDAR) | Size | Evidence |
|---|---|---|
| Sensor + poses (cloud vs laser) | 0.8% scale, 1.9 cm RMSE | `scale_check.py` |
| Raw surface repeatability | 0.69-0.95 cm | repeatability registrations |
| Orientation between captures | 0.22 deg after refinement | registration residual |
| Room-side face selection | 0-24 cm per side (bimodal: ~1 cm or ~20 cm) | per-side laser comparison |
| Partition differences between captures | 15-140 cm when they occur | `fixloop/after/overlay_A_blue_B_red.png` |

Intervals are fitted from measured errors (`scripts/fit_calibration.py`): LiDAR half-width = max(4.3% x length,
46 cm) from 22 laser residuals (errors are roughly constant in cm, so a relative-only interval was 45% covered);
video 97% and photo 39% from errors vs LiDAR. Coverage after fitting: LiDAR 91% vs laser, video/photo 100% vs
LiDAR. **These coverages are in-sample (fitted and evaluated on the same captures) and therefore optimistic.**

## 8. Known failure modes and what is not done

- Far-face wall snapping (~20 cm) and capture-dependent partitions (wardrobes/shelves in the wall band, sliver
  rooms) dominate the LiDAR error. Next step: choose the room-side face using ray-cast free space (the face whose
  room side was observed empty), and merge slivers.
- Mirrors and glass: LiDAR sees through or reflects, creating phantom space; not handled.
- Low texture / long walks: video chunk chaining drifts; needs a global pose graph over chunk overlaps.
- Not implemented: windows, damage regions, concealed-damage rules, scope line items (schema fields are emitted
  empty), consumer-app head-to-head (no device), staged-damage benchmark room.
