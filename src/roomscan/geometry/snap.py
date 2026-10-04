"""Room outlines snapped to measured wall faces.

snap_rooms_rect (used by the backend): each room modelled as an axis-aligned rectangle whose sides are snapped
independently to the ROOM-SIDE wall face (sub-cm median of face points). Rooms filling < 80% of that rectangle fall
back to a rectilinear outline from per-room wall lines (snap_rooms_local), whose edges are then also moved onto the
room-side face (_refine_rectilinear): laser ground truth showed the fallback could include a wall's thickness.
"""
from __future__ import annotations
import numpy as np
import cv2
from scipy.signal import find_peaks
from scipy import ndimage as ndi

from .rooms import Grid, RoomGeom, _poly_area


def _clean(poly):
    """Drop duplicate and collinear vertices."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        if b == a:
            continue
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            continue
        out.append(b)
    return out


def _support(band, p, q, tol=0.03, step=0.05):
    horiz = p[1] == q[1]
    ax_fixed, ax_run = (2, 0) if horiz else (0, 2)
    fixed = p[1] if horiz else p[0]
    lo, hi = sorted([p[0], q[0]] if horiz else [p[1], q[1]])
    if hi - lo < step:
        return 0.0
    sel = band[(np.abs(band[:, ax_fixed] - fixed) < tol) & (band[:, ax_run] > lo) & (band[:, ax_run] < hi)]
    bins = np.arange(lo, hi + step, step)
    return float((np.histogram(sel[:, ax_run], bins=bins)[0] > 2).mean())


def snap_rooms_local(g: Grid, labels: np.ndarray, P: np.ndarray, floor_y: float, ceiling_y: float | None,
                     wall: np.ndarray, ring_m: float = 0.35, inner_m: float = 0.10, min_cover: float = 0.5,
                     min_room_m2: float = 1.0, prom: float = 0.15, band_m: tuple[float, float] = (0.9, 2.1)):
    """Per-room snapping: wall-face lines come only from wall points in a ring around THIS room,
    so furniture and other rooms' walls cannot add spurious edges."""
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + band_m[0]) & (P[:, 1] < min(top - 0.15, floor_y + band_m[1]))]
    br, bc = g.idx(band[:, 0], band[:, 2])
    okb = (br >= 0) & (br < g.shape[0]) & (bc >= 0) & (bc < g.shape[1])
    band, br, bc = band[okb], br[okb], bc[okb]
    ceil_pts = P[np.abs(P[:, 1] - ceiling_y) < 0.08] if ceiling_y is not None else None
    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(ring_m / g.res) + 1,) * 2)
    k_in = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(inner_m / g.res) + 1,) * 2)
    rooms = []
    for lab in np.unique(labels):
        if lab == 0:
            continue
        m = (labels == lab).astype(np.uint8)
        if m.sum() * g.res ** 2 < min_room_m2:
            continue
        ring = cv2.dilate(m, k_out).astype(bool) & ~cv2.erode(m, k_in).astype(bool)
        pts = band[ring[br, bc]]
        if len(pts) < 200:
            continue
        lines = []
        for axis in (0, 2):
            v = pts[:, axis]
            h, e = np.histogram(v, bins=np.arange(v.min() - 0.05, v.max() + 0.06, 0.01))
            h = ndi.gaussian_filter1d(h.astype(float), 1.0)
            pk, _ = find_peaks(h, prominence=prom * h.max(), distance=6)
            lines.append((e[pk] + e[pk + 1]) / 2)
        rr, cc = np.nonzero(m)
        x_lo, z_lo = g.xz(rr.min(), cc.min()); x_hi, z_hi = g.xz(rr.max(), cc.max())
        xb = np.unique(np.concatenate([[x_lo - ring_m], lines[0], [x_hi + ring_m]]))
        zb = np.unique(np.concatenate([[z_lo - ring_m], lines[1], [z_hi + ring_m]]))
        cb = np.clip(((xb - g.x0) / g.res).round().astype(int), 0, g.shape[1])
        rb = np.clip(((zb - g.z0) / g.res).round().astype(int), 0, g.shape[0])
        cells = np.zeros((len(zb) - 1, len(xb) - 1), np.uint8)
        for i in range(len(rb) - 1):
            for j in range(len(cb) - 1):
                blk = m[rb[i]:rb[i + 1], cb[j]:cb[j + 1]]
                wb = wall[rb[i]:rb[i + 1], cb[j]:cb[j + 1]]
                if blk.size == 0:
                    continue
                nonwall = blk[~wb]
                if nonwall.size < 0.3 * blk.size:
                    continue
                if nonwall.mean() >= min_cover:
                    cells[i, j] = 1
        n, comp = cv2.connectedComponents(cells, connectivity=4)
        if n < 2:
            continue
        if n > 2:
            sizes = [(comp == t).sum() for t in range(1, n)]
            cells = (comp == 1 + int(np.argmax(sizes))).astype(np.uint8)
        up = np.pad(cv2.resize(cells, (cells.shape[1] * 4, cells.shape[0] * 4), interpolation=cv2.INTER_NEAREST), 1)
        cs, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        poly = []
        for col, row in max(cs, key=cv2.contourArea)[:, 0, :]:
            jx = min(max(int(round((col - 1) / 4)), 0), len(xb) - 1)
            iz = min(max(int(round((row - 1) / 4)), 0), len(zb) - 1)
            pt = (float(xb[jx]), float(zb[iz]))
            if not poly or pt != poly[-1]:
                poly.append(pt)
        poly = _clean(poly)
        if len(poly) < 4 or _poly_area(poly) < min_room_m2:
            continue
        lengths = [float(abs(poly[(t + 1) % len(poly)][0] - poly[t][0]) + abs(poly[(t + 1) % len(poly)][1] - poly[t][1]))
                   for t in range(len(poly))]
        support = [_support(pts, poly[t], poly[(t + 1) % len(poly)]) for t in range(len(poly))]
        ch = cs_ = None
        if ceil_pts is not None:
            r2, c2 = g.idx(ceil_pts[:, 0], ceil_pts[:, 2])
            ok = (r2 >= 0) & (r2 < g.shape[0]) & (c2 >= 0) & (c2 < g.shape[1])
            inside = np.zeros(len(ceil_pts), bool); inside[ok] = m[r2[ok], c2[ok]].astype(bool)
            yc = ceil_pts[inside, 1]
            if len(yc) > 200:
                med = float(np.median(yc)); ch = med - floor_y
                cs_ = float(np.median(np.abs(yc - med)) * 1.4826)
        rooms.append(RoomGeom(int(lab), poly, lengths, support, _poly_area(poly), ch, cs_))
    return rooms


