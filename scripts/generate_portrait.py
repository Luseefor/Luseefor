#!/usr/bin/env python3
"""Convert the actual uploaded photo into a sparse ASCII portrait + typing GIF.

Concepts (not code) borrowed from the navi3582/mithun50 kits and the
Andrew6rant live profile: single-color glyphs, transparent/blank background,
measured monospace cell ratio, a blank/white floor so skin and lens areas stay
open, and a print-once reveal with a held final frame. No JS/iframe.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- portrait:start -->"
END = "<!-- portrait:end -->"
RAMP = "MWN8B0QOCLft1i "
RAMP_FACE = "  i1tlfLCG08MW"
FONT_SIZE = 24
WHITE_FLOOR = 200  # global branch: >= this is blank background/skin highlight
FACE_FLOOR = 85  # dual branch: face density clamp((lum-85)/(230-85)), dark -> space
FACE_CAP = 230  # dual branch: >= this is blank (wall, earbud, glints)
ALPHA_MIN = 150  # dual branch: below this alpha is outer background -> space
MIN_COLUMNS = 32
MAX_COLUMNS = 160

_DARK_BG = (13, 17, 23)
_LIGHT_BG = (255, 255, 255)
_DARK_FG = (201, 209, 217)
_LIGHT_FG = (36, 41, 47)
PAD = 10

_cell_cache: tuple[int, int] | None = None


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = ROOT / "assets" / "fonts" / "IBMPlexMono-Regular.ttf"
    if path.is_file():
        try:
            return ImageFont.truetype(str(path), FONT_SIZE)
        except OSError:
            pass
    return ImageFont.load_default()


def _cell_metrics() -> tuple[int, int]:
    """Measured monospace cell from the bundled Plex font (not hardcoded)."""
    global _cell_cache
    if _cell_cache is not None:
        return _cell_cache
    path = ROOT / "assets" / "fonts" / "IBMPlexMono-Regular.ttf"
    try:
        if path.is_file():
            font = ImageFont.truetype(str(path), FONT_SIZE)
            advance = font.getlength("M")
            ascent, descent = font.getmetrics()
            cell_w = max(1, int(round(advance)))
            cell_h = int(ascent + descent)
            if cell_w > 0 and cell_h > cell_w:
                _cell_cache = (cell_w, cell_h)
                return _cell_cache
    except OSError:
        pass
    _cell_cache = (12, 27)
    return _cell_cache


def _grid_rows(height: int, width: int, columns: int) -> int:
    cell_w, cell_h = _cell_metrics()
    rows = max(1, round(height / width * columns * cell_w / cell_h))
    if rows > 256:
        raise ValueError("Crop the photo closer to the face before converting it.")
    return rows


def _prepare_gray(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=3))
    return gray


def _has_transparency(image: Image.Image) -> bool:
    if image.mode not in ("RGBA", "LA"):
        return False
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    return extrema[0] < 250


def to_characters(
    image: Image.Image,
    columns: int = 80,
    hair_mask: Image.Image | None = None,
) -> list[str]:
    """Map a photo to letters/numbers/spaces with genuine eye/lens voids.

    Global branch (opaque photo, no mask): dark maps dense, bright maps
    blank, so skin stays open and hair reads dense. Dual branch (alpha
    background or hair mask, i.e. the isolated real portrait): hair cells
    stay dense via the mask (or a top-dark auto mask) while face cells use
    an inverted sparse ramp where the darkest cores (pupils, nostrils,
    mouth interior) fall to space and frames/lips read as accents.
    """
    if not MIN_COLUMNS <= columns <= MAX_COLUMNS:
        raise ValueError(f"Choose between {MIN_COLUMNS} and {MAX_COLUMNS} columns.")
    image = ImageOps.exif_transpose(image)
    dual = hair_mask is not None or _has_transparency(image)

    if dual:
        return _to_characters_dual(image, columns, hair_mask)

    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image)
    gray = _prepare_gray(image)
    rows = _grid_rows(gray.height, gray.width, columns)
    small = gray.resize((columns, rows), Image.Resampling.LANCZOS)
    pixels = list(small.get_flattened_data())
    ramp_last = len(RAMP) - 1
    out: list[str] = []
    for y in range(rows):
        chars: list[str] = []
        for x in range(columns):
            value = pixels[y * columns + x]
            if value >= WHITE_FLOOR:
                chars.append(" ")
            else:
                chars.append(RAMP[value * ramp_last // 255])
        out.append("".join(chars))
    return out


def _to_characters_dual(
    image: Image.Image,
    columns: int,
    hair_mask: Image.Image | None,
) -> list[str]:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    alpha = image.getchannel("A")
    gray = _prepare_gray(image.convert("RGB"))
    rows = _grid_rows(gray.height, gray.width, columns)
    small = gray.resize((columns, rows), Image.Resampling.LANCZOS)
    alpha_small = alpha.resize((columns, rows), Image.Resampling.BILINEAR)
    gray_px = list(small.get_flattened_data())
    alpha_px = list(alpha_small.get_flattened_data())
    if hair_mask is not None:
        mask_small = hair_mask.convert("L").resize((columns, rows), Image.Resampling.BILINEAR)
        mask_px = list(mask_small.get_flattened_data())
    else:
        mask_px = None
    face_last = len(RAMP_FACE) - 1
    grid = gray_px
    out: list[str] = []
    for y in range(rows):
        chars: list[str] = []
        for x in range(columns):
            i = y * columns + x
            lum = grid[i]
            if alpha_px[i] < ALPHA_MIN or lum >= FACE_CAP:
                chars.append(" ")
                continue
            is_hair = False
            if mask_px is not None:
                is_hair = mask_px[i] > 128
            else:
                is_hair = y < rows * 0.45 and lum < 110
            if is_hair:
                density = (205 - lum) / 170
                density = min(1.0, max(0.0, density))
                chars.append(RAMP_FACE[round(density * face_last)])
            else:
                density = (lum - FACE_FLOOR) / (FACE_CAP - FACE_FLOOR)
                density = min(1.0, max(0.0, density))
                chars.append(RAMP_FACE[round(density * face_last)])
        out.append("".join(chars))
    return out


def render_portrait(rows: list[str], dark: bool) -> Image.Image:
    cell_w, cell_h = _cell_metrics()
    font = _font()
    width = len(rows[0]) * cell_w + PAD * 2
    height = len(rows) * cell_h + PAD * 2
    bg = _DARK_BG if dark else _LIGHT_BG
    fg = _DARK_FG if dark else _LIGHT_FG
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    for r, row in enumerate(rows):
        y = PAD + r * cell_h
        for c, char in enumerate(row):
            if char == " ":
                continue
            draw.text((PAD + c * cell_w, y), char, font=font, fill=fg, anchor="lt")
    return image


def _prefix_rows(rows: list[str], count: int) -> list[str]:
    prefix: list[str] = []
    remaining = count
    for row in rows:
        if remaining <= 0:
            prefix.append(" " * len(row))
            continue
        if remaining >= len(row):
            prefix.append(row)
            remaining -= len(row)
        else:
            prefix.append(row[:remaining] + " " * (len(row) - remaining))
            remaining = 0
    return prefix


def save_typing_gif(rows: list[str], path, dark: bool, typing_seconds: float = 6.0) -> None:
    total = sum(len(row) for row in rows)
    n_typing = max(12, min(60, max(12, total // 60)))
    frames: list[Image.Image] = []
    for i in range(n_typing):
        if n_typing == 1:
            count = total
        else:
            count = round(total * i / (n_typing - 1))
        frames.append(render_portrait(_prefix_rows(rows, count), dark))
    typing_ms = max(1, int(round(typing_seconds * 1000)))
    per_frame = max(20, typing_ms // max(1, n_typing))
    durations = [per_frame] * (n_typing - 1) + [max(1200, per_frame)]
    # Final held portrait equals the static render; duplicate last for hold.
    frames.append(render_portrait(rows, dark))
    durations.append(max(1500, per_frame * 4))
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=False,
    )


def insert_portrait(readme: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of portrait markers.")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if end < start:
        raise ValueError("Portrait markers are out of order.")
    picture = '''
<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="./assets/portrait/portrait-dark.png" />
    <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: light)" srcset="./assets/portrait/portrait-light.png" />
    <source media="(prefers-color-scheme: dark)" srcset="./assets/portrait/portrait-dark.gif" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/portrait/portrait-light.gif" />
    <img src="./assets/portrait/portrait-light.png" alt="Rijan Ghimire ASCII portrait, typed from letters and numbers" width="180" />
  </picture>
</p>
'''
    return readme[:start] + picture + readme[end:]


def _strip_and_store_source(photo: Path, directory: Path) -> Path:
    """Copy the photo stripping all metadata (fresh pixels, no EXIF/ICC/XMP)."""
    with Image.open(photo) as image:
        image = ImageOps.exif_transpose(image)
        has_alpha = image.mode in ("RGBA", "LA", "PA")
        if has_alpha:
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")
        fresh = Image.frombytes(image.mode, image.size, image.tobytes())
    target = directory / "source.png"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / ".source.png.tmp"
    fresh.save(temporary, format="PNG")
    temporary.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", nargs="?", type=Path)
    parser.add_argument("--columns", type=int, default=80)
    args = parser.parse_args()
    directory = ROOT / "assets" / "portrait"
    photo = args.photo
    if photo is None:
        sources = [directory / f"source{ext}" for ext in (".png", ".jpg", ".jpeg", ".webp")]
        sources = [source for source in sources if source.is_file()]
        if len(sources) > 1:
            raise ValueError("Keep just one source photo in assets/portrait.")
        if not sources:
            print("No portrait photo yet; leaving the header unchanged.")
            return
        photo = sources[0]
    else:
        photo = _strip_and_store_source(photo, directory)
    with Image.open(photo) as image:
        image = ImageOps.exif_transpose(image)
        mask_path = directory / "hair-mask.png"
        hair_mask = None
        if mask_path.is_file():
            hair_mask = Image.open(mask_path).convert("L")
            if hair_mask.size != image.size:
                raise ValueError(
                    f"hair-mask.png is {hair_mask.size} but the source is "
                    f"{image.size}; replace or delete the mask for a new photo."
                )
        rows = to_characters(image, args.columns, hair_mask=hair_mask)
    readme = ROOT / "README.md"
    updated = insert_portrait(readme.read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    render_portrait(rows, True).save(directory / "portrait-dark.png")
    render_portrait(rows, False).save(directory / "portrait-light.png")
    save_typing_gif(rows, directory / "portrait-dark.gif", True)
    save_typing_gif(rows, directory / "portrait-light.gif", False)
    (directory / "portrait.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    readme.write_text(updated, encoding="utf-8")
    print(f"Generated a {len(rows[0])}-column portrait from {photo.name}.")


if __name__ == "__main__":
    main()
