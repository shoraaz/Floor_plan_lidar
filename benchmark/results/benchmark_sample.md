# Sample-data benchmark (reference = LiDAR plan; no tape ground truth supplied with sample data)

| tier | capture | rooms | footprint_m2 | footprint_err_pct | matched_dims | median_abs_err_pct | within_3pct | within_8pct | interval_coverage | ceiling_m | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lidar | single_room | 4 | 20.61 | 0.0 | ref | ref | ref | ref | ref | not observed | 11.1 |
| video | single_room | 1 | 2.12 | -89.7 | 0 | nan | 0 | 0 | None | 1.778-1.778 | 277.0 |
| photo | single_room | 1 | 1.44 | -93.0 | 0 | nan | 0 | 0 | None | 1.406-1.406 | 166.0 |
| lidar | with_ceiling | 10 | 54.51 | 0.0 | ref | ref | ref | ref | ref | 3.030-3.079 | 15.4 |
| video | with_ceiling | 7 | 24.73 | -54.6 | 2 | 53.6 | 0 | 0 | 0.5 | 2.422-2.453 | 805.9 |
| photo | with_ceiling | 1 | 7.48 | -86.3 | 2 | 20.9 | 0 | 0 | 1.0 | 0.934-0.934 | 89.1 |
| lidar | floor_only | 8 | 51.01 | 0.0 | ref | ref | ref | ref | ref | not observed | 10.9 |
| video | floor_only | 5 | 14.11 | -72.3 | 4 | 32.6 | 0 | 0 | 0.25 | 2.778-2.808 | 749.6 |
| photo | floor_only | 1 | 9.01 | -82.3 | 0 | nan | 0 | 0 | None | 1.046-1.046 | 83.6 |