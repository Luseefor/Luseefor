from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import update_profile as profile


def entry(number=1, repo="Luseefor/vinculum", date="2026-10-17T12:00:00Z", title="A change"):
    return {
        "date": date, "repo": repo, "title": title,
        "url": f"https://github.com/{repo}/pull/{number}",
        "label": f"{repo} #{number}",
    }


def search_item(number=7, repo="other/project", date="2026-10-17T12:00:00Z",
                title="Improve storage", login="Luseefor", merged_at="__default__"):
    return {
        "pull_request": {"merged_at": date if merged_at == "__default__" else merged_at},
        "user": {"login": login},
        "repository_url": f"https://api.github.com/repos/{repo}",
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "title": title, "number": number,
    }


def github_dispatch(search_result, files_by_number, releases_by_repo=None):
    """Route github() calls to search results, files pages, or releases."""
    releases_by_repo = releases_by_repo or {}

    def fake(path):
        if path.startswith("search/issues?"):
            return search_result
        if "/pulls/" in path and path.endswith("/files?per_page=100&page=1") or (
                "/pulls/" in path and "/files?" in path):
            # Parse repos/{repo}/pulls/{n}/files?per_page=100&page={p}
            resource, _, query = path.partition("?")
            parts = resource.split("/")
            number = int(parts[parts.index("pulls") + 1])
            params = dict(pair.split("=") for pair in query.split("&") if "=" in pair)
            page = int(params.get("page", "1"))
            pages = files_by_number[number]
            if isinstance(pages, list) and pages and isinstance(pages[0], list):
                # Explicit pages: [[page1], [page2], ...]
                return pages[page - 1] if page - 1 < len(pages) else []
            return pages if page == 1 else []
        if path.startswith("repos/") and path.endswith("/releases?per_page=5"):
            repo = path.split("/releases")[0].removeprefix("repos/")
            return releases_by_repo.get(repo, [])
        raise AssertionError(f"unexpected github path: {path}")

    return fake


