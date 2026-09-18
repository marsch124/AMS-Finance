#!/usr/bin/env python3
"""Send one month's wealth figures from AMS Main Hub into the budget workbook.

Reads a JSON request on stdin:
    {"month": "2026-09", "accounts": [{"name": "ISK", "kr": 3327000}, ...], "dryRun": true}
and prints a JSON answer on stdout.

It is SURGICAL on purpose. The workbook has charts, drawings, styles and Sam's
formulas; the usual libraries for Excel files quietly drop charts when they save.
So this touches only:
  * the account cells of that month's row (created if they do not exist yet,
    borrowing the number format of the cell above),
  * the cached result of that row's TOTAL, when it is a plain SUM over the row
    (so anything reading the file before Excel next opens it sees the right total),
  * one attribute in workbook.xml asking Excel to recalculate on open.
Every other entry in the .xlsx is copied through byte for byte.

Each time it runs it finds the columns afresh: it reads the header row and matches
every account to a column BY NAME, forgiving capitals, spaces, hyphens and small
typos. If it cannot be sure of a column it writes nothing and says which.

Before a real write it keeps a dated copy next to the workbook (the same
"… BU yyyy-mm-dd-hhmm.xlsx" pattern already used there), refuses while Excel has
the file open, reads the written cells back afterwards, and puts the copy back if
anything does not check out. stdlib only, like wealth_series.py.
"""
import datetime
import difflib
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent
CONFIG = json.loads((APP / "config.json").read_text())
WORKBOOK = Path(os.environ.get("AMS_WORKBOOK_OVERRIDE") or
                (Path(re.sub(r"^~", str(Path.home()), CONFIG["budgetingPath"])) / CONFIG["workbookFile"]))
SHEET = CONFIG.get("budgetSheet", "AMS Main Budget")
HEADER_SEARCH_ROWS = 40          # the header row is somewhere near the top
MATCH_RATIO = 0.8                # how alike two names must be to count as a typo


