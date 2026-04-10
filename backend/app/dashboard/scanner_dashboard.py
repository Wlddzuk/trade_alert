"""Professional scanner dashboard — Trade Ideas / Warrior Trading style.

Mobile-first responsive: card layout on phone, full table on desktop.
"""

from __future__ import annotations


def render_scanner_dashboard() -> str:
    return _DASHBOARD_HTML


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0a0e17">
<title>Alpha Radar — Live Scanner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
/* ═══ RESET & BASE ═══ */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg-primary:#0a0e17;
  --bg-secondary:#111827;
  --bg-card:#1a1f2e;
  --bg-card-hover:#222a3e;
  --bg-row-hover:#1e2740;
  --bg-row-alt:#141926;
  --border:#2a3042;
  --border-light:#1e2538;
  --text-primary:#e2e8f0;
  --text-secondary:#94a3b8;
  --text-muted:#64748b;
  --green:#22c55e;
  --green-dim:#166534;
  --green-bg:rgba(34,197,94,.12);
  --red:#ef4444;
  --red-bg:rgba(239,68,68,.12);
  --amber:#f59e0b;
  --amber-bg:rgba(245,158,11,.12);
  --cyan:#06b6d4;
  --cyan-bg:rgba(6,182,212,.12);
  --purple:#a855f7;
  --blue:#3b82f6;
  --font-mono:'JetBrains Mono','SF Mono','Cascadia Code','Fira Code',monospace;
  --font-sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bottom:env(safe-area-inset-bottom,0px);
}
html{font-size:13px;-webkit-text-size-adjust:100%}
body{
  background:var(--bg-primary);
  color:var(--text-primary);
  font-family:var(--font-sans);
  overflow-x:hidden;
  min-height:100vh;
  min-height:100dvh;
  padding-top:var(--safe-top);
  padding-bottom:var(--safe-bottom);
  -webkit-font-smoothing:antialiased;
}

/* ═══ TOP BAR ═══ */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 16px;
  background:var(--bg-secondary);
  border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:100;
  -webkit-backdrop-filter:blur(12px);
  backdrop-filter:blur(12px);
}
.topbar .logo{
  font-size:15px;font-weight:700;color:var(--cyan);
  letter-spacing:1px;white-space:nowrap;
}
.topbar .logo span{color:var(--text-muted);font-weight:400;font-size:11px;margin-left:6px}
.topbar .status-bar{display:flex;align-items:center;gap:12px;font-size:11px;color:var(--text-secondary)}
.dot{
  width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px;
  flex-shrink:0;
}
.dot.live{background:var(--green);box-shadow:0 0 8px var(--green)}
.dot.offline{background:var(--red);box-shadow:0 0 6px var(--red)}
.dot.waiting{background:var(--amber);animation:pulse 1.5s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.4}50%{opacity:1}}

/* ═══ TABS ═══ */
.tab-bar{
  display:flex;gap:0;
  background:var(--bg-secondary);
  border-bottom:2px solid var(--border);
  padding:0 12px;
  overflow-x:auto;
  -webkit-overflow-scrolling:touch;
  scrollbar-width:none;
}
.tab-bar::-webkit-scrollbar{display:none}
.tab-bar button{
  background:none;border:none;color:var(--text-muted);
  padding:10px 16px;cursor:pointer;font-size:11px;font-weight:600;
  letter-spacing:.5px;text-transform:uppercase;
  border-bottom:2px solid transparent;
  margin-bottom:-2px;
  transition:all .15s;
  white-space:nowrap;
  -webkit-tap-highlight-color:transparent;
}
.tab-bar button:hover{color:var(--text-secondary)}
.tab-bar button.active{color:var(--cyan);border-bottom-color:var(--cyan)}
.tab-count{
  font-size:9px;font-weight:700;
  background:var(--bg-card);
  padding:1px 5px;border-radius:8px;
  margin-left:4px;color:var(--text-muted);
  vertical-align:middle;
}
.tab-bar button.active .tab-count{background:var(--cyan-bg);color:var(--cyan)}

