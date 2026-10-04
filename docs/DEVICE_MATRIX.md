# Device matrix

Measured, not targets. Numbers from `benchmark/results/FINAL_RESULTS.md` (own benchmark = ARKitScenes venue 470350
with laser ground truth; sample = organisers' captures). Processing machine: Windows laptop, RTX 5050 8 GB.

| Tier | Capture hardware | Capture tool | Processing | Delivered accuracy (honest) | Interval model |
|---|---|---|---|---|---|
| LiDAR | iPhone 12 Pro or newer Pro / iPad Pro (LiDAR) | Stray Scanner | CPU, 18-32 s | cloud metric (0.8% vs laser); wall lengths median 5.0 cm on unambiguous walls, 17.8 cm over all (virtual walls / cluttered GT); doors median 11.5 cm | max(4.3% x L, 46 cm); 91% coverage vs laser (in-sample) |
| Video | any iPhone 15 or newer (no LiDAR needed) | native Camera | CUDA GPU, 6 min cold per 90 s clip | footprint -3% to -90% vs LiDAR; fails +/-3% | 97% relative; UNRELIABLE flag on implausible scale |
| Photo | any iPhone 15 or newer | native Camera, per-room folders | CUDA GPU, 30-130 s | does not stitch; 0-1 rooms recovered; fails +/-8% | 39% relative; UNRELIABLE / empty plan flagged |

Non-Pro iPhones run only the video and photo tiers. Known degraders at every tier: mirrors, glass, wet-look floors,
low light, textureless walls, tall furniture against walls.
