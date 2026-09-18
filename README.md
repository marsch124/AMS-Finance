# AMS Finance Hub

The home screen for the AMS monthly finance reporting — a local Mac app that shows, at a
glance, where the whole monthly finance process stands, and gives one-click access to every
part of it.

**Unlike the other AMS apps, this one is not a web app.** It runs entirely on the Mac it is
installed on: a small Node.js server (the "engine", port 7780) reads the real files — the
budget Excel workbook, the Obsidian monthly reports, the ledger, the dashboard data — and
serves the pages locally: AMS Main Hub at `localhost:7780` (the front door) and this Finance Hub
at `localhost:7780/finance`. Nothing is sent anywhere. This repository is the app's code and
its backup; there is no hosted version and no GitHub Pages site.

## What it shows

- **Monthly reporting status** — a spreadsheet-style board with one row per month and four
  live checks: Report (Obsidian report exists), Ledger (row in monthly-ledger.csv),
  Workbook (actuals really written into the budget Excel — the app parses the xlsx itself,
  standard library only), Dashboard (month included in the Spend Dashboard).
  Finished months without a report turn amber: *Due — run this month*.
- **KPI cards** — the latest reported month's income, expenses, net, and savings rate.
- **Dashboard tiles with staleness badges** — the Spend Dashboard and the Finance Dashboard
  (both published on claude.ai) each admit how many months they lag behind the newest data.
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
| `launcher.applescript` | Source of **AMS Finance.app** — starts the engine and opens localhost:7780, the Main Hub |
| `engine.applescript` | Source of **AMS Finance Engine.app** — headless start at login |
| `config.example.json` | Template for the personal configuration |
| `config.json` | **Not in the repo** — the real paths and dashboard links, local only |
| `checklist.json` | **Not in the repo** — the checklist's live data, local only |

## Setup on a Mac

1. Install [Node.js](https://nodejs.org) (any recent version).
2. Copy `config.example.json` to `config.json` and fill in your paths and links.
3. Build the two apps (Terminal, from this folder):
   `osacompile -o "AMS Finance.app" launcher.applescript` and
   `osacompile -o "AMS Finance Engine.app" engine.applescript`.
   A bare `osacompile` bundle has no identity macOS can grant permissions to and the
   generic script icon, so after building **AMS Finance.app**:
   ```
   /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.ams.finance.hub" "AMS Finance.app/Contents/Info.plist"
   /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "AMS Finance.app/Contents/Info.plist"   # never in the Dock
   rm -f "AMS Finance.app/Contents/Resources/Assets.car"                                            # or the icon is ignored
   /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "AMS Finance.app/Contents/Info.plist"
   cp <your applet.icns> "AMS Finance.app/Contents/Resources/applet.icns"
   xattr -cr "AMS Finance.app" && codesign --force --deep --sign - "AMS Finance.app"
   ```
4. Double-click **AMS Finance.app**. It starts the engine if it isn't running, then opens
   the **AMS Main Hub app** (the web app added to the Dock from `localhost:7780/hub/`); the
   Finance Hub is a card on its FINANCE shelf (`localhost:7780/finance`). It deliberately
   never opens a browser tab: a tab — like any second web app on the same address — keeps
   its own separate, EMPTY copy of the hub, which looks exactly like lost wealth data. Only
   if the AMS Main Hub app isn't installed does it fall back to `localhost:7780` in the
   browser. The first launch may ask for permission to read the Documents folder — click Allow.
5. Build **AMS Save Panel.app** the same way from `savepanel.applescript`, with bundle id
   `com.ams.finance.savepanel` and `LSUIElement`. It is the Main Hub's backup window: when
   *Save a backup file* is pressed on the Mac, the engine launches it (`open -W -a`) to show
   Apple's own Save window, reads the chosen file name back, writes the backup there and
   reads its size off the disk. It remembers the last folder in
   `~/Library/Application Support/AMS Finance/last-backup-folder.txt`. Keep it in this folder,
   out of `~/Applications`, so it never shows up in Raycast — nobody launches it by hand.
   (`osacompile` cannot write straight into a Documents folder: build it somewhere else,
   sign it there, then copy it in with `ditto`.)
6. Optional autostart: a LaunchAgent that opens the Engine app at login
   (`~/Library/LaunchAgents/com.ams.financehub.plist`).

## Version

See the version log inside the app ("How this works" → Version log). Current: **v1.14**.