def _face_near(pts: np.ndarray, axis: int, run_axis: int, run_lo: float, run_hi: float, guess: float,
               interior_sign: int, win: float = 0.35, bin_m: float = 0.01, strong: float = 0.15):
    """Pick the wall face near `guess` along `axis`, using points whose run coordinate lies inside the room.

    Among strong histogram peaks in [guess-win, guess+win], return the one closest to the room interior
    (interior_sign=+1 means the room lies at larger coordinates). That is the room-side face, the surface a
    tape measure touches; the far face of the same wall is ignored. Returns (face, support) or (None, 0).
    """
    shrink = 0.15 * (run_hi - run_lo)
    sel = pts[(pts[:, run_axis] > run_lo + shrink) & (pts[:, run_axis] < run_hi - shrink) &
              (np.abs(pts[:, axis] - guess) < win)]
    if len(sel) < 40:
        return None, 0.0
    v = sel[:, axis]
    edges = np.arange(guess - win, guess + win + bin_m, bin_m)
    h, _ = np.histogram(v, bins=edges)
    h = ndi.gaussian_filter1d(h.astype(float), 1.0)
    pk, _ = find_peaks(h, height=strong * h.max(), distance=4)
    if len(pk) == 0:
        return None, 0.0
    centres = (edges[pk] + edges[pk + 1]) / 2
    face = float(centres.max() if interior_sign > 0 else centres.min())
    # refine: median of points within 2 cm of the chosen peak (sub-bin precision)
    near = v[np.abs(v - face) < 0.02]
    face = float(np.median(near)) if len(near) > 10 else face
    on = sel[np.abs(sel[:, axis] - face) < 0.03][:, run_axis]
    b = np.arange(run_lo + shrink, run_hi - shrink + 0.05, 0.05)
    support = float((np.histogram(on, bins=b)[0] > 2).mean()) if len(b) > 1 else 0.0
    return face, support


