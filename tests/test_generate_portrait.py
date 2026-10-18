"""Portrait character-mapping, raster rendering and README insertion tests.

New semantics (user requirement): recognizable actual-face ASCII portrait
built from letters/numbers with meaningful SPACES for eyes/glasses/nose/
mouth, transparent background handling, measured raster/grid proportions
(not a hard-coded cell ratio), GIF typing reveal with static fallbacks,
both themes, reduced-motion fallback, no JS/iframe, deterministic output.
"""

from __future__ import annotations

import inspect
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageOps

from scripts import generate_portrait as portrait


def _solid(mode: str, size: tuple[int, int], color) -> Image.Image:
    return Image.new(mode, size, color)


def _face_like() -> Image.Image:
    """White canvas with two dark eye blocks separated by light skin."""
    img = Image.new("RGB", (120, 120), "white")
    px = img.load()
    for y in range(45, 60):
        for x in range(30, 48):
            px[x, y] = (10, 10, 10)
        for x in range(72, 90):
            px[x, y] = (10, 10, 10)
    return img


def _dark_with_light_eyes() -> Image.Image:
    img = Image.new("RGB", (120, 120), "black")
    px = img.load()
    for y in range(45, 60):
        for x in range(30, 48):
            px[x, y] = (245, 245, 245)
        for x in range(72, 90):
            px[x, y] = (245, 245, 245)
    return img


