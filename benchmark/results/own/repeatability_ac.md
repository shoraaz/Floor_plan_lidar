# Repeatability (LiDAR tier): ark470350_a vs ark470350_c

Registration: coarse overlap 0.862 at 0 deg, ICP fitness 0.856, inlier RMSE 0.71 cm

Footprint: 42.33 vs 40.44 m2 (diff 4.46%)

**Wall gate (<=1 cm or <=0.5%): 0/4 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.758 | 31.048 | 34.021 |
| room2 | room2 | 0.27 | 2.462 | 4.408 |
| room3 | room2 | 0.306 | 2.772 | 4.408 |
| room4 | room3 | 0.485 | 4.069 | 2.011 |
| room5 | room1 | 0.059 | 2.212 | 34.021 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 6.0909 | 7.356 | 126.51 | 1.83 | FAIL |  |
| room1 | 5.0974 | 4.625 | 47.25 | 12.33 | FAIL |  |
| room1 | 6.0909 | None | None | None | FAIL | no matching wall in B |
| room1 | 5.0974 | None | None | None | FAIL | no matching wall in B |