# The wealth tests

`send_wealth.py` **writes into his real budget workbook** and `wealth_series.py`
reads it back for the hub's quiet cross-check. These tests run on every push.

They never touch the real workbook. `make_workbook.py` builds a tiny spreadsheet
of the same shape, and each test puts the wealth block wherever it likes.

## What they guard

Both of the faults found by hand on 2026-11-02, before his first real send:

1. **The block moved and the reader did not follow.** It read columns AY/AZ
   because that is where the block used to be; he had moved it to BK/BL/BN-BS.
   It returned the year **1905**, so the hub's "workbook …" cross-check under
   the wealth total silently stopped appearing — a safety net doing nothing.
   Now both scripts find the block **by the words in the header row**, and a
   test places it in three different sets of columns and two different rows.
2. **Send to Excel could not find the month.** His date cells are written
   `t="n"`; the sender only accepted date cells with no type at all, so every
   press would have failed with `no-month-row`. A test now runs it both ways.

Also guarded: an untyped month reads as empty rather than zero; a workbook with
no wealth block says so instead of returning plausible nonsense; no date before
the year 2000 is ever reported; the sender writes into the right row and leaves
the other months alone; it never overwrites a formula; it takes a dated BU copy
first; and a dry run changes nothing.

Both faults were **put back** afterwards to prove the tests notice: the
hard-coded column gave 5 errors and a failure, the date-cell rejection gave 5
failures, and removing them again went green.

## Running them here

    python3 tests/test_wealth.py -v
