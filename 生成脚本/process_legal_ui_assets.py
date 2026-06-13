import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


WORKSPACE = Path("/Users/lili/Desktop/视频素材工作流")
SOURCE_DIR = WORKSPACE / "法律名词ui"
CUTOUT_DIR = WORKSPACE / "已抠图ui"
BACKGROUND_DIR = WORKSPACE / "参考素材" / "背景"

BACKGROUND_16X9 = BACKGROUND_DIR / "法律名词ui-通用背景-16x9.png"


def make_cutout(source_path: Path) -> Image.Image:
    source = Image.open(source_path).convert("RGBA")
    pixels = source.load()
    width, height = source.size

    # The source already has partial alpha, but the corners keep a faint black
    # residue. Remove only the near-empty background while preserving the glow.
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 10:
                pixels[x, y] = (r, g, b, 0)
            else:
                boosted = min(255, int((a - 8) * 1.35))
                pixels[x, y] = (r, g, b, boosted)

    bbox = source.getbbox()
    if bbox:
        source = source.crop(bbox)
    cutout_path = CUTOUT_DIR / source_path.name
    source.save(cutout_path)
    print(cutout_path)
    return source


def paste_center(base: Image.Image, layer: Image.Image, center: tuple[int, int], alpha: float) -> None:
    layer = layer.copy()
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    x = int(center[0] - layer.width / 2)
    y = int(center[1] - layer.height / 2)
    base.alpha_composite(layer, (x, y))


def resize_keep_ratio(image: Image.Image, width: int) -> Image.Image:
    ratio = width / image.width
    return image.resize((width, int(image.height * ratio)), Image.Resampling.LANCZOS)


def make_16x9_background(cutout: Image.Image) -> None:
    width, height = 1920, 1080
    base = Image.new("RGBA", (width, height), (18, 17, 14, 255))

    # Use the original cutout as a style source, but redraw the main object as
    # a wide 16:9 glass panel instead of placing a square asset in the center.
    source_echo = resize_keep_ratio(cutout, 560).filter(ImageFilter.GaussianBlur(3))
    paste_center(base, source_echo, (115, 930), 0.14)
    paste_center(base, source_echo, (1820, 150), 0.11)

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel, "RGBA")
    rect = (150, 105, 1770, 975)
    radius = 76

    # Outer glow built from several blurred rounded rectangles.
    for blur, alpha, expand in [(44, 78, 22), (24, 96, 12), (10, 118, 4)]:
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        r = (rect[0] - expand, rect[1] - expand, rect[2] + expand, rect[3] + expand)
        gd.rounded_rectangle(r, radius=radius + expand, outline=(234, 188, 65, alpha), width=8)
        panel.alpha_composite(glow.filter(ImageFilter.GaussianBlur(blur)))

    # Wide glass body.
    draw.rounded_rectangle(rect, radius=radius, fill=(45, 51, 51, 178), outline=(238, 207, 95, 204), width=3)
    inner = (rect[0] + 14, rect[1] + 14, rect[2] - 14, rect[3] - 14)
    draw.rounded_rectangle(inner, radius=radius - 14, outline=(220, 230, 216, 84), width=2)

    # Subtle horizontal glass gradient.
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient, "RGBA")
    for y in range(rect[1], rect[3]):
        t = (y - rect[1]) / max(1, rect[3] - rect[1])
        alpha = int(52 * (1 - t) + 14 * t)
        gd.line((rect[0] + 28, y, rect[2] - 28, y), fill=(255, 255, 255, alpha))
    mask = Image.new("L", (width, height), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(inner, radius=radius - 14, fill=255)
    gradient.putalpha(Image.composite(gradient.getchannel("A"), Image.new("L", (width, height), 0), mask))
    panel.alpha_composite(gradient)

    # Diagonal reflections from the original image language, extended for 16:9.
    reflection = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(reflection, "RGBA")
    rd.polygon([(440, 110), (570, 110), (1310, 975), (1150, 975)], fill=(230, 238, 232, 34))
    rd.polygon([(915, 110), (985, 110), (1588, 975), (1490, 975)], fill=(230, 238, 232, 22))
    rd.polygon([(250, 110), (315, 110), (1030, 975), (930, 975)], fill=(230, 238, 232, 13))
    reflection.putalpha(Image.composite(reflection.getchannel("A"), Image.new("L", (width, height), 0), mask))
    panel.alpha_composite(reflection.filter(ImageFilter.GaussianBlur(0.4)))

    # Darken the center slightly to keep future text/cards readable.
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette, "RGBA")
    vd.rounded_rectangle((260, 190, 1660, 890), radius=56, fill=(0, 0, 0, 52))
    panel.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(38)))

    base.alpha_composite(panel)

    # Final low-contrast veil: keeps the background usable behind evidence pages.
    overlay = Image.new("RGBA", (width, height), (8, 8, 6, 58))
    base.alpha_composite(overlay)

    base.convert("RGB").save(BACKGROUND_16X9, quality=96)


def main() -> None:
    CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)

    names = sys.argv[1:] or ["背景图.png"]
    cutouts: dict[str, Image.Image] = {}
    for name in names:
        source_path = SOURCE_DIR / name
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        cutouts[name] = make_cutout(source_path)

    if "背景图.png" in cutouts:
        make_16x9_background(cutouts["背景图.png"])
        print(BACKGROUND_16X9)


if __name__ == "__main__":
    main()
