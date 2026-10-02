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
