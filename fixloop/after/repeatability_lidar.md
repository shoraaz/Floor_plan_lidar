# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.614 at 0 deg, ICP fitness 0.588, inlier RMSE 0.95 cm

Footprint: 54.51 vs 51.01 m2 (diff 6.42%)

**Wall gate (<=1 cm or <=0.5%): 2/20 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.933 | 12.155 | 12.081 |
| room2 | room3 | 0.662 | 9.966 | 7.864 |
| room3 | room2 | 0.548 | 5.989 | 9.542 |
| room4 | room5 | 0.001 | 7.302 | 7.625 |
| room5 | room4 | 0.494 | 5.566 | 7.806 |
| room6 | room5 | 0.914 | 7.626 | 7.625 |
| room7 | room7 | 0.743 | 2.375 | 2.522 |
| room8 | room1 | 0.0 | 2.187 | 12.081 |
| room9 | room5 | 0.324 | 2.473 | 7.625 |
| room10 | room4 | 0.196 | 1.68 | 7.806 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 2.864 | 2.8713 | 0.73 | 10.76 | PASS |  |
| room1 | 4.2442 | 4.2076 | 3.67 | 4.3 | FAIL |  |
| room1 | 2.864 | 2.8713 | 0.73 | 7.09 | PASS |  |
| room1 | 4.2442 | 4.2076 | 3.67 | 3.57 | FAIL |  |
| room2 | 3.4245 | 2.24 | 118.45 | 4.14 | FAIL |  |
| room2 | 2.9103 | None | None | None | FAIL | no matching wall in B |
| room2 | 3.4245 | None | None | None | FAIL | no matching wall in B |
| room2 | 2.9103 | 3.1195 | 20.92 | 5.53 | FAIL |  |
| room3 | 1.99 | 3.36 | 137.0 | 19.23 | FAIL |  |
| room3 | 3.0096 | 2.84 | 16.96 | 3.66 | FAIL |  |
| room3 | 1.99 | 3.36 | 137.0 | 2.27 | FAIL |  |
| room3 | 3.0096 | None | None | None | FAIL | no matching wall in B |
| room6 | 3.02 | 3.07 | 5.0 | 1.52 | FAIL |  |
| room6 | 2.5251 | 2.4837 | 4.14 | 7.04 | FAIL |  |
| room6 | 3.02 | 3.07 | 5.0 | 5.67 | FAIL |  |
| room6 | 2.5251 | 2.4837 | 4.14 | 12.04 | FAIL |  |
| room7 | 1.25 | 1.51 | 26.0 | 0.61 | FAIL |  |
| room7 | 1.9 | 1.67 | 23.0 | 4.21 | FAIL |  |
| room7 | 1.25 | 1.51 | 26.0 | 22.39 | FAIL |  |
| room7 | 1.9 | 1.67 | 23.0 | 21.79 | FAIL |  |