"""Snap room labels to an arrangement of measured wall-face lines.

Wall faces show up as sharp peaks when wall-band points are histogrammed along x (for walls of
constant x) and z. Lines at those peaks cut the plan into rectangular cells; each cell joins the
room label covering most of it. Room polygons are unions of cells, so every edge lies on a
measured wall face (not on a morphology artefact). Thin cells between the two faces of a wall stay empty.
"""
from __future__ import annotations
import numpy as np
import cv2
from scipy.signal import find_peaks
from scipy import ndimage as ndi

from .rooms import Grid, RoomGeom, _poly_area


def face_lines(P_band: np.ndarray, axis: int, bin_m: float = 0.01, min_frac: float = 0.03) -> np.ndarray:
    v = P_band[:, axis]
    h, e = np.histogram(v, bins=np.arange(v.min() - 0.05, v.max() + 0.05, bin_m))
    h = ndi.gaussian_filter1d(h.astype(float), 1.0)
    pk, _ = find_peaks(h, prominence=min_frac * h.max(), distance=int(0.06 / bin_m))
    return (e[pk] + e[pk + 1]) / 2


def snap_rooms(g: Grid, labels: np.ndarray, P: np.ndarray, floor_y: float, ceiling_y: float | None,
               wall: np.ndarray | None = None, min_cover: float = 0.5, min_room_m2: float = 1.0):
    """wall: boolean wall-occupancy grid; wall pixels are neutral when voting a cell's room."""
    top = ceiling_y if ceiling_y is not None else floor_y + 2.3
    band = P[(P[:, 1] > floor_y + 0.9) & (P[:, 1] < min(top - 0.15, floor_y + 2.1))]
    xs = face_lines(band, 0)
    zs = face_lines(band, 2)
    xb = np.concatenate([[g.x0], xs, [g.x0 + g.shape[1] * g.res]])
    zb = np.concatenate([[g.z0], zs, [g.z0 + g.shape[0] * g.res]])
    cb = np.clip(((xb - g.x0) / g.res).round().astype(int), 0, g.shape[1])
    rb = np.clip(((zb - g.z0) / g.res).round().astype(int), 0, g.shape[0])

    nl = labels.max()
    cell_lab = np.zeros((len(zb) - 1, len(xb) - 1), int)
    for i in range(len(rb) - 1):
        for j in range(len(cb) - 1):
            blk = labels[rb[i]:rb[i + 1], cb[j]:cb[j + 1]]
            if blk.size == 0:
                continue
            if wall is not None:
                wb = wall[rb[i]:rb[i + 1], cb[j]:cb[j + 1]]
                blk = blk[~wb]
                if blk.size < 0.3 * wb.size:      # mostly wall: this is a wall slab, not floor
                    continue
            cnt = np.bincount(blk.ravel(), minlength=nl + 1)
            lab = int(np.argmax(cnt[1:]) + 1) if nl else 0
            if nl and cnt[lab] >= min_cover * blk.size:
                cell_lab[i, j] = lab

    ceil_pts = P[np.abs(P[:, 1] - ceiling_y) < 0.08] if ceiling_y is not None else None
    rooms = []
    for lab in np.unique(cell_lab):
        if lab == 0:
            continue
        cm = (cell_lab == lab).astype(np.uint8)
        n, comp = cv2.connectedComponents(cm, connectivity=4)
        if n > 2:   # keep largest component
            sizes = [(comp == k).sum() for k in range(1, n)]
            cm = (comp == 1 + int(np.argmax(sizes))).astype(np.uint8)
        # contour in cell-index space -> vertices are cell corners -> map to line coords
        up = cv2.resize(cm, (cm.shape[1] * 4, cm.shape[0] * 4), interpolation=cv2.INTER_NEAREST)
        up = np.pad(up, 1)
        cs, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)[:, 0, :]
        poly = []
        for col, row in c:
            # pixel corner -> nearest cell boundary index
            jx = int(round((col - 1) / 4)); iz = int(round((row - 1) / 4))
            jx = min(max(jx, 0), len(xb) - 1); iz = min(max(iz, 0), len(zb) - 1)
            pt = (float(xb[jx]), float(zb[iz]))
            if not poly or pt != poly[-1]:
                poly.append(pt)
        poly = _clean(poly)
        if len(poly) < 4:
            continue
        area = _poly_area(poly)
        if area < min_room_m2:
            continue
        lengths, support = [], []
        for k in range(len(poly)):
            p, q = poly[k], poly[(k + 1) % len(poly)]
            L = abs(q[0] - p[0]) + abs(q[1] - p[1])
            lengths.append(float(L))
            support.append(_support(band, p, q))
        ch = cs_ = None
        if ceil_pts is not None:
            m = labels == lab
            r, cc = g.idx(ceil_pts[:, 0], ceil_pts[:, 2])
            ok = (r >= 0) & (r < g.shape[0]) & (cc >= 0) & (cc < g.shape[1])
            inside = np.zeros(len(ceil_pts), bool); inside[ok] = m[r[ok], cc[ok]]
            yc = ceil_pts[inside, 1]
            if len(yc) > 200:
                med = float(np.median(yc)); ch = med - floor_y
                cs_ = float(np.median(np.abs(yc - med)) * 1.4826)
        rooms.append(RoomGeom(int(lab), poly, lengths, support, area, ch, cs_))
    return rooms, xs, zs, cell_lab


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
