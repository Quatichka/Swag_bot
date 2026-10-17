"""Генерирует картинки-заставки для каждого экрана бота в стиле SWAG Studio:
белый фон, чёрный текст, минимализм — как логотип студии (assets/logo.png).

Шрифты свои, собраны по мотивам логотипа (папка fonts/):
  SwagDisplay.ttf — широкий наклонный, как «SW» — заголовки и подписи
  SwagScript.ttf  — тонкий рукописный, как «swag studio» — подзаголовки

Запуск: python generate_images.py  ->  картинки появятся в папке images/
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1280, 720
BASE = Path(__file__).parent
OUT = BASE / "images"
LOGO = BASE / "assets" / "logo.png"
DISPLAY = BASE / "fonts" / "SwagDisplay.ttf"
SCRIPT = BASE / "fonts" / "SwagScript.ttf"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (120, 120, 120)
LINE = (225, 225, 225)
WATERMARK = (246, 246, 246)

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


def display(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(DISPLAY), size)


def script(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(SCRIPT), size)


def load_logo() -> Image.Image:
    """Логотип как маска: чернила -> непрозрачные, белый фон -> прозрачный."""
    gray = Image.open(LOGO).convert("L")
    ink = ImageChops.invert(gray)
    # убираем серый шум сжатия вокруг логотипа и поднимаем контраст
    ink = ink.point(lambda v: 0 if v < 30 else min(255, (v - 30) * 255 // 200))
    return ink.crop(ink.point(lambda v: 255 if v > 60 else 0).getbbox())


def logo_layer(mask: Image.Image, width: int, color) -> Image.Image:
    k = width / mask.width
    m = mask.resize((width, round(mask.height * k)), Image.LANCZOS)
    layer = Image.new("RGBA", m.size, color + (0,))
    layer.putalpha(m)
    return layer


def paste(img: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    img.paste(layer, (x, y), layer)


def fit(d: ImageDraw.ImageDraw, text: str, max_w: int, size: int) -> ImageFont.FreeTypeFont:
    while size > 30 and d.textlength(text, font=display(size)) > max_w:
        size -= 4
    return display(size)


def text_right(d: ImageDraw.ImageDraw, right: int, y: int, text: str, f, fill) -> None:
    d.text((right - d.textlength(text, font=f), y), text, font=f, fill=fill)


def render(mask: Image.Image, title: str | None, subtitle: str, step) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    small = display(18)

    if title is None:  # главный экран — логотип по центру
        logo = logo_layer(mask, 560, BLACK)
        top = 160
        paste(img, logo, (W - logo.width) // 2, top)
        y = top + logo.height + 50
        d.line((W // 2 - 30, y, W // 2 + 30, y), fill=BLACK, width=1)
        f = script(58)
        d.text((W / 2 - d.textlength(subtitle, font=f) / 2, y + 22), subtitle, font=f, fill=GRAY)
        d.text((W / 2 - d.textlength("@SSWAG_STUDIO", font=small) / 2, H - 70), "@SSWAG_STUDIO", font=small, fill=GRAY)
        return img

    # водяной знак — логотип справа, едва заметный
    paste(img, logo_layer(mask, 900, WATERMARK), 560, 190)

    # маленький логотип сверху слева
    paste(img, logo_layer(mask, 170, BLACK), 72, 52)

    # шаги анкеты
    if step:
        n, total = step
        right = W - 72
        text_right(d, right, 44, f"{n:02d} / {total:02d}", display(22), BLACK)
        seg, gap = 34, 8
        x0 = right - total * seg - (total - 1) * gap
        for i in range(total):
            x = x0 + i * (seg + gap)
            d.line((x, 98, x + seg, 98), fill=BLACK if i < n else LINE, width=2)

    # заголовок и подзаголовок
    f = fit(d, title, W - 160, 120)
    y = 290
    box = d.textbbox((72, y), title, font=f)
    d.text((72, y), title, font=f, fill=BLACK)
    y = box[3] + 34
    d.line((76, y, 136, y), fill=BLACK, width=2)
    d.text((76, y + 14), subtitle, font=script(62), fill=GRAY)

    # низ
    d.line((72, H - 92, W - 72, H - 92), fill=LINE, width=1)
    d.text((72, H - 70), "@SSWAG_STUDIO", font=small, fill=GRAY)
    text_right(d, W - 72, H - 70, "DESIGN STUDIO", small, GRAY)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    mask = load_logo()
    for key, (title, subtitle, step) in SCREENS.items():
        render(mask, title, subtitle, step).save(OUT / f"{key}.png", optimize=True)
        print("ok", key)


if __name__ == "__main__":
    main()
