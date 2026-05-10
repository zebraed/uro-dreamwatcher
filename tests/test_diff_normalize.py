#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dreamwatcher.snapshot import (
    _normalize_diff_line,
    _parse_diff,
    get_display_diff,
)
###
###
#testtest

def eq(content: str, expected: Optional[str]) -> None:
    got = _normalize_diff_line(content)
    assert got == expected, f"{content!r} -> {got!r}, expected {expected!r}"


def test_skip_empty_and_comments():
    eq("", None)
    eq("   ", None)
    eq("// comment", None)
    eq("# heading", None)
    eq("| plugin", None)
    eq("#br", None)
    eq("#br;", None)


def test_list_markers_stripped_first():
    eq("- 項目", "項目")
    eq("-- 項目", "項目")
    eq("--- 項目", "項目")
    eq("    - 項目", "項目")
    eq("  -- ネスト", "ネスト")


def test_ampersand_skip_after_list_strip():
    eq("-& fa_li(fas fa-xl fa-spell-check,silver);", None)
    eq("--& fa_li(x);", None)
    eq("& fa_li(x);", None)
    eq("&br;", None)


def test_ampersand_in_middle_not_skipped():
    eq("- 本文 &color(red){赤}; 続き", "本文 赤 続き")


def test_only_list_markers_becomes_empty():
    eq("-", None)
    eq("--", None)
    eq("---", None)
    eq("  -  -  ", None)


def test_asterisk_heading_unchanged():
    eq("* 見出し", "見出し")
    eq("- * 見出し", "見出し")


def test_parse_diff_does_not_misclassify_removed_line_starting_with_dashes():
    raw_diff = """--- 
+++ 
@@ -1,3 +1,3 @@
 [[バグ一覧]]
+-[[sample>https://example.com]]にて、同一文です。 --  &new{2026-05-10 (日) 00:59:39};
----[[sample>https://example.com]]にて、同一文です。 --  &new{2026-05-10 (日) 00:59:39};
"""
    removed, added = _parse_diff(raw_diff.split("\n"))
    expected = "[[sample>https://example.com]]にて、同一文です。 --  2026-05-10 (日) 00:59:39"
    assert removed == [expected]
    assert added == [expected]


def test_display_diff_omits_dash_only_indent_moves():
    raw_diff = """--- 
+++ 
@@ -1,7 +1,7 @@
 [[バグ一覧]]
+-[[sample>https://example.com]]にて、同一文です。 --  &new{2026-05-10 (日) 00:59:39};
 -歓楽通りから窓のない倉庫に来た際、何故か高速で動けてしまう ver0.129 p12 --  &new{2026-05-01 (金) 20:30:24};
 --RPGツクール2000の不具合にある高速化バグではないでしょうか --  &new{2026-05-03 (日) 20:49:04};
----[[sample>https://example.com]]にて、同一文です。 --  &new{2026-05-10 (日) 00:59:39};
 --中身を見てみましたが、これは定期的に並列処理するでBGMの演奏を短い時間に何回も実行する処理になっているのが原因だと思います。 --  &new{2026-05-06 (水) 03:09:27};
"""
    assert get_display_diff(raw_diff) is None


if __name__ == "__main__":
    test_skip_empty_and_comments()
    test_list_markers_stripped_first()
    test_ampersand_skip_after_list_strip()
    test_ampersand_in_middle_not_skipped()
    test_only_list_markers_becomes_empty()
    test_asterisk_heading_unchanged()
    test_parse_diff_does_not_misclassify_removed_line_starting_with_dashes()
    test_display_diff_omits_dash_only_indent_moves()
    print("All checks passed.")
