import os
import re
from datetime import date
from urllib.parse import urlparse

import requests
from dateutil import parser as dtparser

from crawler.models import Article
from crawler.sources.base import NewsSource

_API_URL = "https://openapi.naver.com/v1/search/news.json"
_TAG_RE = re.compile(r"<[^>]+>")

# 자주 등장하는 언론사 도메인 → 매체명. 없으면 호스트명으로 폴백(추정).
_PRESS_BY_DOMAIN = {
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "yna.co.kr": "연합뉴스",
    "news1.kr": "뉴스1",
    "newsis.com": "뉴시스",
    "sbs.co.kr": "SBS",
    "kbs.co.kr": "KBS",
    "imbc.com": "MBC",
    "ytn.co.kr": "YTN",
    "mt.co.kr": "머니투데이",
    "edaily.co.kr": "이데일리",
    "sedaily.com": "서울경제",
    "seoul.co.kr": "서울신문",
    "munhwa.com": "문화일보",
    "hankookilbo.com": "한국일보",
    "zdnet.co.kr": "ZDNet Korea",
    "etnews.com": "전자신문",
}


def _clean(text: str) -> str:
    text = _TAG_RE.sub("", text)
    return (
        text.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&apos;", "'")
        .replace("&#39;", "'")
        .strip()
    )


def _press_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, name in _PRESS_BY_DOMAIN.items():
        if host.endswith(domain):
            return name
    return host or "알 수 없음"  # 폴백: 호스트명


class NaverNewsSource(NewsSource):
    name = "네이버"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET", "")

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search(self, keyword: str, start: date, end: date) -> list[Article]:
        if not self.configured:
            raise RuntimeError(
                "네이버 API 키가 없습니다. NAVER_CLIENT_ID / NAVER_CLIENT_SECRET를 설정하세요."
            )

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        articles: list[Article] = []
        # 네이버는 날짜 범위 파라미터가 없어 최신순으로 받아 기간을 직접 필터링.
        for start_idx in range(1, 1001, 100):  # start: 1, 101, ... 901 (최대 ~1000건)
            resp = requests.get(
                _API_URL,
                headers=headers,
                params={
                    "query": keyword,
                    "display": 100,
                    "start": start_idx,
                    "sort": "date",
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                break

            stop = False
            for item in items:
                pub = dtparser.parse(item["pubDate"])
                pub_d = pub.date()
                if pub_d > end:
                    continue  # 기간보다 미래 → 건너뜀
                if pub_d < start:
                    stop = True  # 최신순이므로 이후는 모두 과거 → 중단
                    break
                url = item.get("originallink") or item["link"]
                articles.append(
                    Article(
                        title=_clean(item["title"]),
                        press=_press_from_url(url),
                        pub_date=pub.replace(tzinfo=None),
                        url=url,
                        source=self.name,
                    )
                )
            if stop or len(items) < 100:
                break

        return articles
