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

    link_cell = ws.cell(row=2, column=5)
    assert link_cell.value == "기사보기"  # 셀에는 실제 URL 미노출
    assert link_cell.hyperlink.target == "https://example.com/news/1"
    assert (
        link_cell.hyperlink.tooltip == "https://example.com/news/1"
    )  # 마우스오버 시 표시


def test_headers():
    wb = load_workbook(BytesIO(to_excel([])))
    ws = wb.active
    assert [c.value for c in ws[1]] == ["제목", "언론사", "배포일자", "출처", "링크"]
