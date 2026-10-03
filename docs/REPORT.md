# roomscan: technical report

Applied AI Engineer case study. Repo: this repository; every number below is regenerable with
`reproduction/run_all.ps1`, `reproduction/fixloop.ps1` and the scripts named next to it.

## 1. What was built

One command per capture (`roomscan run <capture> --out <dir>`) turns a phone capture into a schema-validated
`plan.json` and a rendered `plan.svg`. Three front ends feed one geometry backend, so every tier emits the same
contract and differs only in the evidence behind it and in interval width.

```
LiDAR  (Stray Scanner: depth, confidence, ARKit poses, K) --\
Video  (RGB clip only: DA3 any-view poses + DA3 metric)    ----> metric y-up point cloud + camera path + rays
Photo  (per-room folders: joint DA3 pass + DA3 metric)    --/                     |
                                                                                  v
  floor/ceiling planes -> Manhattan yaw (normals + 0.02 deg sharpness search) -> wall map (0.95-1.6 m band)
  -> doorway closure -> wall extension through unobserved space -> rooms = wall-enclosed regions
  -> rectangle-first snapping to the room-side wall face -> per-room ceiling -> intervals -> stitch checks
  -> plan.json (schema-validated) + plan.svg
```

Design choices that matter at the defense:

- **One backend, three front ends.** Room logic is written and debugged once; tier differences are isolated to
  how a metric cloud is produced. The cost: a weak front end (video/photo) cannot be rescued downstream.
- **Structure, not coverage, defines rooms.** Rooms are regions enclosed by walls, with walls extended through
  space the walk never saw (ROSE2-style). Earlier versions used observed free space, which made room extent
  depend on where the phone happened to point (see fix loop).
- **The wall band is chosen for robustness, not completeness.** 0.95-1.6 m: above beds/tables/counters, and
  observed by any walk that follows the protocol. One sample walk was aimed low (~5% of points above 1.6 m);
  a 1.1-2.0 m band broke its walls.
- **Measure the room-side face.** Each room side is snapped to the wall face nearest the room interior (median
  of face points, sub-cm), i.e. the surface a tape touches, not the wall centreline.
- **Never guess.** Ceiling height is `null` when the ceiling was not observed; rooms not enclosed by detected
  walls are flagged and their intervals widened.

## 2. Tiers and device matrix

| Tier | Input | Front end | Runs on | Sample-data result (vs LiDAR) |
|---|---|---|---|---|
| LiDAR | Stray Scanner export | ARKit poses + LiDAR depth (conf = 2) | iPhone 12 Pro or newer (Pro) | reference; repeatability in sec. 5 |
| Video | any clip | DA3-LARGE-1.1 chunks (24 frames, 8 shared), per-chunk metric scale | any iPhone 15+ clip; CUDA GPU for processing | TBD |
| Photo | per-room folders | joint DA3 pass over all photos, metric scale | any iPhone 15+; CUDA GPU | TBD |

Conventions verified on data, not assumed: Stray Scanner poses are camera-to-world in an OpenCV camera frame
inside an ARKit y-up world (`scripts/test_convention.py`: floor peak 1.4 m below camera only under this
convention). DA3 extrinsics are world-to-camera (`benchmark/results/video/da3_convention_single_room.log`:
5-17 cm ATE per chunk as w2c vs 21-26 cm as c2w). DA3METRIC output is canonical depth; metres = out x f / 300
(`benchmark/results/da3_vs_lidar_single_room.log`: LiDAR/DA3 ratio 1.37-1.59 vs predicted 1.40).

## 3. Drift

LiDAR: ARKit visual-inertial odometry poses are used; drift is measured, not yet corrected. On the 99 m
`with_ceiling` walk the loop gap is 0.39 m and the floor slab spreads 1.8 cm. A plane-anchored pose graph was
planned but not shipped; the PDF's drift row is therefore failed and stated as such.
Video: v1 chained chunk scale relative to the previous chunk, which compounded per-chunk scale error (scale off
by 86% after 54 m, `traj_floor_only.txt`). v2 anchors every chunk to metres independently and chains only
rotation and translation. TBD numbers.

## 4. Error budget (LiDAR tier, from sample data)

| Source | Size | Evidence |
|---|---|---|
| Raw wall surface repeatability between captures | 0.95 cm RMSE | ICP of wall bands, `fixloop/after/repeatability_lidar.md` |
| Residual orientation between captures | 0.22 deg (~1.5 cm at 4 m) | registration residual after yaw refinement |
| Room-side face snapping, rooms partitioned identically | 2-6 cm per dimension | `fixloop/after/room_dims.txt` |
| Room partition differences (furniture-faced walls, slivers) | 15-140 cm when they occur | overlay `fixloop/after/overlay_A_blue_B_red.png` |

The dominant term is partitioning, not sensing. That ordering drove the fix loop.

## 5. Fix loop (25%)

Declared before any fix code (tag `fixloop-before`): worst measured gate = LiDAR repeatability, 0/22 walls.
Hypothesis: room segmentation, not sensing/drift/snapping. Predicted >= 70% after structure-only segmentation.
Shipped (tag `fixloop-after`): structure-only segmentation, protocol-covered wall band, wall extension, fine yaw,
rectangle-first snapping. Result: 2/20 walls pass; matched-room extents median diff 50 -> 19 cm; best room 2.3/2.6 cm.
**Gate not passed; prediction badly wrong.** Root cause partly right: segmentation confirmed dominant; snapping was
wrongly excluded and orientation error (0.75 deg) was missed. Full story: `fixloop/POSTMORTEM.md`.

## 6. Calibration

Intervals are relative half-widths per tier and measurement kind (`calibration.py`), inflated by evidence
quality: wall-face support along each side, enclosure, and for video/photo the disagreement of metric-scale
votes. TBD: coverage of video/photo intervals against LiDAR values.

## 7. Known failure modes

- Wardrobes and tall furniture in the wall band act as walls: rooms split or shrink differently per capture.
- Sliver rooms (< 0.9 m) are not merged.
- Mirrors and glass: LiDAR returns through/off them create phantom space; not handled.
- Low light/low texture: hurts video/photo poses most (COLMAP registered 13-21% of keyframes; replaced by DA3).
- Openings, damage, concealed-damage rules, scope items: not implemented (schema fields emitted empty).
- No tape ground truth for the sample data: accuracy is cross-tier agreement and repeatability only.
