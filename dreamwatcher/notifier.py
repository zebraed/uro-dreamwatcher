# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api import WikiClient, WikiApiConfig, WikiAuth
from .discord import WebhookClient, Event
from .rss import fetch_items
from .state import (
    State, load_state, save_state,
    has_page_content_changed, get_content_hash, get_content_diff_preview
)
from .types import SecretStr

HEADER_TEXT = "🆕 更新通知"


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
    # Simple filtering: include all items by default
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

    events = []

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
                if event:
                    page_content = page_data.get("source")
                    diff_preview = get_content_diff_preview(
                        page_name,
                        page_content,
                        state
                    )
                    event_with_diff = Event(
                        title=event.title,
                        url=event.url,
                        date=event.date,
                        diff_preview=diff_preview
                    )
                    events.append(event_with_diff)
                    content_key = f"content_{page_name}"
                    state.content_hashes[content_key] = get_content_hash(
                        page_content
                    )
            except (OSError, ValueError, TimeoutError) as e:
                print(f"Error getting page '{page_name}': {e}")

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

    page_event_title = f'"{page_title}" ページが更新されました。'

    if page_key not in state.seen:
        return Event(
            title=page_event_title,
            url=page_url,
            date=page_date
        )

    stored_date = state.seen.get(page_key)
    if page_date and stored_date != page_date:
        if page_content and has_page_content_changed(
            page_name, page_content, state
        ):
            return Event(
                title=page_event_title,
                url=page_url,
                date=page_date
            )

    return None


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
                  date=item.date)
            for item in new_items
        ])

    page_events = get_specific_pages_updates(cfg, state)
    events_to_send.extend(page_events)

    if not events_to_send:
        return 0

    client = WebhookClient(cfg.discord_webhook_url)
    client.send_events(events_to_send, header=HEADER_TEXT)

    updated_seen = state.seen.copy()
    for event in events_to_send:
        event_date = event.date
        updated_seen[normalize_link(event.url)] = event_date

    prune_state(updated_seen, max_items=5000)

    updated_state = State(
        seen=updated_seen,
        updated_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        content_hashes=state.content_hashes.copy()
    )

    save_state(cfg.state_path, updated_state)
    return 0
