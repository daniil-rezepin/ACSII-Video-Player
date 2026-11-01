import unittest
import numpy as np

import backlight
from backlight import EXIT_COLOR, KeyboardLight, frame_color, tuf_packet


def solid(b, g, r, size=(18, 32)):
    """A frame filled with one BGR color, like OpenCV produces."""
    frame = np.zeros(size + (3,), dtype=np.uint8)
    frame[:, :] = (b, g, r)
    return frame


class FakeDriver:
    def __init__(self, fail=False):
        self.colors = []
        self.closed = False
        self.fail = fail

    def set_color(self, r, g, b):
        if self.fail:
            raise OSError("keyboard unplugged")
        self.colors.append((r, g, b))

    def close(self):
        self.closed = True


class BacklightTests(unittest.TestCase):
    def test_packet_layout(self):
        expected = bytes.fromhex(
            "44455653 0c000000 56001000 b300ff80 0aeb0000"
        )
        self.assertEqual(tuf_packet(255, 128, 10), expected)

    def test_solid_frames(self):
        np.testing.assert_allclose(frame_color(solid(0, 0, 255)), [1, 0, 0])
        np.testing.assert_allclose(frame_color(solid(0, 0, 0)), [0, 0, 0])
        np.testing.assert_allclose(frame_color(solid(255, 255, 255)), [1, 1, 1])

    def test_vivid_pixels_decide_the_hue(self):
        frame = solid(128, 128, 128)
        frame[6:12, 12:20] = (0, 0, 255)  # small red patch on a grey frame
        r, g, b = frame_color(frame)
        self.assertGreater(r, g + 0.2)
        self.assertGreater(r, b + 0.2)

    def test_fades_between_colors_and_restores(self):
        driver = FakeDriver()
        light = KeyboardLight(lambda: driver)
        self.assertIsNone(light.open())

        light.show(solid(0, 0, 255))
        light.update(0.0)
        self.assertEqual(driver.colors[-1], (255, 0, 0))  # first color is instant

        light.show(solid(255, 0, 0))  # switch to blue
        light.update(0.05)
        r, _, b = driver.colors[-1]
        self.assertTrue(0 < r < 255 and 0 < b < 255)  # partway through the fade

        light.update(2.0)
        self.assertEqual(driver.colors[-1], (0, 0, 255))

        light.close()
        self.assertEqual(driver.colors[-1], EXIT_COLOR)
        self.assertTrue(driver.closed)
        self.assertFalse(light.active)

    def test_limits_update_rate(self):
        driver = FakeDriver()
        light = KeyboardLight(lambda: driver)
        light.open()
        light.show(solid(0, 0, 255))
        light.update(0.0)
        light.show(solid(255, 0, 0))
        light.update(0.5 / backlight.MAX_UPDATES)  # too soon to send again
        self.assertEqual(len(driver.colors), 1)

    def test_driver_errors_turn_lighting_off(self):
        driver = FakeDriver(fail=True)
        light = KeyboardLight(lambda: driver)
        light.open()
        light.show(solid(0, 0, 255))
        light.update(0.0)  # must not raise
        self.assertFalse(light.active)
        self.assertTrue(driver.closed)

    def test_missing_driver_gives_warning(self):
        def unavailable():
            raise OSError("no driver")

        light = KeyboardLight(unavailable)
        self.assertIn("no driver", light.open())
        self.assertFalse(light.active)
        light.update(0.0)
        light.close()


if __name__ == "__main__":
    unittest.main()