/* ═══ STATS ROW ═══ */
.stats-row{
  display:grid;
  grid-template-columns:repeat(5,1fr);
  gap:8px;padding:10px 12px;
  background:var(--bg-secondary);
  border-bottom:1px solid var(--border);
}
.stat-box{
  background:var(--bg-card);
  border:1px solid var(--border-light);
  border-radius:8px;
  padding:8px 12px;
  text-align:center;
}
.stat-box .label{font-size:9px;text-transform:uppercase;color:var(--text-muted);letter-spacing:.5px;font-weight:600}
.stat-box .value{font-size:20px;font-weight:700;font-family:var(--font-mono);margin-top:2px}
.stat-box .value.green{color:var(--green)}
.stat-box .value.amber{color:var(--amber)}
.stat-box .value.red{color:var(--red)}
.stat-box .value.cyan{color:var(--cyan)}

/* ═══ DESKTOP TABLE ═══ */
.table-wrap{
  padding:0 8px 8px;
  overflow-x:auto;
  -webkit-overflow-scrolling:touch;
}
table.scanner{
  width:100%;
  border-collapse:collapse;
  font-size:12px;
  table-layout:auto;
}
table.scanner th{
  position:sticky;top:0;z-index:10;
  background:var(--bg-card);
  color:var(--text-muted);
  font-weight:600;text-transform:uppercase;letter-spacing:.5px;
  font-size:10px;
  padding:8px 10px;
  text-align:right;
  border-bottom:2px solid var(--border);
  cursor:pointer;
  white-space:nowrap;
  user-select:none;
}
table.scanner th:first-child{text-align:left}
table.scanner th:nth-child(2){text-align:left}
table.scanner th .sort-arrow{font-size:8px;margin-left:3px;opacity:.4}
table.scanner th.sorted .sort-arrow{opacity:1;color:var(--cyan)}

table.scanner td{
  padding:7px 10px;
  border-bottom:1px solid var(--border-light);
  font-family:var(--font-mono);
  font-size:12px;
  text-align:right;
  white-space:nowrap;
}
table.scanner td:first-child{text-align:left;font-family:var(--font-sans)}
table.scanner td:nth-child(2){text-align:left;font-family:var(--font-sans);max-width:200px;overflow:hidden;text-overflow:ellipsis}

table.scanner tbody tr{transition:background .1s}
table.scanner tbody tr:hover{background:var(--bg-row-hover)}
table.scanner tbody tr:nth-child(even){background:var(--bg-row-alt)}
table.scanner tbody tr:nth-child(even):hover{background:var(--bg-row-hover)}

/* ═══ MOBILE CARD VIEW ═══ */
.card-list{display:none;padding:8px}
.card{
  background:var(--bg-card);
  border:1px solid var(--border-light);
  border-radius:10px;
  padding:14px;
  margin-bottom:8px;
  transition:background .15s;
  -webkit-tap-highlight-color:transparent;
}
.card:active{background:var(--bg-card-hover)}
.card.stage-trigger{border-left:3px solid var(--green)}
.card.stage-building{border-left:3px solid var(--amber)}
.card.stage-invalid{border-left:3px solid var(--red)}

/* Card header row: symbol + score + stage */
.card-head{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:8px;
}
.card-sym{font-size:16px;font-weight:700;letter-spacing:.3px}
.card-sym .sent-dot{margin-left:5px}
.card-catalyst{font-size:9px;color:var(--text-muted);text-transform:uppercase;margin-top:1px}
.card-score-stage{display:flex;align-items:center;gap:8px}
.card-score{
  font-family:var(--font-mono);font-weight:700;font-size:18px;
}

/* Card headline */
.card-headline{
  font-size:11px;color:var(--text-secondary);
  margin-bottom:10px;
  line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}

/* Card metrics grid — 2 columns on phone */
.card-metrics{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:6px 12px;
}
.card-metric{
  display:flex;justify-content:space-between;align-items:center;
  padding:4px 0;
  border-bottom:1px solid var(--border-light);
}
.card-metric:nth-last-child(-n+2){border-bottom:none}
.card-metric .m-label{font-size:10px;color:var(--text-muted);text-transform:uppercase;font-weight:600}
.card-metric .m-value{font-family:var(--font-mono);font-size:12px;font-weight:600}

/* Card invalid reason */
.card-reason{
  margin-top:8px;padding:5px 8px;
  background:var(--red-bg);border-radius:5px;
  font-size:10px;color:var(--red);font-weight:600;
  text-transform:uppercase;letter-spacing:.3px;
}

