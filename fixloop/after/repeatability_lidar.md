# Repeatability (LiDAR tier): c7d28f72c6 vs 1a8384c3f6

Registration: coarse overlap 0.601 at 0 deg, ICP fitness 0.581, inlier RMSE 0.95 cm

Footprint: 57.34 vs 56.37 m2 (diff 1.69%)

**Wall gate (<=1 cm or <=0.5%): 2/25 walls pass**

## Room matching

| room A | room B | IoU | area A | area B |
|---|---|---|---|---|
| room1 | room1 | 0.863 | 12.914 | 12.674 |
| room2 | room3 | 0.693 | 9.729 | 8.062 |
| room3 | room2 | 0.692 | 9.329 | 13.238 |
| room4 | room1 | 0.0 | 7.374 | 12.674 |
| room5 | room5 | 0.855 | 7.574 | 6.649 |
| room6 | room4 | 0.449 | 5.542 | 8.436 |
| room7 | room7 | 0.811 | 2.175 | 2.488 |
| room8 | room4 | 0.184 | 1.704 | 8.436 |
| room9 | room2 | 0.102 | 1.401 | 13.238 |

## Walls (rooms with IoU >= 0.5)

| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |
|---|---|---|---|---|---|---|
| room1 | 3.27 | 3.37 | 10.0 | 4.74 | FAIL |  |
| room1 | 1.7502 | 1.25 | 50.02 | 11.22 | FAIL |  |
| room1 | 0.5102 | 0.506 | 0.42 | 12.07 | PASS |  |
| room1 | 0.72 | None | None | None | FAIL | no matching wall in B |
| room1 | 2.14 | 2.21 | 7.0 | 19.93 | FAIL |  |
| room1 | 4.37 | 3.97 | 40.0 | 5.66 | FAIL |  |
| room1 | 2.86 | 2.21 | 65.0 | 20.1 | FAIL |  |
| room2 | 0.87 | 0.8 | 7.0 | 7.87 | FAIL |  |
| room2 | 0.65 | 0.7 | 5.0 | 6.63 | FAIL |  |
| room2 | 2.14 | 3.1873 | 104.73 | 5.49 | FAIL |  |
| room2 | 3.42 | None | None | None | FAIL | no matching wall in B |
| room2 | 3.01 | None | None | None | FAIL | no matching wall in B |
| room2 | 2.77 | 2.26 | 51.0 | 11.7 | FAIL |  |
| room3 | 3.07 | None | None | None | FAIL | no matching wall in B |
| room3 | 3.0388 | 3.94 | 90.12 | 2.79 | FAIL |  |
| room3 | 3.07 | 3.36 | 29.0 | 2.72 | FAIL |  |
| room3 | 3.0388 | None | None | None | FAIL | no matching wall in B |
| room5 | 3.05 | 3.05 | 0.0 | 2.07 | PASS |  |
| room5 | 2.4832 | 2.18 | 30.32 | 1.3 | FAIL |  |
| room5 | 3.05 | None | None | None | FAIL | no matching wall in B |
| room5 | 2.4832 | 2.18 | 30.32 | 1.32 | FAIL |  |
| room7 | 1.25 | 1.49 | 24.0 | 1.11 | FAIL |  |
| room7 | 1.74 | 1.67 | 7.0 | 4.99 | FAIL |  |
| room7 | 1.25 | 1.49 | 24.0 | 5.91 | FAIL |  |
| room7 | 1.74 | 1.67 | 7.0 | 18.99 | FAIL |  |