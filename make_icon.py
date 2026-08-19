"""Tiny Bindery icon for shortcuts and the window."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def write_icon(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 48, 64, 128, 256]
    frames = []
    for size in sizes:
        im = Image.new("RGBA", (size, size), (18, 25, 22, 255))
        draw = ImageDraw.Draw(im)
        pad = max(2, size // 12)
        draw.rounded_rectangle(
            [pad, pad, size - pad - 1, size - pad - 1],
            radius=max(3, size // 8),
            fill=(201, 165, 106, 255),
        )
        try:
            font = ImageFont.truetype("georgia.ttf", size=int(size * 0.42))
        except OSError:
            font = ImageFont.load_default()
        text = "36"
        box = draw.textbbox((0, 0), text, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        draw.text(
            ((size - tw) / 2 - box[0], (size - th) / 2 - box[1] - size * 0.03),
            text,
            font=font,
            fill=(18, 25, 22, 255),
        )
        frames.append(im)
    frames[0].save(dest, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])


if __name__ == "__main__":
    write_icon(Path(__file__).resolve().parent / "static" / "bindery.ico")
