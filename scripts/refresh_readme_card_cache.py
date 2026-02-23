#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


KATHMANDU = timezone(timedelta(hours=5, minutes=45))
TARGET_HOSTS = {
    "github-profile-summary-cards.vercel.app",
    "streak-stats.demolab.com",
}


def bump_cache_token(text: str, token: str) -> str:
    pattern = re.compile(r'https://[^\s"\'<>]+')

    def replace(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        parsed = urlparse(raw_url)
        if parsed.netloc not in TARGET_HOSTS:
            return raw_url

        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params["cb"] = token
        new_query = urlencode(params)
        return urlunparse(parsed._replace(query=new_query))

    return pattern.sub(replace, text)


def main() -> int:
    path = Path("README.md")
    if not path.exists():
        return 0

    token = datetime.now(KATHMANDU).strftime("%Y%m%d")
    original = path.read_text(encoding="utf-8")
    updated = bump_cache_token(original, token)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
