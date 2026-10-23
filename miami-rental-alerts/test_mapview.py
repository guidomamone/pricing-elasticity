import io
import unittest

import mapview

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

PINS = [(1, 25.7506, -80.1990, "tennis"),
        (2, 25.7506, -80.1990, "tennis"),   # same building, same coordinate
        (3, 25.7679, -80.1862, "tennis"),
        (4, 25.7580, -80.1930, "brickell"),
        (5, None, None, "brickell")]        # no coordinates


def fake_tile(zoom, x, y):
    out = io.BytesIO()
    Image.new("RGB", (256, 256), (200 + x % 40, 210, 200 + y % 40)).save(out, format="PNG")
    return out.getvalue()


class GeometryTests(unittest.TestCase):
    def test_projection_origin(self):
        self.assertEqual(mapview.project(0, 0, 0), (128.0, 128.0))

    def test_units_of_one_building_share_a_pin(self):
        groups, missing = mapview.group_pins(PINS)
        self.assertEqual(missing, 1)
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0][3], [1, 2])

    def test_invalid_coordinates_counted_as_missing(self):
        groups, missing = mapview.group_pins([(1, 200, 0, "tennis"), (2, 25.7, None, "tennis")])
        self.assertEqual((groups, missing), ([], 2))

    def test_zoom_fits_the_spread(self):
        near = mapview.fit_zoom([(25.7506, -80.1990, "t", [1])], 900, 650)
        far = mapview.fit_zoom([(25.70, -80.30, "t", [1]), (25.85, -80.10, "t", [2])], 900, 650)
        self.assertEqual(near, 16)
        self.assertLess(far, near)


@unittest.skipUnless(Image, "Pillow not installed")
class RenderTests(unittest.TestCase):
    def test_renders_png(self):
        png, missing = mapview.render_map(PINS, fetch=fake_tile)
        self.assertEqual(missing, 1)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertEqual(Image.open(io.BytesIO(png)).size, (900, 650))

    def test_nothing_to_draw(self):
        self.assertEqual(mapview.render_map([(1, None, None, "tennis")], fetch=fake_tile), (None, 1))
        self.assertEqual(mapview.render_map([], fetch=fake_tile), (None, 0))

    def test_all_tiles_failing_raises(self):
        def broken(*_):
            raise OSError("offline")
        with self.assertRaises(RuntimeError):
            mapview.render_map(PINS, fetch=broken)

    def test_some_tiles_failing_still_renders(self):
        calls = []

        def flaky(zoom, x, y):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("one bad tile")
            return fake_tile(zoom, x, y)
        png, _ = mapview.render_map(PINS, fetch=flaky)
        self.assertTrue(png.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
