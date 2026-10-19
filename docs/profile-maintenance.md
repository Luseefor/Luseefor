# Profile maintenance

The introduction and contacts are edited by hand. `scripts/update_profile.py`
refreshes **Selected work** and the collapsed public activity feed. The portrait
and contribution snake remain separate, deterministic generators.

## Morning project selection

`Update profile` runs at **07:23 America/Chicago every morning**, including DST,
on relevant pushes to `main`, or manually from Actions. GitHub may delay schedules;
this is not a guaranteed delivery time. Scheduled workflows must be on the default
branch and can be disabled after 60 days without repository activity.
See [GitHub's scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Every refresh discovers all public repositories owned by `Luseefor`, including
repositories created since the previous run. It excludes forks, archived,
disabled, empty and template repositories, plus the explicit exclusions in
`profile-projects.json`. Synthex UI is excluded at the owner's request; the
profile repository and personal website are not treated as featured products.
No repository is deleted or archived by this automation. GitHub's repository
list ordering and pinned repositories are not changed.

Up to three eligible projects appear, sorted by:

- **Documentation: 60 points.** Ten points each for purpose prose, setup commands,
  usage/features, internals/architecture, verification commands, and a license
  section in the root README. More words do not earn more points.
- **Public entry point: 10 points.** A configured HTTP(S) project homepage.
  This is a way to reach a project, not proof that its features work or that a
  deployment is healthy. Native apps can earn the release points without a site.
- **Published release: 20 points.** An existing, published GitHub release that
  is neither a draft nor a prerelease. This records distribution evidence; it
  does not certify binaries, signing, security or release quality.
- **Recent maintenance: 10 points.** A repository push within the past 90 days.
  This is a coarse maintenance signal, not a count of features or code quality.
- Ties use documentation points and then repository name, deterministically.

Source size earns **zero ranking points**. Eligibility requires at least
**500 approximate authored source lines**, **40 documentation points**, and a
nonempty description. The lower size floor allows focused tools to compete with
larger applications. Counts exclude comment-only lines, tests, generated/bundled
code, dependencies, assets and showcase video code. These are editorial thresholds,
configurable in `profile-projects.json`, not an industry standard or a quality
certification. README signals check documented structure; they do not verify
whether commands, claims or tests work. See `docs/profile-review.md` for the human
audit.

If a new project qualifies and outranks an existing feature, it replaces it at
the next successful refresh. A new project with no GitHub description is not
featured until a description is supplied. Fewer than three qualifying projects
produce a shorter selection; zero qualifying projects fails without replacing
the current content.

Descriptions for the existing projects are reviewed overrides in
`profile-projects.json`; edit these when their capabilities change. New projects
use their GitHub repository description automatically. New homepage links also
come from GitHub metadata. No daily text-generation service or paid API is used.
The workflow does not edit descriptions or READMEs in other repositories.

`data/project-ranking.json` records the public measurements, documentation
signals, eligibility, score and inspected commit SHA. Unchanged SHAs reuse their
code/README measurements, while repository descriptions, latest published release
and maintenance evidence refresh on every run. Increment `VERSION` in
`scripts/rank_projects.py` whenever measurement rules change, invalidating the cache. Config eligibility thresholds recalculate
each run. The ranking snapshot is committed so CI can reuse it.

The inspector reads archives without extracting files. Limits are 60 MiB compressed,
200 MiB declared expanded contents, 30,000 members and 2 MiB per inspected text
file. A failed request, incomplete activity search or inspection-limit failure
leaves both README and ranking snapshot untouched and fails the job. Resolve the
failure or explicitly exclude an uninspectable repository in the config; the
workflow does not silently publish a partial ranking.

## Activity feed and contribution snake

The feed finds public pull requests authored by `Luseefor` and merged in the past
90 days, including contributions to other repositories. Profile repository PRs
are excluded, along with PRs that only change documentation, media or repository
metadata. The filter reads every changed-file page instead of guessing from PR
titles. Functional code, build/configuration and test changes still qualify. If
a PR reaches GitHub’s 3,000-file cap, the job fails instead of publishing from
a truncated list. It also checks published, non-prerelease releases from the
currently selected projects. It shows the four newest items, at most two per repository.

The snake uses the public contribution calendar and is published to the `output`
branch with separate light and dark palettes. Existing branch history is kept.

Both publishing jobs use `Luseefor <sapanakosansar18@gmail.com>` for author and
committer and verify those identities before publishing. Generated commits only
happen when content changes and do not retrigger the workflow. Pull requests run
tests and generate SVGs without publishing.

## Run locally

Python 3.10 or newer:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/update_profile.py
python3 scripts/generate_portrait.py
```

The ranking and feed use the Python standard library and public GitHub endpoints.
An unauthenticated run has GitHub's lower API limit. CI uses its built-in
`GITHUB_TOKEN`; no personal token is required. Pillow is only used for the portrait.

## Code portrait

`assets/portrait/source.png` is a cropped, isolated, metadata-free image.
`assets/portrait/hair-mask.png` has matching dimensions. Both are committed so
regeneration is deterministic; the full original photo is not committed.
Replace source and mask together when changing the portrait subject.

The generator writes light/dark PNGs, single-play typing GIFs and `portrait.txt`.
The README displays the portrait at 180px; reduced-motion media queries use the
static PNG. GitHub caches media, so replay on every visit is not guaranteed.

```sh
python3 scripts/generate_portrait.py /path/to/photo.jpg
```

The supplied crop is stored back stripped of metadata. `--columns 80` is the
default. Letters, numbers and spaces use measured IBM Plex Mono cells
(`assets/fonts/`), preserving proportions. Commit the source, matching mask,
generated assets and root README after changing the photograph.
