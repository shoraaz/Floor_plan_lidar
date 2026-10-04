"""Room segmentation from wall structure (Manhattan-aligned frame: x/z horizontal, y up).

segment_structure_v2:
  1. wall map from a 0.95-1.6 m band (above furniture, covered by any protocol walk)
  2. doorways = 0.6-1.3 m gaps between collinear wall runs -> closed (also recorded as doors)
  3. walls extended through UNOBSERVED space (ray-cast free space never crossed), ROSE2-style
  4. rooms = non-wall regions enclosed by structure, kept only if enough of them was observed;
     observed space leaking to the border keeps its observed extent and is flagged
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import cv2
from scipy import ndimage as ndi


@dataclass
class Grid:
    x0: float
    z0: float
    res: float
    shape: tuple[int, int]   # (rows=z, cols=x)

    def idx(self, x, z):
        return ((z - self.z0) / self.res).astype(int), ((x - self.x0) / self.res).astype(int)

    def xz(self, r, c):
        return self.x0 + (c + 0.5) * self.res, self.z0 + (r + 0.5) * self.res


@dataclass
class RoomGeom:
    label: int
    polygon: list[tuple[float, float]]          # (x, z) metres, aligned frame, CCW-ish
    wall_lengths: list[float]
    wall_support: list[float]                   # fraction of each edge backed by wall points
    area_m2: float
    ceiling_height: float | None
    ceiling_spread: float | None
    neighbours: dict = field(default_factory=dict)   # label -> door dict


def make_grid(P: np.ndarray, res: float, pad: float = 0.5) -> Grid:
    x0, z0 = P[:, 0].min() - pad, P[:, 2].min() - pad
    nx = int((P[:, 0].max() + pad - x0) / res) + 1
    nz = int((P[:, 2].max() + pad - z0) / res) + 1
    return Grid(x0, z0, res, (nz, nx))


def accumulate(g: Grid, pts: np.ndarray) -> np.ndarray:
    r, c = g.idx(pts[:, 0], pts[:, 2])
    ok = (r >= 0) & (r < g.shape[0]) & (c >= 0) & (c < g.shape[1])
    img = np.zeros(g.shape, np.int32)
    np.add.at(img, (r[ok], c[ok]), 1)
    return img


def _poly_area(poly):
    x = np.array([p[0] for p in poly]); z = np.array([p[1] for p in poly])
    return 0.5 * abs(np.dot(x, np.roll(z, 1)) - np.dot(z, np.roll(x, 1)))


def raycast_free(g: Grid, cams: np.ndarray, rays: list[np.ndarray], floor_y: float, top_y: float,
                 shorten_m: float = 0.06) -> np.ndarray:
    """Count, per cell, how many frames saw through it (2D projection of camera->hit segments)."""
    count = np.zeros(g.shape, np.uint16)
    canvas = np.zeros(g.shape, np.uint8)
    for cam, E in zip(cams, rays):
        if len(E) == 0:
            continue
        E = E[(E[:, 1] > floor_y + 0.05) & (E[:, 1] < top_y - 0.05)]
        if len(E) == 0:
            continue
        d = E[:, [0, 2]] - cam[[0, 2]]
        n = np.linalg.norm(d, axis=1, keepdims=True)
        E2 = cam[[0, 2]] + d * np.clip((n - shorten_m) / np.maximum(n, 1e-6), 0, 1)
        canvas[:] = 0
        c0 = (int((cam[0] - g.x0) / g.res), int((cam[2] - g.z0) / g.res))
        for x, z in E2:
            cv2.line(canvas, c0, (int((x - g.x0) / g.res), int((z - g.z0) / g.res)), 1, 1)
        count += canvas
    return count


# ---------------------------------------------------------------------------------------------
# Structure-only segmentation (fix loop). Rooms depend only on the wall map, not on where the
# camera stood: doorways are gaps between collinear wall runs; closing them splits the plan.
# ---------------------------------------------------------------------------------------------

def _runs(row: np.ndarray):
    """Start/end (exclusive) of True runs in a 1D bool array."""
    d = np.diff(np.r_[0, row.astype(np.int8), 0])
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def close_doorways(wall: np.ndarray, res: float, gap_min: float = 0.6, gap_max: float = 1.3,
                   min_run: float = 0.35, min_side: float = 0.10, perp_tol: float = 0.09):
    """Fill gaps of [gap_min, gap_max] m between two wall runs (each >= min_run m) along rows and columns.

    Short crossings (the thickness of a perpendicular wall) are below min_run, so a corridor's two side
    walls never count as a doorway. Returns (closed wall map, list of doorways).
    """
    closed = wall.copy()
    gmin, gmax, rmin = int(gap_min / res), int(gap_max / res), int(min_run / res)
    hits = np.zeros(wall.shape, bool)
    smin, pt = max(1, int(min_side / res)), max(1, int(perp_tol / res))
    for axis in (0, 1):
        # thicken perpendicular to the scan so slightly offset wall pieces share rows
        k = np.ones((2 * pt + 1, 1), np.uint8)
        W = cv2.dilate(wall.astype(np.uint8), k).astype(bool) if axis == 0 else \
            cv2.dilate(wall.T.astype(np.uint8).copy(), k).astype(bool)
        H = hits if axis == 0 else hits.T
        for i in range(W.shape[0]):
            s, e = _runs(W[i])
            for k2 in range(len(s) - 1):
                gap = s[k2 + 1] - e[k2]
                a, b = e[k2] - s[k2], e[k2 + 1] - s[k2 + 1]
                # one side must be a real wall run; the other may be a perpendicular wall (door at a corner)
                if gmin <= gap <= gmax and max(a, b) >= rmin and min(a, b) >= smin:
                    H[i, e[k2]:s[k2 + 1]] = True
    closed |= hits
    n, comp = cv2.connectedComponents(hits.astype(np.uint8), connectivity=8)
    doors = []
    for t in range(1, n):
        rr, cc = np.nonzero(comp == t)
        span_r, span_c = np.ptp(rr) + 1, np.ptp(cc) + 1
        width = max(span_r, span_c) * res
        if width < gap_min * 0.9:
            continue
        doors.append({"rows": (int(rr.min()), int(rr.max())), "cols": (int(cc.min()), int(cc.max())),
                      "width_m": float(width), "along": "x" if span_c >= span_r else "z"})
    return closed, doors


def extend_walls(wall: np.ndarray, seen: np.ndarray, res: float, min_len: float = 0.5, max_ext: float = 1.5) -> np.ndarray:
    """ROSE2-style structure completion: extend each straight wall run (>= min_len) along its own direction
    through UNOBSERVED cells, closing it only if it reaches another wall within max_ext. Observed free space
    is never crossed, so a seen doorway or open area is never walled off by this step."""
    out = wall.copy()
    L, E = int(min_len / res), int(max_ext / res)
    for axis in (0, 1):
        W = wall if axis == 0 else wall.T
        S = seen if axis == 0 else seen.T
        O = out if axis == 0 else out.T
        n = W.shape[1]
        for i in range(W.shape[0]):
            s, e = _runs(W[i])
            for a, b in zip(s, e):
                if b - a < L:
                    continue
                for direction in (1, -1):
                    j = b if direction == 1 else a - 1
                    path = []
                    while 0 <= j < n and len(path) <= E:
                        if W[i, j]:
                            if path:
                                O[i, path] = True
                            break
                        if S[i, j]:
                            break          # observed free space: do not cross
                        path.append(j)
                        j += direction
    return out


def segment_structure_v2(P: np.ndarray, cams: np.ndarray, rays: list[np.ndarray], floor_y: float,
                         ceiling_y: float | None, res: float = 0.025, min_room_m2: float = 1.0, min_views: int = 2,
                         band_m: tuple[float, float] = (0.95, 1.6), min_seen_frac: float = 0.25):
    """Structure-only segmentation with coverage-independent extent.

    1. wall map (protocol-covered band) -> close doorways -> extend walls through unobserved space
    2. rooms = connected non-wall regions NOT touching the map border (i.e. enclosed by structure);
       extent is the enclosed region, not the observed region
    3. an enclosed region is a room only if enough of it was actually observed (min_seen_frac)
    4. fallback: observed free space that leaks to the border (unclosed walls) keeps the observed extent,
       and is flagged so intervals can widen
    """
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + band_m[0]) & (P[:, 1] < min(top - 0.2, floor_y + band_m[1]))]
    g = make_grid(P, res)
    wall = accumulate(g, band) >= 4
    wall = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    seen = raycast_free(g, cams, rays, floor_y, top) >= min_views
    seen = cv2.morphologyEx(seen.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    closed, doors = close_doorways(wall, res)
    closed = extend_walls(closed, seen & ~closed, res)
    wall_d = cv2.dilate(closed.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    nonwall = ~wall_d
    lab, n = ndi.label(nonwall)
    border = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    labels = np.zeros_like(lab)
    leaked = np.zeros(lab.shape, bool)
    cands = []
    for i in range(1, n + 1):
        m = lab == i
        area = m.sum() * res * res
        if i in border:
            leaked |= m & seen
            continue
        seen_frac = (m & seen).sum() / max(m.sum(), 1)
        if area >= min_room_m2 and seen_frac >= min_seen_frac:
            cands.append((area, i, False))
    # fallback for observed space that is not enclosed
    if leaked.any():
        lab2, n2 = ndi.label(leaked & nonwall)
        for i in range(1, n2 + 1):
            area = (lab2 == i).sum() * res * res
            if area >= min_room_m2:
                cands.append((area, -i, True))
    j = 0
    flags = {}
    for area, i, is_leak in sorted(cands, key=lambda t: -t[0]):
        j += 1
        labels[(lab == i) if i > 0 else (lab2 == -i)] = j
        flags[j] = {"enclosed": not is_leak, "area_m2": float(area)}
    for d in doors:
        r0, r1 = d["rows"]; c0, c1 = d["cols"]
        rc, cc_ = (r0 + r1) // 2, (c0 + c1) // 2
        off = int(0.35 / res)
        if d["along"] == "x":
            sides = [(min(r1 + off, labels.shape[0] - 1), cc_), (max(r0 - off, 0), cc_)]
        else:
            sides = [(rc, min(c1 + off, labels.shape[1] - 1)), (rc, max(c0 - off, 0))]
        d["rooms"] = sorted({int(labels[s]) for s in sides if labels[s] > 0})
        d["center"] = g.xz(rc, cc_)
    return g, labels, closed, nonwall, doors, flags
