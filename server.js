#!/usr/bin/env node
/* AMS Finance Hub — local home screen for the monthly finance system.
 * Serves the hub page, computes per-month status, stores the monthly
 * checklist, and opens files/links on the Mac via whitelisted shortcuts.
 * Localhost only, no dependencies. */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFile, execFileSync } = require("child_process");

// Personal settings (paths, dashboard links) live in config.json, which stays
// on this Mac and is never committed — see config.example.json for the shape.
const APP_DIR = __dirname;
const CONFIG = JSON.parse(fs.readFileSync(path.join(APP_DIR, "config.json"), "utf8"));
const expand = p => p.replace(/^~/, os.homedir());

const PORT = CONFIG.port || 7780;
const VAULT = expand(CONFIG.vaultPath);
const VAULT_NAME = CONFIG.vaultName;
const FIN = path.join(VAULT, "Areas", "Finance");
const REPORTS = path.join(FIN, "Reports");
const SKILLS = path.join(VAULT, "Skills", "Finance");
const BUDGETING = expand(CONFIG.budgetingPath);
const WORKBOOK = path.join(BUDGETING, CONFIG.workbookFile);
const LEDGER = path.join(REPORTS, "monthly-ledger.csv");
const DASH_DATA = path.join(REPORTS, "dashboard-data.json");
const CHECKLIST = path.join(APP_DIR, "checklist.json");
const STORAGE = path.join(APP_DIR, "storage.json");

const DASH_SPEND_URL = CONFIG.dashSpendUrl;
const DASH_BUDGET_URL = CONFIG.dashBudgetUrl;

const FIRST_MONTH = CONFIG.firstMonth; // first month the reporting system covers

/* ---------- helpers ---------- */

function obsidianUrl(relPath) {
  return "obsidian://open?vault=" + encodeURIComponent(VAULT_NAME) +
         "&file=" + encodeURIComponent(relPath);
}

function mtimeOf(p) {
  try { return fs.statSync(p).mtime.toISOString(); } catch (e) { return null; }
}

function monthList() {
  // FIRST_MONTH .. current month
  const now = new Date();
  const months = [];
  let [y, m] = FIRST_MONTH.split("-").map(Number);
  const endY = now.getFullYear(), endM = now.getMonth() + 1;
  while (y < endY || (y === endY && m <= endM)) {
    months.push(`${y}-${String(m).padStart(2, "0")}`);
    m++; if (m > 12) { m = 1; y++; }
  }
  return months;
}

function reportPath(month) {
  const year = month.slice(0, 4);
  return path.join(REPORTS, year, `${month}-financial-report.md`);
}

function ledgerMonths() {
  try {
    const rows = fs.readFileSync(LEDGER, "utf8").split(/\r?\n/);
    const set = new Set();
    for (const row of rows) {
      const m = row.match(/^(\d{4}-\d{2}),/);
      if (m) set.add(m[1]);
    }
    return set;
  } catch (e) { return new Set(); }
}

