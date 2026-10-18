"""Typing-GIF animation tests: blank start, progressive reveal, held final frame."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts import generate_portrait as portrait

SMALL_ROWS = [
    "M8i  tL  ",
    "  tL M8i ",
    "CCCC LLLL",
    "    M8i  ",
]


def _frames(gif_path: Path) -> list[Image.Image]:
    frames: list[Image.Image] = []
    with Image.open(gif_path) as gif:
        for index in range(getattr(gif, "n_frames", 1)):
            gif.seek(index)
            frames.append(gif.convert("RGB").copy())
    return frames


def _ink_fraction(frame: Image.Image, background=None) -> float:
    if background is None:
        background = frame.getpixel((2, 2))
    pixels = list(frame.get_flattened_data())
    different = sum(1 for p in pixels if abs(p[0] - background[0]) + abs(p[1] - background[1]) + abs(p[2] - background[2]) > 30)
    return different / max(1, len(pixels))


class TypingGifTests(unittest.TestCase):
    def test_save_typing_gif_contract(self):
        self.assertTrue(hasattr(portrait, "save_typing_gif"), "expected save_typing_gif in new contract")
        params = inspect.signature(portrait.save_typing_gif).parameters
        self.assertIn("rows", params)
        self.assertIn("path", params)
        self.assertIn("dark", params)
        self.assertIn("typing_seconds", params)
        self.assertEqual(params["typing_seconds"].default, 6.0)

    def test_first_frame_blank_progressive_final_held(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "typing.gif"
            portrait.save_typing_gif(SMALL_ROWS, out, False, typing_seconds=2.0)
            frames = _frames(out)
            self.assertGreaterEqual(len(frames), 3, "need blank + progressive + final frames")
            self.assertLess(_ink_fraction(frames[0]), 0.02, "first frame must be blank")
            fractions = [_ink_fraction(f, frames[0].getpixel((2, 2))) for f in frames]
            for earlier, later in zip(fractions, fractions[1:]):
                self.assertLessEqual(earlier, later + 0.02, "ink must grow monotonically")
            self.assertGreater(fractions[-1], fractions[0] + 0.05, "final must hold visible portrait")
            # Intermediate frames must differ: progressive, not a single jump.
            distinct = sum(1 for a, b in zip(fractions, fractions[1:]) if b - a > 0.005)
            self.assertGreaterEqual(distinct, 2, "typing must progress over several frames")

    def test_intermediate_frames_subset_of_final(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "typing.gif"
            portrait.save_typing_gif(SMALL_ROWS, out, False, typing_seconds=2.0)
            frames = _frames(out)
            bg = frames[-1].getpixel((2, 2))
            final_ink = {
                (x, y)
                for y in range(0, frames[-1].height, 4)
                for x in range(0, frames[-1].width, 4)
                if sum(abs(a - b) for a, b in zip(frames[-1].getpixel((x, y)), bg)) > 60
            }
            mid = frames[len(frames) // 2]
            mid_ink = {
                (x, y)
                for y in range(0, mid.height, 4)
                for x in range(0, mid.width, 4)
                if sum(abs(a - b) for a, b in zip(mid.getpixel((x, y)), bg)) > 60
            }
            self.assertTrue(mid_ink, "middle frame must show partial typing")
            self.assertTrue(len(mid_ink) < len(final_ink), "middle frame must be a prefix, not full")
            overlap = len(mid_ink & final_ink) / max(1, len(mid_ink))
            self.assertGreater(overlap, 0.85, "typed pixels must land where the final portrait has ink")

    def test_final_frame_matches_static_render(self):
        if not hasattr(portrait, "save_typing_gif") or not hasattr(portrait, "render_portrait"):
            self.skipTest("needs save_typing_gif + render_portrait")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "typing.gif"
            portrait.save_typing_gif(SMALL_ROWS, out, True, typing_seconds=1.0)
            frames = _frames(out)
            static = portrait.render_portrait(SMALL_ROWS, True)
            if isinstance(static, str):
                self.skipTest("static render must be raster for pixel equality")
            final = frames[-1].convert("RGB").resize(static.size)
            static_px = list(static.convert("RGB").get_flattened_data())
            final_px = list(final.get_flattened_data())
            close = sum(
                1 for a, b in zip(static_px, final_px)
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) < 90
            )
            self.assertGreater(close / len(static_px), 0.95, "GIF final must equal static PNG")

    def test_no_infinite_loop_and_final_hold(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "typing.gif"
            portrait.save_typing_gif(SMALL_ROWS, out, False, typing_seconds=2.0)
            with Image.open(out) as gif:
                self.assertNotEqual(gif.info.get("loop", 1), 0, "GIF must not loop forever")
                durations = []
                for index in range(gif.n_frames):
                    gif.seek(index)
                    durations.append(gif.info.get("duration", 100))
            # Held final portrait: last frame stays longer than the typing cadence.
            self.assertGreaterEqual(max(durations[-1], 0), 700, "final portrait must be held")

    def test_typing_seconds_controls_total_duration(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        totals = []
        with tempfile.TemporaryDirectory() as directory:
            for seconds in (1.0, 4.0):
                out = Path(directory) / f"t{seconds}.gif"
                portrait.save_typing_gif(SMALL_ROWS, out, False, typing_seconds=seconds)
                with Image.open(out) as gif:
                    total = 0
                    for index in range(gif.n_frames):
                        gif.seek(index)
                        total += gif.info.get("duration", 100)
                totals.append(total)
        self.assertGreater(totals[1], totals[0], "longer typing_seconds must lengthen the GIF")

    def test_both_themes_and_actual_characters(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        with tempfile.TemporaryDirectory() as directory:
            light = Path(directory) / "light.gif"
            dark = Path(directory) / "dark.gif"
            portrait.save_typing_gif(SMALL_ROWS, light, False, typing_seconds=1.0)
            portrait.save_typing_gif(SMALL_ROWS, dark, True, typing_seconds=1.0)
            light_frames = _frames(light)
            dark_frames = _frames(dark)
            self.assertEqual(light_frames[-1].size, dark_frames[-1].size)
            self.assertNotEqual(light_frames[-1].getpixel((2, 2)), dark_frames[-1].getpixel((2, 2)))
            # Actual characters drive ink: all-space rows stay blank, all-dense rows fill.
            blank = [" " * 8 for _ in range(4)]
            dense = ["M" * 8 for _ in range(4)]
            blank_path = Path(directory) / "blank.gif"
            dense_path = Path(directory) / "dense.gif"
            portrait.save_typing_gif(blank, blank_path, False, typing_seconds=1.0)
            portrait.save_typing_gif(dense, dense_path, False, typing_seconds=1.0)
            blank_final = _frames(blank_path)[-1]
            dense_final = _frames(dense_path)[-1]
            self.assertLess(_ink_fraction(blank_final), 0.02)
            self.assertGreater(_ink_fraction(dense_final), 0.10)

    def test_gif_deterministic(self):
        if not hasattr(portrait, "save_typing_gif"):
            self.skipTest("save_typing_gif not implemented yet")
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "a.gif"
            second = Path(directory) / "b.gif"
            portrait.save_typing_gif(SMALL_ROWS, first, False, typing_seconds=1.0)
            portrait.save_typing_gif(SMALL_ROWS, second, False, typing_seconds=1.0)
            frames_a = _frames(first)
            frames_b = _frames(second)
            self.assertEqual(len(frames_a), len(frames_b))
            self.assertEqual(list(frames_a[-1].get_flattened_data()), list(frames_b[-1].get_flattened_data()))


if __name__ == "__main__":
    unittest.main()
