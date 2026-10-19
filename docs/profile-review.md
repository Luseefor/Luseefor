# Profile and repository review

Reviewed 2026-10-19 against current public source. Scores below are documentation
and size signals from the generator, not a professional review of code quality.
The live, inspectable results are in [the ranking snapshot](../data/project-ranking.json).

## Chosen direction

The profile now uses three unboxed project descriptions, one introduction, a
smaller code portrait and a collapsed activity feed. The project grid and generic
tools table repeated information and gave every project equal prominence.
Synthex UI is excluded from the feature selection at the owner's request.

References and the specific lesson taken from each:

- [Simon Willison's profile](https://github.com/simonw/simonw): automatic links to
  real releases and work. Its current layout uses a three-column table; we borrow
  its factual automation, not its table layout.
- [Nate Moore's profile](https://github.com/natemoo-re/natemoo-re/blob/master/README.md):
  concrete work-linked prose. We borrow the writing approach, not the Spotify
  widgets or other personal sections.
- [Lazygit's project README](https://github.com/jesseduffield/lazygit): a clear
  product definition followed by visual proof. This is a project README example,
  not a profile template. Our strongest remaining gap is visual proof.
- [Datasette's project README](https://github.com/simonw/datasette): direct ways
  to try a project, documentation and an actual screenshot.

These are specific primary-source examples, not a claim that there is an
objective ranking of the best profiles.

## Current selection and gaps

1. **Vinculum** — the most substantial measured source, with setup, validation,
   architecture and user documentation. Keep first. Add one current screenshot
   near the top of its README and a prominent editor link; the README currently
   starts with a long feature list before showing the product.
2. **LumaWall** — substantial native implementation and clear build/operating
   constraints. The README correctly says distribution still requires signing,
   notarization and packaging. Next: a short screen recording and a release
   artifact once that process is genuinely complete. Keep the profile's
   “build locally” wording until then.
3. **FareDelta** — flexible-date search, persistence and alerting across a web/API
   stack. Its README contradicts itself: “What works today” includes nearby-airport
   expansion, while “Current scope” says it is not provided. Verify the actual
   behavior before correcting either claim. Add one fare-matrix screenshot and
   clear license information; the root README has no license section. The
   profile description avoids the disputed feature and describes cached fares.

[PuzzleTrack](https://github.com/Luseefor/PuzzleTrack) is a credible next candidate,
with reproducible assignments and explicit research limits. Keep its pilot status
clear. It currently scores below the featured three; its root README lacks an
architecture heading and license section. Do not add claims solely to earn points.

alove and Automater remain available through All repositories. Their current
measured implementation sizes fall below the 5,000-line feature threshold.
No repositories were deleted, hidden or archived.

## Next actions, in order

1. Add one real screenshot or short recording to each featured project's README.
   Keep the profile itself concise; one strong project visual can be added later.
2. Resolve FareDelta's conflicting scope claims and confirm its intended license.
3. Publish tested, reproducible releases, starting with Vinculum. For LumaWall,
   finish the documented signing/notarization path before offering downloads.
4. Write one short technical case study about a concrete engineering decision:
   Vinculum's Rust/WASM boundary or LumaWall's multi-display playback and power
   handling. Link actual measurements when available; do not invent usage figures.
5. For a new project, set an accurate GitHub description and homepage, document
   setup/usage/internals/verification/license, and push working source to its
   default branch. The next successful morning refresh evaluates it automatically.
