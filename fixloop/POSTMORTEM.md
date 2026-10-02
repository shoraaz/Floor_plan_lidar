# Fix loop post-mortem

Declaration: `FIX_DECLARATION.md` (committed and tagged `fixloop-before` before any fix code).
Regenerate: `git checkout fixloop-before; .\reproduction\fixloop.ps1 -Label before` and
`git checkout fixloop-after; .\reproduction\fixloop.ps1 -Label after`.
Readable diff: `git diff fixloop-before fixloop-after -- src/` (also saved as `fixloop/after/fix.diff`).

## Result vs prediction

| Metric | Before | Predicted after | Actual after |
|---|---|---|---|
| Repeatability wall gate (<=1 cm or <=0.5%) | 0 / 22 | >= 70% (~16 / 22) | **2 / 20 (10%)** |
| Median matched-room IoU | ~0.5 (0.01-0.78) | >= 0.85 | 0.74 (0.55-0.93) |
| Footprint difference | 0.85% | <= 2% | 6.4% |
| Matched-room wall-to-wall extents, median diff (`room_dims.txt`) | 50 cm | n/a | 19 cm; best room 2.3 / 2.6 cm |

**The gate did not pass and the prediction was badly wrong.** Movement is real but partial: the room that the
two captures partition the same way now agrees to 2-3 cm per dimension (from 18/12 cm), extents improved from
a 50 cm to a 19 cm median, but most walls still fail the 1 cm gate.

## Was the root cause right?

Partly. The declared cause was "room segmentation, not sensing, drift or snapping". Evidence after the fix:

- **Sensing: confirmed not the cause.** Registered wall points of the two captures agree to 0.95 cm RMSE throughout.
- **Segmentation: confirmed a cause, and still the dominant one.** The overlay (`after/overlay_A_blue_B_red.png`)
  shows the remaining large errors are rooms split differently: a stray line splits the top room in capture A only,
  and the boundary between the two right-hand rooms lands ~40 cm apart, leaving a sliver room in A.
- **Snapping/extraction: wrongly excluded.** The declaration held polygon snapping fixed. It was a second cause:
  even rooms matched at IoU > 0.9 differed by 3-18 cm until snapping was replaced by rectangle-first face fitting.
- **Orientation: an unlisted cause.** Each capture's Manhattan yaw was only good to ~1 deg; the two captures
  differed by 0.75 deg (~5 cm at the end of a 4 m wall). Fine yaw search reduced this to 0.22 deg.

## What shipped (iterations, all in `NOTES.md`)

1. Structure-only segmentation: doorway gaps closed in the wall map, rooms = enclosed regions (replaces watershed).
2. Wall band chosen to be covered by any protocol-following walk (0.95-1.6 m). Root of a capture-dependent failure:
   `single_scan_floor_only` was aimed low (~5% of points above 1.6 m vs ~11% for the other capture).
3. ROSE2-style wall extension through unobserved space; extent from enclosure, not from coverage.
4. Fine Manhattan yaw (wall-sharpness search, 0.02 deg steps).
5. Rectangle-first room extraction: each side snapped to the room-side face, sub-cm median of face points.

## Why it fell short

- The doorway-closure and wall-extension rules are thresholded on gap width and run length; furniture faces
  (wardrobes) in the 0.95-1.6 m band look like wall runs and create extra lines in one capture but not the other.
- Small rooms and slivers are not merged; a ~0.5 m sliver changes which walls bound its neighbour.
- The 1 cm gate is below the per-capture noise of the remaining extraction (2-6 cm on the best rooms).

## What I would do next

- Merge sliver rooms (min side < 0.9 m, no detected door) into the neighbour they share the longest boundary with.
- Classify wall-band runs as wall vs furniture by vertical extent (true walls continue to the ceiling band and
  below 0.95 m; wardrobes end before the ceiling) before closing doorways or extending lines.
- Re-run this loop; expected to move the mismatched rooms first, then the 2-6 cm residual on matched rooms.
