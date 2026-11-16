# -*- coding: utf-8 -*-
"""
导出模块
========
把留言导出成 Excel（.xlsx），用的是 openpyxl。
客户提「能不能导出表格」的时候，就是这个功能。
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


HEADERS = ["编号", "留言人", "账号", "内容", "时间"]
WIDTHS = [8, 14, 18, 60, 20]


def messages_to_xlsx(rows) -> BytesIO:
    """rows: db.all_messages_for_export() 的返回值。返回 BytesIO，可直接当文件发。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "留言记录"

    # 表头
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F6FED")
    for col, title in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = WIDTHS[col - 1]

    # 数据
    for i, r in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=r["id"]).alignment = Alignment(horizontal="center")
        ws.cell(row=i, column=2, value=r["author_name"])
        ws.cell(row=i, column=3, value=r["owner"] or "（已注销）")
        ws.cell(row=i, column=4, value=r["content"]).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
        ws.cell(row=i, column=5, value=r["created_at"])

    ws.freeze_panes = "A2"  # 冻结表头，滚动时不跑掉
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{len(rows) + 1}"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