def answer(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def col_to_num(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def num_to_col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def norm(name):
    """compare names without caring about capitals, accents, spaces or hyphens"""
    s = unicodedata.normalize("NFKD", str(name or "")).lower()
    return "".join(ch for ch in s if ch.isalnum())


def excel_serial(y, m, d=1):
    return (datetime.date(y, m, d) - datetime.date(1899, 12, 30)).days


# ---------- reading the workbook ----------

CELL_RE = re.compile(r"<c\b[^>]*?(?:/>|>.*?</c>)", re.S)


def cell_ref(cell_xml):
    m = re.match(r'<c\b[^>]*?\br="([A-Z]+)(\d+)"', cell_xml)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def cell_attr(cell_xml, name):
    head = re.match(r"<c\b[^>]*?(?=/?>)", cell_xml).group(0)
    m = re.search(r'\b%s="([^"]*)"' % name, head)
    return m.group(1) if m else None


def cell_value(cell_xml, shared):
    """the cell's value as the file stores it: text, number, or None"""
    t = cell_attr(cell_xml, "t")
    v = re.search(r"<v>(.*?)</v>", cell_xml, re.S)
    if t == "s" and v:
        try:
            return shared[int(v.group(1))]
        except (ValueError, IndexError):
            return None
    if t == "inlineStr":
        return "".join(re.findall(r"<t[^>]*>(.*?)</t>", cell_xml, re.S))
    if t in ("str", "e", "b"):
        return v.group(1) if v else None
    if v:
        try:
            return float(v.group(1))
        except ValueError:
            return None
    return None


def read_shared(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    xml = z.read("xl/sharedStrings.xml").decode("utf-8")
    out = []
    for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
        out.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))
    return out


def sheet_path(z):
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid = None
    for m in re.finditer(r"<sheet\b[^>]*/>", wb):
        tag = m.group(0)
        nm = re.search(r'\bname="([^"]*)"', tag)
        if nm and nm.group(1).replace("&amp;", "&").replace("&quot;", '"') == SHEET:
            rid = re.search(r'\br:id="([^"]*)"', tag).group(1)
    if not rid:
        answer({"ok": False, "error": "no-sheet", "sheet": SHEET})
    for m in re.finditer(r"<Relationship\b[^>]*/>", rels):
        tag = m.group(0)
        if re.search(r'\bId="%s"' % re.escape(rid), tag):
            target = re.search(r'\bTarget="([^"]*)"', tag).group(1)
            return "xl/" + target.lstrip("/").replace("xl/", "", 1)
    answer({"ok": False, "error": "no-sheet", "sheet": SHEET})


def rows_of(sheet_xml):
    """{row number: row xml}"""
    rows = {}
    for m in re.finditer(r'<row\b[^>]*?\br="(\d+)"[^>]*?(?:/>|>.*?</row>)', sheet_xml, re.S):
        rows[int(m.group(1))] = m.group(0)
    return rows


# ---------- finding the columns and the month's row ----------

def match_columns(accounts, header_cells):
    """map each account name to one header column; never guess between two"""
    headers = [(col, str(text)) for col, text in header_cells if isinstance(text, str) and text.strip()]
    used, mapping, unmatched = set(), {}, []
    for acc in accounts:
        n = norm(acc["name"])
        exact = [col for col, text in headers if norm(text) == n and col not in used]
        if len(exact) == 1:
            mapping[acc["name"]] = exact[0]
            used.add(exact[0])
            continue
        scored = sorted(((difflib.SequenceMatcher(None, n, norm(text)).ratio(), col, text)
                         for col, text in headers if col not in used), reverse=True)
        if scored and scored[0][0] >= MATCH_RATIO and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
            mapping[acc["name"]] = scored[0][1]
            used.add(scored[0][1])
        else:
            unmatched.append(acc["name"])
    return mapping, unmatched


def find_layout(sheet_xml, shared, accounts, month):
    rows = rows_of(sheet_xml)
    # the header row: the one near the top whose texts match the most accounts
    best = (0, None, None)
    for r in range(1, HEADER_SEARCH_ROWS + 1):
        if r not in rows:
            continue
        cells = [(cell_ref(c)[0], cell_value(c, shared)) for c in CELL_RE.findall(rows[r])]
        mapping, _ = match_columns(accounts, cells)
        if len(mapping) > best[0]:
            best = (len(mapping), r, cells)
    if not best[1]:
        return {"error": "no-header"}
    header_row, header_cells = best[1], best[2]
    mapping, unmatched = match_columns(accounts, header_cells)
    total_col = next((col for col, text in header_cells if isinstance(text, str) and norm(text) == "total"), None)

    # the month's row: the date cell holding the 1st of that month, left of the accounts
    y, m = (int(x) for x in month.split("-"))
    target = excel_serial(y, m, 1)
    first_acc = min((col_to_num(c) for c in mapping.values()), default=10 ** 6)
    month_row = None
    for r in sorted(rows):
        if r <= header_row:
            continue
        for c in CELL_RE.findall(rows[r]):
            col, _ = cell_ref(c)
            if col and col_to_num(col) < first_acc and cell_attr(c, "t") is None:
                v = cell_value(c, shared)
                if isinstance(v, float) and int(v) == target:
                    month_row = r
                    break
        if month_row:
            break
    return {"header_row": header_row, "mapping": mapping, "unmatched": unmatched,
            "total_col": total_col, "month_row": month_row, "rows": rows}


# ---------- writing ----------

def style_from_above(rows, col, row):
    for r in range(row - 1, max(0, row - 40), -1):
        if r in rows:
            for c in CELL_RE.findall(rows[r]):
                if cell_ref(c)[0] == col:
                    s = cell_attr(c, "s")
                    if s is not None and cell_value(c, []) is not None:
                        return s
    return None


def set_cells(row_xml, row, writes, rows):
    """write {col: number} into this row's xml; formulas are never overwritten"""
    head_m = re.match(r"<row\b[^>]*?(/?)>", row_xml)
    head, selfclose = head_m.group(0), head_m.group(1) == "/"
    body = "" if selfclose else row_xml[len(head):-len("</row>")]
    cells = CELL_RE.findall(body)
    by_col = {cell_ref(c)[0]: c for c in cells}
    skipped = []
    for col, kr in writes.items():
        ref = f"{col}{row}"
        old = by_col.get(col)
        if old and "<f>" in old or (old and "<f " in old):
            skipped.append(ref)
            continue
        s = (cell_attr(old, "s") if old else None) or style_from_above(rows, col, row)
        by_col[col] = f'<c r="{ref}"' + (f' s="{s}"' if s else "") + f"><v>{int(round(kr))}</v></c>"
    # cells must stay in column order
    new_body = "".join(by_col[c] for c in sorted(by_col, key=col_to_num))
    # anything in the row that is not a cell (rare) is kept after the cells
    rest = CELL_RE.sub("", body)
    new_head = head[:-2] + ">" if selfclose else head
    # widen spans if a new cell falls outside them
    sp = re.search(r'\bspans="(\d+):(\d+)"', new_head)
    if sp:
        lo, hi = int(sp.group(1)), int(sp.group(2))
        need = max(col_to_num(c) for c in by_col)
        if need > hi:
            new_head = new_head.replace(sp.group(0), f'spans="{lo}:{need}"')
    return new_head + new_body + rest + "</row>", skipped


def refresh_total(row_xml, row, total_col):
    """if the TOTAL is a plain SUM over this row, store its up-to-date result"""
    cells = CELL_RE.findall(row_xml)
    tot = next((c for c in cells if cell_ref(c)[0] == total_col), None)
    if not tot:
        return row_xml, None
    f = re.search(r"<f>\s*SUM\(\s*([A-Z]+)%d\s*:\s*([A-Z]+)%d\s*\)\s*</f>" % (row, row), tot)
    if not f:
        return row_xml, None
    lo, hi = col_to_num(f.group(1)), col_to_num(f.group(2))
    total = 0.0
    for c in cells:
        col, _ = cell_ref(c)
        if col and lo <= col_to_num(col) <= hi and cell_attr(c, "t") is None and "<f" not in c:
            v = re.search(r"<v>(.*?)</v>", c)
            if v:
                try:
                    total += float(v.group(1))
                except ValueError:
                    pass
    total = int(round(total))
    if re.search(r"<v>.*?</v>", tot):
        new_tot = re.sub(r"<v>.*?</v>", f"<v>{total}</v>", tot, count=1)
    else:
        new_tot = tot.replace("</c>", f"<v>{total}</v></c>")
    return row_xml.replace(tot, new_tot, 1), total


def recalc_on_open(wb_xml):
    m = re.search(r"<calcPr\b[^>]*?/>", wb_xml)
    if m:
        tag = m.group(0)
        if "fullCalcOnLoad" in tag:
            return wb_xml
        return wb_xml.replace(tag, tag[:-2].rstrip() + ' fullCalcOnLoad="1"/>', 1)
    return wb_xml  # no calcPr at all: leave the file's structure alone


def excel_has_it_open(path):
    folder, name = path.parent, path.name
    for f in os.listdir(folder):
        if f.startswith("~$") and (f[2:] == name or f[2:] == name[2:]):
            return True
    return False


def main():
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except ValueError as e:
        answer({"ok": False, "error": "bad-request", "detail": str(e)})
    month = str(req.get("month", ""))
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        answer({"ok": False, "error": "bad-request", "detail": "month"})
    accounts = [a for a in (req.get("accounts") or [])
                if isinstance(a, dict) and a.get("name") and isinstance(a.get("kr"), (int, float))]
    if not accounts:
        answer({"ok": False, "error": "nothing-to-send"})
    dry = bool(req.get("dryRun"))

    if not WORKBOOK.exists():
        answer({"ok": False, "error": "no-workbook"})
    if not dry and excel_has_it_open(WORKBOOK):
        answer({"ok": False, "error": "open-in-excel"})

    with zipfile.ZipFile(WORKBOOK) as z:
        shared = read_shared(z)
        spath = sheet_path(z)
        sheet_xml = z.read(spath).decode("utf-8")
        wb_xml = z.read("xl/workbook.xml").decode("utf-8")

    lay = find_layout(sheet_xml, shared, accounts, month)
    if lay.get("error"):
        answer({"ok": False, "error": lay["error"]})
    if lay["unmatched"]:
        answer({"ok": False, "error": "unmatched", "unmatched": lay["unmatched"],
                "headerRow": lay["header_row"]})
    if not lay["month_row"]:
        answer({"ok": False, "error": "no-month-row", "month": month})

    row = lay["month_row"]
    rows = lay["rows"]
    writes = {lay["mapping"][a["name"]]: a["kr"] for a in accounts}
    # what is there now, for the preview
    current = {}
    for c in CELL_RE.findall(rows[row]):
        col, _ = cell_ref(c)
        if col in writes:
            current[col] = cell_value(c, shared)
    plan = [{"name": a["name"], "col": lay["mapping"][a["name"]], "cell": f'{lay["mapping"][a["name"]]}{row}',
             "kr": int(round(a["kr"])), "now": current.get(lay["mapping"][a["name"]])} for a in accounts]
    if dry:
        answer({"ok": True, "dryRun": True, "month": month, "row": row, "headerRow": lay["header_row"],
                "plan": plan, "workbook": WORKBOOK.name})

    # ---- the real write ----
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    backup = WORKBOOK.with_name(f"{WORKBOOK.stem} BU {stamp}{WORKBOOK.suffix}")
    shutil.copy2(WORKBOOK, backup)

    new_row, skipped = set_cells(rows[row], row, writes, rows)
    total = None
    if lay["total_col"]:
        new_row, total = refresh_total(new_row, row, lay["total_col"])
    new_sheet = sheet_xml.replace(rows[row], new_row, 1)
    new_wb = recalc_on_open(wb_xml)

    tmp = WORKBOOK.with_name(WORKBOOK.name + ".sending")
    with zipfile.ZipFile(WORKBOOK) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == spath:
                data = new_sheet.encode("utf-8")
            elif info.filename == "xl/workbook.xml":
                data = new_wb.encode("utf-8")
            zout.writestr(info, data, compress_type=info.compress_type)

    # read it back before it replaces anything
    try:
        with zipfile.ZipFile(tmp) as zt:
            if zt.testzip() is not None:
                raise ValueError("zip check failed")
            back = zt.read(spath).decode("utf-8")
        back_rows = rows_of(back)
        got = {cell_ref(c)[0]: cell_value(c, shared) for c in CELL_RE.findall(back_rows[row])}
        for col, kr in writes.items():
            if f"{col}{row}" in skipped:
                continue
            if got.get(col) != float(int(round(kr))):
                raise ValueError(f"{col}{row} reads back as {got.get(col)}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        answer({"ok": False, "error": "verify-failed", "detail": str(e), "backup": backup.name})

    os.replace(tmp, WORKBOOK)
    answer({"ok": True, "month": month, "row": row, "plan": plan, "skipped": skipped,
            "total": total, "backup": backup.name, "workbook": WORKBOOK.name})


if __name__ == "__main__":
    main()