/* ═══ SHARED ═══ */
.badge{
  display:inline-block;padding:3px 8px;border-radius:4px;
  font-size:10px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;
}
.badge.trigger{background:var(--green-bg);color:var(--green)}
.badge.building{background:var(--amber-bg);color:var(--amber)}
.badge.invalid{background:var(--red-bg);color:var(--red)}
.badge.watching{background:var(--cyan-bg);color:var(--cyan)}

.score-bar{display:inline-flex;align-items:center;gap:6px}
.score-fill{height:6px;border-radius:3px;min-width:4px;transition:width .3s}
.score-num{font-weight:700;min-width:24px;text-align:right}

.val-green{color:var(--green)}
.val-red{color:var(--red)}
.val-amber{color:var(--amber)}
.val-cyan{color:var(--cyan)}
.val-muted{color:var(--text-muted)}

.sym-name{font-weight:700;font-size:13px;letter-spacing:.3px}
.sym-catalyst{font-size:9px;color:var(--text-muted);text-transform:uppercase;margin-top:1px}

.sent-dot{width:7px;height:7px;border-radius:50%;display:inline-block;vertical-align:middle}
.sent-dot.bullish{background:var(--green)}
.sent-dot.bearish{background:var(--red)}

/* ═══ EMPTY STATE ═══ */
.empty-state{
  text-align:center;padding:60px 20px;color:var(--text-muted);
}
.empty-state .icon{font-size:48px;margin-bottom:12px}
.empty-state .title{font-size:16px;font-weight:600;color:var(--text-secondary)}
.empty-state .sub{font-size:12px;margin-top:6px;line-height:1.5}

/* ═══ DETAIL DRAWER (mobile tap-to-expand) ═══ */
.card-expand{
  display:none;
  margin-top:10px;padding-top:10px;
  border-top:1px solid var(--border);
}
.card-expand.open{display:block}
.card-expand-row{
  display:flex;justify-content:space-between;
  padding:3px 0;font-size:11px;
}
.card-expand-row .ex-label{color:var(--text-muted)}
.card-expand-row .ex-value{font-family:var(--font-mono);font-weight:600}

/* ═══ FOOTER ═══ */
.footer{
  padding:8px 16px;
  font-size:10px;color:var(--text-muted);
  border-top:1px solid var(--border);
  display:flex;justify-content:space-between;
  position:sticky;bottom:0;
  background:var(--bg-secondary);
  z-index:50;
}

/* ═══ PULL TO REFRESH INDICATOR ═══ */
.pull-indicator{
  text-align:center;padding:8px;
  font-size:11px;color:var(--cyan);
  display:none;
}

/* ═══ RESPONSIVE BREAKPOINTS ═══ */

/* Tablet portrait (768px) */
@media(max-width:768px){
  html{font-size:12px}
  .stats-row{grid-template-columns:repeat(5,1fr);gap:6px;padding:8px}
  .stat-box{padding:6px 8px}
  .stat-box .value{font-size:16px}
  .stat-box .label{font-size:8px}
  .tab-bar button{padding:8px 12px;font-size:10px}
}

/* Phone (640px) — switch table → cards */
@media(max-width:640px){
  html{font-size:12px}
  .topbar{padding:8px 12px}
  .topbar .logo{font-size:13px}
  .topbar .logo span{display:none}
  .topbar .status-bar{gap:8px;font-size:10px}
  #lastScan,#scanDuration{display:none}

  .stats-row{
    grid-template-columns:repeat(3,1fr);
    gap:6px;padding:8px 10px;
  }
  .stat-box:nth-child(4),.stat-box:nth-child(5){
    grid-column:span 1;
  }
  .stat-box .value{font-size:18px}

  .tab-bar{padding:0 8px}
  .tab-bar button{padding:8px 10px;font-size:10px}

  /* Hide table, show cards */
  .table-wrap{display:none!important}
  .card-list{display:block!important}

  .footer{padding:6px 12px;font-size:9px}
}

