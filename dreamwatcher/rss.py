# -*- coding: utf-8 -*-
"""Not Implemented yet."""
from dataclasses import dataclass
from typing import List, Optional

import feedparser

@dataclass(frozen=True)
class Item:
    title: str
    link: str
    date: Optional[str] = None

def fetch_items(url: str) -> List[Item]:
    feed = feedparser.parse(url)
    return [Item(title=entry.title, link=entry.link, date=entry.published) for entry in feed.entries]