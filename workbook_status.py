#!/usr/bin/env python3
"""Report which months (Jan-Dec 2026) have actuals written into the budget workbook.

Reads sheet "AMS Main Budget" of the household budget workbook using only the
standard library (zipfile + XML). A month counts as "written" when at least
half of the 16 category rows carry a numeric value in that month's column
(J-U = Jan-Dec, per Skills/Finance/_config.md cell map).

Prints JSON: {"months": {"2026-01": false, ...}, "error": null}
"""
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

# Personal paths come from config.json next to this script (never committed).
_CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))
WORKBOOK = os.path.join(os.path.expanduser(_CFG["budgetingPath"]), _CFG["workbookFile"])
SHEET_NAME = _CFG.get("budgetSheet", "AMS Main Budget")
# Category rows per _config.md v1.4 (never the formula/group rows)
CATEGORY_ROWS = [16, 25, 32, 40, 47, 56, 58, 61, 66, 70, 83, 87, 92, 98, 102, 113]
MONTH_COLS = ["J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"]

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def sheet_path(zf):
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rid = None
    for sh in wb.find("m:sheets", NS):
        if sh.get("name") == SHEET_NAME:
            rid = sh.get("{%s}id" % NS["r"])
    if rid is None:
        raise KeyError("sheet '%s' not found" % SHEET_NAME)
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels:
        if rel.get("Id") == rid:
            target = rel.get("Target").lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise KeyError("relationship %s not found" % rid)


def main():
    try:
        with zipfile.ZipFile(WORKBOOK) as zf:
            root = ET.fromstring(zf.read(sheet_path(zf)))
            wanted = {"%s%d" % (c, r) for r in CATEGORY_ROWS for c in MONTH_COLS}
            values = {}
            for cell in root.iter("{%s}c" % NS["m"]):
                ref = cell.get("r")
                if ref in wanted and cell.get("t") not in ("s", "str", "inlineStr"):
                    v = cell.find("m:v", NS)
                    if v is not None and v.text is not None:
                        try:
                            values[ref] = float(v.text)
                        except ValueError:
                            pass
            months = {}
            for i, col in enumerate(MONTH_COLS):
                filled = sum(1 for r in CATEGORY_ROWS if "%s%d" % (col, r) in values)
                months["2026-%02d" % (i + 1)] = filled >= len(CATEGORY_ROWS) // 2
            print(json.dumps({"months": months, "error": None}))
    except Exception as e:
        print(json.dumps({"months": {}, "error": "%s: %s" % (type(e).__name__, e)}))
        sys.exit(0)


if __name__ == "__main__":
    main()