/* Small phone (380px) */
@media(max-width:380px){
  .stats-row{grid-template-columns:repeat(3,1fr);gap:4px;padding:6px 8px}
  .stat-box{padding:5px 6px;border-radius:6px}
  .stat-box .value{font-size:16px}
  .card{padding:12px}
  .card-sym{font-size:15px}
  .card-score{font-size:16px}
  .card-metrics{gap:4px 8px}
}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <div class="logo">ALPHA RADAR <span>Live Scanner</span></div>
  <div class="status-bar">
    <span><span class="dot" id="statusDot"></span><span id="statusText">Connecting...</span></span>
    <span id="lastScan">--</span>
    <span id="scanDuration">--</span>
  </div>
</div>

<!-- TAB BAR -->
<div class="tab-bar">
  <button class="active" data-tab="all">All <span class="tab-count" id="tabAll">0</span></button>
  <button data-tab="gappers">Gappers <span class="tab-count" id="tabGappers">0</span></button>
  <button data-tab="building">Building <span class="tab-count" id="tabBuilding">0</span></button>
  <button data-tab="triggered">Triggered <span class="tab-count" id="tabTriggered">0</span></button>
  <button data-tab="invalid">Invalid <span class="tab-count" id="tabInvalid">0</span></button>
</div>

<!-- STATS ROW -->
<div class="stats-row">
  <div class="stat-box"><div class="label">Scanned</div><div class="value cyan" id="statTotal">--</div></div>
  <div class="stat-box"><div class="label">Triggered</div><div class="value green" id="statTriggered">0</div></div>
  <div class="stat-box"><div class="label">Building</div><div class="value amber" id="statBuilding">0</div></div>
  <div class="stat-box"><div class="label">Invalid</div><div class="value red" id="statInvalid">0</div></div>
  <div class="stat-box"><div class="label">Top Score</div><div class="value cyan" id="statTopScore">--</div></div>
</div>

<!-- DESKTOP: SCANNER TABLE -->
<div class="table-wrap">
  <table class="scanner" id="scannerTable">
    <thead>
      <tr>
        <th data-sort="symbol">Symbol <span class="sort-arrow">▼</span></th>
        <th data-sort="headline">Headline <span class="sort-arrow">▼</span></th>
        <th data-sort="price">Price <span class="sort-arrow">▼</span></th>
        <th data-sort="change_percent">Chg% <span class="sort-arrow">▼</span></th>
        <th data-sort="gap_percent">Gap% <span class="sort-arrow">▼</span></th>
        <th data-sort="volume">Vol <span class="sort-arrow">▼</span></th>
        <th data-sort="daily_rvol">RVOL<sub>D</sub> <span class="sort-arrow">▼</span></th>
        <th data-sort="short_term_rvol">RVOL<sub>5m</sub> <span class="sort-arrow">▼</span></th>
        <th data-sort="vwap">VWAP <span class="sort-arrow">▼</span></th>
        <th data-sort="pullback_retracement_pct">Pull% <span class="sort-arrow">▼</span></th>
        <th data-sort="score">Score <span class="sort-arrow">▼</span></th>
        <th data-sort="stage">Stage <span class="sort-arrow">▼</span></th>
        <th>Reason</th>
      </tr>
    </thead>
    <tbody id="scannerBody"></tbody>
  </table>
</div>

<!-- MOBILE: CARD LIST -->
<div class="card-list" id="cardList"></div>

<!-- EMPTY STATE -->
<div class="empty-state" id="emptyState">
  <div class="icon">📡</div>
  <div class="title">Waiting for scanner data</div>
  <div class="sub">Data will appear here once the market opens<br>and the scanner completes its first scan.</div>
</div>

<!-- FOOTER -->
<div class="footer">
  <span>Alpha Radar v1.0</span>
  <span id="refreshCounter">Refreshing in 5s</span>
</div>

