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
MAX_FEED_ITEMS = 4
MAX_PER_REPO = 2

# Extensions that are documentation or media on their own. Anything else
# defaults to substantive so unknown source/config/build/test paths are kept.
_MEDIA_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp",
    ".avif", ".heic", ".heif", ".tif", ".tiff", ".psd", ".ai", ".sketch",
    ".fig", ".blend", ".exr", ".mp4", ".mov", ".webm", ".mkv", ".mp3",
    ".wav", ".ogg", ".flac", ".m4a", ".mpg", ".mpeg", ".avi", ".woff",
    ".woff2", ".ttf", ".otf", ".eot", ".pdf",
)
_DOC_EXTENSIONS = (".md", ".mdx", ".rst", ".adoc")
_DOC_DIRS = {"docs", "documentation", "wiki", "man"}
_METADATA_BASENAMES = {
    ".gitignore", ".gitattributes", ".editorconfig",
    ".mailmap", ".gitkeep", ".git-blame-ignore-revs", "codeowners",
    "funding.yml", "funding.json",
}
_METADATA_STEMS = {
    "license", "licence", "notice", "authors", "contributing",
    "code_of_conduct", "codeofconduct", "security", "changelog",
}


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


def is_non_substantive_path(filename: str) -> bool:
    """True for documentation/media/metadata-only paths; titles are ignored.

    Anything unrecognised defaults to substantive so code, config, build
    and test changes are never dropped because of an unknown extension.
    A pull request titled ``docs: fix`` that touches real code is therefore
    kept, while a ``feature``-titled README rewrite is skipped.
    """
    lower = filename.lower()
    basename = lower.rsplit("/", 1)[-1]
    parts = lower.split("/")
    if lower.endswith(_MEDIA_EXTENSIONS):
        return True
    if lower.endswith(_DOC_EXTENSIONS):
        return True
    if any(part in _DOC_DIRS for part in parts[:-1]):
        return True
    if lower.startswith(".github/"):
        if lower.startswith(".github/workflows/"):
            return False
        if "issue_template" in lower or "pull_request_template" in lower:
            return True
        if lower.endswith(".md"):
            return True
        if basename in _METADATA_BASENAMES:
            return True
        return False
    if basename in _METADATA_BASENAMES:
        return True
    stem = basename.split(".", 1)[0]
    if stem in _METADATA_STEMS and (
        "." not in basename or basename.endswith((".md", ".markdown", ".txt", ".rst", ".adoc"))
    ):
        return True
    return False


def has_substantive_change(files: list[dict]) -> bool:
    """True when at least one changed file is code/config/build/test."""
    substantive = False
    for entry in files:
        filename = entry.get("filename")
        if not isinstance(filename, str) or not filename:
            raise RuntimeError("Unexpected pull-request files response; keeping the existing feed.")
        previous = entry.get("previous_filename")
        if previous is not None and (not isinstance(previous, str) or not previous):
            raise RuntimeError("Unexpected pull-request rename; keeping the existing feed.")
        if not is_non_substantive_path(filename) or (previous and not is_non_substantive_path(previous)):
            substantive = True
    return substantive


def pull_request_files(repo: str, number: int) -> list[dict]:
    """Fetch every changed-file entry for one pull request, paginated."""
    files: list[dict] = []
    page = 1
    while True:
        batch = github(f"repos/{repo}/pulls/{number}/files?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected pull-request files response; keeping the existing feed.")
        files.extend(batch)
        # GitHub caps this endpoint at 3,000 files. At the cap we cannot tell
        # whether an unreturned source change exists, so keep the old feed.
        if len(files) >= 3000:
            raise RuntimeError("Pull-request files reached GitHub's 3,000-file cap; keeping the existing feed.")
        if len(batch) < 100:
            return files
        page += 1


def _feed_selection(work: list[dict]) -> list[dict]:
    """Mirror render_work's newest-first, max-2-per-repo, max-4 selection."""
    selected = []
    seen = set()
    per_repo: Counter = Counter()
    for item in sorted(work, key=lambda item: item["date"], reverse=True):
        if item["url"] in seen or per_repo[item["repo"]] >= MAX_PER_REPO:
            continue
        seen.add(item["url"])
        per_repo[item["repo"]] += 1
        selected.append(item)
        if len(selected) == MAX_FEED_ITEMS:
            break
    return selected


def collect_work(now: datetime, projects: tuple[str, ...] | None = None) -> list[dict]:
    since = (now - timedelta(days=90)).date().isoformat()
    query = (
        f"is:pr is:merged is:public author:{USERNAME} merged:>={since} "
        f"-repo:{USERNAME}/{USERNAME}"
    )
    candidates = []
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
            candidates.append({
                "date": merged_at, "repo": repo, "url": item["html_url"],
                "title": item["title"], "label": f"{repo} #{item['number']}",
                "number": item["number"],
            })
        if page * 100 >= result["total_count"]:
            break
        page += 1
    # Newest merged first so file inspection can stop once the feed is full.
    candidates.sort(key=lambda item: item["date"], reverse=True)

    releases = []
    for name in PROJECTS if projects is None else projects:
        repo = f"{USERNAME}/{name}"
        for release in github(f"repos/{repo}/releases?per_page=5"):
            published = release.get("published_at")
            if release["draft"] or release["prerelease"] or not published:
                continue
            if published[:10] < since:
                continue
            releases.append({
                "date": published, "repo": repo, "url": release["html_url"],
                "title": f"Released {name} {release['tag_name']}",
                "label": f"{repo} · release",
            })

    substantive: list[dict] = []
    for index, candidate in enumerate(candidates):
        # A repo that already has two newer feed items cannot take another;
        # skip its older PRs without spending a files request. Any exception
        # below propagates so the workflow keeps the existing README.
        newer_same_repo = sum(
            1 for item in substantive + releases
            if item["repo"] == candidate["repo"] and item["date"] >= candidate["date"]
        )
        if newer_same_repo >= MAX_PER_REPO:
            continue
        files = pull_request_files(candidate["repo"], candidate["number"])
        if not has_substantive_change(files):
            continue
        substantive.append({key: candidate[key] for key in ("date", "repo", "url", "title", "label")})
        selected = _feed_selection(substantive + releases)
        if len(selected) == MAX_FEED_ITEMS and index + 1 < len(candidates):
            # Remaining candidates are older than everything selected so far
            # only when the oldest selected item is strictly newer; equal
            # timestamps keep scanning to stay deterministic.
            if selected[-1]["date"] > candidates[index + 1]["date"]:
                break
    return substantive + releases


def render_work(work: list[dict]) -> str:
    rows = []
    seen = set()
    per_repo: Counter = Counter()
    for item in sorted(work, key=lambda item: item["date"], reverse=True):
        if item["url"] in seen or per_repo[item["repo"]] >= MAX_PER_REPO:
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
        if len(rows) == MAX_FEED_ITEMS:
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
