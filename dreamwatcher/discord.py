# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Iterable, Optional
from datetime import datetime
import requests

from .types import SecretStr


def _format_date(iso_date_str: Optional[str]) -> str:
    if not iso_date_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_date_str)
        return dt.strftime("%Y年%-m月%-d日 %H時%M分")
    except (ValueError, AttributeError):
        return iso_date_str


@dataclass(frozen=True)
class Event:
    title: str
    url: str
    page_name: str
    date: Optional[str] = None
    diff_preview: Optional[str] = None
    is_initial: bool = False


class WebhookClient:
    """
    Webhook client for Discord.

    Attributes:
        webhook_url: The URL of the Discord webhook.
        timeout_sec: The timeout in seconds.
    """
    def __init__(self, webhook_url: SecretStr, timeout_sec: int = 10):
        self._url = webhook_url
        self._timeout = timeout_sec

    def send_events(
        self,
        events: Iterable[Event],
        header: Optional[str] = None
    ) -> list:
        """Send events to Discord as separate messages per page.

        Args:
            events: Iterable of events to send.
            header: Optional header to add to each message.

        Returns:
            list: List of responses from Discord API.
        """
        items = list(events)
        if not items:
            return []

        responses = []

        for item in items:
            msg_parts = []

            if header and item == items[0]:
                msg_parts.append(header)

            msg_parts.append(f"**{item.title}**")

            if item.date and not item.is_initial:
                formatted_date = _format_date(item.date)
                msg_parts.append(f"🕐 {formatted_date}")

            msg_parts.append(f"🔗 <{item.url}>")

            if item.diff_preview and not item.is_initial:
                msg_parts.append(f"📝 {item.diff_preview} ...\n")

            msg_parts.append("━" * 40)

            msg = "\n".join(msg_parts)

            payload = {
                "content": msg,
                "allowed_mentions": {"parse": []},
            }

            resp = requests.post(
                self._url, json=payload, timeout=self._timeout
            )
            resp.raise_for_status()

            # Discord API may return 204 No Content
            try:
                responses.append(resp.json())
            except requests.exceptions.JSONDecodeError:
                responses.append({"status": "ok"})

        return responses
