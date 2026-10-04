"""Convert an ARKitScenes raw capture into the Stray Scanner export format used by the sample data and the
walk-in test, so the unchanged `roomscan run` command processes it.

ARKitScenes raw (Apple, CC BY-NC-SA 4.0):
  lowres_wide.traj             10 Hz: ts  rx ry rz (axis-angle)  tx ty tz   -- world->camera (ARKitScenes utils
                               invert it to get camera->world); z-up world (rotated to y-up here)
  lowres_depth/<vid>_<ts>.png  256x192 uint16 mm, ~60 Hz
  confidence/<vid>_<ts>.png    0..2
  lowres_wide_intrinsics/<vid>_<ts>.pincam   "w h fx fy cx cy" for 256x192
  <vid>.mov                    RGB video
Stray format written: depth/, confidence/, odometry.csv (camera->world, quaternion, K at 1920x1440 reference),
camera_matrix.csv, rgb.mp4 (copy of the .mov, used only by the video tier), imu.csv (header only).
Each 10 Hz pose is paired with the nearest depth frame (|dt| <= 20 ms).

uv run python scripts/arkitscenes_to_stray.py <arkitscenes_video_dir> <out_dir>
"""
import sys, shutil, zipfile
from pathlib import Path
import numpy as np, cv2
from scipy.spatial.transform import Rotation as R

src, out = Path(sys.argv[1]), Path(sys.argv[2])
vid = src.name
for z in src.glob("*.zip"):
    if not (src / z.stem).exists():
        zipfile.ZipFile(z).extractall(src)


def ts_of(p: Path) -> float:
    return float(p.stem.split("_")[-1])


depths = sorted((src / "lowres_depth").glob("*.png"), key=ts_of)
dts = np.array([ts_of(p) for p in depths])
conf_dir, intr_dir = src / "confidence", src / "lowres_wide_intrinsics"
(out / "depth").mkdir(parents=True, exist_ok=True); (out / "confidence").mkdir(exist_ok=True)
rows, k, used = [], 0, set()
SCALE = 1920 / 256          # odometry/camera_matrix are expressed at the 1920x1440 reference resolution
# ARKitScenes trajectories are in a z-up world (verified: scripts/diagnostics/up_axis_check.py, camera height std 0.30 m along z,
# floor peak along z). Stray/ARKit and our backend use y-up: new = (x, z, -y).
W_ZUP_TO_YUP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
for line in (src / "lowres_wide.traj").read_text().split("\n"):
    tok = line.split()
    if len(tok) != 7:
        continue
    ts = float(tok[0])
    i = int(np.argmin(np.abs(dts - ts)))
    if abs(dts[i] - ts) > 0.020 or i in used:
        continue
    used.add(i)
    Rwc = cv2.Rodrigues(np.array(tok[1:4], float))[0]        # world -> camera
    t = np.array(tok[4:7], float)
    T = np.eye(4); T[:3, :3] = Rwc; T[:3, 3] = t
    Tcw = W_ZUP_TO_YUP @ np.linalg.inv(T)                     # camera -> world, re-expressed y-up
    dp = depths[i]
    stem = dp.name
    pin = intr_dir / dp.name.replace(".png", ".pincam")
    if not pin.exists():
        continue
    w, h, fx, fy, cx, cy = map(float, pin.read_text().split())
    shutil.copyfile(dp, out / "depth" / f"{k:06d}.png")
    cp = conf_dir / stem
    if cp.exists():
        shutil.copyfile(cp, out / "confidence" / f"{k:06d}.png")
    else:
        cv2.imwrite(str(out / "confidence" / f"{k:06d}.png"), np.full((int(h), int(w)), 2, np.uint8))
    q = R.from_matrix(Tcw[:3, :3]).as_quat()                  # x, y, z, w
    rows.append([ts, k, *Tcw[:3, 3], *q, fx * SCALE, fy * SCALE, cx * SCALE, cy * SCALE])
    k += 1
hdr = "timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy"
np.savetxt(out / "odometry.csv", np.array(rows), delimiter=", ", header=hdr, comments="",
           fmt=["%.6f", "%d"] + ["%.8f"] * 11)
K = np.array([[rows[0][9], 0, rows[0][11]], [0, rows[0][10], rows[0][12]], [0, 0, 1]])
np.savetxt(out / "camera_matrix.csv", K, delimiter=",", fmt="%.6f")
(out / "imu.csv").write_text("timestamp, a_x, a_y, a_z, alpha_x, alpha_y, alpha_z\n")
mov = src / f"{vid}.mov"
if mov.exists() and not (out / "rgb.mp4").exists():
    shutil.copyfile(mov, out / "rgb.mp4")
(out / "SOURCE.txt").write_text(f"ARKitScenes raw video {vid} (Apple, CC BY-NC-SA 4.0), converted by scripts/arkitscenes_to_stray.py\n")
print(f"{vid}: {k} frames at 10 Hz from {len(depths)} depth images; rgb.mp4={'yes' if (out / 'rgb.mp4').exists() else 'no'}")