function dashboardInfo() {
  try {
    const d = JSON.parse(fs.readFileSync(DASH_DATA, "utf8"));
    const months = d.months || [];
    const last = months[months.length - 1];
    return {
      generated: d.generated || null,
      months: months.map(x => x.month),
      kpi: last && last.totals ? {
        month: last.month,
        income: last.totals.total_income,
        expenses: last.totals.total_expenses,
        net: last.totals.net,
      } : null,
    };
  } catch (e) { return { generated: null, months: [], kpi: null }; }
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November", "December"];

function parseMonthLabel(label) {
  // "May 2026" -> "2026-05"
  const m = (label || "").match(/^([A-Za-z]+) (\d{4})$/);
  if (!m) return null;
  const idx = MONTH_NAMES.indexOf(m[1]);
  return idx < 0 ? null : `${m[2]}-${String(idx + 1).padStart(2, "0")}`;
}

function monthDiff(newer, older) {
  // both "YYYY-MM"; how many months newer is ahead of older
  if (!newer || !older) return 0;
  const [ny, nm] = newer.split("-").map(Number);
  const [oy, om] = older.split("-").map(Number);
  return (ny * 12 + nm) - (oy * 12 + om);
}

function budgetDashboardInfo() {
  try {
    const txt = fs.readFileSync(path.join(SKILLS, "ams-budget-dashboard.md"), "utf8");
    const refreshed = (txt.match(/Last refreshed \*\*([0-9-]+)\*\*/) || [])[1] || null;
    const through = (txt.match(/actuals through \*\*([A-Za-z]+ \d{4})\*\*/) || [])[1] || null;
    return { refreshed, through };
  } catch (e) { return { refreshed: null, through: null }; }
}

function workbookMonths() {
  try {
    const out = execFileSync("/usr/bin/python3",
      [path.join(APP_DIR, "workbook_status.py")], { timeout: 15000 });
    return JSON.parse(out.toString());
  } catch (e) {
    return { months: {}, error: String(e) };
  }
}

function buildStatus() {
  const ledger = ledgerMonths();
  const dash = dashboardInfo();
  const wb = workbookMonths();
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  const months = monthList().map(month => {
    const rp = reportPath(month);
    const reportExists = fs.existsSync(rp);
    return {
      month,
      isCurrent: month === currentMonth,
      report: reportExists,
      reportMtime: reportExists ? mtimeOf(rp) : null,
      ledger: ledger.has(month),
      workbook: !!wb.months[month],
      dashboard: dash.months.includes(month),
    };
  });

  // staleness: how far each dashboard lags what already exists
  const lastReport = months.filter(m => m.report).map(m => m.month).pop() || null;
  const lastWorkbook = months.filter(m => m.workbook).map(m => m.month).pop() || null;
  const lastSpend = dash.months[dash.months.length - 1] || null;
  const budgetInfo = budgetDashboardInfo();
  const budgetThrough = parseMonthLabel(budgetInfo.through);

  let dueDay = 8;
  try { dueDay = loadChecklist().dueDay; } catch (e) { /* default stands */ }

  return {
    now: now.toISOString(),
    currentMonth,
    dueDay,
    months,
    workbookError: wb.error || null,
    workbookMtime: mtimeOf(WORKBOOK),
    ledgerMtime: mtimeOf(LEDGER),
    kpi: dash.kpi,
    dashSpend: {
      url: DASH_SPEND_URL, generated: dash.generated, months: dash.months,
      behind: Math.max(0, monthDiff(lastReport, lastSpend)),
    },
    dashBudget: Object.assign({
      url: DASH_BUDGET_URL,
      throughMonth: budgetThrough,
      behind: Math.max(0, monthDiff(lastWorkbook, budgetThrough)),
    }, budgetInfo),
  };
}

/* ---------- checklist ---------- */

const DEFAULT_ITEMS = [
  "Export bank transactions (Swedbank)",
  "Log any manual cash expenses",
  "Run the monthly report with Sam",
  "Resolve flagged merchants + name ticket buys",
  "Write actuals to the budget workbook",
  "Refresh AMS Monthly Spend dashboard",
  "Refresh AMS Main Finance Dashboard",
];

function periodStartFor(resetDay, now) {
  // Most recent date whose day-of-month == resetDay (resetDay 1-28).
  const d = new Date(now.getFullYear(), now.getMonth(), resetDay);
  if (now.getDate() < resetDay) d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function sanitizeChecklist(raw) {
  // dueDay: a finished month's report only counts as "due" from this day of the
  // following month (bank statements need time to settle). Default: the 8th.
  const out = { resetDay: 1, dueDay: 8, periodStart: null, items: [] };
  if (raw && typeof raw === "object") {
    const rd = parseInt(raw.resetDay, 10);
    if (rd >= 1 && rd <= 28) out.resetDay = rd;
    const dd = parseInt(raw.dueDay, 10);
    if (dd >= 1 && dd <= 28) out.dueDay = dd;
    if (typeof raw.periodStart === "string") out.periodStart = raw.periodStart;
    if (Array.isArray(raw.items)) {
      const LINKS = ["report", "ledger", "workbook", "dashboard", "dashbudget"];
      out.items = raw.items.slice(0, 200).map((it, i) => {
        const item = {
          id: String(it && it.id ? it.id : "i" + Date.now() + "_" + i).slice(0, 40),
          text: String(it && it.text != null ? it.text : "").slice(0, 300),
          done: !!(it && it.done),
        };
        if (it && LINKS.includes(it.link)) item.link = it.link;
        if (it && /^\d{4}-\d{2}$/.test(it.autoApplied || "")) item.autoApplied = it.autoApplied;
        return item;
      }).filter(it => it.text.trim() !== "");
    }
  }
  return out;
}

function loadChecklist() {
  let data = null;
  try { data = JSON.parse(fs.readFileSync(CHECKLIST, "utf8")); } catch (e) { /* first run */ }
  if (data === null) {
    data = {
      resetDay: 1,
      periodStart: null,
      items: DEFAULT_ITEMS.map((t, i) => ({ id: "seed" + i, text: t, done: false })),
    };
  }
  data = sanitizeChecklist(data);
  // One-time migration: give the seeded process steps their status links
  // (an item with a link ticks itself when the hub sees that check go green).
  const SEED_LINKS = { seed2: "report", seed4: "workbook", seed5: "dashboard", seed6: "dashbudget" };
  data.items.forEach(it => {
    if (SEED_LINKS[it.id] && !it.link) it.link = SEED_LINKS[it.id];
  });
  // Automatic reset: new period => all ticks cleared, items kept.
  const current = periodStartFor(data.resetDay, new Date());
  if (data.periodStart !== current) {
    data.periodStart = current;
    data.items.forEach(it => { it.done = false; });
    saveChecklist(data);
  }
  return data;
}

function saveChecklist(data) {
  const tmp = CHECKLIST + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, CHECKLIST);
}

/* ---------- storage badges ---------- */

const STORAGE_KINDS = ["icloud", "dropbox", "gdrive", "web", "macbook", "amshome", "iphone", "other"];
const STORAGE_DEFAULTS = {
  "panel-status": "macbook", "panel-checklist": "macbook",
  "dash-spend": "web", "dash-budget": "web",
  "workbook": "macbook", "weekly": "macbook", "ledger": "macbook",
  "latest-report": "macbook", "expenses-log": "macbook", "wealth-log": "macbook",
  "canonical": "macbook", "runbook": "macbook",
  "budgeting-folder": "macbook", "reports-folder": "macbook", "imports-folder": "macbook",
};

function loadStorage() {
  let saved = {};
  try { saved = JSON.parse(fs.readFileSync(STORAGE, "utf8")); } catch (e) { /* first run */ }
  const out = {};
  for (const id of Object.keys(STORAGE_DEFAULTS)) {
    out[id] = STORAGE_KINDS.includes(saved[id]) ? saved[id] : STORAGE_DEFAULTS[id];
  }
  return out;
}

function saveStorage(raw) {
  const clean = {};
  if (raw && typeof raw === "object") {
    for (const id of Object.keys(STORAGE_DEFAULTS)) {
      if (STORAGE_KINDS.includes(raw[id])) clean[id] = raw[id];
    }
  }
  const tmp = STORAGE + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(clean, null, 2));
  fs.renameSync(tmp, STORAGE);
  return loadStorage();
}

