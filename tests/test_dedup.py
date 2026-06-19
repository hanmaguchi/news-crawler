from datetime import datetime

from crawler.dedup import dedup
from crawler.models import Article


def _art(title, url, source):
    return Article(
        title=title, press="x", pub_date=datetime(2024, 1, 1), url=url, source=source
    )


def test_same_title_different_url_merges():
    arts = [
        _art("삼성전자, 신제품 발표!", "https://naver.com/a", "네이버"),
        _art("삼성전자 신제품 발표", "https://google.com/b", "구글"),
    ]
    out = dedup(arts)
    assert len(out) == 1
    assert out[0].source == "네이버, 구글"  # 먼저 들어온 것 유지 + 출처 병합


def test_distinct_titles_kept():
    arts = [
        _art("기사 A", "https://x/1", "네이버"),
        _art("기사 B", "https://x/2", "구글"),
    ]
    assert len(dedup(arts)) == 2


def test_same_url_dropped():
    arts = [
        _art("제목 하나", "https://x/1", "네이버"),
        _art("완전 다른 제목", "https://x/1", "구글"),
    ]
    assert len(dedup(arts)) == 1
