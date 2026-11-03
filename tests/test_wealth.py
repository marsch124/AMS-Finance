#!/usr/bin/env python3
"""Tests for the two scripts that read and write the wealth block in the
budget workbook. They run on every push.

What they are here to stop happening again (2026-11-02, both found by hand
before his first real Send to Excel):

  * the block MOVED from AY/AZ/BB-BG to BK/BL/BN-BS, and wealth_series.py
    kept reading the old letters — it reported the year 1905, and the hub's
    "workbook ..." cross-check silently never appeared again;
  * his date cells carry t="n", and send_wealth.py only accepted date cells
    with no type at all, so it could not find the month's row: Send to Excel
    would have failed with "no-month-row" on every press.

Nothing here touches the real workbook: every test builds its own little one.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent
sys.path.insert(0, str(HERE))
from make_workbook import build          # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, APP / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_series(path):
    """run wealth_series.py the way the engine runs it"""
    out = subprocess.run([sys.executable, str(APP / "wealth_series.py")],
                         capture_output=True, text=True, timeout=60,
                         env={**os.environ, "AMS_WORKBOOK_OVERRIDE": str(path)})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def send(path, month, accounts, dry_run=False):
    """run send_wealth.py the way the engine runs it"""
    payload = {"month": month, "dryRun": dry_run,
               "accounts": [{"name": n, "kr": kr} for n, kr in accounts]}
    out = subprocess.run([sys.executable, str(APP / "send_wealth.py")],
                         input=json.dumps(payload), capture_output=True, text=True,
                         timeout=60, env={**os.environ, "AMS_WORKBOOK_OVERRIDE": str(path)})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


ACCOUNTS = [("ISK", 3400000), ("Snabbspar", 250000), ("Strivo", 300000),
            ("Saab-aktier", 400000), ("Nordnet", 500000), ("Avanza", 600000)]
ACC_TOTAL = sum(kr for _, kr in ACCOUNTS)


class TempBook(unittest.TestCase):
    def book(self, **kw):
        d = tempfile.mkdtemp()
        return build(Path(d) / "book.xlsx", **kw)


class ReadingTheSeries(TempBook):
    def test_reads_his_real_layout(self):
        """where the block actually is today: dates BK, TOTAL BL, accounts BN-BS"""
        s = read_series(self.book())["series"]
        self.assertEqual([p["month"] for p in s][:3], ["2026-07", "2026-08", "2026-09"])
        self.assertEqual(s[2]["value"], 3327000 * 6)

    def test_finds_the_block_after_it_moves(self):
        """THE BUG: the same block in different columns must still be found"""
        for date_col, total_col, first_acc in (("AY", "AZ", "BB"),   # where it used to be
                                               ("BK", "BL", "BN"),   # where it is now
                                               ("C", "D", "F")):     # somewhere else entirely
            with self.subTest(date_col=date_col):
                s = read_series(self.book(date_col=date_col, total_col=total_col,
                                          first_acc=first_acc))["series"]
                self.assertEqual(s[2]["month"], "2026-09")
                self.assertEqual(s[2]["value"], 3327000 * 6)

    def test_finds_the_block_after_the_header_row_moves(self):
        s = read_series(self.book(header_row=21))["series"]
        self.assertEqual(s[2]["value"], 3327000 * 6)

    def test_a_month_with_nothing_in_it_is_empty_not_zero(self):
        s = read_series(self.book())["series"]
        self.assertIsNone(s[3]["value"], "an untyped month must be null, not a number")

    def test_a_renamed_account_is_still_counted(self):
        """THE BUG (2026-11-03): he renamed the workbook's "ISK" column to
        "Swedb ISK". Send to Excel wrote all six figures correctly, but the
        series reader only knew the old names, so it left that column out and
        reported November as 4,431,000 instead of 7,763,000 — a wrong number
        shown under his wealth total, with nothing to say it was wrong."""
        renamed = ("Swedb ISK", "Snabbspar", "Strivo", "Saab-aktier",
                   "Nordnet", "Avanza")
        book = self.book(accounts=renamed)
        figures = [(renamed[i], 100000 * (i + 1)) for i in range(len(renamed))]
        self.assertTrue(send(book, "2026-10", figures)["ok"])
        s = read_series(book)["series"]
        oct_ = next(p for p in s if p["month"] == "2026-10")
        self.assertEqual(oct_["value"], sum(kr for _, kr in figures))

    def test_says_so_when_there_is_no_block_at_all(self):
        """rather than returning plausible nonsense, as it did for weeks"""
        d = tempfile.mkdtemp()
        p = Path(d) / "empty.xlsx"
        build(p, accounts=("Nothing", "Like", "An", "Account"))
        got = read_series(p)
        self.assertEqual(got["series"], [])
        self.assertEqual(got.get("error"), "no-wealth-block")

    def test_never_reports_a_date_before_the_spreadsheet_exists(self):
        """the 1905 symptom: a wrong column read as if it held dates"""
        for p in read_series(self.book())["series"]:
            self.assertGreaterEqual(p["month"], "2000-01", "read a nonsense date")


class SendingToExcel(TempBook):
    def test_finds_the_month_row_whichever_way_the_date_is_labelled(self):
        """THE BUG: his date cells say t="n" and were being skipped"""
        for number_type in ("n", ""):
            with self.subTest(t=number_type or "(none)"):
                got = send(self.book(number_type=number_type), "2026-10", ACCOUNTS,
                           dry_run=True)
                self.assertTrue(got.get("ok"), got)
                self.assertEqual(got["headerRow"], 9)
                self.assertEqual(got["row"], 13)          # 2026-10 is the 4th month row

    def test_writes_into_the_right_row_and_only_that_row(self):
        p = self.book()
        before = zipfile.ZipFile(p).read("xl/worksheets/sheet1.xml").decode()
        got = send(p, "2026-11", ACCOUNTS)
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(read_series(p)["series"][-1], {"month": "2026-11",
                                                        "value": ACC_TOTAL})
        # the months he already had are untouched
        s = read_series(p)["series"]
        self.assertEqual(s[2], {"month": "2026-09", "value": 3327000 * 6})
        self.assertIn("<row r=\"9\"", before)

    def test_never_overwrites_a_formula(self):
        """the TOTAL column is a SUM — it must be left alone"""
        p = self.book()
        got = send(p, "2026-11", ACCOUNTS + [("TOTAL", 1)])
        self.assertTrue(got.get("ok"), got)
        xml = zipfile.ZipFile(p).read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("<f>", xml, "the SUM formulas must still be there")

    def test_takes_a_dated_backup_before_writing(self):
        p = self.book()
        got = send(p, "2026-11", ACCOUNTS)
        self.assertTrue(got.get("backup"), "a backup copy must be written first")
        # it reports the name only; the copy lands beside the workbook
        beside = Path(p).with_name(got["backup"])
        self.assertTrue(beside.exists(), f"no backup at {beside}")
        self.assertIn(" BU ", got["backup"], "the copy must be dated and named BU")

    def test_a_dry_run_changes_nothing(self):
        p = self.book()
        before = Path(p).read_bytes()
        got = send(p, "2026-11", ACCOUNTS, dry_run=True)
        self.assertTrue(got.get("dryRun"))
        self.assertEqual(before, Path(p).read_bytes(), "a dry run must not touch the file")

    def test_refuses_a_month_that_is_not_in_the_sheet(self):
        got = send(self.book(), "2031-05", ACCOUNTS, dry_run=True)
        self.assertFalse(got.get("ok"))
        self.assertEqual(got.get("error"), "no-month-row")


if __name__ == "__main__":
    unittest.main(verbosity=2)
