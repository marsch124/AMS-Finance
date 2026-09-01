#!/usr/bin/env python3
"""Monthly net-worth series from the budget workbook, stdlib only (no openpyxl
needed on /usr/bin/python3 — same approach as workbook_status.py).

The net-worth block on the budget sheet: dates in column AY, values in AZ
(rows 10-165; from mid-2026 AZ is =SUM(BB:BF) over the five account columns).
A value of 0 or a blank means the month has not been entered yet -> null.
Output: {"series": [{"month": "2026-01", "value": 1234567}, ...]}
"""
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parent
CONFIG = json.loads((APP / "config.json").read_text())
WORKBOOK = Path(re.sub(r"^~", str(Path.home()), CONFIG["budgetingPath"])) / CONFIG["workbookFile"]
SHEET = CONFIG.get("budgetSheet", "AMS Main Budget")

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
FIRST_ROW, LAST_ROW = 10, 165


def excel_date(serial):
    return date(1899, 12, 30) + timedelta(days=int(serial))


def sheet_xml(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = None
    for s in wb.find(f"{{{M}}}sheets"):
        if s.get("name") == SHEET:
            rid = s.get(REL_ID)
    target = None
    for r in rels:
        if r.get("Id") == rid:
            target = r.get("Target")
    if not target:
        raise RuntimeError("sheet not found: " + SHEET)
    return ET.fromstring(z.read("xl/" + target.replace("xl/", "").lstrip("/")))


def main():
    with zipfile.ZipFile(WORKBOOK) as z:
        sheet = sheet_xml(z)
    want = re.compile(r"^(AY|AZ)(\d+)$")
    dates, values = {}, {}
    for c in sheet.iter(f"{{{M}}}c"):
        ref = want.match(c.get("r") or "")
        if not ref:
            continue
        row = int(ref.group(2))
        if row < FIRST_ROW or row > LAST_ROW:
            continue
        v = c.find(f"{{{M}}}v")
        if v is None or v.text is None:
            continue
        try:
            num = float(v.text)
        except ValueError:
            continue
        if ref.group(1) == "AY":
            dates[row] = num
        else:
            values[row] = num

    series = []
    for row in sorted(dates):
        d = excel_date(dates[row])
        val = values.get(row)
        series.append({
            "month": f"{d.year}-{d.month:02d}",
            "value": round(val) if val else None,  # 0/blank = not entered yet
        })

    # trim the long tail of future never-entered months: keep everything up to
    # the last entered value, plus one trailing open month
    last = max((i for i, p in enumerate(series) if p["value"] is not None), default=-1)
    if last >= 0:
        series = series[:min(len(series), last + 2)]
    print(json.dumps({"series": series}))


if __name__ == "__main__":
    main()
