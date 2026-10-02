"""Drift accountability (automatic fail if poses are used as-is).

Approach: pose graph over keyframes.
  - odometry edges from consecutive poses
  - loop-closure edges from revisited places (ICP / feature match)
  - plane-anchored constraints: wall planes re-observed later must coincide;
    Manhattan prior forces walls to be orthogonal / parallel
Solve (Open3D pose-graph optimisation or scipy least squares).
Expose `correct(poses, ...)` and log stitched footprint with correction ON and OFF
for the ablation table in the report (use `roomscan run --no-drift-correction`).
"""
def correct(poses, observations=None):
    raise NotImplementedError
