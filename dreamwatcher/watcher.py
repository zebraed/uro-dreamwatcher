# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from concurrent.futures import (
    ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
)
import re

from .wiki import WikiClient, WikiApiConfig, WikiAuth
from .discord import WebhookClient, Event
from .emoji import Emoji
from .state import (
    State, load_state, save_state,
    has_page_content_changed, get_content_hash
)
from .snapshot import (
    load_snapshots, save_snapshots, update_snapshot,
    get_content_diff_preview
)
from .types import SecretStr


MAX_WORKERS = 8
_PAGE_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class Config:
    """
    Configuration for watcher.

    Attributes:
        wiki_id: The ID of the wiki.
        api_key_id: The API key ID.
        api_secret: The API secret.
        discord_webhook_url: The URL of the Discord webhook.
        state_path: The path to the state file.
        rss_urls: List of RSS URLs to monitor.
        page_names: List of specific page names to monitor.
        wiki_url: The URL of the wiki.
        snapshots_dir: The directory to store page snapshots.
        monitor_recent_created: Whether to monitor the RecentCreated page.
        auto_track_pattern: Pattern to auto-track pages from RecentCreated.
    """
    wiki_id: str
    api_key_id: SecretStr = field(repr=False)
    api_secret: SecretStr = field(repr=False)
    discord_webhook_url: SecretStr = field(repr=False)
    state_path: Path
    rss_urls: list[str] = field(default_factory=list)
    page_names: list[str] = field(default_factory=list)
    wiki_url: str = ""
    snapshots_dir: Path = field(default_factory=lambda: Path(".snapshots"))
    monitor_recent_created: bool = True
    auto_track_patterns: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return "<Config: hidden>"


def normalize_link(link: str) -> str:
    """Normalize a link."""
    return link.strip().rstrip("/")


def prune_state(seen: dict[str, str], max_items: int):
    """Prune the state."""
    if len(seen) <= max_items:
        return

    keys = sorted(seen.keys(), key=lambda k: seen.get(k, ""))
    for key in keys[:len(keys) - max_items]:
        del seen[key]


def _filter_links(_item, _state: State, _mode: str):
    """TODO: Implement filtering.
    Filter items based on mode.

    Args:
        _item: The item to filter.
        _state: Current state.
        _mode: The filter mode.

    Returns:
        bool: True if the item should be included, False otherwise.
    """
    return True


def _extract_page_names_from_diff(diff_text: str) -> list[str]:
    """
    Extract page names from RecentCreated and RecentChanges diff.

    Extracts page names from [[...]] patterns in the diff text.

    Args:
        diff_text: Diff text containing page names in [[...]] format.

    Returns:
        list[str]: List of extracted page names.
    """
    return _PAGE_LINK_RE.findall(diff_text)


def _is_page_closed(page_content: str) -> bool:
    """
    Check if page is closed.

    Args:
        page_content: Page content to check.

    Returns:
        bool: True if page is closed, False otherwise.
    """
    if not page_content:
        return False
    lines = page_content.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("* 【終了】") or stripped.startswith("*【終了】"):
            return True
        break
    return False


def _matches_pattern(page_name: str, patterns: list[str]) -> bool:
    """
    Check if page name matches any of the patterns.

    Args:
        page_name: Page name to check.
        patterns: List of regex patterns.

    Returns:
        bool: True if matches any pattern, False otherwise.
    """
    if not patterns:
        return False
    for pattern in patterns:
        if re.match(pattern, page_name):
            return True
    return False


