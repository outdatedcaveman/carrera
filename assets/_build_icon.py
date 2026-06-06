"""
Generate Carrera Windows icon (.ico) and PNG variants from the SVG mark.
Run from repo root:  py assets/_build_icon.py
Requires: Pillow, cairosvg (optional — falls back to raster-only if missing).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).parent
TEAL = (13, 148, 136, 255)
WHITE = (255, 255, 255, 255)
AMBER = (251, 191, 36, 255)


def render_mark(size: int) -> Image.Image:
    """Draw the Carrera mark at the given pixel size."""
    # Supersample 4x for crisp anti-aliased arcs
    scale = 4
    s = size * scale
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # Rounded-square background
    radius = int(s * 0.22)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=TEAL)

    # "C" arc — drawn as an open stroke on a pieslice mask
    stroke = max(2, int(s * 0.086))

    # The "C" is an arc from ~40° to ~320° (leaving a mouth on the right)
    # PIL's arc draws counter-clockwise in degrees from 3-o'clock
    pad = int(s * 0.22)
    bbox = (pad, pad, s - pad, s - pad)
    d.arc(bbox, start=40, end=320, fill=WHITE, width=stroke)

    # Amber arrow inside the C mouth
    arrow_stroke = max(2, int(s * 0.072))
    cx, cy = s // 2, s // 2
    shaft_start = (cx + int(s * 0.05), cy)
    shaft_end = (cx + int(s * 0.27), cy)
    d.line([shaft_start, shaft_end], fill=AMBER, width=arrow_stroke)
    # Arrow head
    head = int(s * 0.09)
    d.line(
        [(shaft_end[0] - head, cy - head),
         shaft_end,
         (shaft_end[0] - head, cy + head)],
        fill=AMBER, width=arrow_stroke, joint="curve",
    )

    # Downscale with high-quality filter
    return im.resize((size, size), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [render_mark(s) for s in sizes]

    # Save PNGs for reference
    (ASSETS / "icon-256.png").write_bytes(b"")  # clear
    imgs[-1].save(ASSETS / "icon-256.png", format="PNG")
    imgs[5].save(ASSETS / "icon-128.png", format="PNG")

    # Save multi-resolution .ico for Windows
    ico_path = ASSETS / "icon.ico"
    imgs[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Wrote {ico_path} ({ico_path.stat().st_size} bytes)")
    print(f"Wrote {ASSETS / 'icon-256.png'}")
    print(f"Wrote {ASSETS / 'icon-128.png'}")


if __name__ == "__main__":
    main()
