#!/usr/bin/env python3
"""
Decorate Platane/snk output with premium framing and date labels.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Mon", "Wed", "Fri", "Sun"]
ACCENT_MAGENTA = "#FF2BD6"
ACCENT_CYAN = "#00B8D9"
ACCENT_YELLOW = "#FFD166"


def extract_size(svg: str) -> tuple[int, int]:
    width_match = re.search(r'width="(\d+)"', svg)
    height_match = re.search(r'height="(\d+)"', svg)
    if not width_match or not height_match:
        return (980, 180)
    return (int(width_match.group(1)), int(height_match.group(1)))


def extract_inner(svg: str) -> str:
    start = svg.find(">")
    end = svg.rfind("</svg>")
    if start == -1 or end == -1:
        raise ValueError("Invalid SVG content: missing root svg tags.")
    inner = svg[start + 1 : end].strip()
    inner = re.sub(r"<title[^>]*>.*?</title>", "", inner, flags=re.DOTALL)
    inner = re.sub(r"<desc[^>]*>.*?</desc>", "", inner, flags=re.DOTALL)
    return inner.strip()


def month_labels(width: int) -> str:
    start_x = 110
    usable_width = max(width - 160, 300)
    step = usable_width / 11
    labels = []
    for idx, name in enumerate(MONTHS):
        x = round(start_x + (idx * step), 2)
        labels.append(
            f'<text x="{x}" y="28" fill="{ACCENT_CYAN}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="12">{name}</text>'
        )
    return "\n    ".join(labels)


def weekday_labels() -> str:
    base_x = 22
    base_y = 95
    gap = 34
    labels = []
    for idx, name in enumerate(WEEKDAYS):
        y = base_y + (idx * gap)
        labels.append(
            f'<text x="{base_x}" y="{y}" fill="{ACCENT_YELLOW}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="12">{name}</text>'
        )
    return "\n    ".join(labels)


def year_chips(canvas_width: int) -> str:
    now = dt.datetime.utcnow().year
    years = [now - 2, now - 1, now]
    chip_w = 60
    chip_h = 22
    gap = 10
    total_w = (chip_w * len(years)) + (gap * (len(years) - 1))
    start_x = canvas_width - total_w - 30
    out = []
    for idx, year in enumerate(years):
        x = start_x + idx * (chip_w + gap)
        active = idx == len(years) - 1
        fill = ACCENT_MAGENTA if active else "#161B22"
        stroke = ACCENT_MAGENTA if active else "#30363D"
        text = "#0D1117" if active else "#C9D1D9"
        out.append(
            f'<rect x="{x}" y="14" rx="11" width="{chip_w}" height="{chip_h}" fill="{fill}" stroke="{stroke}"/>'
        )
        out.append(
            f'<text x="{x + 16}" y="29" fill="{text}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="12" font-weight="700">{year}</text>'
        )
    return "\n    ".join(out)


def decorate(svg: str, force: bool = False) -> str:
    if not force and "data-premium-snake=\"true\"" in svg:
        return svg

    width, height = extract_size(svg)
    inner = extract_inner(svg)

    canvas_w = width + 140
    canvas_h = height + 110
    snake_x = 92
    snake_y = 52

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-labelledby="t d" data-premium-snake="true">
  <title id="t">Premium Contribution Snake</title>
  <desc id="d">Contribution snake with month and weekday labels and year chips.</desc>
  <rect width="{canvas_w}" height="{canvas_h}" rx="18" fill="#0D1117"/>
  <rect x="8" y="8" width="{canvas_w - 16}" height="{canvas_h - 16}" rx="14" fill="none" stroke="#313A4A"/>
  <text x="22" y="30" fill="{ACCENT_MAGENTA}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14" font-weight="700">CONTRIBUTION TIMELINE</text>
  {year_chips(canvas_w)}
  {month_labels(width)}
  {weekday_labels()}
  <g transform="translate({snake_x}, {snake_y})">
    {inner}
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Decorate snake svg with date labels and premium frame.")
    parser.add_argument("paths", nargs="+", help="SVG files to decorate")
    parser.add_argument("--force", action="store_true", help="Re-decorate even if marker is present")
    args = parser.parse_args()

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        svg = path.read_text(encoding="utf-8")
        path.write_text(decorate(svg, force=args.force), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