def _check_monitored_pages(
    pages_to_check: list[str],
    client: WikiClient,
    state: State,
    cfg: Config,
    snapshots: dict,
    updated_snapshots: dict,
    events: list
) -> None:
    """
    Check monitored pages for updates and generate events.

    Args:
        pages_to_check: List of page names to check.
        client: WikiClient instance.
        state: Current state object.
        cfg: Configuration object.
        snapshots: Current snapshots dictionary.
        updated_snapshots: Dictionary to store updated snapshots.
        events: List to append events to.
    """
    if not pages_to_check:
        return
    max_workers = min(MAX_WORKERS, len(pages_to_check))
    per_batch_timeout = 10

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(client.get_page, page): page
            for page in pages_to_check
        }

        try:
            for future in as_completed(futures, timeout=per_batch_timeout):
                p_name = futures[future]
                try:
                    p_data = future.result()
                    event = _check_page_data(
                        p_name,
                        p_data,
                        state,
                        cfg
                    )
                    p_content = p_data.get("source")
                    p_date = p_data.get("timestamp")
                    p_key = f"content_{p_name}"

                    if p_content:
                        if _is_page_closed(p_content):
                            state.dynamic_monitored_pages.discard(p_name)

                        p_old = state.content_hashes.get(p_key)
                        p_new = get_content_hash(p_content)
                        state.content_hashes[p_key] = p_new
                        if p_old != p_new:
                            p_snap = update_snapshot(
                                page_name=p_name,
                                current_content=p_content,
                                snapshots=snapshots,
                                timestamp=p_date
                            )
                            updated_snapshots[p_name] = p_snap

                    if event:
                        diff_prev = None
                        if not event.is_initial:
                            evt_snap = updated_snapshots.get(p_name)
                            if evt_snap:
                                diff_prev = get_content_diff_preview(evt_snap)

                        evt = Event(
                            title=event.title,
                            url=event.url,
                            page_name=event.page_name,
                            date=event.date,
                            diff_preview=diff_prev,
                            is_initial=event.is_initial
                        )
                        events.append(evt)
                except (
                    OSError,
                    ValueError,
                    TimeoutError
                ) as e:
                    print(f"Error getting page '{p_name}': {e}")

        except FuturesTimeoutError:
            for future in futures:
                if not future.done():
                    future.cancel()
            pending_pages = [
                page for future, page in futures.items()
                if not future.done()
            ]
            if pending_pages:
                num = len(pending_pages)
                print(
                    "Timeout while fetching monitored pages; "
                    f"cancelled {num} pending request(s): {pending_pages}"
                )


def create_wiki_client(cfg: Config) -> WikiClient:
    """
    Create a WikiClient instance.

    Args:
        cfg: Configuration object.

    Returns:
        WikiClient: Initialized WikiClient instance.
    """
    api_cfg = WikiApiConfig(wiki_id=cfg.wiki_id)
    auth = WikiAuth(api_key_id=cfg.api_key_id, secret=cfg.api_secret)
    return WikiClient(api_cfg, auth)


