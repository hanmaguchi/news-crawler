"""키워드 즐겨찾기 및 RSS 즐겨찾기 영구 저장 (~/.news-crawler/)."""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path.home() / ".news-crawler"
_KW_PATH = _DIR / "keyword_favorites.json"
_RSS_PATH = _DIR / "rss_favorites.json"

RSS_PRESETS: list[dict[str, str]] = [
    {"name": "연합뉴스", "url": "https://www.yonhapnews.co.kr/RSS/headline.xml"},
    {"name": "한겨레", "url": "https://www.hani.co.kr/rss/"},
    {"name": "경향신문", "url": "https://www.khan.co.kr/rss/rssdata/kh_news.xml"},
    {"name": "한국경제", "url": "https://www.hankyung.com/feed/all-news"},
    {"name": "ZDNet Korea", "url": "https://zdnet.co.kr/rss.asp"},
]


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, data) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_kw_favorites() -> list[str]:
    return _read(_KW_PATH, [])


def save_kw_favorites(items: list[str]) -> None:
    _write(_KW_PATH, items)


def load_rss_favorites() -> list[dict[str, str]]:
    return _read(_RSS_PATH, [])


def save_rss_favorites(items: list[dict[str, str]]) -> None:
    _write(_RSS_PATH, items)