class FeedTests(unittest.TestCase):
    def test_newest_first_with_diversity_and_no_duplicates(self):
        work = [
            entry(1, date="2026-09-01T12:00:00Z"),
            entry(2), entry(2), entry(3),
            entry(4, repo="other/project"),
            entry(5, repo="other/project"),
            entry(6, repo="third/project"),
        ]
        rendered = profile.render_work(work)
        self.assertEqual(rendered.count('<a href='), 4)
        self.assertEqual(rendered.count('vinculum/pull/2"'), 1)
        self.assertNotIn('vinculum/pull/1"', rendered)
        self.assertIn('other/project', rendered)

    def test_titles_cannot_inject_markup(self):
        rendered = profile.render_work([entry(title='<img src=x> [link](bad) | **bold**\nnext')])
        self.assertNotIn('<img', rendered)
        self.assertIn('&lt;img src=x&gt;', rendered)
        self.assertIn(r'\[link\]', rendered)
        self.assertIn(r'\*\*bold\*\*', rendered)

    def test_rejects_unexpected_urls(self):
        bad = entry()
        bad['url'] = 'https://example.com/redirect'
        with self.assertRaises(ValueError):
            profile.render_work([bad])

    def test_empty_feed(self):
        self.assertIn('Public releases and merged pull requests', profile.render_work([]))

    def test_replacement_preserves_handwritten_content_and_is_idempotent(self):
        original = f'Introduction\n{profile.START}\nOld work\n{profile.END}\nProjects\n'
        updated = profile.replace_feed(original, 'New work')
        self.assertTrue(updated.startswith('Introduction\n'))
        self.assertTrue(updated.endswith('\nProjects\n'))
        self.assertNotIn('Old work', updated)
        self.assertEqual(profile.replace_feed(updated, 'New work'), updated)

    def test_missing_duplicate_or_reversed_markers_fail(self):
        for readme in ['', profile.START * 2 + profile.END, profile.END + profile.START]:
            with self.subTest(readme=readme), self.assertRaises(ValueError):
                profile.replace_feed(readme, 'New work')

    def test_collection_uses_merge_time_and_skips_unmerged_other_authors_and_drafts(self):
        item = search_item()
        release = {
            'published_at': '2026-10-16T12:00:00Z', 'draft': False,
            'prerelease': False, 'tag_name': 'v1.0.0',
            'html_url': 'https://github.com/Luseefor/vinculum/releases/tag/v1.0.0',
        }
        result = {'total_count': 3, 'items': [
            item, search_item(login='someone-else'),
            search_item(merged_at=None),
        ]}
        files = {7: [[{'filename': 'src/storage.py'}]]}
        releases = {'Luseefor/vinculum': [release, dict(release, draft=True),
                                          dict(release, prerelease=True),
                                          dict(release, published_at='2025-01-01T00:00:00Z')]}
        with patch.object(profile, 'PROJECTS', ('vinculum',)), patch.object(
            profile, 'github', side_effect=github_dispatch(result, files, releases),
        ) as fetch:
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertEqual(len(work), 2)
        self.assertEqual(work[0]['date'], '2026-10-17T12:00:00Z')
        query = fetch.call_args_list[0].args[0]
        self.assertIn('is%3Apublic', query)
        self.assertIn('-repo%3ALuseefor%2FLuseefor', query)
        self.assertIn('merged%3A%3E%3D2026-07-20', query)

    def test_incomplete_search_fails_instead_of_publishing_partial_data(self):
        with patch.object(profile, 'github', return_value={
            'incomplete_results': True, 'total_count': 1, 'items': [],
        }), self.assertRaises(RuntimeError):
            profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))

    def test_path_filter_keeps_code_config_build_test(self):
        for path in ('src/app.py', 'apps/graph/lib/math/runtime/rustMath.ts',
                     'pyproject.toml', '.github/workflows/update-profile.yml',
                     'Dockerfile', 'Makefile', 'tests/test_update_profile.py',
                     'configs/app.json', 'unknown/thing.xyz',
                     'src/security.py', 'lib/changelog.py'):
            with self.subTest(path=path):
                self.assertFalse(profile.is_non_substantive_path(path), path)

    def test_path_filter_excludes_docs_media_metadata_only(self):
        for path in ('README.md', 'docs/guide.md', 'DOCUMENTATION/api.rst',
                     'assets/portrait/portrait-dark.png', 'img/logo.svg',
                     'demo.mp4', '.gitignore', '.gitattributes', 'LICENSE',
                     'NOTICE', '.github/PULL_REQUEST_TEMPLATE.md',
                     '.github/ISSUE_TEMPLATE/bug.md', 'wiki/Home.md'):
            with self.subTest(path=path):
                self.assertTrue(profile.is_non_substantive_path(path), path)

    def test_misleading_titles_follow_files_not_titles(self):
        # A README rewrite titled like a feature is skipped; a real code
        # change titled like docs is retained. Releases are preserved.
        docs_only = search_item(11, repo='Luseefor/vinculum', date='2026-10-17T12:00:00Z',
                                title='feature: awesome rewrite')
        code_fix = search_item(12, repo='Luseefor/vinculum', date='2026-10-16T12:00:00Z',
                               title='docs: fix typo')
        result = {'total_count': 2, 'items': [docs_only, code_fix]}
        files = {
            11: [[{'filename': 'README.md'}]],
            12: [[{'filename': 'src/app.py'}]],
        }
        release = {
            'published_at': '2026-10-15T12:00:00Z', 'draft': False,
            'prerelease': False, 'tag_name': 'v1.2.0',
            'html_url': 'https://github.com/Luseefor/vinculum/releases/tag/v1.2.0',
        }
        releases = {'Luseefor/vinculum': [release]}
        with patch.object(profile, 'PROJECTS', ('vinculum',)), patch.object(
            profile, 'github', side_effect=github_dispatch(result, files, releases),
        ):
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        urls = [item['url'] for item in work]
        self.assertIn('https://github.com/Luseefor/vinculum/pull/12', urls)
        self.assertNotIn('https://github.com/Luseefor/vinculum/pull/11', urls)
        self.assertIn('https://github.com/Luseefor/vinculum/releases/tag/v1.2.0', urls)
        rendered = profile.render_work(work)
        self.assertIn('vinculum/pull/12', rendered)
        self.assertNotIn('vinculum/pull/11', rendered)

    def test_mixed_and_metadata_only_prs_excluded(self):
        mixed = search_item(21, date='2026-10-17T12:00:00Z', title='feature: mixed')
        meta_only = search_item(22, date='2026-10-16T12:00:00Z', title='chore: meta')
        result = {'total_count': 2, 'items': [mixed, meta_only]}
        files = {
            21: [[{'filename': 'README.md'}, {'filename': 'src/app.py'}]],
            22: [[{'filename': 'README.md'}, {'filename': '.gitignore'},
                   {'filename': 'docs/guide.md'}, {'filename': 'img/a.png'}]],
        }
        with patch.object(profile, 'PROJECTS', ()), patch.object(
            profile, 'github', side_effect=github_dispatch(result, files),
        ):
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertEqual([item['url'] for item in work],
                         ['https://github.com/other/project/pull/21'])

    def test_files_pagination_finds_code_on_later_page(self):
        item = search_item(31, date='2026-10-17T12:00:00Z')
        result = {'total_count': 1, 'items': [item]}
        first_page = [{'filename': f'docs/page-{i}.md'} for i in range(100)]
        files = {31: [first_page, [{'filename': 'src/app.py'}]]}
        calls = []

        def fake(path):
            calls.append(path)
            return github_dispatch(result, files)(path)

        with patch.object(profile, 'PROJECTS', ()), patch.object(
            profile, 'github', side_effect=fake,
        ):
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertEqual(len(work), 1)
        file_calls = [call for call in calls if '/pulls/31/files?' in call]
        self.assertIn('repos/other/project/pulls/31/files?per_page=100&page=1', file_calls)
        self.assertIn('repos/other/project/pulls/31/files?per_page=100&page=2', file_calls)

    def test_stops_after_newest_four_without_fetching_older(self):
        items = [search_item(number=n, repo=f'org/repo{n}',
                             date=f'2026-10-{18 - (n - 40):02d}T12:00:00Z')
                 for n in range(40, 46)]
        result = {'total_count': 6, 'items': items}
        files = {n: [[{'filename': 'src/app.py'}]] for n in range(40, 46)}
        calls = []

        def fake(path):
            calls.append(path)
            return github_dispatch(result, files)(path)

        with patch.object(profile, 'PROJECTS', ()), patch.object(
            profile, 'github', side_effect=fake,
        ):
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertEqual(len(work), 4)
        file_calls = [call for call in calls if '/files?' in call]
        self.assertEqual(len(file_calls), 4)
        for n in range(44, 46):
            self.assertFalse(any(f'/pulls/{n}/files?' in call for call in file_calls),
                             f'older PR {n} should not be fetched')

    def test_max_two_per_repo_keeps_scanning_for_diversity(self):
        items = [
            search_item(51, repo='org/a', date='2026-10-17T12:00:00Z'),
            search_item(52, repo='org/a', date='2026-10-16T12:00:00Z'),
            search_item(53, repo='org/a', date='2026-10-15T12:00:00Z'),
            search_item(54, repo='org/b', date='2026-10-14T12:00:00Z'),
            search_item(55, repo='org/b', date='2026-10-13T12:00:00Z'),
            search_item(56, repo='org/c', date='2026-10-12T12:00:00Z'),
        ]
        result = {'total_count': 6, 'items': items}
        files = {n: [[{'filename': 'src/app.py'}]] for n in range(51, 57)}
        calls = []

        def fake(path):
            calls.append(path)
            return github_dispatch(result, files)(path)

        with patch.object(profile, 'PROJECTS', ()), patch.object(
            profile, 'github', side_effect=fake,
        ):
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
            rendered = profile.render_work(work)
        file_calls = [call for call in calls if '/files?' in call]
        self.assertTrue(any('/pulls/55/files?' in call for call in file_calls))
        self.assertFalse(any('/pulls/56/files?' in call for call in file_calls))
        self.assertIn('org/a/pull/51', rendered)
        self.assertIn('org/a/pull/52', rendered)
        self.assertNotIn('org/a/pull/53', rendered)
        self.assertIn('org/b/pull/54', rendered)
        self.assertIn('org/b/pull/55', rendered)

    def test_files_api_failure_fails_closed_without_partial_data(self):
        item = search_item()
        result = {'total_count': 1, 'items': [item]}

        def fake(path):
            if path.startswith('search/issues?'):
                return result
            raise URLError('transient network failure')

        with patch.object(profile, 'PROJECTS', ()), patch.object(
            profile, 'github', side_effect=fake,
        ), self.assertRaises(Exception):
            profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))

    def test_main_failure_leaves_readme_intact(self):
        from scripts import rank_projects
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = f'Intro\n{profile.START}\nOld feed\n{profile.END}\nTail\n'
            (root / 'README.md').write_text(original, encoding='utf-8')
            (root / 'profile-projects.json').write_text('{}', encoding='utf-8')
            with patch.object(profile, 'ROOT', root), patch.object(
                rank_projects, 'collect_projects', return_value=[],
            ), patch.object(
                rank_projects, 'selected_projects', return_value=[],
            ), patch.object(
                rank_projects, 'render_projects', return_value='projects',
            ), patch.object(
                rank_projects, 'replace_projects', side_effect=lambda readme, content: readme,
            ), patch.object(profile, 'collect_work', side_effect=RuntimeError('boom')):
                with self.assertRaises(RuntimeError):
                    profile.main()
            self.assertEqual((root / 'README.md').read_text(encoding='utf-8'), original)
            self.assertFalse((root / 'README.md').with_suffix('.md.tmp').exists())



class ChangedFileSafetyTests(unittest.TestCase):
    def test_submodule_configuration_and_renamed_code_remain_substantive(self):
        self.assertTrue(profile.has_substantive_change([{'filename': '.gitmodules'}]))
        self.assertTrue(profile.has_substantive_change([
            {'filename': 'docs/old-code.md', 'previous_filename': 'src/old-code.py'}]))

    def test_file_api_cap_fails_instead_of_treating_truncated_pr_as_docs(self):
        with patch.object(profile, 'github', return_value=[{'filename': 'README.md'}] * 100) as api:
            with self.assertRaisesRegex(RuntimeError, '3,000-file cap'):
                profile.pull_request_files('Luseefor/project', 1)
        self.assertEqual(api.call_count, 30)


if __name__ == '__main__':
    unittest.main()
