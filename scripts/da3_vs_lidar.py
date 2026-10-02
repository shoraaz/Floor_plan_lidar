"""Calibrate DA3METRIC-LARGE output units against LiDAR depth on the same frames.
uv run python scripts/da3_vs_lidar.py <stray_capture_dir>
"""
import sys
from pathlib import Path
import numpy as np, cv2, torch
from depth_anything_3.api import DepthAnything3
from roomscan.tiers.lidar import load_stray

cap = Path(sys.argv[1])
frames = load_stray(cap, stride=1)
vid = cv2.VideoCapture(str(cap / "rgb.mp4"))
model = DepthAnything3.from_pretrained("depth-anything/DA3METRIC-LARGE").to("cuda").eval()
idx = np.linspace(50, len(frames) - 50, 8).astype(int)
for i in idx:
    vid.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, bgr = vid.read()
    if not ok:
        continue
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        pred = model.inference([rgb])
    d = pred.depth[0]
    T, (fx, fy, cx, cy), dp, cp = frames[i]
    lid = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED).astype(np.float32) / 1000
    conf = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED)
    dd = cv2.resize(d, (lid.shape[1], lid.shape[0]), interpolation=cv2.INTER_NEAREST)
    m = (lid > 0.3) & (lid < 5) & (conf >= 2)
    ratio = np.median(lid[m] / dd[m])
    fx_proc = fx * d.shape[1] / 1920
    print(f"frame {i}: da3 shape {d.shape} is_metric={pred.is_metric} median(lidar/da3)={ratio:.4f} "
          f"fx_proc={fx_proc:.1f} fx_proc/300={fx_proc/300:.4f} rel_err_after_ratio={np.median(np.abs(lid[m]-ratio*dd[m])/lid[m]):.3f}")
