# Sample-data benchmark (reference = LiDAR plan; no tape ground truth supplied with sample data)

| tier | capture | rooms | footprint_m2 | footprint_err_pct | matched_dims | median_abs_err_pct | within_3pct | within_8pct | interval_coverage | ceiling_m | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lidar | single_room | 4 | 20.61 | 0.0 | ref | ref | ref | ref | ref | not observed | 16.0 |
| video | single_room | 1 | 2.12 | -89.7 | 0 | nan | 0 | 0 | None | not observed | 39.3 |
| photo | single_room | 1 | 1.44 | -93.0 | 0 | nan | 0 | 0 | None | not observed | 63.9 |
| lidar | with_ceiling | 10 | 54.51 | 0.0 | ref | ref | ref | ref | ref | 3.030-3.079 | 29.9 |
| video | with_ceiling | 7 | 24.73 | -54.6 | 2 | 53.6 | 0 | 0 | 1.0 | 2.422-2.453 | 106.5 |
| photo | with_ceiling | 1 | 7.48 | -86.3 | 2 | 20.9 | 0 | 0 | 1.0 | not observed | 78.0 |
| lidar | floor_only | 8 | 51.01 | 0.0 | ref | ref | ref | ref | ref | not observed | 22.2 |
| video | floor_only | 5 | 14.11 | -72.3 | 4 | 32.6 | 0 | 0 | 1.0 | 2.778-2.808 | 94.1 |
| photo | floor_only | 1 | 9.01 | -82.3 | 0 | nan | 0 | 0 | None | not observed | 76.3 |