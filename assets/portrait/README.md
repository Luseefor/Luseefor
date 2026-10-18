# Add the portrait

`source.png` (cropped, face-isolated, metadata-free) plus `hair-mask.png`
are bundled here on purpose: the daily workflow regenerates the portrait
deterministically from exactly these files, so scheduled runs reproduce the
same output without the original photograph. The full original photo is never
committed and is not needed after this crop is made.

- To use a NEW photo: replace `source.png` with a close face crop and
  replace `hair-mask.png` with a matching white-on-black hair mask of the
  SAME pixel dimensions (or delete the mask to fall back to the automatic
  top-dark hair rule). A dimension mismatch fails the build on purpose —
  never ship a mask drawn for a different crop.
- The workflow converts the source into light/dark PNGs, typing GIFs that
  play once from blank and hold the final portrait, plus `portrait.txt`,
  then inserts the picture above the name in the profile README.
  `prefers-reduced-motion` viewers get the static PNG.

To generate locally:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/generate_portrait.py /path/to/photo.jpg
```

Giving an explicit photo stores a metadata-stripped copy as `source.png`.
Commit `source.png`, `hair-mask.png`, the generated PNGs/GIFs/`portrait.txt`,
and the updated root README. Until a photo is supplied, the profile displays
its regular header without a placeholder.
