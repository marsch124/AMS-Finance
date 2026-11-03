#!/usr/bin/env python3
"""Monthly net-worth series from the budget workbook, stdlib only (no openpyxl
needed on /usr/bin/python3 — same approach as workbook_status.py).

NOTHING HERE IS FIXED TO A COLUMN LETTER. The block is found the same way
send_wealth.py finds it, by the words in the header row:

  * the header row is the row near the top carrying the most account names;
  * the TOTAL column is the header cell that reads "total";
  * the month's date sits in a plain-number column LEFT of the accounts;
  * a row's figure is its TOTAL, or the sum of its own account cells when the
    TOTAL formula has no usable cached result (#N/A before anything is typed).

Why: until 2026-11-02 this read columns AY and AZ, because that is where the
block used to be. He moved it to BK / BL / BN-BS, so this quietly returned the
year 1905, and the hub's "workbook ..." cross-check under the wealth total
silently stopped appearing — a safety net doing nothing at all. Finding the
block by name means he can rearrange the spreadsheet whenever he likes.

A value of 0 or a blank means the month has not been entered yet -> null.
Output: {"series": [{"month": "2026-01", "value": 1234567}, ...]}
"""
import difflib
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parent
CONFIG = json.loads((APP / "config.json").read_text())
WORKBOOK = Path(os.environ.get("AMS_WORKBOOK_OVERRIDE") or
                (Path(re.sub(r"^~", str(Path.home()), CONFIG["budgetingPath"])) / CONFIG["workbookFile"]))
SHEET = CONFIG.get("budgetSheet", "AMS Main Budget")
# His account columns. Kept here only so the header row can be recognised; the
# hub sends its own names to send_wealth.py, and a name that has been renamed in
# the workbook is still matched by closeness.
ACCOUNTS = CONFIG.get("wealthAccounts") or [
    "ISK", "Snabbspar", "Strivo", "Saab-aktier", "Nordnet", "Avanza",
]

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
HEADER_SEARCH_ROWS = 40          # the header row is somewhere near the top
MATCH_RATIO = 0.82               # how close a header has to read to an account name
FIRST_SERIAL = (date(2000, 1, 1) - date(1899, 12, 30)).days
LAST_SERIAL = (date(2060, 1, 1) - date(1899, 12, 30)).days


def excel_date(serial):
    return date(1899, 12, 30) + timedelta(days=int(serial))


def col_to_num(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def norm(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


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


def shared_strings(z):
    try:
        ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(f"{{{M}}}t")) for si in ss]


def read_cells(sheet, shared):
    """{(row, col): {'v': text-or-number-or-None}} for the whole sheet"""
    cells = {}
    for c in sheet.iter(f"{{{M}}}c"):
        ref = re.match(r"^([A-Z]+)(\d+)$", c.get("r") or "")
        if not ref:
            continue
        v = c.find(f"{{{M}}}v")
        text = None
        if v is not None and v.text is not None:
            if c.get("t") == "s" and v.text.isdigit() and int(v.text) < len(shared):
                text = shared[int(v.text)]
            elif c.get("t") in (None, "n"):      # a plain number, however it is labelled
                try:
                    text = float(v.text)
                except ValueError:
                    text = None
            # t="e" (#N/A) and t="str" (a formula's text) carry nothing we can use
        cells[(int(ref.group(2)), ref.group(1))] = {"v": text}
    return cells


