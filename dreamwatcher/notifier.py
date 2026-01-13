# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api import WikiClient, WikiApiConfig, WikiAuth
from .discord import WebhookClient, Event
from .emoji import Emoji
from .rss import fetch_items
from .state import (
    State, load_state, save_state,
    has_page_content_changed, get_content_hash, get_content_diff_preview,
    load_snapshots, save_snapshots, update_snapshot
)
from .types import SecretStr


@dataclass(frozen=True)
class Config:
    """
    Configuration for the notifier.

    Attributes:
        source: The source of the items.
        wiki_id: The ID of the wiki.
        api_key_id: The API key ID.
        api_secret: The API secret.
        discord_webhook_url: The URL of the Discord webhook.
        state_path: The path to the state file.
        mode: The mode of the notifier.
        rss_url: The URL of the RSS feed.
        page_names: List of specific page names to monitor.
        wiki_url: The URL of the wiki.
        snapshots_dir: The directory to store page snapshots.
    """
    source: str
    wiki_id: str
    api_key_id: SecretStr = field(repr=False)
    api_secret: SecretStr = field(repr=False)
    discord_webhook_url: SecretStr = field(repr=False)
    state_path: Path
    mode: str = "all"
    rss_url: str = ""
    page_names: list[str] = field(default_factory=list)
    wiki_url: str = ""
    snapshots_dir: Path = field(default_factory=lambda: Path(".snapshots"))

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


def filter_links(_item, _state: State, _mode: str):
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


def collect_items(cfg: Config):
    """Collect items from the source."""
    if cfg.source == "rss":
        return fetch_items(cfg.rss_url)
    if cfg.source == "api":
        api_cfg = WikiApiConfig(wiki_id=cfg.wiki_id)
        auth = WikiAuth(api_key_id=cfg.api_key_id, secret=cfg.api_secret)
        client = WikiClient(api_cfg, auth)
        return client.list_pages()

    raise ValueError(f"Unknown source: {cfg.source}")


def get_specific_pages_updates(cfg: Config, state: State) -> list[Event]:
    """
    Get updates for specific pages.

    Args:
        cfg: Configuration object.
        state: Current state object.

    Returns:
        list[Event]: List of events for updated pages.
    """
    if not cfg.page_names:
        return []

    api_cfg = WikiApiConfig(wiki_id=cfg.wiki_id)
    auth = WikiAuth(api_key_id=cfg.api_key_id, secret=cfg.api_secret)
    client = WikiClient(api_cfg, auth)

    cfg.snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshots = load_snapshots(cfg.snapshots_dir / "snapshots.json")
    events = []
    updated_snapshots = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(client.get_page, page_name): page_name
            for page_name in cfg.page_names
        }

        for future in as_completed(futures):
            page_name = futures[future]
            try:
                page_data = future.result(timeout=10)
                event = _check_page_data(page_name, page_data, state, cfg)
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
                    snapshot = updated_snapshots.get(page_name)
                    diff_preview = get_content_diff_preview(snapshot)
                    if diff_preview or event.is_initial:
                        event_with_diff = Event(
                            title=event.title,
                            url=event.url,
                            page_name=event.page_name,
                            date=event.date,
                            diff_preview=diff_preview,
                            is_initial=event.is_initial
                        )
                        events.append(event_with_diff)
            except (OSError, ValueError, TimeoutError) as e:
                print(f"Error getting page '{page_name}': {e}")

    if updated_snapshots:
        snapshots.update(updated_snapshots)
        save_snapshots(cfg.snapshots_dir / "snapshots.json", snapshots)

    return events


def _check_page_data(
    page_name: str,
    page_data: dict,
    state: State,
    cfg: Config
) -> Optional[Event]:
    """
    Process page data and check if it has been updated.

    Args:
        page_name: The name of the page.
        page_data: The page data from the API.
        state: Current state object.
        cfg: Configuration object.

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


def _clean_monitored_state(
    seen: dict[str, str],
    content_hashes: dict[str, str],
    cfg: Config
) -> tuple[dict[str, str], dict[str, str]]:
    """Remove pages that are no longer being monitored from state.

    Args:
        seen: Current seen items.
        content_hashes: Current content hashes.
        cfg: Configuration object.

    Returns:
        Tuple of (cleaned_seen, cleaned_hashes)
    """
    monitored_page_keys = {
        normalize_link(f"page/{page_name}")
        for page_name in cfg.page_names
    }

    cleaned_seen = {
        k: v for k, v in seen.items()
        if k in monitored_page_keys or not k.startswith("page/")
    }

    cleaned_hashes = {
        k: v for k, v in content_hashes.items()
        if any(k == f"content_{page_name}" for page_name in cfg.page_names)
    }

    return cleaned_seen, cleaned_hashes


def run(cfg: Config) -> int:
    """Run the notifier."""
    state = load_state(cfg.state_path)

    events_to_send = []

    if cfg.source == "rss":
        items = collect_items(cfg)
        links = [
            item for item in items
            if filter_links(item, state, cfg.mode)
        ]

        new_items = []
        for item in links:
            key = normalize_link(item.link)
            if key not in state.seen:
                new_items.append(item)

        new_items.sort(key=lambda item: item.date)
        events_to_send.extend([
            Event(title=item.title,
                  url=item.link,
                  page_name=item.link,
                  date=item.date)
            for item in new_items
        ])

    page_events = get_specific_pages_updates(cfg, state)
    events_to_send.extend(page_events)

    if not events_to_send:
        return 0

    client = WebhookClient(cfg.discord_webhook_url)
    client.send_events(events_to_send, header=f"{Emoji.new} 更新通知")

    updated_seen = state.seen.copy()
    for event in events_to_send:
        event_date = event.date
        page_key = normalize_link(f"page/{event.page_name}")
        updated_seen[page_key] = event_date

    updated_seen, updated_hashes = _clean_monitored_state(
        updated_seen,
        state.content_hashes,
        cfg
    )

    prune_state(updated_seen, max_items=5000)

    updated_state = State(
        seen=updated_seen,
        updated_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        content_hashes=updated_hashes
    )

    save_state(cfg.state_path, updated_state)
    return 0