<script>
(function(){
  const REFRESH_MS = 5000;
  const API_URL = '/api/scanner';

  let allRows = [];
  let sortCol = 'score';
  let sortAsc = false;
  let activeTab = 'all';
  let countdown = 5;
  let expandedCard = null;

  // ── Tab switching ──
  document.querySelectorAll('.tab-bar button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelector('.tab-bar button.active').classList.remove('active');
      btn.classList.add('active');
      activeTab = btn.dataset.tab;
      renderAll();
    });
  });

  // ── Column sorting (desktop) ──
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortCol === col) { sortAsc = !sortAsc; }
      else { sortCol = col; sortAsc = false; }
      document.querySelectorAll('th').forEach(t => t.classList.remove('sorted'));
      th.classList.add('sorted');
      th.querySelector('.sort-arrow').textContent = sortAsc ? '▲' : '▼';
      renderAll();
    });
  });

  // ── Formatters ──
  function fmtNum(v, d) {
    if (v == null) return '<span class="val-muted">—</span>';
    return Number(v).toFixed(d);
  }
  function fmtVol(v) {
    if (v == null) return '<span class="val-muted">—</span>';
    if (v >= 1e6) return (v/1e6).toFixed(1)+'M';
    if (v >= 1e3) return (v/1e3).toFixed(0)+'K';
    return v.toString();
  }
  function fmtPct(v) {
    if (v == null) return '<span class="val-muted">—</span>';
    const n = Number(v);
    const cls = n > 0 ? 'val-green' : n < 0 ? 'val-red' : '';
    const sign = n > 0 ? '+' : '';
    return '<span class="'+cls+'">'+sign+n.toFixed(1)+'%</span>';
  }
  function fmtRvol(v) {
    if (v == null) return '<span class="val-muted">—</span>';
    const n = Number(v);
    const cls = n >= 3 ? 'val-green' : n >= 1.5 ? 'val-cyan' : n >= 1 ? 'val-amber' : 'val-red';
    return '<span class="'+cls+'">'+n.toFixed(1)+'x</span>';
  }
  function fmtScore(score) {
    const pct = Math.min(score, 100);
    const color = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--amber)' : 'var(--red)';
    return '<div class="score-bar"><div class="score-fill" style="width:'+pct*.6+'px;background:'+color+'"></div><span class="score-num" style="color:'+color+'">'+score+'</span></div>';
  }
  function scoreColor(score) {
    return score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--amber)' : 'var(--red)';
  }
  function fmtStage(stage) {
    const m = {
      'trigger_ready': '<span class="badge trigger">TRIGGER</span>',
      'building':      '<span class="badge building">BUILDING</span>',
      'invalid':       '<span class="badge invalid">INVALID</span>',
      'watching':      '<span class="badge watching">WATCHING</span>',
    };
    return m[stage] || '<span class="badge watching">'+stage+'</span>';
  }
  function fmtSentiment(dir) {
    if (!dir || dir === 'neutral') return '';
    return '<span class="sent-dot '+dir+'"></span>';
  }
  function fmtVwapDelta(price, vwap) {
    if (price == null || vwap == null) return '<span class="val-muted">—</span>';
    const delta = ((price - vwap) / vwap * 100);
    const cls = delta > 0 ? 'val-green' : 'val-red';
    const sign = delta > 0 ? '+' : '';
    return '<span class="'+cls+'">'+Number(vwap).toFixed(2)+' ('+sign+delta.toFixed(1)+'%)</span>';
  }
  function escHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // ── Filter ──
  function filterRows(rows) {
    if (activeTab === 'all') return rows;
    if (activeTab === 'gappers') return rows.filter(r => r.change_percent != null && r.change_percent >= 5);
    if (activeTab === 'building') return rows.filter(r => r.stage === 'building');
    if (activeTab === 'triggered') return rows.filter(r => r.stage === 'trigger_ready');
    if (activeTab === 'invalid') return rows.filter(r => r.stage === 'invalid');
    return rows;
  }

  // ── Sort ──
  function sortRows(rows) {
    return [...rows].sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? va - vb : vb - va;
    });
  }

  // ── Render desktop table ──
  function renderTable(sorted) {
    const tbody = document.getElementById('scannerBody');
    tbody.innerHTML = sorted.map(r => '<tr>' +
      '<td><div class="sym-name">'+escHtml(r.symbol)+fmtSentiment(r.sentiment_direction)+'</div><div class="sym-catalyst">'+escHtml((r.catalyst_tag||'').replace(/_/g,' '))+'</div></td>' +
      '<td title="'+escHtml(r.headline)+'">'+escHtml((r.headline||'').substring(0,50))+'</td>' +
      '<td>$'+fmtNum(r.price,2)+'</td>' +
      '<td>'+fmtPct(r.change_percent)+'</td>' +
      '<td>'+fmtPct(r.gap_percent)+'</td>' +
      '<td>'+fmtVol(r.volume)+'</td>' +
      '<td>'+fmtRvol(r.daily_rvol)+'</td>' +
      '<td>'+fmtRvol(r.short_term_rvol)+'</td>' +
      '<td>'+fmtVwapDelta(r.price,r.vwap)+'</td>' +
      '<td>'+(r.pullback_retracement_pct!=null?fmtNum(r.pullback_retracement_pct,0)+'%':'<span class="val-muted">—</span>')+'</td>' +
      '<td>'+fmtScore(r.score)+'</td>' +
      '<td>'+fmtStage(r.stage)+'</td>' +
      '<td class="val-muted" style="font-family:var(--font-sans);font-size:10px">'+(r.primary_invalid_reason?r.primary_invalid_reason.replace(/_/g,' '):'')+'</td>' +
    '</tr>').join('');
  }

  // ── Render mobile cards ──
  function renderCards(sorted) {
    const cl = document.getElementById('cardList');
    cl.innerHTML = sorted.map((r, idx) => {
      const stageClass = r.stage === 'trigger_ready' ? 'stage-trigger' : r.stage === 'building' ? 'stage-building' : r.stage === 'invalid' ? 'stage-invalid' : '';
      const reasonHtml = r.primary_invalid_reason ? '<div class="card-reason">'+r.primary_invalid_reason.replace(/_/g,' ')+'</div>' : '';

      return '<div class="card '+stageClass+'" data-idx="'+idx+'">' +
        '<div class="card-head">' +
          '<div><div class="card-sym">'+escHtml(r.symbol)+fmtSentiment(r.sentiment_direction)+'</div><div class="card-catalyst">'+escHtml((r.catalyst_tag||'').replace(/_/g,' '))+'</div></div>' +
          '<div class="card-score-stage">'+fmtStage(r.stage)+'<span class="card-score" style="color:'+scoreColor(r.score)+'">'+r.score+'</span></div>' +
        '</div>' +
        '<div class="card-headline">'+escHtml(r.headline)+'</div>' +
        '<div class="card-metrics">' +
          '<div class="card-metric"><span class="m-label">Price</span><span class="m-value">$'+fmtNum(r.price,2)+'</span></div>' +
          '<div class="card-metric"><span class="m-label">Chg%</span><span class="m-value">'+fmtPct(r.change_percent)+'</span></div>' +
          '<div class="card-metric"><span class="m-label">RVOL</span><span class="m-value">'+fmtRvol(r.daily_rvol)+'</span></div>' +
          '<div class="card-metric"><span class="m-label">Volume</span><span class="m-value">'+fmtVol(r.volume)+'</span></div>' +
          '<div class="card-metric"><span class="m-label">Gap%</span><span class="m-value">'+fmtPct(r.gap_percent)+'</span></div>' +
          '<div class="card-metric"><span class="m-label">RVOL 5m</span><span class="m-value">'+fmtRvol(r.short_term_rvol)+'</span></div>' +
        '</div>' +
        reasonHtml +
        '<div class="card-expand" id="expand-'+idx+'">' +
          '<div class="card-expand-row"><span class="ex-label">VWAP</span><span class="ex-value">'+fmtVwapDelta(r.price,r.vwap)+'</span></div>' +
          '<div class="card-expand-row"><span class="ex-label">EMA 9</span><span class="ex-value">'+(r.ema_9!=null?'$'+Number(r.ema_9).toFixed(2):'—')+'</span></div>' +
          '<div class="card-expand-row"><span class="ex-label">EMA 20</span><span class="ex-value">'+(r.ema_20!=null?'$'+Number(r.ema_20).toFixed(2):'—')+'</span></div>' +
          '<div class="card-expand-row"><span class="ex-label">Pullback</span><span class="ex-value">'+(r.pullback_retracement_pct!=null?r.pullback_retracement_pct.toFixed(0)+'%':'—')+'</span></div>' +
          '<div class="card-expand-row"><span class="ex-label">Catalyst Age</span><span class="ex-value">'+(r.catalyst_age_seconds!=null?Math.round(r.catalyst_age_seconds/60)+'m':'—')+'</span></div>' +
          '<div class="card-expand-row"><span class="ex-label">Avg Volume</span><span class="ex-value">'+fmtVol(r.avg_daily_volume)+'</span></div>' +
        '</div>' +
      '</div>';
    }).join('');

    // Tap to expand cards
    cl.querySelectorAll('.card').forEach(card => {
      card.addEventListener('click', () => {
        const idx = card.dataset.idx;
        const exp = document.getElementById('expand-'+idx);
        if (exp) {
          const isOpen = exp.classList.contains('open');
          // Close all
          cl.querySelectorAll('.card-expand.open').forEach(e => e.classList.remove('open'));
          if (!isOpen) exp.classList.add('open');
        }
      });
    });
  }

  // ── Render all ──
  function renderAll() {
    const filtered = filterRows(allRows);
    const sorted = sortRows(filtered);
    const empty = document.getElementById('emptyState');

    if (sorted.length === 0) {
      document.getElementById('scannerBody').innerHTML = '';
      document.getElementById('cardList').innerHTML = '';
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';
    renderTable(sorted);
    renderCards(sorted);
  }

  // ── Update stats + tab counts ──
  function updateStats(data) {
    const rows = data.rows || [];
    const triggered = rows.filter(r=>r.stage==='trigger_ready').length;
    const building = rows.filter(r=>r.stage==='building').length;
    const invalid = rows.filter(r=>r.stage==='invalid').length;
    const gappers = rows.filter(r=>r.change_percent!=null&&r.change_percent>=5).length;
    const scores = rows.map(r=>r.score).filter(s=>s>0);

    document.getElementById('statTotal').textContent = data.total_symbols_scanned || rows.length;
    document.getElementById('statTriggered').textContent = triggered;
    document.getElementById('statBuilding').textContent = building;
    document.getElementById('statInvalid').textContent = invalid;
    document.getElementById('statTopScore').textContent = scores.length ? Math.max(...scores) : '--';

    // Tab counts
    document.getElementById('tabAll').textContent = rows.length;
    document.getElementById('tabGappers').textContent = gappers;
    document.getElementById('tabBuilding').textContent = building;
    document.getElementById('tabTriggered').textContent = triggered;
    document.getElementById('tabInvalid').textContent = invalid;

    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (data.last_scan_at) {
      const age = (Date.now() - new Date(data.last_scan_at).getTime()) / 1000;
      if (age < 120) {
        dot.className = 'dot live';
        txt.textContent = 'LIVE';
      } else {
        dot.className = 'dot waiting';
        txt.textContent = 'STALE';
      }
      const st = new Date(data.last_scan_at);
      document.getElementById('lastScan').textContent = 'Last: ' + st.toLocaleTimeString();
    } else {
      dot.className = 'dot waiting';
      txt.textContent = 'Waiting...';
    }
    document.getElementById('scanDuration').textContent =
      data.scan_duration_seconds ? data.scan_duration_seconds.toFixed(1) + 's' : '';
  }

  // ── Fetch data ──
  async function fetchData() {
    try {
      const res = await fetch(API_URL);
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      allRows = data.rows || [];
      updateStats(data);
      renderAll();
    } catch(e) {
      document.getElementById('statusDot').className = 'dot offline';
      document.getElementById('statusText').textContent = 'OFFLINE';
      console.error('Fetch failed:', e);
    }
  }

  // ── Countdown timer ──
  function tickCountdown() {
    countdown--;
    if (countdown <= 0) {
      countdown = REFRESH_MS / 1000;
      fetchData();
    }
    document.getElementById('refreshCounter').textContent = 'Refresh ' + countdown + 's';
  }

  // ── Pull to refresh (mobile) ──
  let touchStartY = 0;
  document.addEventListener('touchstart', e => { touchStartY = e.touches[0].clientY; }, {passive:true});
  document.addEventListener('touchend', e => {
    const delta = e.changedTouches[0].clientY - touchStartY;
    if (delta > 100 && window.scrollY === 0) {
      fetchData();
      countdown = REFRESH_MS / 1000;
    }
  }, {passive:true});

  // Boot
  fetchData();
  setInterval(tickCountdown, 1000);
})();
</script>
</body>
</html>"""