def find_layout(cells):
    """the header row, the account columns, the TOTAL column and the date column"""
    best = (0, None)
    for row in range(1, HEADER_SEARCH_ROWS + 1):
        headers = [c["v"] for (r, _), c in cells.items()
                   if r == row and isinstance(c["v"], str) and c["v"].strip()]
        hit = sum(1 for acc in ACCOUNTS
                  if any(norm(t) == norm(acc) or
                         difflib.SequenceMatcher(None, norm(acc), norm(t)).ratio() >= MATCH_RATIO
                         for t in headers))
        if hit > best[0]:
            best = (hit, row)
    header_row = best[1]
    if not header_row or best[0] < 2:
        return None

    headers = [(col, c["v"]) for (r, col), c in cells.items()
               if r == header_row and isinstance(c["v"], str) and c["v"].strip()]
    by_col = dict(headers)
    acc_cols, used = [], set()
    for acc in ACCOUNTS:
        n = norm(acc)
        scored = sorted(((difflib.SequenceMatcher(None, n, norm(t)).ratio(), col)
                         for col, t in headers if col not in used), reverse=True)
        if scored and (norm(by_col[scored[0][1]]) == n or scored[0][0] >= MATCH_RATIO):
            acc_cols.append(scored[0][1])
            used.add(scored[0][1])
    if not acc_cols:
        return None

    # Grow the block sideways over neighbouring headers that are plainly part of
    # it. A renamed account ("ISK" -> "Swedb ISK") no longer matches by name, and
    # leaving it out quietly understated the whole month: November 2026 read
    # 4,431,000 instead of 7,763,000, the ISK column's 3,332,000 simply missing.
    # Stops at "total", at "done" and at the first gap, so nothing is counted twice.
    def part_of_block(col):
        t = by_col.get(col)
        return bool(t) and norm(t) not in ("total", "done") and col not in used
    num_to_col = {col_to_num(c): c for c in by_col}
    for step in (-1, 1):
        edge = (min if step < 0 else max)(col_to_num(c) for c in acc_cols)
        n = edge + step
        while n in num_to_col and part_of_block(num_to_col[n]):
            acc_cols.append(num_to_col[n])
            used.add(num_to_col[n])
            n += step

    first_acc = min(col_to_num(c) for c in acc_cols)
    total_col = next((col for col, t in headers if norm(t) == "total"), None)

    # the date column: of the plain-number columns left of the accounts, the one
    # with the most cells that decode to the 1st of a month
    score = {}
    for (row, col), c in cells.items():
        if row <= header_row or col_to_num(col) >= first_acc or not isinstance(c["v"], float):
            continue
        if FIRST_SERIAL <= c["v"] <= LAST_SERIAL and excel_date(c["v"]).day == 1:
            score[col] = score.get(col, 0) + 1
    if not score:
        return None
    date_col = max(score, key=lambda c: (score[c], col_to_num(c)))
    return {"header_row": header_row, "date_col": date_col,
            "total_col": total_col, "acc_cols": acc_cols}


def build_series(cells, layout):
    series = []
    for (row, col), c in sorted(cells.items()):
        if col != layout["date_col"] or row <= layout["header_row"]:
            continue
        if not isinstance(c["v"], float) or not (FIRST_SERIAL <= c["v"] <= LAST_SERIAL):
            continue
        d = excel_date(c["v"])
        if d.day != 1:
            continue
        val = None
        tc = cells.get((row, layout["total_col"])) if layout["total_col"] else None
        if tc and isinstance(tc["v"], float):
            val = tc["v"]
        else:
            # TOTAL is a formula with no usable cached result (#N/A until a month
            # is typed) — add that row's own account cells up instead
            nums = [cells[(row, ac)]["v"] for ac in layout["acc_cols"]
                    if (row, ac) in cells and isinstance(cells[(row, ac)]["v"], float)]
            val = sum(nums) if nums else None
        series.append({
            "month": f"{d.year}-{d.month:02d}",
            "value": round(val) if val else None,   # 0/blank = not entered yet
        })

    series.sort(key=lambda p: p["month"])
    # trim the long tail of future never-entered months: keep everything up to
    # the last entered value, plus one trailing open month
    last = max((i for i, p in enumerate(series) if p["value"] is not None), default=-1)
    if last >= 0:
        series = series[:min(len(series), last + 2)]
    return series


def main():
    with zipfile.ZipFile(WORKBOOK) as z:
        sheet = sheet_xml(z)
        shared = shared_strings(z)
    cells = read_cells(sheet, shared)
    layout = find_layout(cells)
    if not layout:
        # Say so out loud rather than returning plausible nonsense. The hub then
        # shows no cross-check at all, which is what an empty series already meant.
        print(json.dumps({"series": [], "error": "no-wealth-block"}))
        return
    print(json.dumps({"series": build_series(cells, layout)}))


if __name__ == "__main__":
    main()
