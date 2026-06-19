from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from crawler.models import Article

_HEADERS = ["제목", "언론사", "배포일자", "출처", "링크"]
_WIDTHS = [60, 16, 20, 14, 14]
_LINK_FONT = Font(color="0563C1", underline="single")


def to_excel(articles: list[Article]) -> bytes:
    """기사 목록을 엑셀(.xlsx) 바이트로 변환.

    링크 열의 셀에는 '기사보기'만 표시되고, 마우스를 올리면 실제 URL이
    툴팁으로 보인다(셀에 실제 주소는 노출되지 않음).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    ws.append(_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for art in articles:
        ws.append(
            [
                art.title,
                art.press,
                art.pub_date,
                art.source,
                "기사보기",
            ]
        )
        row = ws.max_row
        date_cell = ws.cell(row=row, column=3)
        date_cell.number_format = "yyyy-mm-dd hh:mm"

        link_cell = ws.cell(row=row, column=5)
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
