from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from scripts import update_profile as profile


def entry(number=1, repo="Luseefor/vinculum", date="2026-10-17T12:00:00Z", title="A change"):
    return {
        "date": date, "repo": repo, "title": title,
        "url": f"https://github.com/{repo}/pull/{number}",
        "label": f"{repo} #{number}",
    }


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
        item = {
            'pull_request': {'merged_at': '2026-10-17T12:00:00Z'},
            'user': {'login': 'Luseefor'},
            'repository_url': 'https://api.github.com/repos/other/project',
            'html_url': 'https://github.com/other/project/pull/7',
            'title': 'Improve storage', 'number': 7,
        }
        release = {
            'published_at': '2026-10-16T12:00:00Z', 'draft': False,
            'prerelease': False, 'tag_name': 'v1.0.0',
            'html_url': 'https://github.com/Luseefor/vinculum/releases/tag/v1.0.0',
        }
        result = {'total_count': 3, 'items': [
            item, dict(item, user={'login': 'someone-else'}),
            dict(item, pull_request={'merged_at': None}),
        ]}
        responses = [result, [release, dict(release, draft=True),
                                 dict(release, prerelease=True),
                                 dict(release, published_at='2025-01-01T00:00:00Z')]]
        with patch.object(profile, 'PROJECTS', ('vinculum',)), patch.object(
            profile, 'github', side_effect=responses,
        ) as fetch:
            work = profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))
        self.assertEqual(len(work), 2)
        self.assertEqual(work[0]['date'], item['pull_request']['merged_at'])
        query = fetch.call_args_list[0].args[0]
        self.assertIn('is%3Apublic', query)
        self.assertIn('-repo%3ALuseefor%2FLuseefor', query)
        self.assertIn('merged%3A%3E%3D2026-07-20', query)

    def test_incomplete_search_fails_instead_of_publishing_partial_data(self):
        with patch.object(profile, 'github', return_value={
            'incomplete_results': True, 'total_count': 1, 'items': [],
        }), self.assertRaises(RuntimeError):
            profile.collect_work(datetime(2026, 10, 18, tzinfo=timezone.utc))



if __name__ == '__main__':
    unittest.main()
