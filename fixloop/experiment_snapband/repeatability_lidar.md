# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.601 at 0 deg, ICP fitness 0.581, inlier RMSE 0.95 cm

Footprint: 61.49 vs 55.22 m2 (diff 10.20%)

**Wall gate (<=1 cm or <=0.5%): 2/25 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.869 | 12.874 | 12.674 |
| room2 | room3 | 0.693 | 9.75 | 8.094 |
| room3 | room1 | 0.0 | 12.182 | 12.674 |
| room4 | room2 | 0.595 | 8.043 | 13.272 |
| room5 | room5 | 0.772 | 6.903 | 6.618 |
| room6 | room4 | 0.451 | 5.519 | 8.445 |
| room7 | room7 | 0.787 | 2.195 | 2.505 |
| room8 | room4 | 0.182 | 1.68 | 8.445 |
| room9 | room2 | 0.167 | 2.343 | 13.272 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 3.26 | 3.37 | 11.0 | 5.12 | FAIL |  |
| room1 | 1.7555 | 1.25 | 50.55 | 10.85 | FAIL |  |
| room1 | 0.5055 | 0.506 | 0.05 | 11.7 | PASS |  |
| room1 | 0.73 | None | None | None | FAIL | no matching wall in B |
| room1 | 2.14 | 2.21 | 7.0 | 16.4 | FAIL |  |
| room1 | 4.33 | 3.97 | 36.0 | 5.04 | FAIL |  |
| room1 | 2.87 | 2.21 | 66.0 | 19.64 | FAIL |  |
| room2 | 0.87 | 0.8 | 7.0 | 8.01 | FAIL |  |
| room2 | 0.66 | 0.71 | 5.0 | 6.62 | FAIL |  |
| room2 | 2.14 | 3.1873 | 104.73 | 5.63 | FAIL |  |
| room2 | 3.43 | None | None | None | FAIL | no matching wall in B |
| room2 | 3.01 | None | None | None | FAIL | no matching wall in B |
| room2 | 2.77 | 2.26 | 51.0 | 11.68 | FAIL |  |
| room4 | 3.07 | None | None | None | FAIL | no matching wall in B |
| room4 | 2.62 | 3.95 | 133.0 | 2.58 | FAIL |  |
| room4 | 3.07 | 3.36 | 29.0 | 2.72 | FAIL |  |
| room4 | 2.62 | None | None | None | FAIL | no matching wall in B |
| room5 | 3.05 | 3.05 | 0.0 | 23.07 | PASS |  |
| room5 | 2.2632 | 2.17 | 9.32 | 1.29 | FAIL |  |
| room5 | 3.05 | None | None | None | FAIL | no matching wall in B |
| room5 | 2.2632 | 2.17 | 9.32 | 1.32 | FAIL |  |
| room7 | 1.24 | 1.5 | 26.0 | 0.09 | FAIL |  |
| room7 | 1.77 | 1.67 | 10.0 | 5.08 | FAIL |  |
| room7 | 1.24 | 1.5 | 26.0 | 9.93 | FAIL |  |
| room7 | 1.77 | 1.67 | 10.0 | 20.91 | FAIL |  |