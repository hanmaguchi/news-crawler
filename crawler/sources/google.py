from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

import feedparser

from crawler.models import Article
from crawler.sources.base import NewsSource

_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


class GoogleNewsSource(NewsSource):
    name = "구글"

    def search(self, keyword: str, start: date, end: date) -> list[Article]:
        # 구글 News 검색의 after/before 연산자로 기간을 지정.
        # before는 미포함이라 end + 1일로 보정.
        query = f"{keyword} after:{start.isoformat()} before:{(end + timedelta(days=1)).isoformat()}"
        feed = feedparser.parse(_RSS_URL.format(query=quote_plus(query)))

        articles: list[Article] = []
        for entry in feed.entries:
            pub = _parse_published(entry)
            if pub is not None and not (start <= pub.date() <= end):
                continue
            press = getattr(getattr(entry, "source", None), "title", "") or "알 수 없음"
            # 구글 뉴스 제목은 끝에 " - 매체명"이 붙음 → 매체명 열과 중복이라 제거
            title = entry.title
            if press != "알 수 없음" and title.endswith(f" - {press}"):
                title = title[: -len(f" - {press}")]
            articles.append(
                Article(
                    title=title,
                    press=press,
                    pub_date=pub or datetime.min,
                    url=entry.link,  # news.google.com 리다이렉트 URL (클릭 시 정상 이동)
                    source=self.name,
                )
            )
        return articles


def _parse_published(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None)
    if parsed is None:
        return None
    return datetime(*parsed[:6])
