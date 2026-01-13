# -*- coding: utf-8 -*-
import json
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

    diff_text = snapshot.diff
    if len(diff_text) > max_chars:
        preview = diff_text[:max_chars].strip()
        return preview

    return diff_text if diff_text.strip() else None


def get_diff(previous_content, current_content):
    """
    Get diff between previous and current content.

    Args:
        previous_content: Previous content.
        current_content: Current content.

    Returns:
        Optional[str]: Diff between previous and current content,
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
    # Filter lines
    added_lines = [
        line[1:] for line in diff
        if line.startswith('+') and not line.startswith('+++')
        and not line.lstrip('+').strip().startswith('//')
    ]

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

    diff = get_diff(previous_content, current_content) if previous_content else None

    return PageSnapshot(
        page_name=page_name,
        content=current_content,
        timestamp=timestamp,
        diff=diff
    )
