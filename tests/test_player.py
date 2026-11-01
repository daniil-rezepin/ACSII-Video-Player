import unittest
import numpy as np

from player import Clock, RAMP, fit_size, render


class PlayerTests(unittest.TestCase):
    def test_black_and_white_mapping(self):
        frame = np.array([[[0, 0, 0], [255, 255, 255]]], dtype=np.uint8)
        self.assertEqual(render(frame, (2, 1), "mono"), [RAMP[0] + RAMP[-1]])
        self.assertEqual(
            render(frame, (2, 1), "mono", invert=True),
            [RAMP[-1] + RAMP[0]],
        )

    def test_truecolor_converts_bgr_to_rgb(self):
        frame = np.array([[[0, 0, 255]]], dtype=np.uint8)
        self.assertIn("\033[38;2;255;0;0m", render(frame, (1, 1), "truecolor")[0])

    def test_fit_respects_both_dimensions(self):
        for source in [(1920, 1080), (1080, 1920)]:
            w, h = fit_size(*source, 80, 24)
            self.assertTrue(1 <= w <= 79)
            self.assertTrue(1 <= h <= 22)

    def test_clock_excludes_pause(self):
        now = [0.0]
        clock = Clock(lambda: now[0])
        now[0] = 2
        clock.toggle()
        now[0] = 10
        self.assertEqual(clock.elapsed(), 2)
        clock.toggle()
        now[0] = 13
        self.assertEqual(clock.elapsed(), 5)


if __name__ == "__main__":
    unittest.main()
