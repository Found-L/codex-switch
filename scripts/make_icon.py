"""Render the original linked-capsule brand at native Windows icon sizes."""
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageFilter

DESTINATION = Path(__file__).resolve().parents[1] / "assets"
SCALE = 4
SIZE = 256 * SCALE


def gradient(top, bottom):
    image = Image.new("RGBA", (SIZE, SIZE))
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (0.25 * x + 0.75 * y) / (SIZE - 1)
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
    return image


def capsule(box, width):
    mask = Image.new("L", (SIZE, SIZE))
    ImageDraw.Draw(mask).rounded_rectangle(tuple(round(n * SCALE) for n in box),
                                         radius=36 * SCALE, outline=255, width=width * SCALE)
    return mask.rotate(38, resample=Image.Resampling.BICUBIC)


def main():
    DESTINATION.mkdir(exist_ok=True)
    silhouette = Image.new("L", (SIZE, SIZE))
    ImageDraw.Draw(silhouette).rounded_rectangle((6*SCALE, 6*SCALE, 250*SCALE, 250*SCALE), radius=57*SCALE, fill=255)
    icon = gradient((37, 50, 91), (12, 19, 37))
    icon.putalpha(silhouette)
    rim = ImageDraw.Draw(icon)
    rim.rounded_rectangle((7*SCALE, 7*SCALE, 249*SCALE, 249*SCALE), radius=56*SCALE,
                          outline=(116, 145, 207, 75), width=SCALE)
    first = capsule((43, 92, 153, 164), 16)
    second = capsule((103, 92, 213, 164), 16)
    icon = Image.composite(gradient((232, 251, 255), (139, 201, 255)), icon, first)
    shadow = second.filter(ImageFilter.MaxFilter(6*SCALE+1))
    icon = Image.composite(Image.new("RGBA", icon.size, (17, 25, 48, 255)), icon, shadow)
    icon = Image.composite(gradient((136, 234, 255), (167, 153, 255)), icon, second)
    icon.putalpha(silhouette)
    large = icon.resize((256, 256), Image.Resampling.LANCZOS)
    large.save(DESTINATION / "logo.png")
    icon.resize((88, 88), Image.Resampling.LANCZOS).save(DESTINATION / "logo-88.png")
    sizes = [(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    large.save(DESTINATION / "codex-switch.ico", sizes=sizes)
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory(prefix="codex-switch-icon-") as temporary:
            iconset = Path(temporary) / "CodexSwitch.iconset"
            iconset.mkdir()
            for points in (16, 32, 128, 256, 512):
                for multiplier, suffix in ((1, ""), (2, "@2x")):
                    pixels = points * multiplier
                    icon.resize((pixels, pixels), Image.Resampling.LANCZOS).save(iconset / f"icon_{points}x{points}{suffix}.png")
            subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(DESTINATION / "codex-switch.icns")], check=True)
    else:
        icon.save(DESTINATION / "codex-switch.icns", format="ICNS")
    template = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    template.putalpha(ImageChops.lighter(ImageChops.subtract(first, shadow), second))
    template.resize((64, 64), Image.Resampling.LANCZOS).save(DESTINATION / "tray-template.png")


if __name__ == "__main__":
    main()
