"""Plane extraction: floor/ceiling heights, Manhattan yaw, wall slice. World frame is ARKit y-up."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import open3d as o3d


@dataclass
class HorizontalPlanes:
    floor_y: float
    ceiling_y: float | None
    floor_spread_m: float      # robust spread of floor points (drift / tilt indicator)
    ceiling_spread_m: float | None

    @property
    def ceiling_height(self) -> float | None:
        return None if self.ceiling_y is None else self.ceiling_y - self.floor_y


def _peak_refine(y: np.ndarray, center: float, win: float = 0.06) -> tuple[float, float]:
    s = y[np.abs(y - center) < win]
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med))) * 1.4826
    return med, mad


def horizontal_planes(P: np.ndarray, cam_y: float, min_support: float = 0.02, bin_m: float = 0.01) -> HorizontalPlanes:
    """Floor = strongest y-peak below the camera; ceiling = strongest y-peak above it (if well supported)."""
    y = P[:, 1]
    h, e = np.histogram(y, bins=np.arange(y.min(), y.max() + bin_m, bin_m))
    c = (e[:-1] + e[1:]) / 2
    below, above = c < cam_y - 0.5, c > cam_y + 0.3
    floor_c = c[below][np.argmax(h[below])]
    floor_y, floor_sp = _peak_refine(y, floor_c)
    ceil_y = ceil_sp = None
    if above.any():
        i = np.argmax(h[above])
        if h[above][i] > min_support * h[below].max() * 5:     # require a real slab, not stray points
            ceil_y, ceil_sp = _peak_refine(y, c[above][i])
    return HorizontalPlanes(floor_y, ceil_y, floor_sp, ceil_sp)


def manhattan_yaw(P_wall: np.ndarray, voxel: float = 0.03) -> tuple[float, float]:
    """Dominant wall direction (radians, mod 90deg) from horizontal normals. Returns (yaw, concentration)."""
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P_wall)).voxel_down_sample(voxel)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    n = np.asarray(pcd.normals)
    n = n[np.abs(n[:, 1]) < 0.2]                       # near-vertical surfaces only
    ang = np.arctan2(n[:, 2], n[:, 0])
    a4 = np.mod(4 * ang, 2 * np.pi)                    # fold 90deg symmetry onto a circle
    z = np.mean(np.exp(1j * a4))
    yaw = float(np.angle(z) / 4)
    return yaw, float(np.abs(z))


def rotate_y(P: np.ndarray, yaw: float) -> np.ndarray:
    """Rotate about the up axis so dominant walls align with x/z."""
    c, s = np.cos(-yaw), np.sin(-yaw)
    R = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    return P @ R.T


def wall_slice(P: np.ndarray, planes: HorizontalPlanes, margin: float = 0.4) -> np.ndarray:
    top = planes.ceiling_y if planes.ceiling_y is not None else planes.floor_y + 2.2
    return P[(P[:, 1] > planes.floor_y + margin) & (P[:, 1] < top - margin)]


def refine_yaw(P_wall: np.ndarray, yaw0: float, span_deg: float = 2.0, step_deg: float = 0.02,
               bin_m: float = 0.01, max_pts: int = 300_000) -> tuple[float, dict]:
    """Refine the Manhattan yaw to ~0.02 deg by maximising wall sharpness.

    For each candidate angle, rotate the wall-band points and histogram them along x and z (1 cm bins).
    When walls are exactly axis-aligned they collapse into narrow spikes, so sum(h^2) peaks.
    The coarse normal-histogram estimate (manhattan_yaw) is only good to ~1 deg; a 0.75 deg error was
    measured between two captures of the same flat, i.e. ~5 cm at the end of a 4 m wall.
    """
    X = P_wall[:, [0, 2]]
    if len(X) > max_pts:
        X = X[np.random.default_rng(0).choice(len(X), max_pts, replace=False)]
    X = X - X.mean(0)
    best = (-1.0, yaw0)
    scores = []
    for d in np.arange(-span_deg, span_deg + 1e-9, step_deg):
        a = yaw0 + np.radians(d)
        c, s = np.cos(-a), np.sin(-a)
        xr = c * X[:, 0] - s * X[:, 1]
        zr = s * X[:, 0] + c * X[:, 1]
        sc = 0.0
        for v in (xr, zr):
            h = np.bincount(((v - v.min()) / bin_m).astype(int)).astype(float)
            sc += float((h * h).sum())
        scores.append(sc)
        if sc > best[0]:
            best = (sc, a)
    scores = np.array(scores)
    return best[1], {"delta_deg": float(np.degrees(best[1] - yaw0)),
                     "sharpness_gain": float(scores.max() / max(scores[len(scores) // 2], 1e-9))}


def estimate_yaw(P: np.ndarray, hp) -> tuple[float, dict]:
    """Coarse (normals) + fine (sharpness) Manhattan yaw. Single entry point used by every tier and tool."""
    W = wall_slice(P, hp)
    yaw0, conc = manhattan_yaw(W)
    yaw, info = refine_yaw(W, yaw0)
    info["coarse_concentration"] = conc
    return yaw, info