def get_specific_pages_updates(
    cfg: Config,
    state: State,
    client: WikiClient,
    snapshots: dict,
    updated_snapshots: dict,
) -> list[Event]:
    """
    Get updates for specific pages by monitoring RecentChanges.

    Args:
        cfg: Configuration object.
        state: Current state object.
        client: WikiClient instance.
        snapshots: Current snapshots dictionary.
        updated_snapshots: Dictionary to store updated snapshots.

    Returns:
        list[Event]: List of events for updated pages.
    """
    all_monitored_pages = set(cfg.page_names) | state.dynamic_monitored_pages

    if not all_monitored_pages:
        return []
    events = []

    page_name = "RecentChanges"
    try:
        page_data = client.get_page(page_name)
        page_content = page_data.get("source")
        page_date = page_data.get("timestamp")
        content_key = f"content_{page_name}"

        if page_content:
            old_hash = state.content_hashes.get(content_key)
            new_hash = get_content_hash(page_content)
            state.content_hashes[content_key] = new_hash

            is_initial = old_hash is None

            if is_initial:
                page_url = (
                    f"{cfg.wiki_url.rstrip('/')}/?{page_name}"
                    if cfg.wiki_url
                    else page_name
                )
                initial_event = Event(
                    title=(
                        f"{Emoji.initial} 【RecentChanges】 "
                        "の通知が設定されました。"
                    ),
                    url=page_url,
                    page_name=page_name,
                    date=page_date,
                    is_initial=True
                )
                events.append(initial_event)

                timestamp = page_date
                snapshot = update_snapshot(
                    page_name=page_name,
                    current_content=page_content,
                    snapshots=snapshots,
                    timestamp=timestamp
                )
                updated_snapshots[page_name] = snapshot

            if old_hash != new_hash and not is_initial:
                timestamp = page_date
                snapshot = update_snapshot(
                    page_name=page_name,
                    current_content=page_content,
                    snapshots=snapshots,
                    timestamp=timestamp
                )
                updated_snapshots[page_name] = snapshot

                if snapshot and snapshot.diff:
                    updated_page_names = (
                        _extract_page_names_from_diff(
                            snapshot.diff
                        )
                    )
                    pages_to_check = [
                        p for p in updated_page_names
                        if p in all_monitored_pages
                    ]
                    if pages_to_check:
                        _check_monitored_pages(
                            pages_to_check,
                            client,
                            state,
                            cfg,
                            snapshots,
                            updated_snapshots,
                            events
                        )

    except (OSError, ValueError, TimeoutError) as e:
        print(f"Error getting RecentChanges: {e}")

    return events


def _process_initial_pages(
    page_content: str,
    page_date: str,
    cfg: Config,
    state: State,
    client: WikiClient,
    events: list
) -> None:
    lines = page_content.split('\n')
    auto_tracked_pages = []
    for line in lines:
        page_names = _extract_page_names_from_diff(line)
        for created_page_name in page_names:
            if _matches_pattern(
                created_page_name,
                cfg.auto_track_patterns
            ):
                try:
                    page_data_for_check = client.get_page(
                        created_page_name
                    )
                    page_content_for_check = (
                        page_data_for_check.get("source")
                    )
                    if page_content_for_check:
                        if not _is_page_closed(
                            page_content_for_check
                        ):
                            state.dynamic_monitored_pages.add(
                                created_page_name
                            )
                            auto_tracked_pages.append(
                                created_page_name
                            )
                except (
                    OSError, ValueError, TimeoutError
                ) as e:
                    print(
                        f"Error checking page "
                        f"'{created_page_name}': {e}"
                    )

    if auto_tracked_pages:
        page_list = "\n".join(
            [f"・{page}" for page in auto_tracked_pages]
        )
        created_event = Event(
            title=(
                f"{Emoji.initial} "
                f"ページが{len(auto_tracked_pages)}件 通知登録されました"
            ),
            url=cfg.wiki_url if cfg.wiki_url else "",
            page_name="RecentCreated",
            date=page_date,
            diff_preview=page_list,
            is_initial=False  # NOTE: its not a new page
        )
        events.append(created_event)


