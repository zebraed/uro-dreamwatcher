# -*- coding: utf-8 -*-
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import hashlib


@dataclass(frozen=True)
class State:
    """State for tracking seen items and content changes."""
    seen: dict[str, str]
    updated_at: str
    content_hashes: dict[str, str] = field(default_factory=dict)


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


def get_page_diff(
    page_name: str,
    current_content: str,
    state: State
) -> Optional[str]:
    """
    Get hash of current page content if it has changed.

    Args:
        page_name: Page name
        current_content: Current page content
        state: State object with previous content

    Returns:
        Optional[str]: Hash if content changed, None otherwise
    """
    if has_page_content_changed(page_name, current_content, state):
        return get_content_hash(current_content)

    return None


def get_content_diff_preview(
    page_name: str,
    current_content: Optional[str],
    state: State,
    max_chars: int = 30
) -> Optional[str]:
    """
    Get preview of changed content (first N characters).

    Args:
        page_name: Page name
        current_content: Current page content. If None, returns None.
        state: State object with previous content
        max_chars: Maximum characters for preview

    Returns:
        Optional[str]: Preview of changed content, or None if unchanged
        or content is None
    """
    if not current_content:
        return None

    if has_page_content_changed(page_name, current_content, state):
        preview = current_content[:max_chars].strip()
        return preview if preview else None

    return None
