# AMS Finance Hub

The home screen for the AMS monthly finance reporting — a local Mac app that shows, at a
glance, where the whole monthly finance process stands, and gives one-click access to every
part of it.

**Unlike the other AMS apps, this one is not a web app.** It runs entirely on the Mac it is
installed on: a small Node.js server (the "engine", port 7780) reads the real files — the
budget Excel workbook, the Obsidian monthly reports, the ledger, the dashboard data — and
serves a single local page. Nothing is sent anywhere. This repository is the app's code and
its backup; there is no hosted version and no GitHub Pages site.

## What it shows

- **Monthly reporting status** — a spreadsheet-style board with one row per month and four
  live checks: Report (Obsidian report exists), Ledger (row in monthly-ledger.csv),
  Workbook (actuals really written into the budget Excel — the app parses the xlsx itself,
  standard library only), Dashboard (month included in the AMS Monthly Spend dashboard).
  Finished months without a report turn amber: *Due — run this month*.
- **KPI cards** — the latest reported month's income, expenses, net, and savings rate.
- **Dashboard tiles with staleness badges** — each published dashboard admits how many
  months it lags behind the newest data.
- **A monthly checklist** — numbered, editable, reorderable, resets its ticks on a chosen
  day of the month, and ⚡-linked items tick themselves when the status board sees the
  work is done.
- **Shortcut tiles** in colour families for the budget files, Obsidian notes, and folders.
- **A full "How this works" guide** with collapsible chapters, a worked example, and a
  version log — at the bottom of the page.

Everything is drawn in a hand-sketched style: all icons are handmade inline SVGs, on a
lilac canvas.

## Layout

| File | Role |
|---|---|
| `server.js` | The engine — local HTTP server, status checks, checklist storage, file opening |
| `index.html` | The entire interface (no build step, no dependencies) |
| `workbook_status.py` | Reads the budget workbook's monthly actuals columns (stdlib only) |
| `launcher.applescript` | Source of **AMS Finance.app** — starts the engine and opens the hub |
| `engine.applescript` | Source of **AMS Finance Engine.app** — headless start at login |
| `config.example.json` | Template for the personal configuration |
| `config.json` | **Not in the repo** — the real paths and dashboard links, local only |
| `checklist.json` | **Not in the repo** — the checklist's live data, local only |

## Setup on a Mac

1. Install [Node.js](https://nodejs.org) (any recent version).
2. Copy `config.example.json` to `config.json` and fill in your paths and links.
3. Build the two apps (Terminal, from this folder):
   `osacompile -o "AMS Finance.app" launcher.applescript` and
   `osacompile -o "AMS Finance Engine.app" engine.applescript`
4. Double-click **AMS Finance.app**. The first launch asks for permission to read the
   Documents folder — click Allow.
5. Optional autostart: a LaunchAgent that opens the Engine app at login
   (`~/Library/LaunchAgents/com.ams.financehub.plist`).

## Version

See the version log inside the app ("How this works" → Version log). Current: **v1.7**.