/* ---------- open targets (whitelist) ---------- */

function openTargets(id) {
  const fixed = {
    "workbook": WORKBOOK,
    "weekly": path.join(BUDGETING, CONFIG.weeklyFile),
    "ledger": LEDGER,
    "budgeting-folder": BUDGETING,
    "reports-folder": path.join(REPORTS, "2026"),
    "imports-folder": path.join(FIN, "Imports"),
    "dash-spend": DASH_SPEND_URL,
    "dash-budget": DASH_BUDGET_URL,
    "canonical": obsidianUrl("Areas/Finance/Finance System Canonical State.md"),
    "expenses-log": obsidianUrl("Areas/Finance/expenses-logg-manual-through-month.md"),
    "wealth-log": obsidianUrl("Areas/Finance/wealth-log.md"),
    "runbook": obsidianUrl("Skills/Finance/monthly-financial-report.md"),
  };
  if (id in fixed) return fixed[id];
  const m = id.match(/^report-(\d{4})-(\d{2})$/);
  if (m) {
    const month = `${m[1]}-${m[2]}`;
    if (fs.existsSync(reportPath(month))) {
      return obsidianUrl(`Areas/Finance/Reports/${m[1]}/${month}-financial-report.md`);
    }
  }
  return null;
}

/* ---------- server ---------- */