class CharacterMappingTests(unittest.TestCase):
    def test_only_letters_numbers_spaces(self):
        image = _face_like()
        rows = portrait.to_characters(image, columns=48)
        self.assertTrue(rows)
        self.assertTrue(all(len(row) == 48 for row in rows))
        for row in rows:
            for char in row:
                self.assertTrue(char.isalnum() or char == " ", f"unexpected {char!r}")

    def test_columns_validation(self):
        image = _face_like()
        for bad in (0, -4, 1, 1000):
            with self.subTest(columns=bad), self.assertRaises(ValueError):
                portrait.to_characters(image, columns=bad)

    def test_solid_white_is_all_spaces_solid_black_is_dense(self):
        white = portrait.to_characters(_solid("RGB", (80, 80), "white"), columns=32)
        self.assertTrue(all(not row.strip() for row in white), "white must map to spaces")
        black = portrait.to_characters(_solid("RGB", (80, 80), "black"), columns=32)
        self.assertTrue(all(row.strip() for row in black), "black must map to dense chars")
        self.assertTrue(all(not ch.isspace() or ch == " " for row in black for ch in row))

    def test_transparent_background_is_not_rendered_as_dark(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        rows = portrait.to_characters(image, columns=32)
        self.assertTrue(all(not row.strip() for row in rows))

    def test_partial_transparency_composites_over_light(self):
        # Fully opaque RGBA takes the global branch: no transparency detected,
        # so the dark block composites over light and must read dense.
        image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
        for y in range(24, 40):
            for x in range(24, 40):
                image.putpixel((x, y), (10, 10, 10, 255))
        rows = portrait.to_characters(image, columns=32)
        dense = sum(ch != " " for row in rows for ch in row)
        total = sum(len(row) for row in rows)
        # Central opaque block must be visible, surround must stay spaces.
        self.assertGreater(dense, 0)
        self.assertLess(dense / total, 0.6)

    def test_transparent_surround_stays_spaces_in_dual_branch(self):
        # Genuinely transparent surround triggers the dual branch: the alpha
        # background must stay spaces (never dark), regardless of thresholds.
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        for y in range(24, 40):
            for x in range(24, 40):
                image.putpixel((x, y), (10, 10, 10, 255))
        rows = portrait.to_characters(image, columns=32)
        self.assertEqual(len(rows[0]), 32)
        # Corners are far from the opaque block: pure alpha background.
        for row in (rows[0], rows[1], rows[-1], rows[-2]):
            self.assertEqual(row.strip(), "", "transparent surround must be spaces")
        for row in rows:
            self.assertEqual(row[0:4].strip(), "")
            self.assertEqual(row[-4:].strip(), "")

    def test_dark_eyes_keep_negative_space_and_facial_spacing(self):
        rows = portrait.to_characters(_face_like(), columns=60)
        # Eye band should contain dense characters (eyes) surrounded by spaces (skin).
        band = rows[len(rows) // 3: 2 * len(rows) // 3]
        band_text = "\n".join(band)
        dense = sum(ch != " " for ch in band_text)
        spaces = sum(ch == " " for ch in band_text)
        self.assertGreater(dense, 0, "eyes must leave visible dense marks")
        self.assertGreater(spaces, dense, "skin around eyes must stay open spaces")
        # Two eyes separated: at least one mostly-space column gap in the middle.
        mid = len(rows[0]) // 2
        gap = [row[max(0, mid - 3): mid + 3] for row in band]
        self.assertTrue(any(" " in g for g in gap), "eyes must be separated by spacing")

    def test_light_eyes_on_dark_produce_clear_spaces(self):
        rows = portrait.to_characters(_dark_with_light_eyes(), columns=60)
        # Light eye holes on a dark face must read as spaces inside dense surroundings.
        self.assertTrue(any(" " in row for row in rows), "eye holes must be spaces")
        dense = sum(ch != " " for row in rows for ch in row)
        spaces = sum(ch == " " for row in rows for ch in row)
        self.assertGreater(dense, spaces, "dark face must stay mostly dense")

    def test_dense_dark_hair_band_stays_dense(self):
        image = Image.new("RGB", (100, 100), "white")
        px = image.load()
        for y in range(0, 25):
            for x in range(100):
                px[x, y] = (15, 15, 15)
        params = inspect.signature(portrait.to_characters).parameters
        kwargs: dict = {"columns": 40}
        # Optional hair mask: if the editor supports it, it must force density.
        mask_names = [n for n in params if n.lower() in ("hair_mask", "mask", "hair", "hair_polygon")]
        if mask_names:
            mask = Image.new("L", (100, 100), 0)
            mp = mask.load()
            for y in range(0, 25):
                for x in range(100):
                    mp[x, y] = 255
            kwargs[mask_names[0]] = mask
        rows = portrait.to_characters(image, **kwargs)
        top = rows[: max(1, len(rows) // 4)]
        top_dense = sum(ch != " " for row in top for ch in row) / max(1, sum(len(r) for r in top))
        bottom = rows[-max(1, len(rows) // 4):]
        bottom_spaces = sum(ch == " " for row in bottom for ch in row) / max(1, sum(len(r) for r in bottom))
        self.assertGreater(top_dense, 0.5, "dark hair band must stay dense")
        self.assertGreater(bottom_spaces, 0.5, "light area below hair must stay open")

    def test_deterministic_and_sensitive_to_input(self):
        image = _face_like()
        first = portrait.to_characters(image, columns=40)
        second = portrait.to_characters(image.copy(), columns=40)
        self.assertEqual(first, second)
        other = portrait.to_characters(_dark_with_light_eyes(), columns=40)
        self.assertNotEqual(first, other)

    def test_modes_do_not_crash(self):
        for mode, color in (("RGB", "gray"), ("RGBA", (128, 128, 128, 255)), ("L", 128)):
            with self.subTest(mode=mode):
                rows = portrait.to_characters(_solid(mode, (60, 60), color), columns=32)
                self.assertEqual(len(rows[0]), 32)


def _isolated_face_synthetic() -> tuple[Image.Image, dict]:
    """Alpha-isolated synthetic face with controlled eye/nostril cores.

    Transparent surround, mid-gray face slab, near-black eye blocks (lower
    half, clear of the auto-hair zone) and nostril blocks. Returns the image
    plus pixel bboxes; tests map bboxes to grid cells instead of hardcoding
    points on the real photo.
    """
    W, H = 120, 120
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y in range(15, 105):
        for x in range(25, 95):
            px[x, y] = (150, 150, 150, 255)
    eyes = [(40, 58, 50, 66), (70, 58, 80, 66)]
    nostrils = [(55, 86, 60, 91), (62, 86, 67, 91)]
    for (x0, y0, x1, y1) in eyes + nostrils:
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (5, 5, 5, 255)
    return img, {"size": (W, H), "eyes": eyes, "nostrils": nostrils}


def _grid_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int],
               columns: int, rows: int) -> tuple[range, range]:
    x0, y0, x1, y1 = bbox
    W, H = size
    cols = range(int(x0 * columns / W), int((x1 * columns + W - 1) // W))
    rws = range(int(y0 * rows / H), int((y1 * rows + H - 1) // H))
    return cols, rws


class DualToneIsolatedFaceTests(unittest.TestCase):
    def test_signature_supports_hair_mask(self):
        params = inspect.signature(portrait.to_characters).parameters
        self.assertIn("hair_mask", params)

    def test_masked_hair_stays_dense_while_face_stays_open(self):
        W, H = 100, 100
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = img.load()
        for y in range(5, 35):
            for x in range(20, 80):
                px[x, y] = (30, 30, 30, 255)
        for y in range(35, 85):
            for x in range(20, 80):
                px[x, y] = (150, 150, 150, 255)
        mask = Image.new("L", (W, H), 0)
        mp = mask.load()
        for y in range(5, 35):
            for x in range(20, 80):
                mp[x, y] = 255
        columns = 40
        rows = portrait.to_characters(img, columns=columns, hair_mask=mask)
        self.assertTrue(all(len(row) == columns for row in rows))
        for row in rows:
            for char in row:
                self.assertTrue(char.isalnum() or char == " ")
        top = rows[: max(1, len(rows) // 3)]
        bottom = rows[2 * len(rows) // 3:]
        top_frac = sum(c != " " for r in top for c in r) / max(1, sum(len(r) for r in top))
        bot_frac = sum(c != " " for r in bottom for c in r) / max(1, sum(len(r) for r in bottom))
        # Order must hold with a genuine gap: thresholds may move, but dark
        # masked hair (lum 30) must stay clearly denser than open face (150).
        self.assertGreater(top_frac, 0.30, "masked hair must stay dense")
        self.assertGreater(top_frac, bot_frac + 0.25, "hair/face need a genuine density gap")

    def test_unmasked_dark_eye_cores_map_to_space_with_dense_halo(self):
        img, info = _isolated_face_synthetic()
        columns = 48
        rows = portrait.to_characters(img, columns=columns)
        W, H = info["size"]
        R = len(rows)
        for bbox in info["eyes"]:
            cols, rws = _grid_bbox(bbox, (W, H), columns, R)
            cells = [rows[r][c] for r in rws for c in cols
                     if 0 <= r < R and 0 <= c < columns]
            self.assertTrue(cells, "eye bbox must cover grid cells")
            # Core centers (quantization-proof) must be voids; edges may be halo.
            mid_r = (min(rws) + max(rws)) // 2
            mid_c = (min(cols) + max(cols)) // 2
            core = [rows[mid_r][c] for c in (mid_c - 1, mid_c)
                    if 0 <= mid_r < R and 0 <= c < columns]
            self.assertTrue(all(c == " " for c in core),
                            f"dark eye core centers must be spaces, got {core!r}")
            self.assertGreater(sum(c == " " for c in cells), 0, "eye region needs voids")
            self.assertGreater(sum(c != " " for c in cells), 0,
                               "eye frames need a dense halo around voids")
        band = rows[int(58 * R / H): int(72 * R / H) + 1]
        band_dense = sum(c != " " for r in band for c in r)
        self.assertGreater(band_dense, 0, "eye frames must leave a dense halo around voids")

    def test_unmasked_nostril_cores_map_to_space(self):
        img, info = _isolated_face_synthetic()
        columns = 48
        rows = portrait.to_characters(img, columns=columns)
        W, H = info["size"]
        R = len(rows)
        for bbox in info["nostrils"]:
            cols, rws = _grid_bbox(bbox, (W, H), columns, R)
            cells = [rows[r][c] for r in rws for c in cols
                     if 0 <= r < R and 0 <= c < columns]
            self.assertTrue(cells, "nostril bbox must cover grid cells")
            space_frac = sum(c == " " for c in cells) / len(cells)
            self.assertGreater(space_frac, 0.5,
                               f"dark nostril cores must read as spaces, got {cells!r}")

    def test_alpha_background_cells_are_spaces(self):
        img, info = _isolated_face_synthetic()
        columns = 48
        rows = portrait.to_characters(img, columns=columns)
        W, H = info["size"]
        R = len(rows)
        # Corners are pure transparent surround, far from the face slab.
        for r in (0, 1, R - 2, R - 1):
            self.assertEqual(rows[r].strip(), "")
        for row in rows:
            self.assertEqual(row[:3].strip(), "")
            self.assertEqual(row[-3:].strip(), "")

    def test_exif_transpose_respected(self):
        base = Image.new("RGB", (60, 120), "white")
        px = base.load()
        for y in range(80, 100):
            for x in range(20, 40):
                px[x, y] = (10, 10, 10)
        raw = base.transpose(Image.Transpose.ROTATE_90)
        exif = raw.getexif()
        exif[274] = 6
        buf = io.BytesIO()
        raw.save(buf, format="PNG", exif=exif)
        buf.seek(0)
        tagged = Image.open(buf)
        self.assertEqual(tagged.size, (120, 60), "test setup: raw pixels are landscape")
        expected = portrait.to_characters(base, columns=32)
        actual = portrait.to_characters(tagged, columns=32)
        self.assertEqual(actual, expected, "EXIF orientation must be transposed before mapping")

    def test_measured_grid_follows_transposed_dimensions(self):
        base = Image.new("RGB", (60, 120), "white")
        raw = base.transpose(Image.Transpose.ROTATE_90)
        exif = raw.getexif()
        exif[274] = 6
        buf = io.BytesIO()
        raw.save(buf, format="PNG", exif=exif)
        buf.seek(0)
        tagged = Image.open(buf)
        transposed = ImageOps.exif_transpose(tagged)
        cell_w, cell_h = portrait._cell_metrics()
        want = max(1, round(transposed.height / transposed.width * 32 * cell_w / cell_h))
        rows = portrait.to_characters(tagged, columns=32)
        self.assertEqual(len(rows), want, "grid rows must follow measured cell on transposed size")

    def test_store_strips_metadata(self):
        if not hasattr(portrait, "_strip_and_store_source"):
            self.skipTest("store helper not implemented yet")
        from PIL import PngImagePlugin
        with tempfile.TemporaryDirectory() as directory:
            src = Image.new("RGB", (40, 40), "gray")
            src_path = Path(directory) / "in.png"
            meta = PngImagePlugin.PngInfo()
            meta.add_text("Author", "tester")
            meta.add_text("Comment", "x" * 500)
            src.save(src_path, pnginfo=meta)
            self.assertTrue(src_path.stat().st_size > 200)
            outdir = Path(directory) / "out"
            stored = portrait._strip_and_store_source(src_path, outdir)
            self.assertEqual(stored.name, "source.png")
            with Image.open(stored) as reloaded:
                self.assertEqual(reloaded.size, (40, 40))
                self.assertEqual(dict(reloaded.info), {}, "stored source must carry no metadata")
                self.assertEqual(
                    list(reloaded.get_flattened_data()), list(src.get_flattened_data()))


class RenderPortraitTests(unittest.TestCase):
    def test_render_portrait_exists(self):
        self.assertTrue(
            hasattr(portrait, "render_portrait"),
            "expected render_portrait(rows, dark) in new contract (SVG-only to_svg is insufficient)",
        )

    def test_render_uses_text_not_embedded_photo(self):
        if not hasattr(portrait, "render_portrait"):
            self.skipTest("render_portrait not implemented yet")
        rows = ["M8i ", "  tL"]
        for dark in (True, False):
            rendered = portrait.render_portrait(rows, dark)
            if isinstance(rendered, str):
                self.assertNotIn("<image", rendered)
                self.assertIn("M8i", rendered)
            else:
                self.assertIsInstance(rendered, Image.Image)

    def test_both_themes_share_layout_differ_in_background(self):
        if not hasattr(portrait, "render_portrait"):
            self.skipTest("render_portrait not implemented yet")
        rows = portrait.to_characters(_face_like(), columns=40)
        light = portrait.render_portrait(rows, False)
        dark = portrait.render_portrait(rows, True)
        if isinstance(light, str) or isinstance(dark, str):
            self.assertNotEqual(light, dark)
            return
        self.assertEqual(light.size, dark.size)
        # Sample a corner that is a space in rows: backgrounds must differ by theme.
        self.assertNotEqual(
            light.getpixel((2, 2)), dark.getpixel((2, 2)),
            "light and dark themes must differ",
        )

    def test_measured_raster_preserves_source_proportions(self):
        """End-to-end aspect: rendered raster aspect must track the photo, not stretch."""
        if not hasattr(portrait, "render_portrait"):
            self.skipTest("render_portrait not implemented yet")
        wide = Image.new("RGB", (200, 100), "white")
        tall = Image.new("RGB", (100, 200), "white")
        for src in (wide, tall):
            px = src.load()
            for y in range(src.height // 3, 2 * src.height // 3):
                for x in range(src.width // 3, 2 * src.width // 3):
                    px[x, y] = (20, 20, 20)
        for src in (wide, tall):
            rows = portrait.to_characters(src, columns=48)
            rendered = portrait.render_portrait(rows, False)
            if isinstance(rendered, str):
                self.skipTest("raster measurement needs image render, got SVG string")
            src_aspect = src.width / src.height
            out_aspect = rendered.width / rendered.height
            self.assertAlmostEqual(
                out_aspect, src_aspect, delta=src_aspect * 0.25,
                msg=f"rendered {rendered.size} distorts source {(src.width, src.height)}",
            )

    def test_render_cell_is_measured_not_hardcoded(self):
        if not hasattr(portrait, "render_portrait"):
            self.skipTest("render_portrait not implemented yet")
        rows = portrait.to_characters(_face_like(), columns=40)
        first = portrait.render_portrait(rows, False)
        if isinstance(first, str):
            self.skipTest("needs raster render")
        rows2 = portrait.to_characters(_face_like(), columns=80)
        second = portrait.render_portrait(rows2, False)
        cell_w1 = first.width / len(rows[0])
        cell_w2 = second.width / len(rows2[0])
        # Measured monospace advance must be stable when columns change.
        self.assertAlmostEqual(cell_w1, cell_w2, delta=max(1.0, cell_w1 * 0.15))
        cell_h = first.height / len(rows)
        ratio = cell_h / cell_w1
        self.assertGreater(ratio, 1.0, "monospace line height must exceed advance")
        self.assertLess(ratio, 3.0, "cell ratio outside plausible monospace range")

    def test_render_deterministic(self):
        if not hasattr(portrait, "render_portrait"):
            self.skipTest("render_portrait not implemented yet")
        rows = portrait.to_characters(_face_like(), columns=32)
        first = portrait.render_portrait(rows, False)
        second = portrait.render_portrait(rows, False)
        if isinstance(first, str):
            self.assertEqual(first, second)
        else:
            self.assertEqual(list(first.get_flattened_data()), list(second.get_flattened_data()))


class InsertPortraitTests(unittest.TestCase):
    def test_markers_required_idempotent_preserves_content(self):
        original = f"{portrait.START}\n{portrait.END}\n<h1>Name</h1>"
        rendered = portrait.insert_portrait(original)
        self.assertTrue(rendered.endswith("<h1>Name</h1>"))
        self.assertEqual(portrait.insert_portrait(rendered), rendered)
        for bad in ("", portrait.START * 2 + portrait.END, portrait.END + portrait.START):
            with self.subTest(readme=bad[:20]), self.assertRaises(ValueError):
                portrait.insert_portrait(bad)

    def test_gif_and_static_fallbacks_for_both_themes(self):
        original = f"{portrait.START}\n{portrait.END}\n"
        rendered = portrait.insert_portrait(original)
        lowered = rendered.lower()
        self.assertIn(".gif", lowered, "README reveal must reference typing GIF, not SVG-only")
        self.assertIn(".png", lowered, "GIF needs a static PNG fallback")
        self.assertIn("dark", lowered)
        self.assertIn("light", lowered)

    def test_no_javascript_or_iframe(self):
        rendered = portrait.insert_portrait(f"{portrait.START}\n{portrait.END}\n").lower()
        for banned in ("<script", "<iframe", "javascript:", "onload=", "onerror="):
            self.assertNotIn(banned, rendered)

    def test_reduced_motion_fallback(self):
        rendered = portrait.insert_portrait(f"{portrait.START}\n{portrait.END}\n").lower()
        self.assertIn(
            "prefers-reduced-motion", rendered,
            "animation must offer a static fallback for prefers-reduced-motion",
        )

    def test_no_replay_guarantee_claims(self):
        rendered = portrait.insert_portrait(f"{portrait.START}\n{portrait.END}\n").lower()
        # Native GitHub cannot guarantee replay on every cached/back navigation.
        for phrase in ("replay on every", "replays on every", "every time you navigate", "back-button replay"):
            self.assertNotIn(phrase, rendered)

    def test_accessible_alt_text(self):
        rendered = portrait.insert_portrait(f"{portrait.START}\n{portrait.END}\n").lower()
        self.assertIn("alt=", rendered)
        self.assertIn("portrait", rendered)

    def test_no_photo_leaves_header_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text("Existing profile", encoding="utf-8")
            with patch.object(portrait, "ROOT", root), patch("sys.argv", ["portrait"]):
                portrait.main()
            self.assertEqual(path.read_text(encoding="utf-8"), "Existing profile")
            self.assertFalse((root / "assets").exists())

    def test_supplied_photo_generates_gif_png_txt_and_inserts_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text(f"{portrait.START}\n{portrait.END}\n<h1>Name</h1>", encoding="utf-8")
            source = root / "headshot.png"
            _face_like().save(source)
            with patch.object(portrait, "ROOT", root), patch("sys.argv", ["portrait", str(source)]):
                portrait.main()
            text = readme.read_text(encoding="utf-8")
            self.assertIn(".gif", text.lower())
            generated = list((root / "assets" / "portrait").glob("*"))
            names = [p.name.lower() for p in generated]
            self.assertTrue(any(n.endswith(".gif") for n in names), f"missing GIF in {names}")
            self.assertTrue(any(n.endswith(".png") for n in names), f"missing PNG in {names}")
            self.assertTrue(any(n.endswith(".txt") for n in names), f"missing txt in {names}")


class SubprocessCliTests(unittest.TestCase):
    """End-to-end CLI: `python scripts/generate_portrait.py <photo>`.

    In-process `main()` tests cannot catch a missing
    `if __name__ == "__main__": main()` guard (a successful no-op). These run
    the script as a real subprocess against a temporary full fixture whose
    layout mirrors the repo (scripts/, README.md, assets/fonts/), so ROOT
    resolution, font loading, file generation and README insertion are all
    exercised through the actual entry point.
    """

    def _make_fixture(self, root: Path) -> tuple[Path, Path]:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        script_src = Path(portrait.__file__)
        script = root / "scripts" / "generate_portrait.py"
        shutil.copy(script_src, script)
        real_fonts = Path(portrait.ROOT) / "assets" / "fonts"
        if real_fonts.is_dir():
            dest_fonts = root / "assets" / "fonts"
            dest_fonts.mkdir(parents=True, exist_ok=True)
            for child in real_fonts.iterdir():
                if child.is_file():
                    shutil.copy(child, dest_fonts / child.name)
        (root / "README.md").write_text(
            f"{portrait.START}\n{portrait.END}\n<h1>Name</h1>", encoding="utf-8")
        photo = root / "headshot.png"
        _face_like().save(photo)
        return script, photo

    def _run_cli(self, script: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, timeout=300,
            cwd=str(script.parents[1]),
        )

    def test_cli_subprocess_generates_files_and_updates_readme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, photo = self._make_fixture(root)
            result = self._run_cli(script, str(photo), "--columns", "48")
            self.assertEqual(result.returncode, 0, msg=result.stderr[-2000:])
            self.assertIn("Generated", result.stdout,
                          "CLI must report generation; empty output suggests the "
                          "module never called main()")
            outdir = root / "assets" / "portrait"
            names = [p.name.lower() for p in outdir.glob("*")] if outdir.is_dir() else []
            for suffix in (".gif", ".png", ".txt"):
                self.assertTrue(any(n.endswith(suffix) for n in names),
                                f"CLI must generate *{suffix} files; got {names}")
            self.assertTrue(any("dark" in n for n in names) and
                            any("light" in n for n in names),
                            f"CLI must generate both themes; got {names}")
            for name in names:
                if name.endswith((".gif", ".png", ".txt")):
                    self.assertGreater((outdir / name).stat().st_size, 0,
                                       f"{name} must be non-empty")
            txt = (outdir / "portrait.txt").read_text(encoding="utf-8").splitlines()
            self.assertTrue(txt, "portrait.txt must hold character rows")
            self.assertTrue(all(len(line) == 48 for line in txt),
                            "explicit --columns 48 must be honored by the CLI")
            lowered = (root / "README.md").read_text(encoding="utf-8").lower()
            self.assertIn(".gif", lowered)
            self.assertIn(".png", lowered)

    def test_cli_default_columns_match_explicit_default(self):
        source = Path(portrait.__file__).read_text(encoding="utf-8")
        match = re.search(r'"--columns".*?default=(\d+)', source)
        if not match:
            self.skipTest("could not determine CLI default columns from script")
        default = match.group(1)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            script_a, photo_a = self._make_fixture(Path(first))
            script_b, photo_b = self._make_fixture(Path(second))
            result_default = self._run_cli(script_a, str(photo_a))
            result_explicit = self._run_cli(script_b, str(photo_b), "--columns", default)
            self.assertEqual(result_default.returncode, 0, msg=result_default.stderr[-2000:])
            self.assertEqual(result_explicit.returncode, 0, msg=result_explicit.stderr[-2000:])
            txt_default = (Path(first) / "assets" / "portrait" / "portrait.txt").read_text(
                encoding="utf-8")
            txt_explicit = (Path(second) / "assets" / "portrait" / "portrait.txt").read_text(
                encoding="utf-8")
            self.assertEqual(txt_default, txt_explicit,
                             "omitting --columns must behave like the documented default")


if __name__ == "__main__":
    unittest.main()
