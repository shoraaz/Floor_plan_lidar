# Repeatability (LiDAR tier): ark470350_a vs ark470350_b

Registration: coarse overlap 0.934 at 180 deg, ICP fitness 0.826, inlier RMSE 0.69 cm

Footprint: 42.33 vs 41.76 m2 (diff 1.35%)

**Wall gate (<=1 cm or <=0.5%): 0/8 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.575 | 31.048 | 39.445 |
| room2 | room1 | 0.062 | 2.462 | 39.445 |
| room3 | room1 | 0.068 | 2.772 | 39.445 |
| room4 | room2 | 0.527 | 4.069 | 2.302 |
| room5 | room1 | 0.048 | 2.212 | 39.445 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 6.0909 | 7.9797 | 188.88 | 1.04 | FAIL |  |
| room1 | 5.0974 | None | None | None | FAIL | no matching wall in B |
| room1 | 6.0909 | None | None | None | FAIL | no matching wall in B |
| room1 | 5.0974 | None | None | None | FAIL | no matching wall in B |
| room4 | 3.3758 | None | None | None | FAIL | no matching wall in B |
| room4 | 1.2054 | None | None | None | FAIL | no matching wall in B |
| room4 | 3.3758 | 2.6954 | 68.03 | 2.84 | FAIL |  |
| room4 | 1.2054 | 0.854 | 35.14 | 3.29 | FAIL |  |