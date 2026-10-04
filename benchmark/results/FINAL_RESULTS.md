# Final results

Sample data = organisers' 3 Stray Scanner captures (no ground truth supplied). Own benchmark = ARKitScenes venue
470350 (Apple, CC BY-NC-SA 4.0): 3 iPad-LiDAR captures of the same space, Faro laser-scanner ground truth,
converted to Stray format (`scripts/arkitscenes_to_stray.py`). Substitution disclosed: no own phone/room was
available. Regenerate: `reproduction/get_arkitscenes.ps1`, `reproduction/run_final.ps1`, this script.

## Gate table

| gate | target | measured | status |
|---|---|---|---|
| Wall lengths (LiDAR) vs laser | <= 1 cm or 0.5% (repeat gate used as accuracy proxy) | 22 walls scored; median |err| 20.5 cm; within 2 cm: 2 | FAIL |
| Opening widths | <= 2 cm on >= 85%, missed/phantom = miss | 7 doors scored; median |err| 11.5 cm; within 2 cm: 0/7 | FAIL |
| Ceiling height | <= 1.5 cm; spread <= 1 cm | laser GT 2.308, 2.311, 2.266, 2.265 m; ours reported in 2 rooms (ceiling not observed by the iPad sweeps -> withheld) | NOT SCORED |
| Repeatability (LiDAR) | <= 1 cm or 0.5% per wall | own a/b 0/8, own a/c 0/4, sample 4/24 | FAIL |
| Drift accountability | method + on/off footprint ablation | pose graph + ICP-verified revisit loops, ON by default; ablation in `drift_ablation_*.log` (no measured benefit on sample data) | PARTIAL |
| Photo-tier whole-property stitch | one stitched plan, correct adjacency, footprint +/-8% | see tier table: collapses / flagged UNRELIABLE | FAIL |
| Video tier | walls +/-3% | see tier table | FAIL |
| Calibration / no confident garbage | intervals honest at every tier | LiDAR interval coverage vs laser: 45% | PARTIAL |

## Own benchmark: LiDAR tier vs Faro laser ground truth

| capture | walls scored | median abs err (cm) | within 2 cm | within 5 cm | doors scored |
|---|---|---|---|---|---|
| ark470350_a | 12/20 | 20.7 | 0 | 0 | 4 |
| ark470350_b | 4/8 | 44.42 | 0 | 0 | 0 |
| ark470350_c | 6/12 | 5.09 | 2 | 2 | 3 |

## Tier agreement vs LiDAR plan (same capture)

| set | tier | capture | rooms | footprint m2 | footprint err | median dim err | interval coverage | reliable |
|---|---|---|---|---|---|---|---|---|
| sample | video | floor_only | 5 vs 8 | 13.25 | -70.8% | 58.6% | 1.0 | True |
| sample | video | single_room | 1 vs 4 | 2.12 | -89.6% | nan% | None | False |
| sample | video | with_ceiling | 7 vs 11 | 19.59 | -64.7% | 11.9% | 1.0 | True |
| sample | photo | floor_only | 1 vs 8 | 5.19 | -88.6% | nan% | None | False |
| sample | photo | single_room | 1 vs 4 | 1.09 | -94.7% | nan% | None | False |
| sample | photo | with_ceiling | 1 vs 11 | 8.46 | -84.7% | 17.6% | 1.0 | False |
| own | video | ark470350_a | 1 vs 5 | 41.01 | -3.1% | nan% | None | True |
| own | photo | ark470350_a | 0 rooms (empty plan, flagged) | 0 | -100% | - | - | False |

## Timing (seconds, this laptop: RTX 5050 8 GB; video/photo include DA3 inference, cold where not cached)

| set | tier | capture | s |
|---|---|---|---|
| sample | lidar | single_room | 18.3 |
| sample | lidar | with_ceiling | 27.6 |
| sample | lidar | floor_only | 20.4 |
| own | lidar | ark470350_a | 17.8 |
| own | lidar | ark470350_b | 19.9 |
| own | lidar | ark470350_c | 32.3 |
| sample | video | single_room | 39.5 |
| sample | photo | single_room | 131.6 |
| sample | video | with_ceiling | 109 |
| sample | photo | with_ceiling | 83.6 |
| sample | video | floor_only | 45.4 |
| sample | photo | floor_only | 47.4 |
| own | video | ark470350_a | 379.6 |
| own | photo | ark470350_a | 31.7 |