def _process_updated_pages(
    snapshot,
    page_date: str,
    cfg: Config,
    state: State,
    client: WikiClient,
    events: list
) -> None:
    if not snapshot or not snapshot.diff:
        return

    page_names = _extract_page_names_from_diff(
        snapshot.diff
    )
    newly_created_pages = []
    auto_tracked_pages = []
    for created_page_name in page_names:
        newly_created_pages.append(created_page_name)
        if _matches_pattern(
            created_page_name,
            cfg.auto_track_patterns
        ):
            try:
                page_data_for_check = client.get_page(
                    created_page_name
                )
                page_content_for_check = (
                    page_data_for_check.get("source")
                )
                if page_content_for_check:
                    if not _is_page_closed(
                        page_content_for_check
                    ):
                        if created_page_name not in (
                            state.dynamic_monitored_pages
                        ):
                            auto_tracked_pages.append(
                                created_page_name
                            )
                        state.dynamic_monitored_pages.add(
                            created_page_name
                        )
            except (
                OSError, ValueError, TimeoutError
            ) as e:
                print(
                    f"Error checking page "
                    f"'{created_page_name}': {e}"
                )

    if newly_created_pages:
        page_list = "\n".join(
            [f"・{page}" for page in newly_created_pages]
        )
        created_event = Event(
            title=(
                f"{Emoji.new} "
                f"ページが{len(newly_created_pages)}件 新規作成されました"
            ),
            url=cfg.wiki_url if cfg.wiki_url else "",
            page_name="RecentCreated",
            date=page_date,
            diff_preview=page_list,
            is_initial=False
        )
        events.append(created_event)

    if auto_tracked_pages:
        page_list = "\n".join(
            [f"・{page}" for page in auto_tracked_pages]
        )
        tracked_event = Event(
            title=(
                f"{Emoji.initial} "
                f"ページが{len(auto_tracked_pages)}件 通知登録されました"
            ),
            url=cfg.wiki_url if cfg.wiki_url else "",
            page_name="RecentCreated",
            date=page_date,
            diff_preview=page_list,
            is_initial=False
        )
        events.append(tracked_event)


def get_recent_created_updates(
    cfg: Config,
    state: State,
    client: WikiClient,
    snapshots: dict,
    updated_snapshots: dict,
) -> list[Event]:
    """
    Get updates from the RecentCreated page.

    Args:
        cfg: Configuration object.
        state: Current state object.
        client: WikiClient instance.
        snapshots: Current snapshots dictionary.
        updated_snapshots: Dictionary to store updated snapshots.

    Returns:
        list[Event]: List of events for newly created pages.
    """
    if not cfg.monitor_recent_created:
        return []
    events = []

    page_name = "RecentCreated"
    try:
        page_data = client.get_page(page_name)
        event = _check_page_data(
            page_name, page_data, state, cfg, event_type="created"
        )
        page_content = page_data.get("source")
        page_date = page_data.get("timestamp")
        content_key = f"content_{page_name}"

        if page_content:
            old_hash = state.content_hashes.get(content_key)
            new_hash = get_content_hash(page_content)
            state.content_hashes[content_key] = new_hash
            if old_hash != new_hash:
                timestamp = page_date
                snapshot = update_snapshot(
                    page_name=page_name,
                    current_content=page_content,
                    snapshots=snapshots,
                    timestamp=timestamp
                )
                updated_snapshots[page_name] = snapshot

        if event:
            if event.is_initial:
                if page_content:
                    _process_initial_pages(
                        page_content, page_date, cfg, state,
                        client, events
                    )
                events.append(event)
            else:
                snapshot = updated_snapshots.get(page_name)
                _process_updated_pages(
                    snapshot, page_date, cfg, state,
                    client, events
                )
    except (OSError, ValueError, TimeoutError) as e:
        print(f"Error getting page '{page_name}': {e}")

    return events


def _check_page_data(
    page_name: str,
    page_data: dict,
    state: State,
    cfg: Config,
    event_type: str = "update"
) -> Optional[Event]:
    """
    Process page data and check if it has been updated.

    Args:
        page_name: The name of the page.
        page_data: The page data from the API.
        state: Current state object.
        cfg: Configuration object.
        event_type: Type of event ("update" or "created").

    Returns:
        Optional[Event]: Event if page is new or updated, None otherwise.
    """
    page_path = f"page/{page_name}"
    page_key = normalize_link(page_path)
    page_title = page_data.get("page", page_name)
    page_date = page_data.get("timestamp")
    page_content = page_data.get("source")

    page_url = (
        f"{cfg.wiki_url.rstrip('/')}/?{page_name}"
        if cfg.wiki_url
        else page_name
    )

    if event_type == "created":
        page_event_title = f"{Emoji.new} 【{page_title}】 が新規作成されました。"
    else:
        page_event_title = f"{Emoji.update} 【{page_title}】 が更新されました。"

    is_page_first_run = f"content_{page_name}" not in state.content_hashes

    if is_page_first_run:
        return Event(
            title=f"{Emoji.initial} 【{page_title}】 の通知が設定されました。",
            url=page_url,
            page_name=page_name,
            date=page_date,
            is_initial=True
        )

    stored_date = state.seen.get(page_key)
    if page_date and stored_date != page_date:
        if page_content and has_page_content_changed(
            page_name, page_content, state
        ):
            return Event(
                title=page_event_title,
                url=page_url,
                page_name=page_name,
                date=page_date
            )

    return None


