# 뉴스기사 크롤러

검색어와 기간을 입력하면 네이버·구글(및 추가한 RSS 소스)에서 뉴스 기사를
수집해 **제목 / 언론사 / 배포일자 / 출처 / 링크**를 표로 보여주고 엑셀로
내려받는 Streamlit 앱.

## 기능
- 검색어 입력, 기간(시작·종료일) 설정
- 기본 출처: 네이버(공식 검색 API), 구글(News RSS) — 체크박스로 선택
- 커스텀 RSS 피드 URL 추가로 다른 수집처 확장
- 네이버·구글 간 중복 기사 자동 제거(정규화 제목 기준)
- 엑셀(.xlsx) 출력 — 링크 셀은 "기사보기"만 표시되고 마우스를 올리면 실제
  URL이 툴팁으로 보임

## 설치 / 실행
```bash
uv sync
cp .env.example .env   # 네이버 키 입력 (없으면 구글만으로도 동작)
uv run streamlit run app.py
```

### 네이버 API 키
https://developers.naver.com/apps 에서 애플리케이션 등록 후 "검색" API를
추가하면 Client ID/Secret을 발급받을 수 있다. `.env`에 입력한다.
키가 없으면 네이버 출처는 비활성화되고 구글만으로 동작한다.

## 새 검색엔진/수집처 추가
`crawler/sources/base.py`의 `NewsSource`를 구현하면 된다:
```python
class MySource(NewsSource):
    name = "내소스"
    def search(self, keyword, start, end) -> list[Article]: ...
```
`crawler/sources/__init__.py`에서 export하고 `app.py`의 출처 목록에 추가한다.
RSS 기반 소스는 `RssSource(name, url)`로 코드 수정 없이 UI에서 바로 추가 가능.

## 테스트
```bash
uv run pytest
```

## 알려진 제약
- 네이버 검색 API는 날짜 범위 파라미터가 없어 최신순으로 받아 기간을 필터링
  한다(최대 ~1000건). 매체명은 API가 직접 주지 않아 도메인으로 추정한다.
- 구글 News RSS의 링크는 `news.google.com` 리다이렉트 URL이다(클릭하면 정상
  이동). 최종 언론사 URL 자동 해석은 포함하지 않는다.