def snap_rooms_rect(g: Grid, labels: np.ndarray, P: np.ndarray, floor_y: float, ceiling_y: float | None,
                    wall: np.ndarray, min_fill: float = 0.80, min_room_m2: float = 1.0,
                    band_m: tuple[float, float] = (0.95, 1.6)):
    """Rectangle-first room extraction (stable across captures).

    Each room is first modelled as an axis-aligned rectangle whose four sides are snapped independently to
    the room-side wall face (sub-cm median of the face points). Only if the room mask fills less than
    `min_fill` of that rectangle (an L-shape or similar) do we fall back to the rectilinear cell polygon,
    and the room is flagged. Few free parameters -> the same flat gives the same numbers on every walk.
    """
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + band_m[0]) & (P[:, 1] < min(top - 0.15, floor_y + band_m[1]))]
    ceil_pts = P[np.abs(P[:, 1] - ceiling_y) < 0.08] if ceiling_y is not None else None
    fallback = {r.label: r for r in snap_rooms_local(g, labels, P, floor_y, ceiling_y, wall)}
    rooms, shapes = [], {}
    for lab in np.unique(labels):
        if lab == 0:
            continue
        m = labels == lab
        if m.sum() * g.res ** 2 < min_room_m2:
            continue
        rr, cc = np.nonzero(m)
        xs = g.x0 + (cc + 0.5) * g.res; zs = g.z0 + (rr + 0.5) * g.res
        xl, xr = np.percentile(xs, 1), np.percentile(xs, 99)
        zb, zt = np.percentile(zs, 1), np.percentile(zs, 99)
        L, sL = _face_near(band, 0, 2, zb, zt, xl, +1)
        R, sR = _face_near(band, 0, 2, zb, zt, xr, -1)
        B, sB = _face_near(band, 2, 0, xl, xr, zb, +1)
        T, sT = _face_near(band, 2, 0, xl, xr, zt, -1)
        L = xl if L is None else L; R = xr if R is None else R
        B = zb if B is None else B; T = zt if T is None else T
        rect_area = max((R - L) * (T - B), 1e-6)
        fill = m.sum() * g.res ** 2 / rect_area
        if fill < min_fill and lab in fallback:
            fb = fallback[lab]
            fb.polygon, fb.wall_support = _refine_rectilinear(fb.polygon, band)
            n_ = len(fb.polygon)
            fb.wall_lengths = [float(abs(fb.polygon[(t + 1) % n_][0] - fb.polygon[t][0]) +
                                     abs(fb.polygon[(t + 1) % n_][1] - fb.polygon[t][1])) for t in range(n_)]
            fb.area_m2 = float(_poly_area(fb.polygon))
            rooms.append(fb); shapes[lab] = {"shape": "rectilinear", "fill": float(fill)}
            continue
        poly = [(L, B), (R, B), (R, T), (L, T)]
        lengths = [R - L, T - B, R - L, T - B]
        support = [sB, sR, sT, sL]
        ch = cs_ = None
        if ceil_pts is not None:
            r2, c2 = g.idx(ceil_pts[:, 0], ceil_pts[:, 2])
            ok = (r2 >= 0) & (r2 < g.shape[0]) & (c2 >= 0) & (c2 < g.shape[1])
            inside = np.zeros(len(ceil_pts), bool); inside[ok] = m[r2[ok], c2[ok]]
            yc = ceil_pts[inside, 1]
            if len(yc) > 200:
                med = float(np.median(yc)); ch = med - floor_y
                cs_ = float(np.median(np.abs(yc - med)) * 1.4826)
        rooms.append(RoomGeom(int(lab), poly, [float(x) for x in lengths], support, float(rect_area), ch, cs_))
        shapes[lab] = {"shape": "rectangle", "fill": float(fill)}
    return rooms, shapes


def _refine_rectilinear(poly, band, min_edge: float = 0.4):
    """Move every axis-aligned edge (>= min_edge) of a rectilinear room outline onto the room-side wall face.
    The cell-voting outline can include a wall's thickness (cells between its two faces); laser ground truth showed
    such edges ~20 cm outside the room-side face."""
    from shapely.geometry import Polygon as SP, Point as SPt
    P = [list(p) for p in poly]
    shp = SP(poly)
    n = len(P)
    support = [0.0] * n
    for i in range(n):
        p, q = P[i], P[(i + 1) % n]
        L = abs(q[0] - p[0]) + abs(q[1] - p[1])
        if L < min_edge:
            continue
        horiz = abs(q[1] - p[1]) < abs(q[0] - p[0])
        mx, mz = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        # interior side: step 5 cm along the edge normal and test containment
        if horiz:
            sign = +1 if shp.contains(SPt(mx, mz + 0.05)) else -1
            face, sup = _face_near(band, 2, 0, min(p[0], q[0]), max(p[0], q[0]), p[1], sign)
            if face is not None:
                p[1] = q[1] = face
        else:
            sign = +1 if shp.contains(SPt(mx + 0.05, mz)) else -1
            face, sup = _face_near(band, 0, 2, min(p[1], q[1]), max(p[1], q[1]), p[0], sign)
            if face is not None:
                p[0] = q[0] = face
        support[i] = sup
    return [tuple(p) for p in P], support