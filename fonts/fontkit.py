"""Общие инструменты для сборки шрифтов SWAG: геометрия контуров и запись TTF.

Без внешних геометрических библиотек: прямоугольники объединяются через сетку,
углы скругляются квадратичными кривыми (родной формат TrueType).
"""
import math

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

Point = tuple[float, float]
Contour = list[Point]


# ---------------------------------------------------------------- объединение прямоугольников

def union_rects(rects: list[tuple[float, float, float, float]]) -> list[Contour]:
    """Точное объединение прямоугольников (x0, y0, x1, y1).

    Возвращает замкнутые контуры: внешние по часовой стрелке, дырки — против (как требует TrueType).
    """
    xs = sorted({v for r in rects for v in (r[0], r[2])})
    ys = sorted({v for r in rects for v in (r[1], r[3])})

    def filled(i: int, j: int) -> bool:
        if not (0 <= i < len(xs) - 1 and 0 <= j < len(ys) - 1):
            return False
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        return any(r[0] < cx < r[2] and r[1] < cy < r[3] for r in rects)

    grid = {(i, j): filled(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)}
    edges: dict[Point, list[Point]] = {}

    def add(a: Point, b: Point) -> None:
        edges.setdefault(a, []).append(b)

    # обход по часовой стрелке (y вверх): заливка всегда справа от направления движения
    for (i, j), on in grid.items():
        if not on:
            continue
        x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
        if not grid.get((i, j - 1)):
            add((x1, y0), (x0, y0))      # низ — влево
        if not grid.get((i - 1, j)):
            add((x0, y0), (x0, y1))      # левый край — вверх
        if not grid.get((i, j + 1)):
            add((x0, y1), (x1, y1))      # верх — вправо
        if not grid.get((i + 1, j)):
            add((x1, y1), (x1, y0))      # правый край — вниз

    contours = []
    while edges:
        start = next(iter(edges))
        loop, cur, prev_dir = [start], start, None
        while True:
            outs = edges[cur]
            # в точке касания углов выбираем самый правый поворот, чтобы не склеить контуры
            if len(outs) > 1 and prev_dir:
                outs.sort(key=lambda p: _turn(prev_dir, (p[0] - cur[0], p[1] - cur[1])))
            nxt = outs.pop(0)
            if not outs:
                del edges[cur]
            prev_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
            cur = nxt
            if cur == start:
                break
            loop.append(cur)
        contours.append(_merge_collinear(loop))
    return contours


def _turn(d1: Point, d2: Point) -> float:
    return d1[0] * d2[1] - d1[1] * d2[0]  # < 0 — поворот направо


def _merge_collinear(loop: Contour) -> Contour:
    out = []
    n = len(loop)
    for k in range(n):
        a, b, c = loop[k - 1], loop[k], loop[(k + 1) % n]
        d1, d2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        if abs(_turn(d1, d2)) / (l1 * l2) > 1e-6:
            out.append(b)
    return out


