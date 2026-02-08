# -*- coding: utf-8 -*-
import unittest

from dreamwatcher.snapshot import get_display_diff


REMOVED_LINE = ("TESTtest")
ADDED_LINE = ("TESTtesttt")


def make_raw_diff(removed: str, added: str) -> str:
    """Build unified diff string with one removed and one added line."""
    return f"--- a/page.txt\n+++ b/page.txt\n-{removed}\n+{added}\n"


class TestSequenceMatchSameEdit(unittest.TestCase):
    def test_white_bird_mask_diff_treated_as_edit(self):
        raw = make_raw_diff(REMOVED_LINE, ADDED_LINE)
        display = get_display_diff(raw)
        self.assertIsNone(
            display,
            "None",
        )


if __name__ == "__main__":
    unittest.main()
