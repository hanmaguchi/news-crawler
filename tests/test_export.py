from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook

from crawler.export import to_excel
from crawler.models import Article


def test_link_cell_has_hyperlink_and_tooltip():
    art = Article(
        title="테스트 기사",
        press="연합뉴스",
        pub_date=datetime(2024, 5, 1, 9, 30),
        url="https://example.com/news/1",
        source="네이버",
    )
    wb = load_workbook(BytesIO(to_excel([art])))
    ws = wb.active

    # 컬럼 순서: 제목(1) 언론사(2) 배포일자(3) 출처(4) 감성(5) 링크(6)
    link_cell = ws.cell(row=2, column=6)
    assert link_cell.value == "기사보기"  # 셀에는 실제 URL 미노출
    assert link_cell.hyperlink.target == "https://example.com/news/1"
    assert link_cell.hyperlink.tooltip == "https://example.com/news/1"


def test_headers():
    wb = load_workbook(BytesIO(to_excel([])))
    ws = wb.active
    assert [c.value for c in ws[1]] == ["제목", "언론사", "배포일자", "출처", "감성", "링크"]


def test_sentiment_column_filled():
    art = Article(
        title="삼성전자 주가 급등 신고가 달성",
        press="한국경제",
        pub_date=datetime(2024, 5, 1),
        url="https://example.com/2",
        source="구글",
    )
    wb = load_workbook(BytesIO(to_excel([art])))
    ws = wb.active
    sentiment = ws.cell(row=2, column=5).value
    assert sentiment in ("긍정", "부정", "중립")
    assert sentiment == "긍정"  # 급등·신고가·달성 → 긍정
