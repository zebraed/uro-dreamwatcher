# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv

from .watcher import Config, run
from .types import SecretStr


def main():
    """
    Main entry point.
    Load environment variables from .env file and run the notifier.

    Returns:
        int: Exit code.
    """
    # Load environment variables from .env file
    load_dotenv()

    wiki_id = os.environ.get("WIKIWIKI_ID", "").strip()
    wiki_url_base = os.environ.get("WIKIWIKI_URL_BASE", "").strip()
    api_key_id = SecretStr(os.environ.get("WIKIWIKI_API_KEY_ID", "").strip())
    api_secret = SecretStr(os.environ.get("WIKIWIKI_API_SECRET", "").strip())
    rss_urls_str = os.environ.get("WIKIWIKI_RSS_URLS", "").strip()
    webhook_url = SecretStr(os.environ.get("DISCORD_WEBHOOK_URL", "").strip())
    state_path = os.environ.get("STATE_PATH", "state.json").strip()
    snapshots_dir = os.environ.get("SNAPSHOTS_DIR_PATH", ".snapshots").strip()
    page_names_str = os.environ.get("WIKIWIKI_PAGE_NAMES", "").strip()
    monitor_recent_created_str = os.environ.get(
        "WIKIWIKI_MONITOR_RECENT_CREATED", "true"
    ).strip().lower()
    monitor_recent_created = monitor_recent_created_str == "true"
    auto_track_patterns = os.environ.get(
        "WIKIWIKI_AUTO_TRACK_PATTERNS", ""
    ).strip()
    auto_track_patterns = [
        pattern.strip() for pattern in auto_track_patterns.split(",")
        if pattern.strip()
    ]

    if not wiki_id:
        print("Error: WIKIWIKI_ID is not set")
        return 2
    if not wiki_url_base:
        print("Error: WIKIWIKI_URL_BASE is not set")
        return 2
    if not api_key_id:
        print("Error: WIKIWIKI_API_KEY_ID is not set")
        return 2
    if not api_secret:
        print("Error: WIKIWIKI_API_SECRET is not set")
        return 2
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL is not set")
        return 2

    page_names = [
        name.strip() for name in page_names_str.split(",")
        if name.strip()
    ]

    rss_urls = [
        url.strip() for url in rss_urls_str.split(",")
        if url.strip()
    ]

    wiki_url = f"{wiki_url_base.rstrip("/")}/{wiki_id}/"

    cfg = Config(
        wiki_id=wiki_id,
        api_key_id=api_key_id,
        api_secret=api_secret,
        discord_webhook_url=webhook_url,
        state_path=Path(state_path),
        rss_urls=rss_urls,
        page_names=page_names,
        wiki_url=wiki_url,
        snapshots_dir=Path(snapshots_dir),
        monitor_recent_created=monitor_recent_created,
        auto_track_patterns=auto_track_patterns
        )

    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
