# Drift ablation: start-end loop closure ON vs OFF (LiDAR tier, sample data)

| capture | drift | rooms | footprint_m2 | floor_spread_cm | loop | loops_acc | max_shift_cm |
|---|---|---|---|---|---|---|---|
| with_ceiling | OFF | 10 | 54.51 | 1.4 | - | - | - |
| floor_only | OFF | 8 | 51.01 | 1.72 | - | - | - |
| single_room | OFF | 4 | 20.61 | 2.01 | - | - | - |
| with_ceiling | ON | 10 | 60.85 | 1.8 | accepted | 5/5 | 19.4 |
| floor_only | ON | 8 | 51.01 | 1.72 | no verified revisit loop | 0/2 | 0 |
| single_room | ON | 4 | 20.61 | 2.01 | no verified revisit loop | 0/0 | 0 |

## Repeatability with_ceiling vs floor_only

| drift | icp_rmse_cm | walls_pass | footprint_diff_pct |
|---|---|---|---|
| OFF | 0.95 | 2/20 | 6.42 |
| ON | 0.93 | 2/20 | 16.17 |