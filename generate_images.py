"""Генерирует картинки-заставки для каждого экрана бота в стиле SWAG Studio:
белый фон, чёрный текст, минимализм — как логотип студии (assets/logo.png).

Запуск: python generate_images.py  ->  картинки появятся в папке images/
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1280, 720
BASE = Path(__file__).parent
OUT = BASE / "images"
LOGO = BASE / "assets" / "logo.png"
FONTS = Path("C:/Windows/Fonts")

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (130, 130, 130)
LINE = (225, 225, 225)
WATERMARK = (246, 246, 246)

TITLE = "bahnschrift.ttf"  # геометричный гротеск, ближе всего к «SW» в логотипе
LIGHT = "segoeuil.ttf"
REGULAR = "segoeui.ttf"

# key: (заголовок, подзаголовок, шаг заказа или None)
SCREENS = {
    "welcome": (None, "превью  ·  рендер  ·  арт  ·  монтаж", None),
    "services": ("УСЛУГИ", "что мы делаем", None),
    "order_service": ("ЗАКАЗ", "выбери услугу", (1, 5)),
    "order_details": ("ИДЕЯ", "опиши задачу", (2, 5)),
    "order_refs": ("РЕФЕРЕНСЫ", "примеры, фото, файлы", (3, 5)),
    "order_deadline": ("СРОКИ", "к какому дню нужно", (4, 5)),
    "order_budget": ("БЮДЖЕТ", "на какую сумму рассчитываешь", (5, 5)),
    "order_confirm": ("ПРОВЕРКА", "всё верно?", None),
    "order_success": ("ПРИНЯТО", "менеджер скоро напишет", None),
    "my_orders": ("ЗАКАЗЫ", "история и статусы", None),
    "question": ("ВОПРОС", "мы ответим здесь же", None),
    "status_accepted": ("В РАБОТЕ", "дизайнер уже начал", None),
    "status_done": ("ГОТОВО", "спасибо, что выбрал нас", None),
    "status_rejected": ("ОТКЛОНЁН", "подробности в сообщении", None),
}


def font(name: str, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    try:
        f = ImageFont.truetype(str(FONTS / name), size)
        if variation:
            f.set_variation_by_name(variation)
        return f
    except OSError:
        return ImageFont.load_default(size)


def load_logo() -> Image.Image:
    """Логотип как маска: чернила -> непрозрачные, белый фон -> прозрачный."""
    gray = Image.open(LOGO).convert("L")
    ink = ImageChops.invert(gray)
    # убираем серый шум сжатия вокруг логотипа и поднимаем контраст
    ink = ink.point(lambda v: 0 if v < 30 else min(255, (v - 30) * 255 // 200))
    ink = ink.crop(ink.point(lambda v: 255 if v > 60 else 0).getbbox())
    return ink


def logo_layer(mask: Image.Image, width: int, color) -> Image.Image:
    k = width / mask.width
    m = mask.resize((width, round(mask.height * k)), Image.LANCZOS)
    layer = Image.new("RGBA", m.size, color + (0,))
    layer.putalpha(m)
    return layer


def slanted(text: str, size: int, color, stretch: float = 1.3, slant: float = 0.24) -> Image.Image:
    """Заголовок в духе логотипа: жирный, растянутый по ширине, с наклоном вправо."""
    size *= 2  # рисуем в 2× и уменьшаем — так края гладкие
    f = font(TITLE, size, "Bold")
    l, t, r, b = f.getbbox(text)
    w, h = r - l, b - t
    layer = Image.new("RGBA", (w + 8, h + 8), color + (0,))
    ImageDraw.Draw(layer).text((4 - l, 4 - t), text, font=f, fill=color)
    layer = layer.resize((int(layer.width * stretch), layer.height), Image.LANCZOS)
    sheared = layer.transform(
        (layer.width + int(layer.height * slant), layer.height), Image.AFFINE,
        (1, slant, -layer.height * slant, 0, 1, 0), resample=Image.BICUBIC)
    sheared = sheared.crop(sheared.getbbox())
    return sheared.resize((sheared.width // 2, sheared.height // 2), Image.LANCZOS)


def fit_slanted(text: str, max_w: int, size: int) -> Image.Image:
    layer = slanted(text, size, BLACK)
    while layer.width > max_w and size > 40:
        size -= 6
        layer = slanted(text, size, BLACK)
    return layer


def paste(img: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    img.paste(layer, (x, y), layer)


def render(mask: Image.Image, title: str | None, subtitle: str, step) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    if title is None:  # главный экран — логотип по центру
        logo = logo_layer(mask, 560, BLACK)
        top = 170
        paste(img, logo, (W - logo.width) // 2, top)
        y = top + logo.height + 56
        d.line((W // 2 - 30, y, W // 2 + 30, y), fill=BLACK, width=1)
        f = font(LIGHT, 30)
        d.text((W / 2 - d.textlength(subtitle, font=f) / 2, y + 26), subtitle, font=f, fill=GRAY)
        f = font(REGULAR, 20)
        d.text((W / 2 - d.textlength("@swagdsgn", font=f) / 2, H - 70), "@swagdsgn", font=f, fill=GRAY)
        return img

    # водяной знак — логотип справа, едва заметный
    mark = logo_layer(mask, 900, WATERMARK)
    paste(img, mark, 560, 190)

    # маленький логотип сверху слева
    paste(img, logo_layer(mask, 170, BLACK), 72, 52)

    # шаги анкеты
    if step:
        n, total = step
        label = f"{n:02d} / {total:02d}"
        f = font(REGULAR, 20)
        right = W - 72
        d.text((right - d.textlength(label, font=f), 58), label, font=f, fill=BLACK)
        seg, gap = 34, 8
        x0 = right - total * seg - (total - 1) * gap
        for i in range(total):
            x = x0 + i * (seg + gap)
            d.line((x, 98, x + seg, 98), fill=BLACK if i < n else LINE, width=2)

    # заголовок и подзаголовок
    head = fit_slanted(title, W - 160, 110)
    y = 300
    paste(img, head, 72, y)
    y += head.height + 34
    d.line((76, y, 136, y), fill=BLACK, width=2)
    d.text((76, y + 22), subtitle, font=font(LIGHT, 34), fill=GRAY)

    # низ
    d.line((72, H - 92, W - 72, H - 92), fill=LINE, width=1)
    f = font(REGULAR, 20)
    d.text((72, H - 72), "@swagdsgn", font=f, fill=GRAY)
    tag = "design studio"
    d.text((W - 72 - d.textlength(tag, font=f), H - 72), tag, font=f, fill=GRAY)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    mask = load_logo()
    for key, (title, subtitle, step) in SCREENS.items():
        render(mask, title, subtitle, step).save(OUT / f"{key}.png", optimize=True)
        print("ok", key)


if __name__ == "__main__":
    main()
