import sys, numpy as np, cv2
from pathlib import Path
from roomscan.tiers.lidar import load_stray, scale_intrinsics
cap = Path(sys.argv[1])
frames = load_stray(cap, stride=30)[:60]
for name, flip in [("arkit (y up, -z fwd)", np.diag([1,-1,-1])), ("opencv (y down, +z fwd)", np.eye(3))]:
    P=[]; C=[]
    for T,(fx,fy,cx,cy),dp,cp in frames:
        d=cv2.imread(str(dp),cv2.IMREAD_UNCHANGED).astype(np.float32)/1000; c=cv2.imread(str(cp),cv2.IMREAD_UNCHANGED)
        fxd,fyd,cxd,cyd=scale_intrinsics(fx,fy,cx,cy,d.shape[1],d.shape[0])
        v,u=np.mgrid[0:d.shape[0]:4,0:d.shape[1]:4]; z=d[v,u]; m=(z>0.1)&(c[v,u]>=2)
        pc=np.stack([(u[m]-cxd)/fxd*z[m],(v[m]-cyd)/fyd*z[m],z[m]])   # opencv camera coords
        pc=flip@pc
        P.append((T[:3,:3]@pc).T+T[:3,3]); C.append(T[:3,3])
    P=np.concatenate(P); C=np.array(C); y=P[:,1]-C[:,1].mean()
    h,e=np.histogram(y,bins=np.arange(-3,3,0.02))
    top=sorted(np.argsort(h)[::-1][:4])
    print(f"{name}: y rel to cam p1={np.percentile(y,1):.2f} p99={np.percentile(y,99):.2f} peaks="+", ".join(f"{e[i]:.2f}({h[i]})" for i in top))
