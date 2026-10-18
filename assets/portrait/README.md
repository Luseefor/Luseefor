# Add the portrait

Put a closely cropped, clear photo here as `source.png`, `source.jpg`,
`source.jpeg`, or `source.webp`. Keep only one source file.

The profile workflow converts it into a portrait made entirely from letters,
numbers, and spaces. It creates light and dark SVGs plus `portrait.txt`, then
inserts the picture above the name in the profile README. SVG keeps the characters
sharp and scales the whole portrait on phones.

To generate it locally without keeping the source photo in this repository:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/generate_portrait.py /path/to/photo.jpg
```

Commit the generated SVGs, `portrait.txt`, and the updated root README. Until a
photo is supplied, the profile displays its regular header without a placeholder.
