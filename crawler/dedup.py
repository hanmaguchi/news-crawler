import re
from dataclasses import replace

from crawler.models import Article

_NORM_RE = re.compile(r"[^0-9a-z가-힣]+")


def _title_key(title: str) -> str:
    """제목을 소문자화하고 공백/구두점/특수문자를 제거한 정규화 키."""
    return _NORM_RE.sub("", title.lower())


def dedup(articles: list[Article]) -> list[Article]:
    """정규화 제목과 URL 기준으로 중복 기사를 제거한다.

    네이버·구글이 같은 기사를 서로 다른 리다이렉트 URL로 주므로 URL 일치만으로는
    부족하다. 정규화 제목이 같으면 동일 기사로 간주하고 먼저 들어온 것을 남긴다.
    남긴 기사의 source에는 잡힌 엔진들을 모두 표기한다(예: "네이버, 구글").
    """
    seen_title: dict[str, int] = {}
    seen_url: set[str] = set()
    result: list[Article] = []

    for art in articles:
        tkey = _title_key(art.title)
        if tkey and tkey in seen_title:
            idx = seen_title[tkey]
            _merge_source(result, idx, art.source)
            continue
        if art.url and art.url in seen_url:
            continue

        seen_title[tkey] = len(result)
        if art.url:
            seen_url.add(art.url)
        result.append(art)

    return result


def _merge_source(result: list[Article], idx: int, source: str) -> None:
    existing = result[idx]
    sources = [s.strip() for s in existing.source.split(",")]
    if source not in sources:
        result[idx] = replace(existing, source=f"{existing.source}, {source}")
