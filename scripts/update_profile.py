#!/usr/bin/env python3
"""Refresh the public work feed. Requires only the Python standard library."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "Luseefor"
PROJECTS = ("vinculum", "LumaWall", "faredelta")
START = "<!-- recent-work:start -->"
END = "<!-- recent-work:end -->"


def github(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Luseefor-profile",
    }
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/{path}", headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def collect_work(now: datetime, projects: tuple[str, ...] | None = None) -> list[dict]:
    since = (now - timedelta(days=90)).date().isoformat()
    query = (
        f"is:pr is:merged is:public author:{USERNAME} merged:>={since} "
        f"-repo:{USERNAME}/{USERNAME}"
    )
    work = []
    page = 1
    while True:
        result = github("search/issues?" + urlencode({
            "q": query, "sort": "updated", "order": "desc",
            "per_page": 100, "page": page,
        }))
        if result.get("incomplete_results") or result["total_count"] > 1000:
            raise RuntimeError("Incomplete GitHub search; keeping the existing feed.")
        for item in result["items"]:
            merged_at = item.get("pull_request", {}).get("merged_at")
            # Only public, authored, actually merged work belongs in this feed.
            if not merged_at or item["user"]["login"].lower() != USERNAME.lower():
                continue
            repo = item["repository_url"].removeprefix("https://api.github.com/repos/")
            work.append({
                "date": merged_at, "repo": repo, "url": item["html_url"],
                "title": item["title"], "label": f"{repo} #{item['number']}",
            })
        if page * 100 >= result["total_count"]:
            break
        page += 1

    for name in PROJECTS if projects is None else projects:
        repo = f"{USERNAME}/{name}"
        for release in github(f"repos/{repo}/releases?per_page=5"):
            published = release.get("published_at")
            if release["draft"] or release["prerelease"] or not published:
                continue
            if published[:10] < since:
                continue
            work.append({
                "date": published, "repo": repo, "url": release["html_url"],
                "title": f"Released {name} {release['tag_name']}",
                "label": f"{repo} · release",
            })
    return work


def render_work(work: list[dict]) -> str:
    rows = []
    seen = set()
    per_repo: Counter = Counter()
    for item in sorted(work, key=lambda item: item["date"], reverse=True):
        if item["url"] in seen or per_repo[item["repo"]] >= 2:
            continue
        if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/(pull/\d+|releases/tag/[^\s<>]+)", item["url"]):
            raise ValueError("Unexpected activity URL; keeping the existing feed.")
        title = escape(" ".join(item["title"].split()))
        # GitHub titles are content, never README markup.
        title = re.sub(r"([\\`*_[\]{}|])", r"\\\1", title)
        label = escape(item["label"])
        url = escape(item["url"], quote=True)
        rows.append(
            f'- <a href="{url}">{title}</a><br />\n'
            f'  <sub>{item["date"][:10]} · {label}</sub>'
        )
        seen.add(item["url"])
        per_repo[item["repo"]] += 1
        if len(rows) == 4:
            break
    return "\n\n".join(rows) or "Public releases and merged pull requests will appear here."


def replace_feed(readme: str, feed: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of feed markers.")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if end < start:
        raise ValueError("Feed markers are out of order.")
    return readme[:start] + "\n" + feed + "\n" + readme[end:]


def main() -> None:
    # The import stays local so legacy feed-only callers remain independent.
    from scripts import rank_projects

    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    config = json.loads((ROOT / "profile-projects.json").read_text())
    ranking_path = ROOT / "data/project-ranking.json"
    previous = json.loads(ranking_path.read_text()) if ranking_path.exists() else None
    projects = rank_projects.collect_projects(config, previous)
    selected = rank_projects.selected_projects(projects, config)
    # Finish all requests and validation before touching the current README.
    updated = rank_projects.replace_projects(original, rank_projects.render_projects(selected))
    work = collect_work(datetime.now(timezone.utc), tuple(p["name"] for p in selected))
    updated = replace_feed(updated, render_work(work))
    ranking = rank_projects.snapshot(projects)
    if updated != original:
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
        print("Updated featured projects and public work.")
    else:
        print("Featured projects and public work are unchanged.")
    ranking_path.parent.mkdir(parents=True, exist_ok=True)
    if not ranking_path.exists() or ranking_path.read_text(encoding="utf-8") != ranking:
        temporary = ranking_path.with_suffix(".json.tmp")
        temporary.write_text(ranking, encoding="utf-8")
        temporary.replace(ranking_path)


if __name__ == "__main__":
    # Support both `python scripts/update_profile.py` and module invocation.
    import sys
    sys.path.insert(0, str(ROOT))
    main()
