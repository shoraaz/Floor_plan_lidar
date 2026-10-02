# Fix-loop working notes (in progress; final post-mortem goes in POSTMORTEM.md)

Iterations on the declared fix (structure-only segmentation), all regenerable with reproduction/fixloop.ps1:

| iteration | change | rooms A/B | room IoU (matched) | walls pass | footprint diff |
|---|---|---|---|---|---|
| before (tag fixloop-before) | watershed split | 7/6 | 0.01-0.78 | 0/22 | 0.85% |
| it1 | doorway closure, strict collinear runs, band 1.1-2.0 m | 5/2 | one room 0.85 | 1/4 | 20.1% |
| it2 | + perpendicular tolerance, door-at-corner rule | 8/5 | 0.81 max | 0/4 | 9.8% |
| it3 | + segmentation band 0.95-1.6 m | 9/8 | 0.86, 0.69, 0.69, 0.86, 0.81 | 2/25 | 9.2% |
| experiment | it3 + snapping band 0.95-1.6 m (not shipped) | 9/8 | ~same | 2/25 | 10.2% |

Findings
- it2 -> it3: `floor_only` walk was aimed low (scripts/height_profile.py: ~4.8% of its points above 1.6 m,
  ~0% above 2.2 m, vs 11%/21% for `with_ceiling`). Wall band 1.1-2.0 m broke its walls, merging rooms.
  Same declared root cause (segmentation depends on what the walk observed); mechanism now identified.
- experiment: snapping band is not the remaining cause.
- Remaining error source: room EXTENT. Structure-only split takes room area from ray-cast seen space, which
  depends on coverage; footprint diff grew 0.85% -> ~9%. Watershed + snapping previously masked this.

| it4 | + ROSE2-style wall extension through unobserved space; rooms = wall-enclosed regions (fallback: observed extent, flagged + widened) | 9/8 | 0.86, 0.69, 0.69, 0.86, 0.81 | 2/25 | **1.7%** |

it4 findings
- Footprint agreement recovered (9.2% -> 1.7%): extent completion works at property level.
- Matched-room IoUs unchanged, wall gate unchanged: per-room polygon shape still differs between captures.
- Registration reports a residual rotation of 0.75 deg between the two captures' Manhattan frames. Each capture's
  polygons are axis-aligned in its own frame, so B's walls end up rotated 0.75 deg vs A's: ~5 cm at the end of a 4 m wall.
  The Manhattan yaw estimate (normal-histogram, concentration ~0.6) is not precise enough for a 1 cm gate.
- Next candidates: (a) refine yaw by fitting long wall lines (target < 0.1 deg); (b) regularise polygons (remove
  notches < 0.3 m caused by furniture/door plugs) so walls are not fragmented differently per capture.

| it5 | + fine yaw refinement (wall-sharpness search, 0.02 deg) | 10/8 | (see room_dims_check) | 0/25 | 5.2% |

it5 findings
- Residual rotation between captures 0.75 -> 0.22 deg (per-capture yaw moved 0.5 / 0.86 deg). Yaw refinement works.
- Wall gate and footprint got worse: the room split is sensitive to sub-degree rotation (cells flip between rooms).
- scripts/room_dims_check.py: matched rooms' wall-to-wall extents differ by 3-138 cm (median 20 cm); the best-matched
  room (IoU 0.91) differs 3.0 / 5.9 cm. So beyond partitioning, the per-room polygon extraction itself
  (cell voting + local face lines) is not stable; raw wall surfaces agree to ~1 cm (ICP), so the error is in extraction.