def union_shapes(shapes: list[list[Contour]], eps: float = 1e-6) -> list[Contour]:
    """Объединение произвольных многоугольников с прямыми рёбрами.

    shapes — список фигур, каждая фигура — список контуров (внешние по часовой, дырки против).
    Рёбра режутся во всех точках пересечения; остаются куски, лежащие на внешней границе объединения.
    """
    edges = []  # (a, b, shape_index)
    for si, shape in enumerate(shapes):
        for c in shape:
            for k in range(len(c)):
                edges.append((c[k], c[(k + 1) % len(c)], si))

    def inter(p, p2, q, q2):
        r = (p2[0] - p[0], p2[1] - p[1])
        s = (q2[0] - q[0], q2[1] - q[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            return None
        qp = (q[0] - p[0], q[1] - p[1])
        t = (qp[0] * s[1] - qp[1] * s[0]) / den
        u = (qp[0] * r[1] - qp[1] * r[0]) / den
        if -eps <= t <= 1 + eps and -eps <= u <= 1 + eps:
            return t
        return None

    def on_segment(pt, a, b) -> float | None:
        """Параметр t, если pt лежит на отрезке ab."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln2 = dx * dx + dy * dy
        if ln2 == 0:
            return None
        t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / ln2
        if not (-eps <= t <= 1 + eps):
            return None
        px, py = a[0] + t * dx, a[1] + t * dy
        return t if math.hypot(px - pt[0], py - pt[1]) < 1e-4 else None

    pieces = []
    for i, (a, b, si) in enumerate(edges):
        ts = {0.0, 1.0}
        for j, (c, d, sj) in enumerate(edges):
            if sj == si:
                continue
            t = inter(a, b, c, d)
            if t is not None:
                ts.add(min(1.0, max(0.0, t)))
            for pt in (c, d):  # концы чужих рёбер на нашем ребре (в т.ч. при наложении)
                t = on_segment(pt, a, b)
                if t is not None:
                    ts.add(min(1.0, max(0.0, t)))
        ts = sorted(ts)
        for t0, t1 in zip(ts, ts[1:]):
            if t1 - t0 < 1e-9:
                continue
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            pieces.append((p0, p1, si))

    def winding(pt, shape) -> int:
        w = 0
        for c in shape:
            for k in range(len(c)):
                a, b = c[k], c[(k + 1) % len(c)]
                if a[1] <= pt[1] < b[1] or b[1] <= pt[1] < a[1]:
                    x = a[0] + (pt[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                    if x > pt[0]:
                        w += 1 if b[1] > a[1] else -1
        return w

    kept = []
    for p0, p1, si in pieces:
        m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        keep = True
        for sj, shape in enumerate(shapes):
            if sj == si:
                continue
            # ребро на границе другой фигуры: совпадающее направление — оставляем одно, встречное — оба убираем
            on_border = None
            for c in shape:
                for k in range(len(c)):
                    a, b = c[k], c[(k + 1) % len(c)]
                    if on_segment(m, a, b) is not None:
                        same = (b[0] - a[0]) * (p1[0] - p0[0]) + (b[1] - a[1]) * (p1[1] - p0[1]) > 0
                        on_border = same
            if on_border is not None:
                if not on_border or sj < si:
                    keep = False
                    break
                continue
            if winding(m, shape) != 0:
                keep = False
                break
        if keep:
            kept.append((p0, p1))

    def key(p):
        return (round(p[0], 4), round(p[1], 4))

    out_edges: dict = {}
    for p0, p1 in kept:
        out_edges.setdefault(key(p0), []).append((key(p1), p0, p1))

    contours = []
    while out_edges:
        start = next(iter(out_edges))
        loop, cur, prev_dir = [], start, None
        for _ in range(100000):
            outs = out_edges.get(cur)
            if not outs:
                break
            if len(outs) > 1 and prev_dir:
                outs.sort(key=lambda o: _turn(prev_dir, (o[2][0] - o[1][0], o[2][1] - o[1][1])))
            nk, p0, p1 = outs.pop(0)
            if not outs:
                del out_edges[cur]
            loop.append(p0)
            prev_dir = (p1[0] - p0[0], p1[1] - p0[1])
            cur = nk
            if cur == start:
                break
        if len(loop) >= 3:
            merged = _merge_collinear(loop)
            if len(merged) >= 3:
                contours.append(merged)
    return contours


def orient_cw(contour: Contour) -> Contour:
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(contour, contour[1:] + contour[:1]))
    return contour if area < 0 else contour[::-1]


# ---------------------------------------------------------------- скругление углов

Segment = tuple  # ("L", p) | ("Q", ctrl, p)


def round_contour(contour: Contour, radius_for) -> list[Segment]:
    """Скругляет углы контура. radius_for(prev, p, next, convex) -> радиус (0 — острый угол)."""
    n = len(contour)
    segs: list[Segment] = []
    for k in range(n):
        a, p, b = contour[k - 1], contour[k], contour[(k + 1) % n]
        ua, ub = _unit(a, p), _unit(b, p)
        la, lb = math.dist(a, p), math.dist(b, p)
        convex = _turn((p[0] - a[0], p[1] - a[1]), (b[0] - p[0], b[1] - p[1])) < 0
        r = radius_for(a, p, b, convex)
        cos_t = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
        theta = math.acos(cos_t)
        if r <= 0 or theta < 1e-3 or theta > math.pi - 1e-3:
            segs.append(("L", p))
            continue
        d = min(r / math.tan(theta / 2), 0.48 * la, 0.48 * lb)
        p1 = (p[0] + ua[0] * d, p[1] + ua[1] * d)
        p2 = (p[0] + ub[0] * d, p[1] + ub[1] * d)
        segs.append(("L", p1))
        segs.append(("Q", p, p2))
    return segs


def _unit(frm: Point, to: Point) -> Point:
    dx, dy = frm[0] - to[0], frm[1] - to[1]
    ln = math.hypot(dx, dy) or 1
    return dx / ln, dy / ln


# ---------------------------------------------------------------- обводка линий (для рукописного)

def catmull_rom(points: list[Point], samples: int = 14) -> list[Point]:
    """Гладкая кривая, проходящая через все точки."""
    if len(points) < 3:
        return list(points)
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                       + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)))
    out.append(points[-1])
    return out


def stroke_outline(line: list[Point], width: float) -> Contour:
    """Контур монолинейного штриха с круглыми концами (по часовой стрелке)."""
    clean = [line[0]]
    for p in line[1:]:
        if math.dist(p, clean[-1]) > 0.5:
            clean.append(p)
    line = clean
    h = width / 2
    if len(line) == 1:  # точка
        return [(line[0][0] + h * math.cos(a), line[0][1] - h * math.sin(a))
                for a in (i * math.pi / 8 for i in range(16))]

    normals = []
    for i in range(len(line)):
        a = line[max(i - 1, 0)]
        b = line[min(i + 1, len(line) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        normals.append((-dy / ln, dx / ln))  # левая нормаль

    left = [(p[0] + n[0] * h, p[1] + n[1] * h) for p, n in zip(line, normals)]
    right = [(p[0] - n[0] * h, p[1] - n[1] * h) for p, n in zip(line, normals)]

    def cap(center: Point, normal: Point, steps: int = 8) -> list[Point]:
        base = math.atan2(normal[1], normal[0])
        return [(center[0] + h * math.cos(base - math.pi * s / steps),
                 center[1] + h * math.sin(base - math.pi * s / steps)) for s in range(1, steps)]

    # вперёд по правой стороне, круглый конец, назад по левой, круглое начало — заливка справа
    contour = right + cap(line[-1], (-normals[-1][0], -normals[-1][1]))[::-1] + left[::-1] \
        + cap(line[0], normals[0])[::-1]
    return orient_cw(contour)


def simplify(points: Contour, tol: float = 0.8) -> Contour:
    """Упрощение Дугласа–Пекера для замкнутого контура."""
    if len(points) < 8:
        return points

    def dp(pts: list[Point]) -> list[Point]:
        if len(pts) < 3:
            return pts
        a, b = pts[0], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        idx, dmax = 0, 0.0
        for i in range(1, len(pts) - 1):
            d = abs(dy * (pts[i][0] - a[0]) - dx * (pts[i][1] - a[1])) / ln
            if d > dmax:
                idx, dmax = i, d
        if dmax <= tol:
            return [a, b]
        return dp(pts[: idx + 1])[:-1] + dp(pts[idx:])

    half = len(points) // 2
    return dp(points[: half + 1])[:-1] + dp(points[half:] + points[:1])[:-1]


# ---------------------------------------------------------------- запись шрифта

def skew(p: Point, s: float, pivot_y: float = 0) -> Point:
    return (p[0] + (p[1] - pivot_y) * s, p[1])


def draw_segments(pen, segments: list[Segment], transform) -> None:
    pts = [transform(s[-1]) for s in segments]
    start = pts[-1]
    pen.moveTo((round(start[0]), round(start[1])))
    for seg in segments:
        if seg[0] == "L":
            x, y = transform(seg[1])
            pen.lineTo((round(x), round(y)))
        else:
            c, e = transform(seg[1]), transform(seg[2])
            pen.qCurveTo((round(c[0]), round(c[1])), (round(e[0]), round(e[1])))
    pen.closePath()


def build_font(path, family: str, style: str, glyphs: dict, cmap: dict[int, str],
               ascent: int, descent: int, upm: int = 1000) -> None:
    """glyphs: {name: (advance, draw(pen) | None)}"""
    names = [".notdef"] + [n for n in glyphs if n != ".notdef"]
    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)

    tt_glyphs, metrics = {}, {}
    for name in names:
        adv, draw = glyphs.get(name, (500, None))
        pen = TTGlyphPen(None)
        if draw:
            draw(pen)
        tt_glyphs[name] = pen.glyph()
        metrics[name] = (adv, 0)
    fb.setupGlyf(tt_glyphs)
    for name, g in tt_glyphs.items():
        g.recalcBounds(fb.font["glyf"])
        metrics[name] = (metrics[name][0], getattr(g, "xMin", 0))
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ascent, descent=descent)
    fb.setupNameTable({"familyName": family, "styleName": style,
                       "uniqueFontIdentifier": f"{family} {style}",
                       "fullName": f"{family} {style}", "psName": f"{family.replace(' ', '')}-{style}",
                       "version": "Version 1.0", "copyright": "SWAG Studio"})
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=descent, usWinAscent=ascent,
                usWinDescent=abs(descent), sxHeight=0, sCapHeight=0)
    fb.setupPost()
    fb.save(str(path))
