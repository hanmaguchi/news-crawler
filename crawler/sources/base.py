from abc import ABC, abstractmethod
from datetime import date

from crawler.models import Article


class NewsSource(ABC):
    """뉴스 출처의 공통 인터페이스.

    새 검색엔진/수집처를 추가하려면 이 클래스를 구현하고 registry에 등록한다.
    """

    name: str

    @abstractmethod
    def search(self, keyword: str, start: date, end: date) -> list[Article]:
        """keyword로 start~end(포함) 기간의 기사를 수집한다."""
        ...
