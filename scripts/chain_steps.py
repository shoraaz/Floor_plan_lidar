import sys, hashlib, numpy as np
from pathlib import Path
clip = Path(sys.argv[1]) / "rgb.mp4"
h = hashlib.sha1(f"{clip.resolve()}|3.0|960".encode()).hexdigest()[:12]
z = np.load(Path("cache") / f"video_{h}" / "da3_chain_metric.npz", allow_pickle=True)
C = np.array([np.asarray(T, float)[:3, 3] for T in z["Twc"]])
st = np.linalg.norm(np.diff(C, axis=0), axis=1)
print("frames", len(C), "path", round(st.sum(), 2), "median step", round(np.median(st), 3), "max step", round(st.max(), 3))
big = np.argsort(st)[::-1][:8]
print("largest steps at frame idx:", [(int(i), round(float(st[i]), 2)) for i in sorted(big)])
D = [np.asarray(d, float) for d in z["D"]]
print("median depth per 24 frames:", [round(float(np.median(D[i][D[i] > 0])), 2) for i in range(0, len(D), 16)])
