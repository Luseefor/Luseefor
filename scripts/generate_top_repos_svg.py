#!/usr/bin/env python3
"""Fetch top public repositories and generate an SVG card for the profile README."""

from __future__ import annotations

import json
import os
import urllib.request
from xml.sax.saxutils import escape

USERNAME = "Luseefor"
API_URL = f"https://api.github.com/users/{USERNAME}/repos?sort=stars&order=desc&per_page=100"
OUTPUT_PATH = "dist/top-repos.svg"
MAX_REPOS = 6


def fetch_repos() -> list[dict]:
    request = urllib.request.Request(API_URL)
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github.v3+json")
    request.add_header("User-Agent", "Luseefor-profile-asset-generator")

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    cleaned = text.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def build_svg(repos: list[dict]) -> str:
    width = 800
    row_height = 78
    header_height = 90
    padding_bottom = 30
    height = header_height + len(repos) * row_height + padding_bottom

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-labelledby="title">',
        f'<title id="title">Top repositories for {USERNAME}</title>',
        f'<rect width="{width}" height="{height}" fill="#0A1220"/>',
        f'<rect x="40" y="30" width="{width - 80}" height="4" rx="2" fill="#58A6FF" opacity="0.8"/>',
        f'<text x="40" y="74" fill="#F0F5FA" font-family="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif" font-size="24" font-weight="800">Top Repositories</text>',
    ]

    for index, repo in enumerate(repos):
        y = header_height + index * row_height
        name = escape(repo.get("name", "unknown"))
        description = escape(truncate(repo.get("description", ""), 72))
        stars = repo.get("stargazers_count", 0)
        language = escape(repo.get("language") or "—")

        lines.extend(
            [
                f'<rect x="40" y="{y}" width="{width - 80}" height="{row_height - 12}" rx="12" fill="#0D1729" stroke="#1F2F47"/>',
                f'<text x="62" y="{y + 32}" fill="#58A6FF" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="16" font-weight="600">{name}</text>',
                f'<text x="{width - 62}" y="{y + 34}" fill="#F0F5FA" font-family="ui-sans-serif, system-ui, sans-serif" font-size="13" font-weight="600" text-anchor="end">⭐ {stars}</text>',
                f'<text x="62" y="{y + 56}" fill="#7A9CC6" font-family="ui-sans-serif, system-ui, sans-serif" font-size="13">{description}</text>',
                f'<text x="{width - 62}" y="{y + 56}" fill="#7A9CC6" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" text-anchor="end">{language}</text>',
            ]
        )

    lines.append("</svg>")
    return "\n".join(lines)


def main() -> int:
    try:
        repos = fetch_repos()
    except Exception as exc:
        print(f"Failed to fetch repositories: {exc}")
        repos = []

    # Exclude the special profile README repository.
    repos = [repo for repo in repos if repo.get("name") != USERNAME]
    top_repos = repos[:MAX_REPOS]

    svg = build_svg(top_repos)

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as output_file:
        output_file.write(svg)

    print(f"Generated {OUTPUT_PATH} with {len(top_repos)} repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
