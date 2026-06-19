from datetime import date
from unittest.mock import patch

from crawler.sources.naver import NaverNewsSource

# 최신순(date) 응답을 흉내낸 고정 픽스처
_ITEMS = [
    {
        "title": "<b>오늘</b> 기사",
        "originallink": "https://chosun.com/1",
        "link": "x",
        "pubDate": "Wed, 15 May 2024 10:00:00 +0900",
    },
    {
        "title": "어제 기사",
        "originallink": "https://unknown-press.kr/2",
        "link": "x",
        "pubDate": "Tue, 14 May 2024 10:00:00 +0900",
    },
    {
        "title": "범위 밖 과거",
        "originallink": "https://x/3",
        "link": "x",
        "pubDate": "Mon, 01 Jan 2024 10:00:00 +0900",
    },
]


class _Resp:
    def __init__(self, items):
        self._items = items

    def raise_for_status(self):
        pass

    def json(self):
        return {"items": self._items}


def test_date_filtering_and_press_mapping():
    src = NaverNewsSource(client_id="id", client_secret="secret")
    with patch("crawler.sources.naver.requests.get") as mock_get:
        # 첫 페이지에 픽스처, 이후 페이지는 빈 결과
        mock_get.side_effect = [_Resp(_ITEMS), _Resp([])]
        out = src.search("키워드", date(2024, 5, 14), date(2024, 5, 15))

    assert [a.title for a in out] == [
        "오늘 기사",
        "어제 기사",
    ]  # 범위 밖 과거 제외, 태그 제거
    assert out[0].press == "조선일보"  # 도메인 매핑
    assert out[1].press == "unknown-press.kr"  # 폴백: 호스트명


def test_missing_key_raises():
    src = NaverNewsSource(client_id="", client_secret="")
    try:
        src.search("x", date(2024, 1, 1), date(2024, 1, 2))
        assert False, "should raise"
    except RuntimeError:
        pass
