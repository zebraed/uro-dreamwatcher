# -*- coding: utf-8 -*-
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import hashlib
import difflib


@dataclass(frozen=True)
class State:
    """State for tracking seen items and content changes."""
    seen: dict[str, str]
    updated_at: str
    content_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PageSnapshot:
    """Snapshot of page content."""
    page_name: str
    content: str
    timestamp: str
    diff: Optional[str] = None


def load_state(path: Path) -> State:
    """Load state from a file.
    Args:
        path: The path to the state file.

    Returns:
        State: The state object.
    """
    if not path.exists():
        return State(seen={}, updated_at=None, content_hashes={})

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        seen = data.get("seen", {})
        updated_at = data.get("updated_at", None)
        content_hashes = data.get("content_hashes", {})

        if not isinstance(seen, dict):
            seen = {}
        if not isinstance(updated_at, str):
            updated_at = None
        if not isinstance(content_hashes, dict):
            content_hashes = {}

        return State(
            seen=seen,
            updated_at=updated_at,
            content_hashes=content_hashes
        )
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Error loading state: {e}")
        return State(seen={}, updated_at=None, content_hashes={})


def save_state(path: Path, state: State):
    """
    Save state to a file.

    Args:
        path: The path to the state file.
        state: The state object.
    """
    data = {
        "seen": state.seen,
        "updated_at": state.updated_at,
        "content_hashes": state.content_hashes
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_content_hash(content: Optional[str]) -> Optional[str]:
    """
    Get MD5 hash of content.

    Args:
        content: The content to hash. If None, returns None.

    Returns:
        str: MD5 hash of the content, or None if content is None.
    """
    if not content:
        return None
    return hashlib.md5(content.encode()).hexdigest()


def has_page_content_changed(
    page_name: str,
    current_content: Optional[str],
    state: State
) -> bool:
    """
    Check if page content has changed.

    Args:
        page_name: Page name
        current_content: Current page content. If None, returns False.
        state: State object with previous content hashes

    Returns:
        bool: True if content changed or is new, False otherwise
    """
    if not current_content:
        return False

    page_key = f"content_{page_name}"
    current_hash = get_content_hash(current_content)

    if (page_key not in state.content_hashes or
            state.content_hashes[page_key] != current_hash):
        return True

    return False


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
        return preview + " ..."

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
        fromfile="previous_content",
        tofile="current_content",
        lineterm=""
    )
    return "\n".join(diff)


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
