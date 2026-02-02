# -*- coding: utf-8 -*-
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import difflib


@dataclass(frozen=True)
class PageSnapshot:
    """Snapshot of page content."""
    page_name: str
    content: str
    timestamp: str
    diff: Optional[str] = None


def _filter_wiki_syntax(diff) -> list[str]:
    """
    Extract added lines from unified diff, filtering wiki syntax and comments.
    """
    result = []
    for line in diff:
        # Ignore file headers
        if not line.startswith("+") or line.startswith("+++"):
            continue
        # Remove the diff marker
        content = line[1:].rstrip("\n")
        # Skip empty lines
        if not content.strip():
            continue
        # Skip comment lines
        if content.lstrip().startswith("//"):
            continue
        # Skip plug-in content lines
        if content.lstrip().startswith("|"):
            continue
        # Drop common no-content macros
        if content.strip() in {"#br", "#br;"}:
            continue
        # Skip lines starting with #
        if content.lstrip().startswith("#"):
            continue
        # Convert wiki emphasis markers
        filtered = content.replace("''", "")
        # color
        filtered = re.sub(r"&color\([^)]*\)\{([^}]*)\};?", r"\1", filtered)
        filtered = re.sub(r"&color\([^)]*\)", "", filtered)
        # size
        filtered = re.sub(r"&size\([^)]*\)\{([^}]*)\};?", r"\1", filtered)
        filtered = re.sub(r"&size\([^)]*\)", "", filtered)
        # date
        filtered = re.sub(r"&\w+([^;]*);", r"\1", filtered)
        # strikethrough convert
        filtered = re.sub(r"%%([^%]*)%%", r"~~\1~~", filtered)
        # underline convert
        filtered = re.sub(r"%%%([^%]*)%%%", r"__\1__", filtered)
        # braces
        filtered = re.sub(r"\{([^}]*)\}", r"\1", filtered)
        # anchors
        filtered = re.sub(r"\s*\[#[^\]]+\]", "", filtered)
        # bullets
        stripped = filtered.lstrip()
        if stripped.startswith("--"):
            filtered = re.sub(r"^\s*--\s*", "", filtered)
        elif stripped.startswith("-"):
            filtered = re.sub(r"^\s*-\s*", "", filtered)
        # &br() and &br;
        filtered = re.sub(r"&br\(\)", "", filtered)
        filtered = re.sub(r"&br;", "", filtered)
        # leading '*'
        filtered = re.sub(r"^\*+\s*", "", filtered)
        # cleanup
        filtered = filtered.strip()
        if not filtered:
            continue

        result.append(filtered)

    return result


def _convert_links(text: str) -> str:
    """
    Remove URLs from text.

    Args:
        text: Text with wiki-style links and URLs

    Returns:
        str: Text with URLs removed
    """
    text = re.sub(r"\[\[([^\]]+)>([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://[^\s]+", "", text)
    return text


def _get_display_width(text: str) -> int:
    """
    Get display width of text.
    """
    width = 0
    for char in text:
        if ord(char) > 127:
            width += 2
        else:
            width += 1
    return width


def get_content_diff_preview(
    snapshot: Optional["PageSnapshot"],
    max_chars: int = 80
) -> Optional[str]:
    """
    Get preview of diff from snapshot.

    Args:
        snapshot: PageSnapshot object with diff
        max_chars: Maximum characters for preview

    Returns:
        Optional[str]: Preview of diff, or None if no diff available
    """
    if not snapshot or not snapshot.diff:
        return None

    display_diff = get_display_diff(snapshot.diff)
    if not display_diff:
        return None

    diff_text = _convert_links(display_diff)
    first_line = diff_text.split("\n")[0]
    parts = re.split(r"(\[[^\]]+\]\([^\)]+\))", first_line)
    result = []
    char_count = 0
    for part in parts:
        if re.match(r"^\[[^\]]+\]\([^\)]+\)$", part):
            result.append(part)
        else:
            if char_count < max_chars:
                remaining = max_chars - char_count
                part_width = _get_display_width(part)
                if part_width > remaining:
                    truncated = ""
                    current_width = 0
                    for char in part:
                        char_width = (2 if ord(char) > 127 else 1)
                        if (current_width + char_width > remaining):
                            break
                        truncated += char
                        current_width += char_width
                    result.append(truncated)
                    char_count = max_chars
                else:
                    result.append(part)
                    char_count += part_width

    preview_text = "".join(result).strip()
    return preview_text if preview_text else None


def get_raw_diff(previous_content, current_content):
    """
    Get raw diff between previous and current content.

    Args:
        previous_content: Previous content.
        current_content: Current content.

    Returns:
        Optional[str]: Raw diff between previous and current content,
                       or None if unchanged.
    """
    if not previous_content:
        return None

    previous_lines = previous_content.splitlines()
    current_lines = current_content.splitlines()

    diff = difflib.unified_diff(
        previous_lines,
        current_lines,
        lineterm=""
    )

    diff_lines = list(diff)
    return "\n".join(diff_lines) if diff_lines else None


def get_display_diff(raw_diff):
    """
    Get display diff from raw diff.

    Args:
        raw_diff: Raw diff string.

    Returns:
        Optional[str]: Display diff with wiki syntax filtered,
                       or None if no content.
    """
    if not raw_diff:
        return None

    diff_lines = raw_diff.split("\n")
    added_lines = _filter_wiki_syntax(diff_lines)

    return "\n".join(added_lines) if added_lines else None


def load_snapshots(path: Path) -> dict[str, PageSnapshot]:
    """
    Load page snapshots from file.

    Args:
        path: The path to the snapshots file.

    Returns:
        dict[str, PageSnapshot]: Dictionary of page snapshots.
    """
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshots = {}
        for page_name, snapshot_data in data.items():
            snapshots[page_name] = PageSnapshot(
                page_name=snapshot_data["page_name"],
                content=snapshot_data["content"],
                timestamp=snapshot_data["timestamp"],
                diff=snapshot_data.get("diff")
            )
        return snapshots
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Error loading snapshots: {e}")
        return {}


def save_snapshots(path: Path, snapshots: dict[str, PageSnapshot]):
    """
    Save page snapshots to file.

    Args:
        path: The path to the snapshots file.
        snapshots: Dictionary of page snapshots.
    """
    data = {
        page_name: {
            "page_name": snapshot.page_name,
            "content": snapshot.content,
            "timestamp": snapshot.timestamp,
            "diff": snapshot.diff
        }
        for page_name, snapshot in snapshots.items()
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def update_snapshot(
    page_name: str,
    current_content: str,
    snapshots: dict[str, PageSnapshot],
    timestamp: str
) -> PageSnapshot:
    """
    Update snapshot with new content and diff.

    Args:
        page_name: Page name
        current_content: Current page content
        snapshots: Current snapshots dictionary
        timestamp: Current timestamp

    Returns:
        PageSnapshot: Updated snapshot
    """
    previous_snapshot = snapshots.get(page_name)
    previous_content = previous_snapshot.content if previous_snapshot else None

    diff = (
        get_raw_diff(previous_content, current_content)
        if previous_content
        else None
    )

    return PageSnapshot(
        page_name=page_name,
        content=current_content,
        timestamp=timestamp,
        diff=diff
    )
