# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv

from .notifier import Config, run
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

    rss_url = os.environ.get("WIKIWIKI_RSS_URL", "").strip()
    wiki_id = os.environ.get("WIKIWIKI_ID", "").strip()
    api_key_id = SecretStr(os.environ.get("WIKIWIKI_API_KEY_ID", "").strip())
    api_secret = SecretStr(os.environ.get("WIKIWIKI_API_SECRET", "").strip())
    webhook = SecretStr(os.environ.get("DISCORD_WEBHOOK_URL", "").strip())
    state_path = os.environ.get("STATE_PATH", "state.json").strip()
    page_names_str = os.environ.get("WIKIWIKI_PAGE_NAMES", "").strip()

    if not wiki_id:
        print("Error: WIKIWIKI_ID is not set")
        return 2
    if not api_key_id:
        print("Error: WIKIWIKI_API_KEY_ID is not set")
        return 2
    if not api_secret:
        print("Error: WIKIWIKI_API_SECRET is not set")
        return 2
    if not webhook:
        print("Error: DISCORD_WEBHOOK_URL is not set")
        return 2

    # Parse page names from comma-separated string
    page_names = [
        name.strip() for name in page_names_str.split(",")
        if name.strip()
    ]

    cfg = Config(
        source="api",
        wiki_id=wiki_id,
        api_key_id=api_key_id,
        api_secret=api_secret,
        discord_webhook_url=webhook,
        state_path=Path(state_path),
        rss_url=rss_url,
        page_names=page_names)

    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
