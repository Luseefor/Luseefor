# Profile maintenance

The introduction and project grid in `README.md` are edited by hand. The section
between `recent-work` comments is refreshed by `scripts/update_profile.py`.

The feed uses GitHub's public API to find:

- Pull requests authored by `Luseefor` and merged in the past 90 days, including
  contributions to other people's repositories. Profile repository PRs are excluded.
- Published, non-prerelease GitHub releases from the projects listed in `PROJECTS`.

It shows the four most recent items by merge or publication time, with at most two
items per repository. Titles link to the original work. No activity or statistics
are invented. A failed request leaves the existing README intact and fails the job.

## Run locally

Python 3.10 or newer; no packages to install:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/update_profile.py
```

Unauthenticated runs use GitHub's public API rate limit. The workflow uses its
built-in `GITHUB_TOKEN`; no personal access token or external service is needed.

## GitHub Actions

`Update profile` runs daily at 12:23 UTC, on relevant pushes to `main`, or manually
from the Actions tab. Pull requests run tests without publishing. The refresh job
commits only when the generated text changes, using the configured Luseefor author
and committer identity. Generated commits do not retrigger the workflow.

The workflow becomes active when it is on the default branch. GitHub can delay
scheduled runs and disables scheduled workflows in public repositories after
60 days without repository activity; re-enable it in Actions if that happens.
See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

To change featured projects, edit the README grid. Add a repository name to
`PROJECTS` in the script to include its releases in the feed. A portrait can be
added to the header later without changing the automation.
