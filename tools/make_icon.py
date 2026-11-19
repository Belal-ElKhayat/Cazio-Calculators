"""Regenerate assets/icon.png and assets/icon.ico (needs Pillow):  python tools/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets"


def draw(size: int = 512) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size / 256
    d.rounded_rectangle([16 * s, 8 * s, 240 * s, 248 * s], 38 * s, fill="#2f3748", outline="#141821", width=int(5 * s))
    d.rounded_rectangle([36 * s, 28 * s, 220 * s, 92 * s], 12 * s, fill="#b7c9a4", outline="#12161d", width=int(4 * s))
    for i in range(10):  # LCD "dots"
        d.rectangle([(50 + i * 16) * s, 62 * s, (60 + i * 16) * s, 80 * s], fill="#1c261a" if i in (1, 4, 5, 8) else "#a8ba95")
    colours = ["#6e7480"] * 3 + ["#b8d43c", "#5fa83a"] + ["#6e7480"] * 3 + ["#4b515d"] * 2 + ["#6e7480"] * 3 + ["#4b515d"] * 2
    for i, col in enumerate(colours):
        r, c = divmod(i, 5)
        x, y = (38 + c * 36) * s, (112 + r * 44) * s
        d.rounded_rectangle([x, y, x + 30 * s, y + 34 * s], 8 * s, fill=col, outline="#141821", width=int(2 * s))
    return im


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    img = draw()
    img.save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT / "icon.png", OUT / "icon.ico")
