# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.619 at 0 deg, ICP fitness 0.601, inlier RMSE 0.93 cm

Footprint: 55.47 vs 45.33 m2 (diff 18.28%)

**Wall gate (<=1 cm or <=0.5%): 4/24 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.897 | 12.473 | 11.42 |
| room2 | room3 | 0.639 | 9.45 | 6.948 |
| room3 | room2 | 0.918 | 8.388 | 8.613 |
| room4 | room4 | 0.465 | 5.036 | 5.99 |
| room5 | room1 | 0.0 | 3.424 | 11.42 |
| room6 | room5 | 0.505 | 3.291 | 5.411 |
| room7 | room5 | 0.919 | 5.364 | 5.411 |
| room8 | room1 | 0.0 | 5.928 | 11.42 |
| room9 | room7 | 0.84 | 2.411 | 2.526 |
| room10 | room1 | 0.0 | 1.951 | 11.42 |
| room11 | room4 | 0.236 | 1.756 | 5.99 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 2.8694 | 2.8713 | 0.19 | 24.26 | PASS |  |
| room1 | 4.3471 | 3.9773 | 36.98 | 3.09 | FAIL |  |
| room1 | 2.8694 | 2.8713 | 0.19 | 12.74 | PASS |  |
| room1 | 4.3471 | 3.9773 | 36.98 | 2.91 | FAIL |  |
| room2 | 3.1429 | 2.2859 | 85.7 | 27.98 | FAIL |  |
| room2 | 3.0068 | None | None | None | FAIL | no matching wall in B |
| room2 | 3.1429 | 2.1904 | 95.25 | 28.64 | FAIL |  |
| room2 | 3.0068 | 3.1215 | 11.47 | 5.27 | FAIL |  |
| room3 | 2.6399 | 2.5953 | 4.46 | 17.69 | FAIL |  |
| room3 | 3.1773 | 3.3188 | 14.14 | 0.13 | FAIL |  |
| room3 | 2.6399 | 2.5953 | 4.46 | 3.56 | FAIL |  |
| room3 | 3.1773 | 3.3188 | 14.14 | 4.6 | FAIL |  |
| room6 | 1.5983 | 1.7093 | 11.1 | 2.94 | FAIL |  |
| room6 | 2.0593 | 3.1657 | 110.64 | 27.56 | FAIL |  |
| room6 | 1.5983 | None | None | None | FAIL | no matching wall in B |
| room6 | 2.0593 | 3.1657 | 110.64 | 16.46 | FAIL |  |
| room7 | 1.7053 | 1.7093 | 0.41 | 2.92 | PASS |  |
| room7 | 3.1454 | 3.1657 | 2.03 | 4.96 | FAIL |  |
| room7 | 1.7053 | 1.7093 | 0.41 | 4.93 | PASS |  |
| room7 | 3.1454 | 3.1657 | 2.03 | 5.36 | FAIL |  |
| room9 | 1.3613 | 1.5175 | 15.62 | 0.85 | FAIL |  |
| room9 | 1.7714 | 1.6646 | 10.68 | 8.75 | FAIL |  |
| room9 | 1.3613 | 1.5175 | 15.62 | 11.53 | FAIL |  |
| room9 | 1.7714 | 1.6646 | 10.68 | 6.86 | FAIL |  |