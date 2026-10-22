"""Focused synthetic-array tests for the experimental native hold."""
import unittest
import numpy as np
from native_yuv import planes, support_masks, hold_frames


class NativeYuv(unittest.TestCase):
    def test_chroma_support_is_shared_two_by_two(self):
        mask = np.zeros((4, 6), np.uint8)
        mask[1, 3] = 255
        y, c = support_masks(mask)
        self.assertEqual(int(y.sum()), 1)
        self.assertEqual(int(c.sum()), 1)
        self.assertTrue(c[0, 1])

    def test_odd_dimensions_rejected(self):
        for shape in [(3, 4), (4, 3)]:
            with self.assertRaises(ValueError):
                support_masks(np.zeros(shape, np.uint8))

    def test_entire_clip_hold_preserves_outside_native_samples(self):
        mask = np.zeros((4, 6), np.uint8)
        mask[1, 3] = 255
        source = [np.arange(36, dtype=np.uint8) + i for i in range(4)]
        snapshots = [x.copy() for x in source]
        actual = list(hold_frames(source, mask))
        y, c = support_masks(mask)
        for t, frame in enumerate(actual):
            for output, original, reference, selected in zip(
                planes(frame, 6, 4), planes(source[t], 6, 4),
                planes(source[0], 6, 4), (y, c, c)
            ):
                np.testing.assert_array_equal(output[selected], reference[selected])
                np.testing.assert_array_equal(output[~selected], original[~selected])
        for a, b in zip(source, snapshots):
            np.testing.assert_array_equal(a, b)

    def test_empty_mask_is_identity_without_aliasing(self):
        source = [np.arange(36, dtype=np.uint8), np.arange(36, dtype=np.uint8) + 2]
        out = list(hold_frames(source, np.zeros((4, 6), np.uint8)))
        for a, b in zip(source, out):
            np.testing.assert_array_equal(a, b)
            self.assertFalse(np.shares_memory(a, b))


if __name__ == "__main__":
    unittest.main()
