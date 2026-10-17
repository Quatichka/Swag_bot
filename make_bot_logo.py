"""Логотип «SW БОТ» в стиле логотипа студии: «SW» и подпись из assets/logo.png,
«БОТ» — шрифтом SWAG Display (он нарисован по мотивам «SW»).

Запуск: python make_bot_logo.py  ->  images/bot_logo.png (1280×1280, белый фон)
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

BASE = Path(__file__).parent
SIZE = 1280
FILL = 0.85          # строка «SW БОТ» занимает 85% ширины
WORD = "БОТ"


def logo_bands() -> tuple[Image.Image, Image.Image]:
    """Маски «SW» и рукописной подписи из логотипа (белым по чёрному)."""
    gray = Image.open(BASE / "assets" / "logo.png").convert("L")
    ink = ImageChops.invert(gray).point(lambda v: 0 if v < 30 else min(255, (v - 30) * 255 // 200))
    solid = ink.point(lambda v: 255 if v > 80 else 0)
    rows = [any(solid.getpixel((x, y)) for x in range(0, solid.width, 2)) for y in range(solid.height)]
    bands, start = [], None
    for y, on in enumerate(rows + [False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            bands.append((start, y))
            start = None
    (sw_top, sw_bottom), (sc_top, sc_bottom) = bands[0], bands[1]

    def crop(y0, y1):
        band = ink.crop((0, max(0, y0 - 4), ink.width, y1 + 4))
        return band.crop(band.point(lambda v: 255 if v > 60 else 0).getbbox())
    return crop(sw_top, sw_bottom), crop(sc_top, sc_bottom)


def word_layer(text: str, cap: int) -> Image.Image:
    f = ImageFont.truetype(str(BASE / "fonts" / "SwagDisplay.ttf"), round(cap / 0.70 * 2))
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 20, b - t + 20), 0)
    ImageDraw.Draw(im).text((10 - l, 10 - t), text, font=f, fill=255)
    im = im.crop(im.getbbox())
    return im.resize((round(im.width * cap / im.height), cap), Image.LANCZOS)


def scale(im: Image.Image, k: float) -> Image.Image:
    return im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)


def main() -> None:
    sw0, script0 = logo_bands()
    row0 = sw0.width + round(sw0.height * 0.32) + word_layer(WORD, sw0.height).width
    k = SIZE * FILL / row0
    sw, script = scale(sw0, k), scale(script0, k)
    cap = sw.height
    word = word_layer(WORD, cap)
    gap, sgap = round(cap * 0.32), round(cap * 0.17)

    mask = Image.new("L", (SIZE, SIZE), 0)
    x0 = (SIZE - (sw.width + gap + word.width)) // 2
    y0 = (SIZE - (cap + sgap + script.height)) // 2
    mask.paste(sw, (x0, y0), sw)
    mask.paste(word, (x0 + sw.width + gap, y0), word)
    mask.paste(script, ((SIZE - script.width) // 2, y0 + cap + sgap), script)

    img = Image.new("RGB", (SIZE, SIZE), "white")
    img.paste((0, 0, 0), (0, 0), mask)
    out = BASE / "images" / "bot_logo.png"
    img.save(out, optimize=True)
    print("saved", out)


if __name__ == "__main__":
    main()
