"""Which camera convention does DA3 extrinsics use? Test one chunk against LiDAR odometry, both ways.
uv run python scripts/da3_convention_check.py <stray_capture_dir>
"""
import sys, hashlib
from pathlib import Path
import numpy as np, cv2, pandas as pd, torch
from depth_anything_3.api import DepthAnything3

cap = Path(sys.argv[1]); fps = 3.0; ray = len(sys.argv) > 2 and sys.argv[2] == 'ray'
clip = cap / "rgb.mp4"
h = hashlib.sha1(f"{clip.resolve()}|{fps}|960".encode()).hexdigest()[:12]
imgs_p = sorted((Path("cache") / f"video_{h}" / "images").glob("*.jpg"))
v = cv2.VideoCapture(str(clip)); step = max(1, int(round(v.get(cv2.CAP_PROP_FPS) / fps)))
odo = pd.read_csv(cap / "odometry.csv", skipinitialspace=True); odo.columns = [c.strip() for c in odo.columns]


def ate(est, gt):
    mu_e, mu_g = est.mean(0), gt.mean(0); E, G = est - mu_e, gt - mu_g
    U, S, Vt = np.linalg.svd(G.T @ E / len(E)); D = np.eye(3)
    if np.linalg.det(U @ Vt) < 0: D[2, 2] = -1
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / (E ** 2).sum(1).mean()
    return np.sqrt((np.linalg.norm((s * (R @ E.T)).T + mu_g - gt, axis=1) ** 2).mean()), s


model = DepthAnything3.from_pretrained("depth-anything/DA3-LARGE-1.1").to("cuda").eval()
for start in (0, 40, 80):
    sel = list(range(start, min(start + 24, len(imgs_p))))
    imgs = [cv2.cvtColor(cv2.imread(str(imgs_p[i])), cv2.COLOR_BGR2RGB) for i in sel]
    with torch.no_grad():
        pred = model.inference(imgs, process_res=504, use_ray_pose=ray)
    E = np.array(pred.extrinsics, dtype=float)
    if E.shape[1] == 3:
        E = np.concatenate([E, np.tile([[[0, 0, 0, 1]]], (len(E), 1, 1))], 1)
    gt = odo[["x", "y", "z"]].to_numpy()[[i * step for i in sel]]
    c_w2c = np.array([np.linalg.inv(T)[:3, 3] for T in E])     # extrinsics are world->camera
    c_c2w = E[:, :3, 3]                                          # extrinsics are camera->world
    a1, s1 = ate(c_w2c, gt); a2, s2 = ate(c_c2w, gt)
    path = np.linalg.norm(np.diff(gt, axis=0), axis=1).sum()
    print(f"chunk {start}: path {path:.2f} m | as world->cam: ATE {a1*100:.1f} cm | as cam->world: ATE {a2*100:.1f} cm")
