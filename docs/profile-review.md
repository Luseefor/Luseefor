# Profile and repository review

Reviewed 2026-10-19 against current public source. Ranking uses documentation
and public delivery signals from the generator, not a professional review of code quality.
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

## Follow-up improvements

- **Vinculum:** added a current browser capture near the top of its README,
  direct editor/examples/guide links, and an engineering note about its actual
  TypeScript/mathjs and Rust/WASM computation boundary. The note was checked
  against the bridge, Rust source and existing tests. Local validation passed:
  lint, typecheck, 2,140 tests in 227 files, production build, zero-advisory
  dependency audit, four Rust tests and public-source/media checks.
- **FareDelta:** added a genuine capture of the public beta search form.
  Confirmed that nearby-airport expansion is implemented (one alternate at
  each end, up to four airport pairs) and corrected the contradictory scope
  sentence. The three nearby-airport backend tests and 24 frontend tests pass.
- **LumaWall:** clarified local-build availability and the two playback paths,
  with a source-based architecture diagram. The 129 Swift tests pass. No native
  screenshot was published because capture failed; no substitute UI was fabricated.

These changes improve evidence and documentation; no application features,
licensing terms or repository visibility settings were changed.

## Remaining decisions and external requirements

1. **FareDelta license:** no LICENSE file or explicit license field exists.
   The owner needs to choose terms before they can be documented. No license
   was inferred from the project's public visibility.
2. **LumaWall distribution:** the installed app is ad-hoc signed. A Developer ID
   Application identity and a notarization Keychain profile are needed by the
   existing release script before a verified DMG can be offered.
3. **Vinculum versioning:** package metadata says `0.1.0`, while merged PR titles
   refer to `v0.5.1` and the changelog remains Unreleased. No tag or release was
   published using an assumed version. Align the release version and changelog
   before publishing a versioned artifact.

[PuzzleTrack](https://github.com/Luseefor/PuzzleTrack) remains a credible next
candidate with reproducible assignments and explicit research limits. Keep its
pilot status and measurement limitations clear. alove and Automater remain
accessible through All repositories. No projects were deleted or archived.

For future projects, supply an accurate repository description and homepage,
document setup/usage/internals/verification/license, and push working source to
the default branch. The next successful morning refresh evaluates them without
editing the profile's project list by hand.

## Evidence-focused profile refinement

Source size no longer earns ranking points. The morning selection scores README
structure, a public entry point, published stable releases and recent maintenance;
500 authored source lines is only an eligibility floor. A linked site is not
presented as a tested demo. Documentation-only PRs no longer fill the activity feed.
The engineering section names a real decision: bounded Rust/WASM sampling while
preserving the existing saved-scene format. It makes no unmeasured speed, adoption,
team-leadership or usage claims.

The sidebar bio and pinned repositories are account settings maintained separately
from this README. Keep them consistent with the current selected work. Suggested bio:

> Software engineer building mathematical software, developer tools, and macOS apps. Studying Computer Engineering and Mathematics at Southern Miss.

Suggested pins are the same three projects as Selected work; remove the older
Synthex UI and portfolio pins. Repository automation does not control account pins.
