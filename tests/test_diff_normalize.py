#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dreamwatcher.snapshot import _normalize_diff_line


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


if __name__ == "__main__":
    test_skip_empty_and_comments()
    test_list_markers_stripped_first()
    test_ampersand_skip_after_list_strip()
    test_ampersand_in_middle_not_skipped()
    test_only_list_markers_becomes_empty()
    test_asterisk_heading_unchanged()
    print("All checks passed.")
