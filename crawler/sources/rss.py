from datetime import date, datetime

import feedparser

from crawler.models import Article
from crawler.sources.base import NewsSource


class RssSource(NewsSource):
    """임의의 RSS 피드를 수집하는 범용 소스. UI에서 사용자가 URL로 추가할 수 있다.

    대부분의 RSS는 검색어/기간 파라미터를 지원하지 않으므로, 피드를 받아온 뒤
    제목·요약에 keyword가 포함되고 발행일이 기간 내인 항목만 남긴다.
    """

    def __init__(self, name: str, feed_url: str):
        self.name = name
        self.feed_url = feed_url

    def search(self, keyword: str, start: date, end: date) -> list[Article]:
        feed = feedparser.parse(self.feed_url)
        kw = keyword.lower()
        articles: list[Article] = []
        for entry in feed.entries:
            haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
            if kw and kw not in haystack:
                continue
            pub = _parse_published(entry)
            if pub is not None and not (start <= pub.date() <= end):
                continue
            press = getattr(getattr(entry, "source", None), "title", "") or self.name
            articles.append(
                Article(
                    title=entry.get("title", ""),
                    press=press,
                    pub_date=pub or datetime.min,
                    url=entry.get("link", ""),
                    source=self.name,
                )
            )
        return articles


def _parse_published(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6])
