from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from crawler.models import Article
from crawler.sentiment import classify

_HEADERS = ["순번", "배포일시", "제목", "링크", "감성", "출처"]
_WIDTHS = [6, 18, 60, 14, 8, 14]
_LINK_FONT = Font(color="0563C1", underline="single")

_FILL = {
    "긍정": PatternFill(fill_type="solid", fgColor="C6EFCE"),
    "부정": PatternFill(fill_type="solid", fgColor="FFC7CE"),
    "중립": None,
}


def to_excel(articles: list[Article]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for idx, art in enumerate(articles, start=1):
        sentiment = classify(art.title)
        ws.append([idx, art.pub_date, art.title, "기사보기", sentiment, art.source])
        row = ws.max_row

        ws.cell(row=row, column=2).number_format = "yyyy-mm-dd hh:mm"

        sent_cell = ws.cell(row=row, column=5)
        fill = _FILL.get(sentiment)
        if fill:
            sent_cell.fill = fill

        link_cell = ws.cell(row=row, column=4)
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
