# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.601 at 0 deg, ICP fitness 0.581, inlier RMSE 0.95 cm

Footprint: 47.97 vs 48.38 m2 (diff 0.85%)

**Wall gate (<=1 cm or <=0.5%): 0/22 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.011 | 7.125 | 9.18 |
| room2 | room1 | 0.489 | 4.49 | 9.18 |
| room3 | room2 | 0.501 | 11.081 | 5.763 |
| room4 | room3 | 0.601 | 8.773 | 12.103 |
| room5 | room4 | 0.778 | 2.871 | 2.803 |
| room6 | room1 | 0.276 | 3.572 | 9.18 |
| room7 | room6 | 0.633 | 10.066 | 13.888 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room3 | 0.86 | 2.55 | 169.0 | 18.14 | FAIL |  |
| room3 | 0.92 | None | None | None | FAIL | no matching wall in B |
| room3 | 3.86 | None | None | None | FAIL | no matching wall in B |
| room3 | 0.92 | None | None | None | FAIL | no matching wall in B |
| room3 | 1.72 | None | None | None | FAIL | no matching wall in B |
| room3 | 2.51 | None | None | None | FAIL | no matching wall in B |
| room3 | 3.0 | None | None | None | FAIL | no matching wall in B |
| room3 | 2.51 | 2.26 | 25.0 | 10.61 | FAIL |  |
| room4 | 2.75 | None | None | None | FAIL | no matching wall in B |
| room4 | 3.19 | None | None | None | FAIL | no matching wall in B |
| room4 | 2.75 | 3.77 | 102.0 | 4.62 | FAIL |  |
| room4 | 3.19 | None | None | None | FAIL | no matching wall in B |
| room5 | 1.94 | 2.19 | 25.0 | 2.2 | FAIL |  |
| room5 | 1.48 | 1.28 | 20.0 | 4.45 | FAIL |  |
| room5 | 1.94 | 2.19 | 25.0 | 17.81 | FAIL |  |
| room5 | 1.48 | 1.28 | 20.0 | 20.53 | FAIL |  |
| room7 | 2.4 | 3.35 | 95.0 | 2.46 | FAIL |  |
| room7 | 2.81 | 3.95 | 114.0 | 2.41 | FAIL |  |
| room7 | 0.54 | None | None | None | FAIL | no matching wall in B |
| room7 | 1.13 | None | None | None | FAIL | no matching wall in B |
| room7 | 2.94 | 3.67 | 73.0 | 3.21 | FAIL |  |
| room7 | 3.94 | None | None | None | FAIL | no matching wall in B |