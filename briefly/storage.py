"""Portable preferences and a small local reading list."""

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from .news import Article, canonical_url, parse_date, safe_article_url, PUBLISHERS, clean_text


class Store:
    def __init__(self, directory: Path | None = None):
        directory = directory or Path(__file__).resolve().parents[1] / ".briefly"
        directory.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(directory / "preferences.ini"), QSettings.Format.IniFormat)

    def topics(self) -> list[str]:
        value = self.settings.value("topics", "[]")
        try:
            result = json.loads(value)
            return result if isinstance(result, list) and len(result) == 3 and all(isinstance(x, str) for x in result) else []
        except (ValueError, TypeError):
            return []

    def save_topics(self, topics: list[str]):
        self.settings.setValue("topics", json.dumps(topics))
        self.settings.sync()

    def bookmarks(self) -> dict[str, Article]:
        try:
            data = json.loads(self.settings.value("bookmarks", "[]"))
            if not isinstance(data, list):
                return {}
            result = {}
            for item in data:
                if not isinstance(item, dict):
                    continue
                via_google = item.get("via_google") is True
                url = item.get("url", "")
                if not isinstance(url, str) or not safe_article_url(url, via_google) or item.get("publisher") not in PUBLISHERS.values():
                    continue
                article = Article(clean_text(item.get("title")), url, item["publisher"],
                                  clean_text(item.get("description")), parse_date(item.get("published")), via_google)
                if article.title:
                    result[canonical_url(url)] = article
            return result
        except (ValueError, TypeError, AttributeError):
            return {}

    def save_bookmarks(self, bookmarks: dict[str, Article]):
        payload = [{"title": a.title, "url": a.url, "publisher": a.publisher,
                    "description": a.description, "published": a.published.isoformat() if a.published else None,
                    "via_google": a.via_google} for a in bookmarks.values()]
        self.settings.setValue("bookmarks", json.dumps(payload))
        self.settings.sync()
