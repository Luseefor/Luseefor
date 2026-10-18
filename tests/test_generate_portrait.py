from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from PIL import Image

from scripts import generate_portrait as portrait


class PortraitTests(unittest.TestCase):
    def test_only_letters_numbers_spaces_and_preserves_aspect(self):
        image = Image.new('L', (100, 200))
        image.putdata([x * 255 // 99 for y in range(200) for x in range(100)])
        rows = portrait.to_characters(image, columns=80)
        self.assertEqual(len(rows), 96)
        self.assertTrue(all(len(row) == 80 for row in rows))
        self.assertTrue(all(char.isalnum() or char == ' ' for row in rows for char in row))
        self.assertEqual(rows[0][0], portrait.RAMP[0])
        self.assertEqual(rows[0][-1], ' ')

    def test_transparent_background_is_not_rendered_as_dark_pixels(self):
        image = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
        rows = portrait.to_characters(image, columns=32)
        self.assertTrue(all(not row.strip() for row in rows))

    def test_svg_keeps_character_rows_and_contains_no_embedded_photo(self):
        rows = ['M8i ', '  tL']
        for dark in (True, False):
            svg = portrait.to_svg(rows, dark)
            root = ElementTree.fromstring(svg)
            texts = root.findall('.//{http://www.w3.org/2000/svg}text')
            self.assertEqual([element.text for element in texts], rows)
            self.assertEqual(root.attrib['viewBox'], '0 0 24 20')
            self.assertNotIn('<image', svg)

    def test_header_insertion_is_idempotent_and_preserves_other_content(self):
        original = f'{portrait.START}\n{portrait.END}\n<h1>Name</h1>'
        rendered = portrait.insert_portrait(original)
        self.assertTrue(rendered.endswith('<h1>Name</h1>'))
        self.assertIn('portrait-dark.svg', rendered)
        self.assertEqual(portrait.insert_portrait(rendered), rendered)

    def test_no_photo_leaves_header_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'README.md'
            path.write_text('Existing profile')
            with patch.object(portrait, 'ROOT', root), patch('sys.argv', ['portrait']):
                portrait.main()
            self.assertEqual(path.read_text(), 'Existing profile')
            self.assertFalse((root / 'assets').exists())

    def test_supplied_photo_generates_both_themes_and_inserts_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / 'README.md'
            readme.write_text(f'{portrait.START}\n{portrait.END}\n<h1>Name</h1>')
            source = root / 'headshot.png'
            Image.new('RGB', (100, 150), '#777777').save(source)
            with patch.object(portrait, 'ROOT', root), patch('sys.argv', ['portrait', str(source)]):
                portrait.main()
            self.assertIn('<picture>', readme.read_text())
            for name in ['portrait-dark.svg', 'portrait-light.svg', 'portrait.txt']:
                self.assertTrue((root / 'assets' / 'portrait' / name).is_file())


if __name__ == '__main__':
    unittest.main()
