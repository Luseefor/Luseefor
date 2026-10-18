# Profile maintenance

The introduction, project grid, and tools table in `README.md` are edited by hand.
The feed inside the collapsed contributions section is refreshed by
`scripts/update_profile.py`. The contribution snake is generated from the public
contribution calendar and published to the `output` branch.

The feed uses GitHub's public API to find:

- Pull requests authored by `Luseefor` and merged in the past 90 days, including
  contributions to other people's repositories. Profile repository PRs are excluded.
- Published, non-prerelease GitHub releases from the projects listed in `PROJECTS`.

It shows the four most recent items by merge or publication time, with at most two
items per repository. Titles link to the original work. No activity or statistics
are invented. A failed request leaves the existing README intact and fails the job.

## Run locally

Python 3.10 or newer. The feed uses the standard library; portrait generation uses
Pillow:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/update_profile.py
python3 scripts/generate_portrait.py
```

Unauthenticated runs use GitHub's public API rate limit. The workflow uses its
built-in `GITHUB_TOKEN`; no personal access token or external service is needed.

## GitHub Actions

`Update profile` runs daily at 12:23 UTC, on relevant pushes to `main`, or manually
from the Actions tab. Pull requests run tests and generate both contribution SVGs
without publishing. The refresh job commits only when generated content changes.
The contributions job publishes SVGs with a blue snake and green activity cells,
with separate light and dark palettes. Both jobs use the configured Luseefor
author and committer identity. Existing output branch history is preserved.
Generated commits do not retrigger the workflow.

The workflow becomes active when it is on the default branch. GitHub can delay
scheduled runs and disables scheduled workflows in public repositories after
60 days without repository activity; re-enable it in Actions if that happens.
See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

To change featured projects, edit the README grid. Add a repository name to
`PROJECTS` in the script to include its releases in the feed.

## Code portrait

`assets/portrait/source.png` (cropped, face-isolated, metadata-free) and
`assets/portrait/hair-mask.png` (same dimensions) are committed so the daily
refresh regenerates the portrait deterministically. The full original photo
is never committed and is not needed. To change the portrait subject, replace
both files together; a mask drawn for a different crop fails the build.

On refresh the workflow converts the source into `portrait-dark.png`,
`portrait-light.png`, `portrait-dark.gif`, `portrait-light.gif`, and
`portrait.txt`, then inserts the typing reveal above the name. The GIF plays
once from blank and holds the final portrait; `prefers-reduced-motion`
viewers are served the static PNG via `<picture>` media queries (no JS).
GitHub caches raw media aggressively, so after publishing, a hard/refresh
load may be needed to see a new GIF; no replay-on-every-visit is promised.

To generate locally without publishing the original photograph:

```sh
python3 scripts/generate_portrait.py /path/to/photo.jpg
```

The supplied photo is stored back stripped of metadata (`source.png`). Use a
close crop of the face with a simple background. `--columns 80` is the default;
64 reads larger at small widths, 100 keeps more detail. Generated portraits use
only letters, numbers, and spaces, use the measured IBM Plex Mono cell
(`assets/fonts/`) so the rendered proportions match the photo, and scale as
one image on mobile. After conversion, commit the source, mask, generated
assets, and root README.
