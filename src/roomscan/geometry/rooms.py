"""Room segmentation + rectilinear room polygons from an aligned (Manhattan) point cloud.

Pipeline (all in the Manhattan-aligned frame, x/z horizontal, y up):
  1. 2D grids: wall occupancy (points in a band above furniture), floor observations, camera path
  2. interior = filled union; free = interior minus dilated walls
  3. room cores = free cells farther than `core_m` from any wall (doorways pinch off), connected components
  4. watershed cores back into all free space -> one label per room
  5. per room: rectilinear polygon, edges snapped to the nearest wall-face peak in the raw points
  6. doors = boundaries between adjacent room labels; ceiling height per room from ceiling points over it
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


def segment(P: np.ndarray, cams: np.ndarray | None, floor_y: float, ceiling_y: float | None,
            res: float = 0.025, core_m: float = 0.5, min_room_m2: float = 1.0):
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + 1.1) & (P[:, 1] < min(top - 0.2, floor_y + 2.0))]   # above most furniture
    floor_pts = P[np.abs(P[:, 1] - floor_y) < 0.04]
    g = make_grid(P, res)

    wall = accumulate(g, band) >= 4
    wall = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    seen = accumulate(g, floor_pts) > 0
    if cams is not None and len(cams):
        cr, cc = g.idx(cams[:, 0], cams[:, 2])
        seen[np.clip(cr, 0, g.shape[0] - 1), np.clip(cc, 0, g.shape[1] - 1)] = True
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    interior = cv2.morphologyEx((seen | wall).astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool)
    interior = ndi.binary_fill_holes(interior)
    wall_d = cv2.dilate(wall.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    free = interior & ~wall_d
    free = cv2.morphologyEx(free.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)

    dist = ndi.distance_transform_edt(free) * res
    cores, n = ndi.label(dist > core_m)
    sizes = ndi.sum(np.ones_like(cores), cores, index=np.arange(1, n + 1)) * res * res
    keep = np.zeros(n + 1, int)
    j = 0
    for i, s in enumerate(sizes, 1):
        if s >= 0.15:
            j += 1; keep[i] = j
    cores = keep[cores]

    # watershed: grow cores through free space only
    markers = cores.astype(np.int32).copy()
    markers[~free] = j + 1
    img = cv2.cvtColor(np.clip(255 - dist / max(dist.max(), 1e-6) * 255, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    cv2.watershed(img, markers)
    labels = np.where((markers > 0) & (markers <= j) & free, markers, 0)

    # drop tiny rooms (merge into nothing; they become unlabelled)
    for lab in range(1, j + 1):
        if (labels == lab).sum() * res * res < min_room_m2:
            labels[labels == lab] = 0
    return g, labels, wall, free


def _rectilinear(mask: np.ndarray, g: Grid, eps_m: float = 0.12) -> list[tuple[float, float]]:
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    a = cv2.approxPolyDP(c, eps_m / g.res, True)[:, 0, :].astype(float)   # (col,row)
    # classify edges as horizontal/vertical, merge runs, rebuild vertices as axis-line intersections
    lines = []
    for i in range(len(a)):
        p, q = a[i], a[(i + 1) % len(a)]
        horiz = abs(q[0] - p[0]) >= abs(q[1] - p[1])
        val = (p[1] + q[1]) / 2 if horiz else (p[0] + q[0]) / 2
        L = abs(q[0] - p[0]) + abs(q[1] - p[1])
        if lines and lines[-1][0] == horiz:
            h, v, l0 = lines[-1]
            lines[-1] = (h, (v * l0 + val * L) / (l0 + L), l0 + L)
        else:
            lines.append((horiz, val, L))
    if len(lines) > 1 and lines[0][0] == lines[-1][0]:
        h, v, L = lines.pop()
        h0, v0, L0 = lines[0]
        lines[0] = (h0, (v0 * L0 + v * L) / (L0 + L), L0 + L)
    verts = []
    for i in range(len(lines)):
        a1, b1 = lines[i - 1], lines[i]
        if a1[0] == b1[0]:
            continue
        col = b1[1] if not b1[0] else a1[1]
        row = b1[1] if b1[0] else a1[1]
        verts.append(g.xz(row, col))
    return verts


def _snap_edges(poly, P_band: np.ndarray, search: float = 0.15, bin_m: float = 0.005):
    """Move each axis-aligned edge to the wall-face peak nearest the room side. Returns new poly + support."""
    n = len(poly)
    poly = [list(p) for p in poly]
    support = []
    cx = np.mean([p[0] for p in poly]); cz = np.mean([p[1] for p in poly])
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        horiz = abs(q[0] - p[0]) > abs(q[1] - p[1])            # edge runs along x -> wall at fixed z
        ax_fixed, ax_run = (2, 0) if horiz else (0, 2)
        fixed = p[1] if horiz else p[0]
        lo, hi = sorted([p[0], q[0]] if horiz else [p[1], q[1]])
        shrink = 0.1 * (hi - lo)
        sel = P_band[(P_band[:, ax_run] > lo + shrink) & (P_band[:, ax_run] < hi - shrink) &
                     (np.abs(P_band[:, ax_fixed] - fixed) < search)]
        if len(sel) < 30:
            support.append(0.0); continue
        h, e = np.histogram(sel[:, ax_fixed], bins=np.arange(fixed - search, fixed + search + bin_m, bin_m))
        h = ndi.uniform_filter1d(h.astype(float), 3)
        centres = (e[:-1] + e[1:]) / 2
        strong = h >= 0.5 * h.max()
        # room side: the face whose normal points toward the room centre -> peak closest to centre
        centre_coord = cz if horiz else cx
        cand = centres[strong]
        new = float(cand[np.argmin(np.abs(cand - centre_coord))])
        # coverage: fraction of edge run backed by wall points near the face
        on = sel[np.abs(sel[:, ax_fixed] - new) < 0.03][:, ax_run]
        bins = np.arange(lo, hi + 0.05, 0.05)
        cov = (np.histogram(on, bins=bins)[0] > 0).mean() if len(bins) > 1 else 0
        support.append(float(cov))
        if horiz:
            p[1] = q[1] = new
        else:
            p[0] = q[0] = new
    return [tuple(p) for p in poly], support


def _poly_area(poly):
    x = np.array([p[0] for p in poly]); z = np.array([p[1] for p in poly])
    return 0.5 * abs(np.dot(x, np.roll(z, 1)) - np.dot(z, np.roll(x, 1)))


def rooms_from_labels(g: Grid, labels: np.ndarray, P: np.ndarray, floor_y: float, ceiling_y: float | None):
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + 0.9) & (P[:, 1] < min(top - 0.15, floor_y + 2.1))]
    ceil_pts = P[np.abs(P[:, 1] - ceiling_y) < 0.08] if ceiling_y is not None else None
    rooms = []
    for lab in np.unique(labels):
        if lab == 0:
            continue
        mask = labels == lab
        mask_d = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8))   # reach the wall face
        poly = _rectilinear(mask_d, g)
        if len(poly) < 4:
            continue
        poly, support = _snap_edges(poly, band)
        lengths = [float(np.hypot(poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]))
                   for i in range(len(poly))]
        ch = cs = None
        if ceil_pts is not None:
            r, c = g.idx(ceil_pts[:, 0], ceil_pts[:, 2])
            ok = (r >= 0) & (r < g.shape[0]) & (c >= 0) & (c < g.shape[1])
            inside = np.zeros(len(ceil_pts), bool); inside[ok] = mask[r[ok], c[ok]]
            yc = ceil_pts[inside, 1]
            if len(yc) > 200:
                med = float(np.median(yc))
                ch = med - floor_y
                cs = float(np.median(np.abs(yc - med)) * 1.4826)
        rooms.append(RoomGeom(int(lab), poly, lengths, support, _poly_area(poly), ch, cs))

    # doors / adjacency: label boundaries inside free space
    for i, a in enumerate(rooms):
        ma = labels == a.label
        ring = cv2.dilate(ma.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~ma
        for b in rooms:
            if b.label == a.label:
                continue
            touch = ring & (labels == b.label)
            if touch.sum() < 4:
                continue
            rr, cc = np.nonzero(touch)
            w = max(np.ptp(rr), np.ptp(cc)) * g.res + g.res
            x, z = g.xz(rr.mean(), cc.mean())
            a.neighbours[b.label] = {"width_m": float(w), "center": (float(x), float(z))}
    return rooms


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


def segment_rays(P: np.ndarray, cams: np.ndarray, rays: list[np.ndarray], floor_y: float, ceiling_y: float | None,
                 res: float = 0.025, core_m: float = 0.5, min_room_m2: float = 1.0, min_views: int = 2):
    """Like `segment`, but free space comes from ray casting instead of floor visibility."""
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + 1.1) & (P[:, 1] < min(top - 0.2, floor_y + 2.0))]
    g = make_grid(P, res)
    wall = accumulate(g, band) >= 4
    wall = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    seen = raycast_free(g, cams, rays, floor_y, top) >= min_views
    wall_d = cv2.dilate(wall.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    free = seen & ~wall_d
    free = cv2.morphologyEx(free.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool) & ~wall_d
    free = cv2.morphologyEx(free.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)

    dist = ndi.distance_transform_edt(free) * res
    cores, n = ndi.label(dist > core_m)
    sizes = ndi.sum(np.ones_like(cores), cores, index=np.arange(1, n + 1)) * res * res
    keep = np.zeros(n + 1, int); j = 0
    for i, s in enumerate(sizes, 1):
        if s >= 0.15:
            j += 1; keep[i] = j
    cores = keep[cores]
    markers = cores.astype(np.int32).copy()
    markers[~free] = j + 1
    img = cv2.cvtColor(np.clip(255 - dist / max(dist.max(), 1e-6) * 255, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    cv2.watershed(img, markers)
    labels = np.where((markers > 0) & (markers <= j) & free, markers, 0)
    for lab in range(1, j + 1):
        m = labels == lab
        if m.sum() * res * res < min_room_m2:
            labels[m] = 0
        else:
            # fill furniture holes enclosed by the room
            labels[ndi.binary_fill_holes(m) & (labels == 0) & ~wall] = lab
    return g, labels, wall, free


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


def segment_structure(P: np.ndarray, cams: np.ndarray, rays: list[np.ndarray], floor_y: float,
                      ceiling_y: float | None, res: float = 0.025, min_room_m2: float = 1.0, min_views: int = 2,
                      band_m: tuple[float, float] = (0.95, 1.6)):
    """band_m: wall band above the floor used for segmentation. Chosen so that any walk following the
    capture protocol covers it (a low-pointed walk barely observes >1.6 m; see scripts/height_profile.py)
    while staying above most furniture (tables, beds, counters < 0.95 m)."""
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + band_m[0]) & (P[:, 1] < min(top - 0.2, floor_y + band_m[1]))]
    g = make_grid(P, res)
    wall = accumulate(g, band) >= 4
    wall = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    seen = raycast_free(g, cams, rays, floor_y, top) >= min_views
    interior = ndi.binary_fill_holes(cv2.morphologyEx((seen | wall).astype(np.uint8), cv2.MORPH_CLOSE,
                                                      np.ones((7, 7), np.uint8)).astype(bool))
    closed, doors = close_doorways(wall, res)
    wall_d = cv2.dilate(closed.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    free = interior & ~wall_d
    lab, n = ndi.label(free)          # 4-connectivity: a 1-px leak diagonal through a wall corner is not a door
    labels = np.zeros_like(lab)
    j = 0
    sizes = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) * res * res
    for i in np.argsort(-sizes):      # deterministic order: largest room first
        if sizes[i] >= min_room_m2:
            j += 1
            labels[lab == i + 1] = j
    # which rooms each doorway connects: sample both sides perpendicular to the door line
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
    return g, labels, closed, free, doors


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
