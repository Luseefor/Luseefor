#!/usr/bin/env python3
"""Discover and rank public projects using bounded, inspectable signals."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from scripts.update_profile import USERNAME, github

ROOT = Path(__file__).resolve().parents[1]
VERSION = 1
START = '<!-- projects:start -->'
END = '<!-- projects:end -->'
MAX_ARCHIVE = 60 * 1024 * 1024
MAX_EXPANDED = 200 * 1024 * 1024
SOURCE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.swift', '.go', '.c', '.cpp',
    '.h', '.hpp', '.java', '.kt', '.m', '.mm', '.cs', '.rb', '.sh', '.sql',
    '.css', '.scss', '.html', '.vue', '.svelte', '.ex', '.exs', '.zig', '.dart',
}
EXCLUDED_DIRS = {
    'node_modules', 'vendor', 'third_party', 'third-party', 'dist', 'build',
    'target', 'public', 'assets', 'data', 'examples', 'fixtures', '__tests__',
    'tests', 'test', 'coverage', 'generated', '.build', '.next', '.git', 'video',
}
GENERATED = re.compile(r'(?:\.test\.|\.spec\.|\.generated\.|\.min\.|\.d\.ts$|Tests?\.)', re.I)


def inventory() -> list[dict]:
    repos = []
    page = 1
    while True:
        batch = github(f'users/{USERNAME}/repos?type=owner&per_page=100&page={page}')
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def source_lines(path: str, content: str) -> int:
    """Approximate authored source size, not a claim of exact executable LOC.

    Excludes blank and comment-only lines, tests, bundled/generated files and
    showcase video code. Inline comments count with their source statement.
    """
    p = PurePosixPath(path)
    if (p.suffix.lower() not in SOURCE_EXTENSIONS
            or set(x.lower() for x in p.parts) & EXCLUDED_DIRS
            or GENERATED.search(p.name)):
        return 0
    if re.search(r'(?im)^.{0,12}(?:auto[- ]generated|code generated|@generated|do not edit)', content[:1024]):
        return 0
    count, block = 0, False
    hash_comments = p.suffix.lower() in {'.py', '.rb', '.sh', '.ex', '.exs'}
    for line in content.splitlines():
        text = line.strip()
        if block:
            if '*/' not in text:
                continue
            text = text.split('*/', 1)[1].strip()
            block = False
        if text.startswith('/*'):
            if '*/' not in text:
                block = True
                continue
            text = text.split('*/', 1)[1].strip()
        if not text or text.startswith(('//', '<!--')) or (hash_comments and text.startswith('#')):
            continue
        count += 1
    return count


def readme_signals(readme: str) -> dict[str, bool]:
    """Documentation completeness signals; these do not certify correctness."""
    # Ignore comments and code when detecting structure or purpose prose.
    clean = re.sub(r'<!--[\s\S]*?-->', '', readme)
    prose = re.sub(r'```[\s\S]*?```', '', clean)
    headings = re.findall(r'^#{1,6}\s+(.+)$', prose, re.M)
    sections = '\n'.join(headings).lower()
    commands = bool(re.search(r'(?:^|[\s`])(?:bun|npm|pnpm|yarn|uv|python3?|cargo|swift|docker|go|make|xcodebuild)\s+[\w:-]+', clean))
    paragraphs = re.split(r'\n\s*\n', prose)
    purpose = any(len(re.sub(r'<[^>]+>|!\[[^]]*\]\([^)]*\)', '', p).strip()) >= 70
                  and not p.lstrip().startswith(('#', '-', '|', '<', '[')) for p in paragraphs[:5])
    return {
        'purpose': purpose,
        'setup': commands and bool(re.search(r'setup|install|quickstart|quick start|try it|build|local development|run the', sections)),
        'usage': bool(re.search(r'features|usage|product|what works|how to use|user documentation|local decision study', sections)),
        'internals': bool(re.search(r'architecture|internals|how .+ works|computation|design', sections)),
        'verification': bool(re.search(r'(?:^|[\s`])(?:bun run|npm run|pnpm|uv run|cargo|swift|go|npm)\s+(?:test[\w:-]*|check[\w:-]*|pytest|typecheck|lint|build)', clean)),
        'license': bool(re.search(r'license|licence', sections)),
    }


def inspect_archive(data: bytes) -> dict:
    lines, readme = 0, ''
    with tarfile.open(fileobj=io.BytesIO(data), mode='r|gz') as archive:
        expanded, members = 0, 0
        for member in archive:
            expanded += member.size
            members += 1
            if expanded > MAX_EXPANDED or members > 30000:
                raise ValueError('Repository archive exceeds inspection limits.')
            if not member.isfile():
                continue
            path = PurePosixPath(*PurePosixPath(member.name).parts[1:])
            is_readme = len(path.parts) == 1 and path.name.lower() in {'readme.md', 'readme.markdown', 'readme'}
            if not is_readme and (path.suffix.lower() not in SOURCE_EXTENSIONS
                                  or set(x.lower() for x in path.parts) & EXCLUDED_DIRS
                                  or GENERATED.search(path.name)):
                continue
            if member.size > 2 * 1024 * 1024:
                continue
            content = archive.extractfile(member).read().decode('utf-8', errors='replace')
            if is_readme:
                readme = content
            else:
                lines += source_lines(str(path), content)
    signals = readme_signals(readme)
    return {'source_lines': lines, 'readme_signals': signals,
            'readme_points': sum(signals.values()) * 10}


def download_archive(name: str, sha: str) -> bytes:
    request = Request(f'https://codeload.github.com/{USERNAME}/{quote(name, safe="")}/tar.gz/{sha}',
                      headers={'User-Agent': 'Luseefor-profile'})
    with urlopen(request, timeout=90) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError(f'{name}: repository archive exceeds inspection limits.')
    return data


def plain(text: str, limit: int = 240) -> str:
    text = ' '.join(re.sub(r'<[^>]*>', '', text).split())
    if len(text) > limit:
        text = text[:limit - 1].rsplit(' ', 1)[0] + '…'
    return text


def score(measurement: dict) -> float:
    # Size saturates at 100k source lines; doubling a large repo buys few points.
    size_points = min(40, 8 * math.log10(1 + measurement['source_lines']))
    return round(measurement['readme_points'] + size_points, 2)


def collect_projects(config: dict, previous: dict | None = None) -> list[dict]:
    cached = {p['name']: p for p in (previous or {}).get('projects', [])}
    cache_valid = (previous or {}).get('version') == VERSION
    excluded = {name.lower() for name in config['exclude']}
    candidates = [r for r in inventory() if not (
        r['private'] or r['fork'] or r['archived'] or r.get('disabled')
        or r.get('is_template') or not r['size']
        or r['name'].lower() in excluded
        or r['owner']['login'].lower() != USERNAME.lower()
    )]

    def inspect(repo):
        name = repo['name']
        try:
            commit = github(f'repos/{USERNAME}/{quote(name, safe="")}/commits/{quote(repo["default_branch"], safe="")}')
        except HTTPError as error:
            # A newly created empty repo has no default-branch commit yet.
            if error.code == 409:
                return None
            raise
        sha = commit['sha']
        if not re.fullmatch(r'[a-f0-9]{40}', sha):
            raise ValueError('Unexpected commit SHA.')
        old = cached.get(name, {})
        if cache_valid and old.get('sha') == sha:
            measurement = {key: old[key] for key in ('source_lines', 'readme_signals', 'readme_points')}
        else:
            measurement = inspect_archive(download_archive(name, sha))
        override = config.get('projects', {}).get(name, {})
        description = plain(override.get('description') or repo.get('description') or '')
        homepage = override.get('homepage', repo.get('homepage') or '')
        parsed = urlsplit(homepage)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password:
            homepage = ''
        return {
            'name': name, 'title': plain(override.get('title') or name, 80), 'sha': sha,
            **measurement, 'score': score(measurement),
            'description': description, 'language': repo.get('language') or '',
            'homepage': homepage, 'pushed_at': repo.get('pushed_at') or '',
            'eligible': bool(description) and measurement['source_lines'] >= config['minimum_source_lines']
                        and measurement['readme_points'] >= config['minimum_readme_points'],
        }

    # All results must succeed before anything is published. No partial ranking.
    with ThreadPoolExecutor(max_workers=3) as pool:
        projects = [p for p in pool.map(inspect, candidates) if p is not None]
    return sorted(projects, key=lambda p: (-p['score'], -p['source_lines'], p['name'].lower()))


def selected_projects(projects: list[dict], config: dict) -> list[dict]:
    return [p for p in projects if p['eligible']][:config['featured_count']]


def render_projects(projects: list[dict]) -> str:
    rows = []
    for project in projects:
        name = project['name']
        if not re.fullmatch(r'[\w.-]+', name):
            raise ValueError('Unexpected repository name.')
        source = f'https://github.com/{USERNAME}/{quote(name, safe="")}'
        title = escape(project['title'])
        description = escape(project['description'])
        links = f'<a href="{source}">Source & documentation</a>'
        if project['homepage']:
            links = f'<a href="{escape(project["homepage"], quote=True)}">Website</a> · ' + links
        rows.append(f'<h3><a href="{source}">{title}</a></h3>\n\n<p>{description}</p>\n\n{links}')
    if not rows:
        raise ValueError('No eligible projects; keeping the existing profile.')
    return '\n\n'.join(rows)


def replace_projects(readme: str, content: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError('README must contain exactly one pair of project markers.')
    start, end = readme.index(START) + len(START), readme.index(END)
    if end < start:
        raise ValueError('Project markers are out of order.')
    return readme[:start] + '\n' + content + '\n' + readme[end:]


def snapshot(projects: list[dict]) -> str:
    return json.dumps({'version': VERSION, 'projects': projects}, indent=2, ensure_ascii=False) + '\n'
