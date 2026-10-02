# Fix declaration

Declared at commit tagged `fixloop-before`, **before any fix code was written**.
Regenerate: `git checkout fixloop-before; .\reproduction\fixloop.ps1 -Label before` -> `fixloop/before/`.

## 1. Worst-performing gate (with the failing number)

**Repeatability, LiDAR tier** (two captures of the same place at the same tier must agree within 1 cm or 0.5% per wall).

- Captures: `single_scan_with_ceiling/c7d28f72c6` (A) vs `single_scan_floor_only/1a8384c3f6` (B), same apartment, same tier, same device.
- **Result: 0 / 22 walls pass.** Matched wall length differences range from 20 to 169 cm; 13 of 22 walls in A have no matching wall in B at all.

Scope note: at declaration time, this is the only gate with a measured number besides footprint. Ground-truth gates (wall/ceiling/opening accuracy vs tape) are pending measurements; openings are not implemented. Of the measured gates, this one is the furthest from passing.

## 2. Root-cause hypothesis and evidence

**Hypothesis: the failure is in room segmentation, not in sensing, pose drift, or wall-face snapping.**
The room split (distance-transform cores + watershed over ray-cast free space) depends on which space each walk happened to observe and from where. Where two captures look into a doorway differently, or see an open area from different positions, the split lands in a different place. Room polygons then differ by metres even though the walls are the same.

Evidence (all in `fixloop/before/`):

| Measurement | Value | What it shows |
|---|---|---|
| ICP inlier RMSE, wall-band points of A vs B after registration | **0.95 cm** | Raw wall geometry repeats at ~1 cm: the sensor and poses are not the problem at this scale |
| Footprint A vs B | 47.97 vs 48.38 m2 (**0.85%**) | The overall extent agrees; the error is in how it is partitioned |
| Room IoU A->B (7 rooms) | 0.011, 0.276, 0.489, 0.501, 0.601, 0.633, 0.778 | Same space is cut into different rooms; 2 rooms in A have no counterpart |
| Room count | 7 vs 6 | Partition is not stable |
| Wall-face offset of matched walls | median ~4.5 cm, max 20.5 cm | Where walls are matched, faces are close; the 18-20 cm cases are opposite faces of the same wall, a consequence of the room boundary landing on the other side of the wall |

What would falsify the hypothesis: if, after a segmentation that depends only on wall structure, matched rooms still disagree by more than a few cm per wall, the cause is downstream (snapping) or upstream (drift), not the split.

## 3. The fix to ship, and the predicted number after it

**Fix: structure-only room segmentation.**
1. Detect doorways as gaps of 0.6-1.3 m between collinear wall runs in the wall-occupancy map (the 1.1-2.0 m band, so furniture below 1.1 m cannot create or hide them).
2. Close each detected doorway with a virtual wall segment; record it as an opening between the two rooms (this also gives adjacency from doors instead of from watershed contact).
3. Rooms = connected components of interior free space after closure (4-connectivity, minimum 1 m2). No distance-transform cores, no watershed, so no dependence on viewing position.
4. Wall-face snapping (`snap_rooms_local`) unchanged, so any change in the number is attributable to the split.

**Prediction: >= 70% of walls pass (point estimate ~75%, i.e. about 16-17 of 22), median matched-room IoU >= 0.85, footprint difference stays <= 2%.**

Why not 100%: open-plan boundaries without a door frame will merge consistently, but any doorway seen as a gap in one capture and blocked (closed door, clutter) in the other will still split differently; and `floor_only` has no ceiling sweep, so a few high wall bands are thinner there.
