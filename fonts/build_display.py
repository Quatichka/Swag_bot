"""SWAG Display — широкий жирный наклонный шрифт по мотивам «SW» из логотипа студии.

Только прописные (строчные буквы показываются прописными), латиница + кириллица + цифры.
Запуск: python fonts/build_display.py  ->  fonts/SwagDisplay.ttf
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fontkit import build_font, orient_cw, round_contour, skew, union_rects, union_shapes  # noqa: E402

OUT = Path(__file__).parent / "SwagDisplay.ttf"

H = 700            # высота прописных
T = 175            # толщина горизонталей
V = 290            # толщина вертикалей
M = (H - T) // 2   # низ средней перекладины
W = 1100           # обычная ширина буквы
SLANT = 0.30       # наклон (tg угла)
SB = 70            # отступы слева и справа
R_BIG = 210        # радиус скругления «поворотов» штриха
R_SMALL = 22       # лёгкое смягчение остальных углов


class G:
    """Буква: прямоугольники (объединяются) + наклонные штрихи (параллелограммы)."""

    def __init__(self, width=W, rects=(), diags=(), sharp=()):
        self.width = width
        self.rects = list(rects)
        self.diags = list(diags)
        self.sharp = list(sharp)  # углы, которые не скругляем крупно

    def __add__(self, other: "G") -> "G":
        return G(max(self.width, other.width), self.rects + other.rects,
                 self.diags + other.diags, self.sharp + other.sharp)

    def shift(self, dx: float, width: float | None = None) -> "G":
        return G(width or self.width + dx,
                 [(a + dx, b, c + dx, d) for a, b, c, d in self.rects],
                 [[(x + dx, y) for x, y in poly] for poly in self.diags],
                 [(x + dx, y) for x, y in self.sharp])

    def mirror(self) -> "G":
        w = self.width
        return G(w, [(w - c, b, w - a, d) for a, b, c, d in self.rects],
                 [[(w - x, y) for x, y in poly][::-1] for poly in self.diags],
                 [(w - x, y) for x, y in self.sharp])


def R(x0, y0, x1, y1) -> G:
    return G(0, rects=[(x0, y0, x1, y1)])


def D(xb, yb, xt, yt, w) -> G:
    """Наклонный штрих: левый нижний угол (xb, yb), левый верхний (xt, yt), ширина по горизонтали w."""
    return G(0, diags=[[(xb, yb), (xt, yt), (xt + w, yt), (xb + w, yb)]])


def g(width, *parts, sharp=()) -> G:
    out = G(width, sharp=sharp)
    for p in parts:
        out = out + p
    out.width = width
    return out


# ---------------------------------------------------------------- типовые элементы

def stemL(w, y0=0, y1=H): return R(0, y0, V, y1)
def stemR(w, y0=0, y1=H): return R(w - V, y0, w, y1)
def top(w, x0=0, x1=None): return R(x0, H - T, w if x1 is None else x1, H)
def mid(w, x0=0, x1=None): return R(x0, M, w if x1 is None else x1, M + T)
def bot(w, x0=0, x1=None): return R(x0, 0, w if x1 is None else x1, T)


def O(w=W): return g(w, stemL(w), stemR(w), top(w), bot(w))


DIAG = int(V * 1.12)

GLYPHS: dict[str, G] = {}

# ---------------------------------------------------------------- латиница
w = W
GLYPHS["A"] = g(w, D(0, 0, int(w * 0.30), H, DIAG), top(w, int(w * 0.30)), stemR(w),
                mid(w, int(w * 0.2)), sharp=[(0, 0)])
GLYPHS["B"] = g(w, stemL(w), top(w, 0, w - 70), R(w - V - 70, M, w - 70, H), mid(w), bot(w),
                stemR(w, 0, M + T))
GLYPHS["C"] = g(w, stemL(w), top(w), bot(w))
GLYPHS["D"] = g(w, O(w), sharp=[(0, 0), (0, H)])
GLYPHS["E"] = g(w, stemL(w), top(w), mid(w, 0, w - 90), bot(w))
GLYPHS["F"] = g(w, stemL(w), top(w), mid(w, 0, w - 90))
GLYPHS["G"] = g(w, stemL(w), top(w), bot(w), stemR(w, 0, M + T), mid(w, int(w * 0.5)))
GLYPHS["H"] = g(w, stemL(w), stemR(w), mid(w))
GLYPHS["I"] = g(V, stemL(V))
GLYPHS["J"] = g(w, stemR(w), bot(w), stemL(w, 0, M + T))
GLYPHS["K"] = g(w, stemL(w), R(0, M, V + 140, M + T), D(V - 150, M - 40, w - DIAG, H, DIAG), D(w - DIAG, 0, V - 150, M + T + 40, DIAG))
GLYPHS["L"] = g(w, stemL(w), bot(w))
wm = 1260
GLYPHS["M"] = g(wm, stemL(wm), stemR(wm), top(wm), R(wm / 2 - V * 0.42, 0, wm / 2 + V * 0.42, H))
GLYPHS["N"] = g(w, stemL(w), stemR(w), D(w - V - 40, 0, 40, H, V + 40))
GLYPHS["O"] = O(w)
GLYPHS["P"] = g(w, stemL(w), top(w), mid(w), stemR(w, M, H))
GLYPHS["Q"] = g(w, O(w), R(int(w * 0.6), -120, w, T), sharp=[(w, -120)])
GLYPHS["R"] = g(w, stemL(w), top(w), mid(w), stemR(w, M, H), D(w - DIAG - 10, 0, int(w * 0.42), M + T, DIAG))
GLYPHS["S"] = g(w, top(w), stemL(w, M, H), mid(w), stemR(w, 0, M + T), bot(w))
GLYPHS["T"] = g(w, top(w), R(w / 2 - V / 2, 0, w / 2 + V / 2, H))
GLYPHS["U"] = g(w, stemL(w), stemR(w), bot(w))
GLYPHS["V"] = g(w, D(int(w * 0.5 - DIAG * 0.75), 0, 0, H, DIAG), D(int(w * 0.5 - DIAG * 0.25), 0, w - DIAG, H, DIAG))
GLYPHS["W"] = g(wm, stemL(wm), stemR(wm), bot(wm), R(wm / 2 - V * 0.42, 0, wm / 2 + V * 0.42, H))
GLYPHS["X"] = g(w, D(0, 0, w - DIAG, H, DIAG), D(w - DIAG, 0, 0, H, DIAG))
GLYPHS["Y"] = g(w, stemL(w, M, H), stemR(w, M, H), mid(w), R(w / 2 - V / 2, 0, w / 2 + V / 2, M + T))
GLYPHS["Z"] = g(w, top(w), bot(w), D(0, T - 20, w - DIAG, H - T + 20, DIAG))

# ---------------------------------------------------------------- цифры
w = 980
GLYPHS["zero"] = O(w)
GLYPHS["one"] = g(560, stemR(560), top(560))
GLYPHS["two"] = g(w, top(w), stemR(w, M, H), mid(w), stemL(w, 0, M + T), bot(w))
GLYPHS["three"] = g(w, top(w), mid(w, int(w * 0.25)), bot(w), stemR(w))
GLYPHS["four"] = g(w, D(0, M, int(w * 0.28), H, DIAG), mid(w), stemR(w))
GLYPHS["five"] = g(w, top(w), stemL(w, M, H), mid(w), stemR(w, 0, M + T), bot(w), sharp=[(0, H)])
GLYPHS["six"] = g(w, stemL(w), top(w), mid(w), bot(w), stemR(w, 0, M + T))
GLYPHS["seven"] = g(w, top(w), D(int(w * 0.25), 0, w - DIAG, H - 10, DIAG))
GLYPHS["eight"] = g(w, stemL(w), stemR(w), top(w), mid(w), bot(w))
GLYPHS["nine"] = g(w, top(w), stemL(w, M, H), mid(w), stemR(w), bot(w))

# ---------------------------------------------------------------- кириллица
w = W
L = GLYPHS
CYR = {
    "А": L["A"], "В": L["B"], "Е": L["E"], "К": L["K"], "М": L["M"], "Н": L["H"], "О": L["O"],
    "Р": L["P"], "С": L["C"], "Т": L["T"], "Х": L["X"], "З": L["three"],
    # верхняя перекладина выступает вправо флажком, иначе «Б» не отличить от «6»
    "Б": g(1150, stemL(1150), top(1150), mid(1150, 0, 800), bot(1150, 0, 800), R(800 - V, 0, 800, M + T),
           sharp=[(0, H)]),
    "Г": g(w, stemL(w), top(w)),
    "Д": g(w, R(90, T, 90 + V, H), stemR(w), top(w, 90), bot(w), R(0, -140, int(V * 0.75), 0),
           R(w - int(V * 0.75), -140, w, 0), sharp=[(0, -140), (w, -140)]),
    "Ё": g(w, L["E"], R(w * 0.22, H + 70, w * 0.22 + V * 0.8, H + 70 + T * 0.8),
           R(w * 0.62, H + 70, w * 0.62 + V * 0.8, H + 70 + T * 0.8)),
    "И": g(w, stemL(w), stemR(w), D(40, 0, w - V - 40, H, V + 40)),
    "Л": g(w, D(0, 0, int(w * 0.24), H, DIAG), top(w, int(w * 0.24)), stemR(w)),
    "П": g(w, stemL(w), stemR(w), top(w)),
    "У": g(w, stemL(w, M, H), mid(w), stemR(w), bot(w)),
    "Ф": g(1200, R(0, 90, V, H - 90), R(1200 - V, 90, 1200, H - 90), R(0, H - 90 - T * 0.85, 1200, H - 90),
           R(0, 90, 1200, 90 + T * 0.85), R(600 - V * 0.42, -60, 600 + V * 0.42, H + 60)),
    "Ц": g(w, stemL(w), stemR(w), bot(w), R(w - int(V * 0.75), -140, w + 40, 0), sharp=[(w + 40, -140)]),
    "Ч": g(w, stemL(w, M, H), mid(w), stemR(w)),
    "Ш": L["W"],
    "Щ": g(wm, L["W"], R(wm - int(V * 0.75), -140, wm + 40, 0), sharp=[(wm + 40, -140)]),
    "Ь": g(w, stemL(w), mid(w), bot(w), stemR(w, 0, M + T)),
    "Э": g(w, top(w), bot(w), stemR(w), mid(w, int(w * 0.32))),
    "Я": g(w, stemR(w), top(w), mid(w), stemL(w, M, H), D(10, 0, int(w * 0.58) - DIAG, M + T, DIAG)),
}
CYR["Ъ"] = g(w + 260, CYR["Ь"].shift(260), R(0, H - T, 260 + V, H))
CYR["Ы"] = g(w + 380, CYR["Ь"], R(w + 90, 0, w + 90 + V, H))
CYR["Ж"] = g(1500, R(750 - V / 2, 0, 750 + V / 2, H), R(750 - V / 2 - 140, M, 750 + V / 2 + 140, M + T),
             D(750 + V / 2 - 150, M - 40, 1500 - DIAG, H, DIAG), D(1500 - DIAG, 0, 750 + V / 2 - 150, M + T + 40, DIAG),
             D(0, 0, 750 - V / 2 + 150 - DIAG, M + T + 40, DIAG), D(750 - V / 2 + 150 - DIAG, M - 40, 0, H, DIAG))
CYR["Й"] = g(w, CYR["И"], R(w * 0.3, H + 70, w * 0.7, H + 70 + T * 0.8))
CYR["Ю"] = g(1560, stemL(1560), R(V, M, 420, M + T), O(1140).shift(420, 1560))

# ---------------------------------------------------------------- знаки
P = {
    "space": G(380),
    "period": g(V, R(0, 0, V, T)),
    "comma": g(V, R(0, 0, V, T), R(0, -150, int(V * 0.55), 0)),
    "colon": g(V, R(0, 0, V, T), R(0, H - 300, V, H - 300 + T)),
    "semicolon": g(V, R(0, 0, V, T), R(0, -150, int(V * 0.55), 0), R(0, H - 300, V, H - 300 + T)),
    "hyphen": g(620, mid(620)),
    "exclam": g(V, R(0, T + 90, V, H), R(0, 0, V, T)),
    "question": g(900, top(900), stemR(900, M, H), mid(900, 300), R(300, T + 90, 300 + V, M + T), R(300, 0, 300 + V, T)),
    "quotesingle": g(int(V * 0.7), R(0, H - 260, int(V * 0.7), H)),
    "quotedbl": g(int(V * 1.7), R(0, H - 260, int(V * 0.7), H), R(V, H - 260, int(V * 1.7), H)),
    "slash": g(780, D(0, -60, 780 - V, H + 60, V)),
    "parenleft": g(380, R(0, -110, V, H + 110), R(0, H, 380, H + 110), R(0, -110, 380, 0)),
    "parenright": g(380, R(380 - V, -110, 380, H + 110), R(0, H, 380, H + 110), R(0, -110, 380, 0)),
    "plus": g(760, R(0, M, 760, M + T), R(380 - T / 2, M - 230, 380 + T / 2, M + T + 230)),
    "equal": g(760, R(0, M - 130, 760, M - 130 + T * 0.8), R(0, M + 130, 760, M + 130 + T * 0.8)),
    "underscore": g(900, R(0, -160, 900, -160 + T * 0.6)),
    "numbersign": g(1000, R(150, 0, 150 + V * 0.8, H), R(1000 - 150 - V * 0.8, 0, 850, H),
                    R(0, 160, 1000, 160 + T * 0.8), R(0, H - 160 - T * 0.8, 1000, H - 160)),
    "at": g(1100, O(1100), R(380, 260, 1100 - V, 260 + T), R(380, 260, 380 + V * 0.7, H - T)),
    "guillemotleft": g(900, D(250, 120, 0, 350, V), D(0, 350, 250, 580, V), D(650, 120, 400, 350, V), D(400, 350, 650, 580, V)),
    "guillemotright": g(900, D(0, 120, 250, 350, V), D(250, 350, 0, 580, V), D(400, 120, 650, 350, V), D(650, 350, 400, 580, V)),
    "uni2116": g(1500, L["N"], R(1160, 290, 1160 + 330, H), R(1160, 120, 1490, 220)),  # №
}

CHAR_NAMES = {".": "period", ",": "comma", ":": "colon", ";": "semicolon", "-": "hyphen",
              "!": "exclam", "?": "question", "'": "quotesingle", '"': "quotedbl", "/": "slash",
              "(": "parenleft", ")": "parenright", "+": "plus", "=": "equal", "_": "underscore",
              "#": "numbersign", "@": "at", "«": "guillemotleft", "»": "guillemotright",
              "№": "uni2116", " ": "space", " ": "space", "–": "hyphen", "—": "hyphen"}
DIGITS = "zero one two three four five six seven eight nine".split()


# ---------------------------------------------------------------- отрисовка

def radius_for_factory(glyph: G):
    long_edge = max(T, V) + 40

    def radius_for(a, p, b, convex):
        if any(abs(p[0] - x) < 3 and abs(p[1] - y) < 3 for x, y in glyph.sharp):
            return R_SMALL
        if not convex:
            return R_SMALL
        if math.dist(a, p) > long_edge and math.dist(b, p) > long_edge:
            return R_BIG
        return R_SMALL
    return radius_for


def drawer(glyph: G):
    def draw(pen):
        radius_for = radius_for_factory(glyph)
        tf = lambda p: skew((p[0] + SB, p[1]), SLANT, H / 2)  # noqa: E731
        from fontkit import draw_segments
        shapes = ([union_rects(glyph.rects)] if glyph.rects else []) + [[orient_cw(d)] for d in glyph.diags]
        contours = shapes[0] if len(shapes) == 1 else union_shapes(shapes)
        for contour in contours:
            draw_segments(pen, round_contour(contour, radius_for), tf)
    return draw


def main() -> None:
    glyphs, cmap = {}, {}

    def add(name: str, glyph: G, chars: str = "") -> None:
        glyphs[name] = (int(glyph.width + 2 * SB), drawer(glyph) if (glyph.rects or glyph.diags) else None)
        for ch in chars:
            cmap[ord(ch)] = name

    glyphs[".notdef"] = (W, drawer(O()))
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        add(ch, GLYPHS[ch], ch + ch.lower())
    for i, name in enumerate(DIGITS):
        add(name, GLYPHS[name], str(i))
    for ch, glyph in CYR.items():
        add(f"uni{ord(ch):04X}", glyph, ch + ch.lower())
    for name, glyph in P.items():
        add(name, glyph)
    for ch, name in CHAR_NAMES.items():
        cmap[ord(ch)] = name

    build_font(OUT, "SWAG Display", "Regular", glyphs, cmap, ascent=950, descent=-250)
    print("saved", OUT, len(glyphs), "glyphs")


if __name__ == "__main__":
    main()
