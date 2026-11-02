#!/usr/bin/env python3
"""Build a tiny .xlsx that looks like his budget sheet, for the tests.

The point is that the tests can put the wealth block ANYWHERE — that is what
broke in real life: the block moved from AY/AZ/BB-BG to BK/BL/BN-BS and the
reader kept looking at the old letters.
"""
import datetime
import zipfile

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def serial(y, m, d=1):
    return (datetime.date(y, m, d) - datetime.date(1899, 12, 30)).days


def col_name(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def col_num(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def build(path, *, date_col="BK", total_col="BL", first_acc="BN", header_row=9,
          accounts=("ISK", "Snabbspar", "Strivo", "Saab-aktier", "Nordnet", "Avanza"),
          months=(("2026-07", 3334000), ("2026-08", 3328000), ("2026-09", 3327000)),
          open_months=("2026-10", "2026-11"), number_type='n', total_formula=True):
    """number_type: 'n' writes t="n" on the date cells (as his workbook does),
    '' leaves the type off (as other spreadsheets do). Both must work."""
    strings, sidx = [], {}

    def s_id(text):
        if text not in sidx:
            sidx[text] = len(strings)
            strings.append(text)
        return sidx[text]

    acc_cols = [col_name(col_num(first_acc) + i) for i in range(len(accounts))]
    rows = {}

    head = [f'<c r="{total_col}{header_row}" t="s"><v>{s_id("TOTAL")}</v></c>']
    for col, name in zip(acc_cols, accounts):
        head.append(f'<c r="{col}{header_row}" t="s"><v>{s_id(name)}</v></c>')
    rows[header_row] = "".join(head)

    t = f' t="{number_type}"' if number_type else ""
    row = header_row + 1
    for month, per_account in months:
        y, m = (int(x) for x in month.split("-"))
        cells = [f'<c r="{date_col}{row}"{t}><v>{serial(y, m)}</v></c>']
        total = per_account * len(accounts)
        if total_formula:
            cells.append(f'<c r="{total_col}{row}"{t}>'
                         f'<f>SUM({acc_cols[0]}{row}:{acc_cols[-1]}{row})</f><v>{total}</v></c>')
        else:
            cells.append(f'<c r="{total_col}{row}"{t}><v>{total}</v></c>')
        for col in acc_cols:
            cells.append(f'<c r="{col}{row}"{t}><v>{per_account}</v></c>')
        rows[row] = "".join(cells)
        row += 1

    for month in open_months:
        y, m = (int(x) for x in month.split("-"))
        # an empty month: a date, and a TOTAL formula whose cached value is #N/A
        rows[row] = (f'<c r="{date_col}{row}"{t}><v>{serial(y, m)}</v></c>'
                     f'<c r="{total_col}{row}" t="e">'
                     f'<f>IF(COUNT({acc_cols[0]}{row}:{acc_cols[-1]}{row})=0,NA(),'
                     f'SUM({acc_cols[0]}{row}:{acc_cols[-1]}{row}))</f><v>#N/A</v></c>')
        row += 1

    body = "".join(f'<row r="{r}">{rows[r]}</row>' for r in sorted(rows))
    sheet = (f'<?xml version="1.0"?><worksheet xmlns="{M}"><sheetData>{body}'
             f'</sheetData></worksheet>')
    sst = (f'<?xml version="1.0"?><sst xmlns="{M}" count="{len(strings)}" '
           f'uniqueCount="{len(strings)}">'
           + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
    wb = (f'<?xml version="1.0"?><workbook xmlns="{M}" '
          f'xmlns:r="{R}"><sheets><sheet name="AMS Main Budget" sheetId="1" '
          f'r:id="rId1"/></sheets></workbook>')
    rels = (f'<?xml version="1.0"?><Relationships '
            f'xmlns="{R}/package/2006/relationships"><Relationship Id="rId1" '
            f'Type="{R}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="xml" '
          'ContentType="application/xml"/></Types>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
    return path
