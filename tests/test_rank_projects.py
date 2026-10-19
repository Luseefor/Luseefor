import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import rank_projects as ranking
from scripts import update_profile as profile

CONFIG = {'featured_count': 3, 'minimum_source_lines': 5000,
          'minimum_readme_points': 40, 'exclude': {'synthex-ui': 'Requested'}, 'projects': {}}


def repo(name='new-project', **kwargs):
    return {'name': name, 'owner': {'login': 'Luseefor'}, 'private': False,
            'fork': False, 'archived': False, 'disabled': False, 'is_template': False,
            'size': 10, 'default_branch': 'main', 'description': 'A useful new project.',
            'homepage': 'https://example.com', 'language': 'Python',
            'pushed_at': '2026-10-19T00:00:00Z', **kwargs}


def measurement(lines=12000, docs=50):
    return {'source_lines': lines, 'readme_points': docs, 'readme_signals': {'purpose': True}}


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo('repo-sha/' + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


class RankingTests(unittest.TestCase):
    def test_real_source_excludes_bundled_generated_tests_and_comment_only_lines(self):
        files = {
            'src/main.ts': '// comment\nconst x = 1;\n\n/* block\nmore\n*/\nrun(x);',
            'src/main.py': '# comment\nprint(1)\n\n',
            'node_modules/lib/a.ts': 'code\n' * 1000,
            'src/view.test.tsx': 'test\n' * 1000,
            'Tests/ThingTests.swift': 'test\n' * 1000,
            'src/schema.generated.ts': 'generated\n' * 1000,
            'src/generated-helper.ts': '// Code generated. DO NOT EDIT.\ncode\n' * 1000,
            'public/data.json': 'data\n' * 1000,
            'apps/video/src/scene.tsx': 'showcase\n' * 1000,
        }
        self.assertEqual(ranking.inspect_archive(archive(files))['source_lines'], 3)

    def test_padding_readme_does_not_buy_points(self):
        minimal = '# A\n\nA tiny project.\n'
        self.assertEqual(ranking.readme_signals(minimal), ranking.readme_signals(minimal + '\n' * 50000))
        self.assertFalse(ranking.readme_signals(minimal)['setup'])

    def test_documentation_scores_structure_and_commands_not_length(self):
        text = '''# Project

This project helps researchers inspect mathematical results locally and export reproducible records.

## Setup
```sh
npm install
```
## Features
- View results
## Architecture
Data is local.
## Verification
```sh
npm test
```
## License
MIT
'''
        self.assertTrue(all(ranking.readme_signals(text).values()))
        self.assertLess(ranking.score(measurement(1000000, 10)), ranking.score(measurement(6000, 60)))
        self.assertEqual(ranking.score(measurement(100000000, 60)), 100)

    def test_discovery_is_paginated_and_does_not_use_fixed_project_names(self):
        with patch.object(ranking, 'github', side_effect=[[repo(str(i)) for i in range(100)], [repo()]]):
            self.assertEqual(len(ranking.inventory()), 101)

    def test_new_better_project_replaces_old_feature_and_exclusions_stay_out(self):
        repos = [repo('old'), repo('new-tomorrow'), repo('synthex-ui'),
                 repo('private', private=True), repo('fork', fork=True),
                 repo('archived', archived=True), repo('empty', size=0)]
        with patch.object(ranking, 'inventory', return_value=repos), patch.object(
            ranking, 'github', return_value={'sha': 'a' * 40},
        ), patch.object(ranking, 'download_archive', return_value=b'archive') as download, patch.object(
            ranking, 'inspect_archive', side_effect=[measurement(6000, 40), measurement(20000, 60)],
        ):
            # Sequential executor removes scheduling dependence from the test fixture.
            with patch.object(ranking, 'ThreadPoolExecutor') as pool:
                pool.return_value.__enter__.return_value.map.side_effect = lambda f, xs: map(f, xs)
                ranked = ranking.collect_projects(CONFIG)
        self.assertEqual([p['name'] for p in ranked], ['new-tomorrow', 'old'])
        self.assertEqual(download.call_count, 2)
        self.assertEqual(ranking.selected_projects(ranked, dict(CONFIG, featured_count=1))[0]['name'], 'new-tomorrow')

    def test_size_alone_does_not_make_undocumented_project_eligible(self):
        with patch.object(ranking, 'inventory', return_value=[repo()]), patch.object(
            ranking, 'github', return_value={'sha': 'a' * 40},
        ), patch.object(ranking, 'download_archive', return_value=b''), patch.object(
            ranking, 'inspect_archive', return_value=measurement(200000, 30),
        ):
            self.assertEqual(ranking.selected_projects(ranking.collect_projects(CONFIG), CONFIG), [])

    def test_cached_code_measurement_still_refreshes_repository_description(self):
        old = {'version': ranking.VERSION, 'projects': [dict(name='new-project', sha='a'*40, **measurement())]}
        with patch.object(ranking, 'inventory', return_value=[repo(description='Updated description')]), patch.object(
            ranking, 'github', return_value={'sha': 'a'*40},
        ), patch.object(ranking, 'download_archive') as download:
            result = ranking.collect_projects(CONFIG, old)
        download.assert_not_called()
        self.assertEqual(result[0]['description'], 'Updated description')

    def test_changed_head_or_scoring_version_reinspects_code(self):
        old = {'version': ranking.VERSION, 'projects': [dict(name='new-project', sha='a'*40, **measurement())]}
        with patch.object(ranking, 'inventory', return_value=[repo()]), patch.object(
            ranking, 'github', return_value={'sha': 'b'*40},
        ), patch.object(ranking, 'download_archive', return_value=b'') as download, patch.object(
            ranking, 'inspect_archive', return_value=measurement(),
        ):
            ranking.collect_projects(CONFIG, old)
        download.assert_called_once()

    def test_description_and_name_cannot_inject_html_or_markdown(self):
        project = dict(name='safe', title='<img src=x>', description='[click](javascript:bad) <script>bad</script>', homepage='')
        result = ranking.render_projects([project])
        self.assertNotIn('<img', result)
        self.assertNotIn('<script>', result)
        self.assertIn('<p>', result)  # Markdown stays literal inside the HTML block.
        with self.assertRaises(ValueError):
            ranking.render_projects([dict(project, name='bad/../path')])

    def test_unsafe_homepage_dropped_and_missing_description_ineligible(self):
        with patch.object(ranking, 'inventory', return_value=[repo(homepage='javascript:alert(1)', description=None)]), patch.object(
            ranking, 'github', return_value={'sha': 'a'*40},
        ), patch.object(ranking, 'download_archive', return_value=b''), patch.object(
            ranking, 'inspect_archive', return_value=measurement(),
        ):
            result = ranking.collect_projects(CONFIG)
        self.assertEqual(result[0]['homepage'], '')
        self.assertFalse(result[0]['eligible'])

    def test_no_selection_or_invalid_markers_fail_without_deleting_content(self):
        with self.assertRaises(ValueError):
            ranking.render_projects([])
        for text in ('old content', ranking.END + ranking.START, ranking.START * 2 + ranking.END):
            with self.assertRaises(ValueError):
                ranking.replace_projects(text, 'new')

    def test_failed_activity_fetch_preserves_readme_and_ranking_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / 'README.md'
            content = ranking.START + '\nold\n' + ranking.END + profile.START + 'feed' + profile.END
            readme.write_text(content)
            (root / 'profile-projects.json').write_text(json.dumps(CONFIG))
            old = root / 'data/project-ranking.json'
            old.parent.mkdir()
            old.write_text('{"version": 1, "projects": []}')
            project = dict(repo(), eligible=True, title='New', **measurement())
            with patch.object(profile, 'ROOT', root), patch.object(ranking, 'collect_projects', return_value=[project]), patch.object(
                profile, 'collect_work', side_effect=RuntimeError('GitHub unavailable'),
            ), self.assertRaises(RuntimeError):
                profile.main()
            self.assertEqual(readme.read_text(), content)
            self.assertEqual(old.read_text(), '{"version": 1, "projects": []}')


if __name__ == '__main__':
    unittest.main()
