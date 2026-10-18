#!/usr/bin/env python3
"""Convert a supplied photo into an alphanumeric SVG portrait and plain text."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- portrait:start -->"
END = "<!-- portrait:end -->"
RAMP = "MWN8B0QOCLft1i "
CELL_WIDTH = 6
CELL_HEIGHT = 10


def to_characters(image: Image.Image, columns: int = 96) -> list[str]:
    if not 32 <= columns <= 160:
        raise ValueError("Choose between 32 and 160 columns.")
    image = ImageOps.exif_transpose(image).convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)
    gray = ImageOps.autocontrast(background.convert("L"), cutoff=1)
    rows = max(1, round(gray.height / gray.width * columns * CELL_WIDTH / CELL_HEIGHT))
    if rows > 256:
        raise ValueError("Crop the photo closer to the face before converting it.")
    gray = gray.resize((columns, rows), Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data())
    return [
        "".join(RAMP[pixel * (len(RAMP) - 1) // 255] for pixel in pixels[y * columns:(y + 1) * columns])
        for y in range(rows)
    ]


def to_svg(rows: list[str], dark: bool) -> str:
    width = len(rows[0]) * CELL_WIDTH
    height = len(rows) * CELL_HEIGHT
    color = "#c9d1d9" if dark else "#24292f"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Rijan Ghimire</title>',
        '<desc id="desc">Portrait rendered entirely with letters and numbers, converted from a supplied photograph.</desc>',
        f'<g fill="{color}" font-family="Menlo,Consolas,monospace" font-size="10" xml:space="preserve">',
    ]
    for index, row in enumerate(rows):
        lines.append(f'<text x="0" y="{index * CELL_HEIGHT + 8}" textLength="{width}" lengthAdjust="spacingAndGlyphs">{escape(row)}</text>')
    return "\n".join(lines + ['</g>', '</svg>', ''])


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
    <source media="(prefers-color-scheme: dark)" srcset="./assets/portrait/portrait-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/portrait/portrait-light.svg" />
    <img src="./assets/portrait/portrait-light.svg" alt="Rijan Ghimire, a portrait made from letters and numbers" width="280" />
  </picture>
</p>
'''
    return readme[:start] + picture + readme[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", nargs="?", type=Path)
    parser.add_argument("--columns", type=int, default=96)
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
    with Image.open(photo) as image:
        rows = to_characters(image, args.columns)
    readme = ROOT / "README.md"
    updated = insert_portrait(readme.read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "portrait-dark.svg").write_text(to_svg(rows, dark=True), encoding="utf-8")
    (directory / "portrait-light.svg").write_text(to_svg(rows, dark=False), encoding="utf-8")
    (directory / "portrait.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    readme.write_text(updated, encoding="utf-8")
    print(f"Generated a {len(rows[0])}-column portrait from {photo.name}.")


if __name__ == "__main__":
    main()
