from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from crawler.models import Article
from crawler.sentiment import classify

_HEADERS = ["제목", "언론사", "배포일자", "출처", "감성", "링크"]
_WIDTHS = [60, 16, 20, 14, 8, 14]
_LINK_FONT = Font(color="0563C1", underline="single")

_FILL = {
    "긍정": PatternFill(fill_type="solid", fgColor="C6EFCE"),  # 연초록
    "부정": PatternFill(fill_type="solid", fgColor="FFC7CE"),  # 연빨강
    "중립": None,
}


def to_excel(articles: list[Article]) -> bytes:
    """기사 목록을 엑셀(.xlsx) 바이트로 변환.

    링크 열의 셀에는 '기사보기'만 표시되고, 마우스를 올리면 실제 URL이
    툴팁으로 보인다. 감성 열은 긍정(녹색)/부정(빨간) 배경색으로 표시.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for art in articles:
        sentiment = classify(art.title)
        ws.append(
            [
                art.title,
                art.press,
                art.pub_date,
                art.source,
                sentiment,
                "기사보기",
            ]
        )
        row = ws.max_row

        ws.cell(row=row, column=3).number_format = "yyyy-mm-dd hh:mm"

        sent_cell = ws.cell(row=row, column=5)
        fill = _FILL.get(sentiment)
        if fill:
            sent_cell.fill = fill

        link_cell = ws.cell(row=row, column=6)
        if art.url:
            link_cell.hyperlink = Hyperlink(
                ref=link_cell.coordinate, target=art.url, tooltip=art.url
            )
            link_cell.font = _LINK_FONT

    for i, width in enumerate(_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
