# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.614 at 0 deg, ICP fitness 0.588, inlier RMSE 0.95 cm

Footprint: 55.32 vs 52.43 m2 (diff 5.23%)

**Wall gate (<=1 cm or <=0.5%): 0/25 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.837 | 13.269 | 13.083 |
| room2 | room3 | 0.68 | 9.66 | 7.864 |
| room3 | room2 | 0.548 | 5.989 | 9.542 |
| room4 | room5 | 0.001 | 7.302 | 7.625 |
| room5 | room4 | 0.494 | 5.566 | 7.806 |
| room6 | room5 | 0.914 | 7.626 | 7.625 |
| room7 | room7 | 0.743 | 2.375 | 2.522 |
| room8 | room1 | 0.0 | 2.187 | 13.083 |
| room9 | room5 | 0.324 | 2.473 | 7.625 |
| room10 | room4 | 0.196 | 1.68 | 7.806 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 3.27 | 3.39 | 12.0 | 16.6 | FAIL |  |
| room1 | 1.7574 | 1.23 | 52.74 | 12.73 | FAIL |  |
| room1 | 0.92 | None | None | None | FAIL | no matching wall in B |
| room1 | 0.6674 | None | None | None | FAIL | no matching wall in B |
| room1 | 2.11 | 2.16 | 5.0 | 18.54 | FAIL |  |
| room1 | 4.36 | 3.98 | 38.0 | 4.66 | FAIL |  |
| room1 | 2.86 | 2.16 | 70.0 | 19.46 | FAIL |  |
| room2 | 0.87 | 0.85 | 2.0 | 8.73 | FAIL |  |
| room2 | 0.65 | 0.69 | 4.0 | 11.5 | FAIL |  |
| room2 | 2.12 | 3.1195 | 99.95 | 5.47 | FAIL |  |
| room2 | 3.42 | None | None | None | FAIL | no matching wall in B |
| room2 | 2.99 | None | None | None | FAIL | no matching wall in B |
| room2 | 2.77 | 2.24 | 53.0 | 12.95 | FAIL |  |
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