from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Article:
    """수집된 뉴스 기사 한 건의 메타데이터."""

    title: str
    press: str  # 언론사/매체명
    pub_date: datetime
    url: str
    source: str  # 수집한 엔진 이름 ("네이버", "구글" 등)
