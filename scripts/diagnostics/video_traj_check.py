"""Video-tier trajectory check against the LiDAR (ARKit) odometry of the same clip.
uv run python scripts/diagnostics/video_traj_check.py <stray_capture_dir> [fps]
Reports: metric scale error of the video front end, and absolute trajectory error after a similarity alignment.
"""
import sys, hashlib
from pathlib import Path
import numpy as np, cv2, pandas as pd

cap = Path(sys.argv[1]); fps = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
clip = cap / "rgb.mp4"
h = hashlib.sha1(f"{clip.resolve()}|{fps}|960".encode()).hexdigest()[:12]
cd = Path("cache") / f"video_{h}"
z = np.load(cd / ("da3_chain_metric.npz" if (cd / "da3_chain_metric.npz").exists() else "da3_chain.npz"), allow_pickle=True)
Twc, scale = list(z["Twc"]), float(z["scale"])
v = cv2.VideoCapture(str(clip)); src_fps = v.get(cv2.CAP_PROP_FPS); n = int(v.get(cv2.CAP_PROP_FRAME_COUNT))
step = max(1, int(round(src_fps / fps))); idx = list(range(0, n, step))[:len(Twc)]
if (cd / "frames.json").exists():
    import json; idx = json.loads((cd / "frames.json").read_text())[:len(Twc)]
odo = pd.read_csv(cap / "odometry.csv", skipinitialspace=True); odo.columns = [c.strip() for c in odo.columns]
gt = odo[["x", "y", "z"]].to_numpy()[idx]
est = np.array([np.asarray(T, dtype=float)[:3, 3] * scale for T in Twc])
mu_e, mu_g = est.mean(0), gt.mean(0); E, G = est - mu_e, gt - mu_g
U, S, Vt = np.linalg.svd(G.T @ E / len(E)); D = np.eye(3)
if np.linalg.det(U @ Vt) < 0: D[2, 2] = -1
R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / (E ** 2).sum(1).mean()
aligned = (s * (R @ E.T)).T + mu_g
err = np.linalg.norm(aligned - gt, axis=1)
path = np.linalg.norm(np.diff(gt, axis=0), axis=1).sum()
print(f"frames {len(est)}  path {path:.2f} m")
print(f"metric scale correction needed: {s:.4f}  (1.0 = video scale already metric; error {abs(s-1)*100:.1f}%)")
print(f"ATE after sim3: rmse {np.sqrt((err**2).mean())*100:.1f} cm, max {err.max()*100:.1f} cm ({np.sqrt((err**2).mean())/path*100:.2f}% of path)")
