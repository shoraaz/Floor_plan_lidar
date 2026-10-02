# Device Matrix

Accuracy numbers are **targets until the benchmark runs**. Replace with measured values (from `benchmark/results/`) before submission.

| Tier | Hardware | Capture tool | Pipeline path | Walls | Ceiling | Openings | Honest interval |
|---|---|---|---|---|---|---|---|
| LiDAR | iPhone 12 Pro+ / 13-17 Pro / Pro Max (LiDAR) | Stray Scanner | depth + poses + K, pose graph | target <=1% | target <=1.5 cm | target <=2 cm on >=85% | TBD (conformal) |
| Video | iPhone 15 or newer (any, incl. non-Pro) | Native Camera 4K30 | SfM + metric depth + door prior | target <=3% | target <=4% | target <=8% | TBD |
| Photo | iPhone 15 or newer (any) | Native Camera | metric mono depth + layout + constraint stitch | target <=8% | target <=6% | target <=15% | TBD |

Notes
- Non-Pro iPhones have no LiDAR: they only run Video and Photo tiers.
- Pro-class devices can also run Video and Photo tiers (used for the same-rooms-at-all-tiers benchmark).
- Known degraders (all tiers): mirrors, glass, wet-look floors, low light, textureless white walls, clutter hiding wall/floor line.