def clean_monitored_state(
    seen: dict[str, str],
    content_hashes: dict[str, str],
    cfg: Config,
    state: State
) -> tuple[dict[str, str], dict[str, str]]:
    """Remove pages that are no longer being monitored from state.

    Args:
        seen: Current seen items.
        content_hashes: Current content hashes.
        cfg: Configuration object.
        state: Current state object.

    Returns:
        Tuple of (cleaned_seen, cleaned_hashes)
    """
    monitored_page_keys = {
        normalize_link(f"page/{page_name}")
        for page_name in cfg.page_names
    }

    # Add dynamic monitored pages
    for page_name in state.dynamic_monitored_pages:
        monitored_page_keys.add(normalize_link(f"page/{page_name}"))

    if cfg.monitor_recent_created:
        monitored_page_keys.add(normalize_link("page/RecentCreated"))

    if cfg.page_names or state.dynamic_monitored_pages:
        monitored_page_keys.add(normalize_link("page/RecentChanges"))

    cleaned_seen = {
        k: v for k, v in seen.items()
        if k in monitored_page_keys or not k.startswith("page/")
    }

    monitored_content_keys = {
        f"content_{page_name}" for page_name in cfg.page_names
    }

    for page_name in state.dynamic_monitored_pages:
        monitored_content_keys.add(f"content_{page_name}")

    if cfg.monitor_recent_created:
        monitored_content_keys.add("content_RecentCreated")

    if cfg.page_names or state.dynamic_monitored_pages:
        monitored_content_keys.add("content_RecentChanges")

    cleaned_hashes = {
        k: v for k, v in content_hashes.items()
        if k in monitored_content_keys
    }

    return cleaned_seen, cleaned_hashes


def run(cfg: Config) -> int:
    """Run watcher."""
    state = load_state(cfg.state_path)

    events_to_send = []

    wiki_client = create_wiki_client(cfg)

    cfg.snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshots_path = cfg.snapshots_dir / "snapshots.json"
    snapshots = load_snapshots(snapshots_path)
    updated_snapshots: dict = {}

    page_events = get_specific_pages_updates(
        cfg, state, wiki_client, snapshots, updated_snapshots
    )
    events_to_send.extend(page_events)

    recent_created_events = get_recent_created_updates(
        cfg, state, wiki_client, snapshots, updated_snapshots
    )
    events_to_send.extend(recent_created_events)

    if updated_snapshots:
        snapshots.update(updated_snapshots)
        save_snapshots(snapshots_path, snapshots)

    if not events_to_send:
        return 0

    client = WebhookClient(cfg.discord_webhook_url)
    client.send_events(events_to_send, header="")

    updated_seen = state.seen.copy()
    for event in events_to_send:
        event_date = event.date
        page_key = normalize_link(f"page/{event.page_name}")
        updated_seen[page_key] = event_date

    updated_seen, updated_hashes = clean_monitored_state(
        updated_seen,
        state.content_hashes,
        cfg,
        state
    )

    prune_state(updated_seen, max_items=5000)

    updated_state = State(
        seen=updated_seen,
        updated_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        content_hashes=updated_hashes,
        dynamic_monitored_pages=state.dynamic_monitored_pages
    )

    save_state(cfg.state_path, updated_state)
    return 0
