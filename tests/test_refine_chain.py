"""M1 chain writer smoke test.

Run from the pack folder:
  python -m unittest discover -s tests -v
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from .. import refine_chain as rc


class ChainTests(unittest.TestCase):
    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            clip = os.path.join(td, "clip_00001.mp4")
            open(clip, "w").close()
            entry = {
                "take": "upscale_00001.mp4",
                "layout": [0, 10],
                "seed": 42,
                "denoise": 0.35,
                "preset": "h3_upscale_options",
                "megapixels": 0.98,
                "group": "upscale_00001",
                "pass": 1,
            }
            with patch.object(rc, "resolve_clip", lambda p: p):
                rc.append_entry(clip, entry)
                loaded = rc.load_chain(clip)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["take"], "upscale_00001.mp4")
            self.assertEqual(loaded[0]["seed"], 42)
            # second append
            with patch.object(rc, "resolve_clip", lambda p: p):
                rc.append_entry(clip, {"take": "upscale_00002.mp4", "pass": 2})
                loaded = rc.load_chain(clip)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[1]["pass"], 2)


if __name__ == "__main__":
    unittest.main()