function send(res, code, body, type) {
  res.writeHead(code, {
    "Content-Type": type || "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function appVersion() {
  // single source of truth: the visible version in the page footer
  try {
    const m = fs.readFileSync(path.join(APP_DIR, "index.html"), "utf8")
      .match(/AMS Finance Hub v([\d.]+)/);
    return m ? m[1] : null;
  } catch (e) { return null; }
}

// AMS Main Hub may ask this engine for its version, the net-worth series and
// a compact month status — allow only those origins
const CORS_ORIGINS = ["https://marsch124.github.io", "http://localhost:7794", "http://127.0.0.1:7794"];

/* ---------- hub endpoints (net worth + compact status) ---------- */

function wealthSeries() {
  const out = execFileSync("/usr/bin/python3",
    [path.join(APP_DIR, "wealth_series.py")], { timeout: 15000 });
  return JSON.parse(out.toString());
}

// both endpoints shell out to python — cache for a minute so the hub can
// poke them freely
const hubCache = { wealth: { at: 0, data: null }, status: { at: 0, data: null } };

function cachedWealth() {
  if (!hubCache.wealth.data || Date.now() - hubCache.wealth.at > 60000) {
    hubCache.wealth = { at: Date.now(), data: wealthSeries() };
  }
  return hubCache.wealth.data;
}

function cachedHubStatus() {
  if (!hubCache.status.data || Date.now() - hubCache.status.at > 60000) {
    const st = buildStatus();
    const current = st.months.find(m => m.isCurrent) || null;
    const previous = st.months.filter(m => !m.isCurrent).pop() || null;
    // deliberately compact: no config URLs or paths leave the engine here
    hubCache.status = { at: Date.now(), data: {
      ok: true, now: st.now, currentMonth: st.currentMonth, dueDay: st.dueDay,
      current, previous,
    } };
  }
  return hubCache.status.data;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const origin = req.headers.origin || "";
  if (CORS_ORIGINS.includes(origin)) res.setHeader("Access-Control-Allow-Origin", origin);

  if (url.pathname === "/" || url.pathname === "/index.html") {
    fs.readFile(path.join(APP_DIR, "index.html"), (err, data) => {
      if (err) return send(res, 500, "index.html missing", "text/plain");
      send(res, 200, data, "text/html; charset=utf-8");
    });
    return;
  }
  if (url.pathname === "/health") return send(res, 200, JSON.stringify({ ok: true, version: appVersion() }));
  if (url.pathname === "/wealth") {
    try {
      const w = cachedWealth();
      return send(res, 200, JSON.stringify({ ok: true, currency: "SEK", series: w.series || [] }));
    } catch (e) { return send(res, 500, JSON.stringify({ ok: false, error: String(e) })); }
  }
  if (url.pathname === "/hubstatus") {
    try { return send(res, 200, JSON.stringify(cachedHubStatus())); }
    catch (e) { return send(res, 500, JSON.stringify({ ok: false, error: String(e) })); }
  }
  if (url.pathname === "/api/status") {
    try { return send(res, 200, JSON.stringify(buildStatus())); }
    catch (e) { return send(res, 500, JSON.stringify({ error: String(e) })); }
  }
  if (url.pathname === "/api/checklist" && req.method === "GET") {
    try { return send(res, 200, JSON.stringify(loadChecklist())); }
    catch (e) { return send(res, 500, JSON.stringify({ error: String(e) })); }
  }
  if (url.pathname === "/api/checklist" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
      if (body.length > 500000) req.destroy();
    });
    req.on("end", () => {
      try {
        const data = sanitizeChecklist(JSON.parse(body));
        data.periodStart = periodStartFor(data.resetDay, new Date());
        saveChecklist(data);
        send(res, 200, JSON.stringify(data));
      } catch (e) {
        send(res, 400, JSON.stringify({ error: String(e) }));
      }
    });
    return;
  }
  if (url.pathname === "/api/storage" && req.method === "GET") {
    try { return send(res, 200, JSON.stringify(loadStorage())); }
    catch (e) { return send(res, 500, JSON.stringify({ error: String(e) })); }
  }
  if (url.pathname === "/api/storage" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
      if (body.length > 100000) req.destroy();
    });
    req.on("end", () => {
      try { send(res, 200, JSON.stringify(saveStorage(JSON.parse(body)))); }
      catch (e) { send(res, 400, JSON.stringify({ error: String(e) })); }
    });
    return;
  }
  if (url.pathname === "/api/open") {
    const target = openTargets(url.searchParams.get("id") || "");
    if (!target) return send(res, 404, JSON.stringify({ ok: false, error: "unknown target" }));
    execFile("/usr/bin/open", [target], (err) => {
      if (err) return send(res, 500, JSON.stringify({ ok: false, error: String(err) }));
      send(res, 200, JSON.stringify({ ok: true }));
    });
    return;
  }
  send(res, 404, "not found", "text/plain");
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`AMS Finance Hub running at http://localhost:${PORT}`);
});
