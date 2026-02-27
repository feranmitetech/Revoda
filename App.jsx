// src/App.jsx — Revoda Main Application
// EiE Nigeria · Election Incident Dashboard

import { useState, useEffect, useRef, useCallback } from "react";

// ── CONSTANTS ────────────────────────────────────────────────────────────────
const API = window.location.hostname === "localhost"
  ? "http://localhost:8000/api/v1"
  : "https://api.revoda.eienigeria.org/api/v1";

const WS_URL = window.location.hostname === "localhost"
  ? "ws://localhost:8000/ws/live"
  : "wss://api.revoda.eienigeria.org/ws/live";

const CATEGORIES = {
  violence:                  { label: "Violence",           icon: "⚡", color: "#E53D2E" },
  voting_irregularity:       { label: "Voting",             icon: "🗳️", color: "#008751" },
  material_availability:     { label: "Materials",          icon: "📦", color: "#E8C440" },
  police_behaviour:          { label: "Police",             icon: "🚔", color: "#3d8bcd" },
  vote_counting:             { label: "Counting",           icon: "🔢", color: "#fb923c" },
  results_verification:      { label: "Results",            icon: "📋", color: "#c084fc" },
  electoral_officials_arrival:{ label: "Officials",         icon: "⏰", color: "#34d399" },
  result_announcement:       { label: "Announcement",       icon: "📢", color: "#f472b6" },
};

const NIGERIA_STATES = [
  "Abia","Adamawa","Akwa Ibom","Anambra","Bauchi","Bayelsa","Benue","Borno",
  "Cross River","Delta","Ebonyi","Edo","Ekiti","Enugu","FCT","Gombe","Imo",
  "Jigawa","Kaduna","Kano","Katsina","Kebbi","Kogi","Kwara","Lagos",
  "Nasarawa","Niger","Ogun","Ondo","Osun","Oyo","Plateau","Rivers",
  "Sokoto","Taraba","Yobe","Zamfara"
];

// Approximate state center coordinates for map pins
const STATE_COORDS = {
  "Abia":{lat:5.4527,lng:7.5248},"Adamawa":{lat:9.3265,lng:12.3984},
  "Akwa Ibom":{lat:5.0079,lng:7.8537},"Anambra":{lat:6.2209,lng:7.0670},
  "Bauchi":{lat:10.3158,lng:9.8442},"Bayelsa":{lat:4.7719,lng:6.0699},
  "Benue":{lat:7.1906,lng:8.1275},"Borno":{lat:11.8333,lng:13.1500},
  "Cross River":{lat:5.8702,lng:8.5988},"Delta":{lat:5.5320,lng:5.8987},
  "Ebonyi":{lat:6.2649,lng:8.0137},"Edo":{lat:6.5244,lng:5.8987},
  "Ekiti":{lat:7.6190,lng:5.2211},"Enugu":{lat:6.4584,lng:7.5464},
  "FCT":{lat:9.0579,lng:7.4951},"Gombe":{lat:10.2791,lng:11.1671},
  "Imo":{lat:5.5720,lng:7.0588},"Jigawa":{lat:12.2280,lng:9.5616},
  "Kaduna":{lat:10.5105,lng:7.4165},"Kano":{lat:12.0022,lng:8.5920},
  "Katsina":{lat:12.9889,lng:7.6006},"Kebbi":{lat:12.4539,lng:4.1975},
  "Kogi":{lat:7.7337,lng:6.6906},"Kwara":{lat:8.9669,lng:4.3877},
  "Lagos":{lat:6.5244,lng:3.3792},"Nasarawa":{lat:8.4972,lng:8.5240},
  "Niger":{lat:9.9309,lng:5.5983},"Ogun":{lat:7.1608,lng:3.3498},
  "Ondo":{lat:7.1000,lng:5.0000},"Osun":{lat:7.5629,lng:4.5200},
  "Oyo":{lat:7.8500,lng:3.9300},"Plateau":{lat:9.2182,lng:9.5179},
  "Rivers":{lat:4.8156,lng:7.0498},"Sokoto":{lat:13.0059,lng:5.2476},
  "Taraba":{lat:7.9993,lng:11.3694},"Yobe":{lat:12.2939,lng:11.4390},
  "Zamfara":{lat:12.1222,lng:6.2236}
};

// ── MOCK DATA (replace with real API calls) ──────────────────────────────────
const MOCK_INCIDENTS = [
  { id:"inc-001", category:"violence", description:"Armed thugs disrupted voting at PU 007, intimidating voters and INEC officials.", state:"Rivers", lga:"Obio-Akpor", polling_unit_code:"RV-OBK-007", status:"escalated", created_at:"2027-02-20T09:47:00Z", reporter_type:"citizen" },
  { id:"inc-002", category:"material_availability", description:"BVAS machine malfunction. 200+ voters unable to accredit. Manual fallback not authorised.", state:"Lagos", lga:"Ikeja", polling_unit_code:"LG-IKJ-031", status:"unverified", created_at:"2027-02-20T10:12:00Z", reporter_type:"observer" },
  { id:"inc-003", category:"voting_irregularity", description:"Multiple voters turned away despite valid PVCs. Polling officer refusing accreditation.", state:"Lagos", lga:"Oshodi-Isolo", polling_unit_code:"LG-OSH-018", status:"verified", created_at:"2027-02-20T10:35:00Z", reporter_type:"party_agent" },
  { id:"inc-004", category:"police_behaviour", description:"Police stationed inside polling unit in violation of INEC guidelines.", state:"Kano", lga:"Gwale", polling_unit_code:"KN-GWL-002", status:"verified", created_at:"2027-02-20T11:02:00Z", reporter_type:"journalist" },
  { id:"inc-005", category:"results_verification", description:"Result sheet Form EC8A not displayed at polling unit before departure.", state:"FCT", lga:"Bwari", polling_unit_code:"FC-BWR-011", status:"unverified", created_at:"2027-02-20T17:15:00Z", reporter_type:"citizen" },
  { id:"inc-006", category:"vote_counting", description:"Ballot box snatching during collation. Multiple eyewitnesses recorded incident.", state:"Borno", lga:"Maiduguri MC", polling_unit_code:"BO-MMC-044", status:"escalated", created_at:"2027-02-20T16:48:00Z", reporter_type:"observer" },
  { id:"inc-007", category:"voting_irregularity", description:"Underage individuals observed in voter queue. Party agent raised objection, ignored.", state:"Imo", lga:"Owerri North", polling_unit_code:"IM-OWN-003", status:"unverified", created_at:"2027-02-20T08:30:00Z", reporter_type:"citizen" },
  { id:"inc-008", category:"electoral_officials_arrival", description:"INEC officials arrived 3 hours late. Polling commenced at 11am instead of 8am.", state:"Oyo", lga:"Ibadan North", polling_unit_code:"OY-IBN-022", status:"verified", created_at:"2027-02-20T11:05:00Z", reporter_type:"observer" },
];

const MOCK_STATS = {
  total: 1247, unverified: 384, verified: 863, escalated: 37,
  by_category: Object.keys(CATEGORIES).map((k,i) => ({ category:k, count: [218,341,187,156,142,203,78,122][i]||50 })),
  by_state: [
    { state:"Rivers", count:182 },{ state:"Lagos", count:154 },
    { state:"Kano", count:138 },{ state:"Imo", count:117 },
    { state:"Borno", count:99 },{ state:"Delta", count:87 },
    { state:"Kaduna", count:76 },{ state:"Oyo", count:65 },
  ]
};

// ── UTILITY HOOKS ─────────────────────────────────────────────────────────────
function useApi(endpoint, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}${endpoint}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => {
        // Fall back to mock data
        if (endpoint.startsWith("/stats")) setData(MOCK_STATS);
        else if (endpoint.startsWith("/incidents")) setData({ incidents: MOCK_INCIDENTS, total: MOCK_INCIDENTS.length, page: 1, per_page: 20, pages: 1 });
        setLoading(false);
      });
  }, deps);

  return { data, loading, error };
}

function useWebSocket(onMessage) {
  const wsRef = useRef(null);
  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(WS_URL);
        ws.onmessage = e => { try { onMessage(JSON.parse(e.data)); } catch {} };
        ws.onclose = () => setTimeout(connect, 3000);
        wsRef.current = ws;
      } catch { setTimeout(connect, 5000); }
    };
    connect();
    return () => wsRef.current?.close();
  }, []);
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr);
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (m < 1440) return `${Math.floor(m/60)}h ago`;
  return `${Math.floor(m/1440)}d ago`;
}

// ── CSS INJECTED ─────────────────────────────────────────────────────────────
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Instrument+Sans:wght@400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --g: #008751; --gl: #00a862; --gd: #005c37;
  --ink: #080c0f; --ink2: #0d1117; --ink3: #161b22; --ink4: #21262d;
  --w: #edeae4; --m: #6b7a8d;
  --acc: #E8C440; --red: #E53D2E; --blue: #3d8bcd;
  --bd: rgba(255,255,255,0.07);
  --r: 10px;
}

html,body,#root { height:100%; background:var(--ink); color:var(--w); font-family:'Instrument Sans',sans-serif; font-size:14px; }

/* scrollbars */
::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--ink4); border-radius:2px; }

/* layout */
.app { display:grid; grid-template-rows:52px 1fr; height:100vh; overflow:hidden; }
.body { display:grid; grid-template-columns:240px 1fr 300px; overflow:hidden; }

/* nav */
nav { display:flex; align-items:center; gap:14px; padding:0 20px; border-bottom:1px solid var(--bd); background:rgba(8,12,15,0.95); backdrop-filter:blur(12px); z-index:50; }
.nav-brand { display:flex; align-items:center; gap:8px; }
.nav-logo { width:30px;height:30px;background:var(--g);border-radius:7px;display:flex;align-items:center;justify-content:center;font-family:'Syne',sans-serif;font-weight:800;font-size:14px;color:#fff;flex-shrink:0; }
.nav-wordmark { font-family:'Syne',sans-serif;font-weight:800;font-size:16px;letter-spacing:-0.2px; }
.nav-wordmark em { color:var(--gl);font-style:normal; }
.live-pill { background:rgba(229,61,46,0.15);border:1px solid rgba(229,61,46,0.4);color:#ff6b5b;font-size:10px;font-family:'DM Mono',monospace;padding:2px 8px;border-radius:20px;display:flex;align-items:center;gap:5px; }
.live-dot { width:5px;height:5px;background:#E53D2E;border-radius:50%;animation:blink 1.2s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
.nav-election { margin-left:auto;text-align:right; }
.nav-election-title { font-size:12px;font-weight:600;color:var(--acc); }
.nav-election-sub { font-size:10px;color:var(--m);font-family:'DM Mono',monospace; }
.btn-report-nav { background:var(--g);color:#fff;border:none;padding:7px 14px;border-radius:7px;font-family:'Syne',sans-serif;font-weight:700;font-size:12px;cursor:pointer;transition:all 0.15s;white-space:nowrap; }
.btn-report-nav:hover { background:var(--gl); }

/* sidebar */
.sidebar { border-right:1px solid var(--bd);padding:16px 14px;overflow-y:auto;display:flex;flex-direction:column;gap:20px;background:var(--ink2); }
.sec-label { font-family:'DM Mono',monospace;font-size:9px;color:var(--m);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px; }

/* stat cards */
.stat-grid { display:grid;grid-template-columns:1fr 1fr;gap:6px; }
.stat-card { background:var(--ink3);border:1px solid var(--bd);border-radius:var(--r);padding:10px 10px; transition:border-color 0.2s; }
.stat-card:hover { border-color:var(--g); }
.stat-num { font-family:'Syne',sans-serif;font-size:22px;font-weight:800;line-height:1; }
.stat-label { font-size:10px;color:var(--m);margin-top:3px; }
.c-red { color:#ff6b5b; } .c-acc { color:var(--acc); } .c-g { color:var(--gl); } .c-blue { color:var(--blue); }

/* category list */
.cat-list { display:flex;flex-direction:column;gap:2px; }
.cat-row { display:flex;align-items:center;justify-content:space-between;padding:7px 8px;border-radius:6px;cursor:pointer;transition:all 0.12s;border:1px solid transparent; }
.cat-row:hover,.cat-row.active { background:var(--ink3);border-color:var(--bd); }
.cat-row.active { border-color:rgba(0,135,81,0.4); }
.cat-left { display:flex;align-items:center;gap:7px; }
.cat-dot { width:7px;height:7px;border-radius:50%;flex-shrink:0; }
.cat-name { font-size:12px;font-weight:500; }
.cat-cnt { font-family:'DM Mono',monospace;font-size:10px;color:var(--m);background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px; }

/* mini bar chart */
.bar-row { display:flex;align-items:center;gap:7px;margin-bottom:7px; }
.bar-label { font-size:10px;color:var(--m);font-family:'DM Mono',monospace;width:65px;flex-shrink:0; }
.bar-track { flex:1;height:5px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden; }
.bar-fill { height:100%;border-radius:3px; }
.bar-val { font-size:10px;color:var(--w);font-family:'DM Mono',monospace;width:28px;text-align:right; }

/* map */
.map-area { position:relative;background:#060a0d;overflow:hidden; }
.map-overlay-top { position:absolute;top:14px;left:14px;right:14px;z-index:20;display:flex;align-items:flex-start;justify-content:space-between;gap:10px;pointer-events:none; }
.map-overlay-top > * { pointer-events:all; }
.map-crumb { background:rgba(8,12,15,0.88);backdrop-filter:blur(8px);border:1px solid var(--bd);border-radius:7px;padding:6px 12px;font-family:'DM Mono',monospace;font-size:11px;display:flex;align-items:center;gap:6px; }
.map-crumb span { color:var(--gl); }
.map-controls { display:flex;flex-direction:column;gap:3px; }
.map-btn { width:30px;height:30px;background:rgba(8,12,15,0.88);backdrop-filter:blur(8px);border:1px solid var(--bd);border-radius:6px;color:var(--w);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;transition:all 0.15s; }
.map-btn:hover { border-color:var(--g);background:rgba(0,135,81,0.15); }
.map-overlay-bot { position:absolute;bottom:14px;left:14px;right:14px;z-index:20;display:flex;align-items:flex-end;justify-content:space-between;pointer-events:none; }
.map-legend { background:rgba(8,12,15,0.88);backdrop-filter:blur(8px);border:1px solid var(--bd);border-radius:7px;padding:7px 12px;display:flex;align-items:center;gap:12px; }
.leg-item { display:flex;align-items:center;gap:4px;font-size:10px;font-family:'DM Mono',monospace;color:var(--m); }
.leg-dot { width:7px;height:7px;border-radius:50%; }
.map-live-badge { background:rgba(8,12,15,0.88);backdrop-filter:blur(8px);border:1px solid rgba(229,61,46,0.4);border-radius:7px;padding:7px 12px;font-family:'DM Mono',monospace;font-size:10px;color:#ff6b5b;display:flex;align-items:center;gap:6px; }

/* SVG map markers */
.marker { cursor:pointer; }
.marker-pulse { animation:markerPulse 2s ease-in-out infinite; }
@keyframes markerPulse { 0%,100%{r:10;opacity:0.2} 50%{r:16;opacity:0.05} }

/* right panel */
.right-panel { border-left:1px solid var(--bd);display:flex;flex-direction:column;background:var(--ink2); }
.tabs { display:flex;border-bottom:1px solid var(--bd); }
.tab { flex:1;padding:11px 8px;text-align:center;font-size:10px;font-family:'DM Mono',monospace;text-transform:uppercase;letter-spacing:0.5px;color:var(--m);cursor:pointer;transition:all 0.15s;border-bottom:2px solid transparent; }
.tab:hover { color:var(--w); }
.tab.active { color:var(--gl);border-bottom-color:var(--g); }
.panel-body { flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px; }

/* incident card */
.inc-card { background:var(--ink3);border:1px solid var(--bd);border-radius:var(--r);padding:12px;cursor:pointer;transition:all 0.15s;animation:slideDown 0.25s ease; }
.inc-card:hover { border-color:rgba(0,135,81,0.5);background:rgba(0,135,81,0.04); }
.inc-card.escalated { border-left:3px solid var(--red); }
.inc-card.verified { border-left:3px solid var(--g); }
.inc-card.unverified { border-left:3px solid var(--acc); }
@keyframes slideDown { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:none} }
.inc-header { display:flex;align-items:center;justify-content:space-between;margin-bottom:7px; }
.badge { font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;font-family:'DM Mono',monospace;text-transform:uppercase;letter-spacing:0.5px; }
.time { font-family:'DM Mono',monospace;font-size:10px;color:var(--m); }
.inc-desc { font-size:12px;line-height:1.55;opacity:0.85;margin-bottom:7px; }
.inc-loc { font-size:10px;color:var(--m);font-family:'DM Mono',monospace;display:flex;align-items:center;gap:4px; }
.inc-footer { display:flex;align-items:center;justify-content:space-between;margin-top:8px;padding-top:8px;border-top:1px solid var(--bd); }
.status-badge { font-size:10px;font-weight:600;display:flex;align-items:center;gap:3px; }
.action-btns { display:flex;gap:4px; }
.action-btn { font-size:10px;padding:3px 8px;border-radius:4px;border:1px solid var(--bd);background:none;color:var(--m);cursor:pointer;transition:all 0.12s;font-family:'DM Mono',monospace; }
.action-btn:hover { border-color:var(--g);color:var(--gl); }

/* report form */
.report-form { display:flex;flex-direction:column;gap:14px; }
.field-grp { display:flex;flex-direction:column;gap:5px; }
.field-lbl { font-size:10px;font-weight:600;color:var(--m);text-transform:uppercase;letter-spacing:0.5px;font-family:'DM Mono',monospace; }
.field-inp,.field-sel,.field-ta { background:rgba(255,255,255,0.04);border:1px solid var(--bd);border-radius:7px;padding:10px 11px;color:var(--w);font-family:'Instrument Sans',sans-serif;font-size:13px;transition:border-color 0.15s;width:100%;-webkit-appearance:none; }
.field-inp:focus,.field-sel:focus,.field-ta:focus { outline:none;border-color:var(--g); }
.field-sel option { background:#161b22; }
.field-ta { resize:vertical;min-height:90px;line-height:1.55; }
.anon-notice { background:rgba(0,135,81,0.08);border:1px solid rgba(0,135,81,0.22);border-radius:7px;padding:10px;font-size:11px;color:var(--gl);line-height:1.55;display:flex;gap:7px; }
.btn-submit { background:var(--g);color:#fff;border:none;padding:11px;border-radius:7px;font-family:'Syne',sans-serif;font-weight:700;font-size:13px;cursor:pointer;transition:all 0.15s;width:100%; }
.btn-submit:hover { background:var(--gl); }
.btn-submit:disabled { opacity:0.5; }
.btn-submit.success { background:#166534; }

/* alert cards */
.alert-card { background:rgba(229,61,46,0.07);border:1px solid rgba(229,61,46,0.22);border-radius:var(--r);padding:12px; }
.alert-title { font-size:12px;font-weight:700;color:#ff6b5b;display:flex;align-items:center;gap:6px;margin-bottom:6px; }
.alert-body { font-size:11px;opacity:0.8;line-height:1.55;margin-bottom:7px; }
.alert-meta { display:flex;gap:7px;font-size:10px;font-family:'DM Mono',monospace;color:var(--m); }

/* phase tabs sidebar */
.phase-list { display:flex;flex-direction:column;gap:4px; }
.phase-item { padding:9px 10px;border-radius:7px;border:1px solid var(--bd);cursor:pointer;transition:all 0.15s;display:flex;align-items:center;justify-content:space-between; }
.phase-item:hover,.phase-item.active { border-color:rgba(0,135,81,0.5);background:rgba(0,135,81,0.07); }
.phase-name { font-size:12px;font-weight:600; }
.phase-desc { font-size:10px;color:var(--m);font-family:'DM Mono',monospace; }
.phase-pill { font-size:9px;padding:2px 6px;border-radius:4px;font-weight:700; }
.live-phase { background:rgba(229,61,46,0.15);color:#ff6b5b; }
.soon-phase { background:rgba(61,139,205,0.15);color:var(--blue); }

/* loading */
.skeleton { background:linear-gradient(90deg,var(--ink3) 25%,var(--ink4) 50%,var(--ink3) 75%);background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:6px; }
@keyframes shimmer { 0%{background-position:200%} 100%{background-position:-200%} }

/* responsive */
@media(max-width:1024px) { .body{grid-template-columns:200px 1fr 260px} }
@media(max-width:768px) { .body{grid-template-columns:1fr} .sidebar,.right-panel{display:none} }
`;

// ── COMPONENTS ────────────────────────────────────────────────────────────────

function Badge({ category }) {
  const cat = CATEGORIES[category] || { label: category, color: "#6b7a8d" };
  return (
    <span className="badge" style={{
      background: cat.color + "22",
      color: cat.color
    }}>{cat.icon} {cat.label}</span>
  );
}

function StatusBadge({ status }) {
  const map = {
    escalated: { label: "⚠ Escalated", color: "#ff6b5b" },
    verified:  { label: "✓ Verified",  color: "#00a862" },
    unverified:{ label: "⏳ Pending",  color: "#E8C440" },
    dismissed: { label: "✕ Dismissed", color: "#6b7a8d" },
  };
  const s = map[status] || map.unverified;
  return <span className="status-badge" style={{ color: s.color }}>{s.label}</span>;
}

function IncidentCard({ incident, onSelect }) {
  return (
    <div className={`inc-card ${incident.status}`} onClick={() => onSelect(incident)}>
      <div className="inc-header">
        <Badge category={incident.category} />
        <span className="time">{timeAgo(incident.created_at)}</span>
      </div>
      <div className="inc-desc">{incident.description}</div>
      <div className="inc-loc">📍 {incident.lga ? `${incident.lga}, ` : ""}{incident.state}</div>
      <div className="inc-footer">
        <StatusBadge status={incident.status} />
        <div className="action-btns">
          <button className="action-btn">Verify</button>
          <button className="action-btn" style={{color:"#ff6b5b"}}>Escalate</button>
        </div>
      </div>
    </div>
  );
}

function AlertCard({ alert }) {
  return (
    <div className="alert-card">
      <div className="alert-title">⚠ {alert.title}</div>
      <div className="alert-body">{alert.body}</div>
      <div className="alert-meta">
        {alert.meta?.map((m, i) => <span key={i}>{m}</span>)}
      </div>
    </div>
  );
}

function Skeleton({ h = 80, mb = 10 }) {
  return <div className="skeleton" style={{ height: h, marginBottom: mb }} />;
}

// ── NIGERIA SVG MAP ──────────────────────────────────────────────────────────
function NigeriaMap({ incidents, selectedState, onStateClick }) {
  // Build per-state incident counts for coloring
  const stateCounts = {};
  incidents.forEach(i => {
    stateCounts[i.state] = (stateCounts[i.state] || 0) + 1;
  });

  const maxCount = Math.max(...Object.values(stateCounts), 1);

  function getColor(state) {
    const count = stateCounts[state] || 0;
    if (count === 0) return "#0a1a10";
    const intensity = count / maxCount;
    if (intensity > 0.7) return "#7f1d1d";
    if (intensity > 0.4) return "#991b1b";
    if (intensity > 0.2) return "#1e3a1e";
    return "#0f2d0f";
  }

  // Simplified Nigeria geo regions as polygons (illustrative)
  const regions = [
    { name:"Lagos",     d:"M 68 290 L 95 285 L 105 305 L 100 325 L 75 330 L 58 310 Z" },
    { name:"Ogun",      d:"M 95 265 L 130 258 L 145 278 L 135 300 L 105 305 L 95 285 Z" },
    { name:"Oyo",       d:"M 100 235 L 150 228 L 165 255 L 155 280 L 130 285 L 100 265 Z" },
    { name:"Osun",      d:"M 150 245 L 185 240 L 195 260 L 180 280 L 160 280 L 145 265 Z" },
    { name:"Ekiti",     d:"M 185 235 L 220 230 L 228 255 L 210 268 L 190 265 L 178 248 Z" },
    { name:"Ondo",      d:"M 150 280 L 190 275 L 205 298 L 195 320 L 165 325 L 148 305 Z" },
    { name:"Edo",       d:"M 190 268 L 230 262 L 240 285 L 225 305 L 200 308 L 188 288 Z" },
    { name:"Delta",     d:"M 195 308 L 235 302 L 245 322 L 232 342 L 208 345 L 195 328 Z" },
    { name:"Bayelsa",   d:"M 200 342 L 235 338 L 240 358 L 222 368 L 205 365 L 198 350 Z" },
    { name:"Rivers",    d:"M 235 318 L 275 312 L 285 335 L 270 355 L 248 358 L 235 340 Z" },
    { name:"Akwa Ibom", d:"M 272 308 L 310 302 L 318 322 L 305 340 L 282 342 L 270 325 Z" },
    { name:"Cross River",d:"M 305 278 L 342 272 L 350 295 L 338 315 L 315 318 L 302 298 Z"},
    { name:"Anambra",   d:"M 230 268 L 265 262 L 272 282 L 260 298 L 238 300 L 228 282 Z" },
    { name:"Imo",       d:"M 245 298 L 278 292 L 285 310 L 272 325 L 252 328 L 242 312 Z" },
    { name:"Abia",      d:"M 265 282 L 300 276 L 308 295 L 295 310 L 275 312 L 262 295 Z" },
    { name:"Ebonyi",    d:"M 295 258 L 330 252 L 338 272 L 325 288 L 305 290 L 292 272 Z" },
    { name:"Enugu",     d:"M 260 245 L 298 238 L 305 258 L 292 272 L 268 275 L 258 258 Z" },
    { name:"Benue",     d:"M 230 218 L 285 210 L 295 238 L 278 255 L 248 258 L 228 238 Z" },
    { name:"Kogi",      d:"M 170 215 L 230 208 L 238 232 L 222 250 L 195 252 L 168 235 Z" },
    { name:"Kwara",     d:"M 130 195 L 185 188 L 195 212 L 178 230 L 152 232 L 128 215 Z" },
    { name:"FCT",       d:"M 205 192 L 240 186 L 248 208 L 232 222 L 210 224 L 202 208 Z" },
    { name:"Nasarawa",  d:"M 238 180 L 278 174 L 285 196 L 270 210 L 248 212 L 236 196 Z" },
    { name:"Niger",     d:"M 100 165 L 165 155 L 178 188 L 160 205 L 128 208 L 98 188 Z" },
    { name:"Plateau",   d:"M 270 165 L 315 158 L 322 182 L 308 198 L 282 200 L 268 182 Z" },
    { name:"Taraba",    d:"M 310 172 L 360 165 L 368 192 L 352 208 L 325 210 L 308 192 Z" },
    { name:"Kaduna",    d:"M 175 130 L 230 122 L 238 152 L 220 168 L 192 170 L 172 150 Z" },
    { name:"Bauchi",    d:"M 272 128 L 325 120 L 332 148 L 315 164 L 288 166 L 270 148 Z" },
    { name:"Gombe",     d:"M 318 125 L 362 118 L 368 145 L 352 160 L 328 162 L 316 144 Z" },
    { name:"Adamawa",   d:"M 355 148 L 405 140 L 412 170 L 395 186 L 368 188 L 352 168 Z" },
    { name:"Borno",     d:"M 340 75 L 415 65 L 425 105 L 408 140 L 370 145 L 338 108 Z" },
    { name:"Yobe",      d:"M 285 75 L 345 68 L 350 105 L 335 122 L 305 125 L 282 102 Z" },
    { name:"Jigawa",    d:"M 225 72 L 280 65 L 285 98 L 270 114 L 245 116 L 222 95 Z" },
    { name:"Kano",      d:"M 200 90 L 248 82 L 252 110 L 238 126 L 215 128 L 198 108 Z" },
    { name:"Katsina",   d:"M 155 62 L 215 55 L 220 85 L 205 100 L 178 102 L 152 82 Z" },
    { name:"Sokoto",    d:"M 55 58 L 130 50 L 138 82 L 120 98 L 88 100 L 52 80 Z" },
    { name:"Kebbi",     d:"M 55 95 L 115 88 L 122 118 L 108 135 L 78 138 L 52 118 Z" },
    { name:"Zamfara",   d:"M 120 80 L 175 72 L 182 102 L 165 118 L 138 120 L 118 100 Z" },
  ];

  return (
    <svg viewBox="0 0 470 400" style={{ width:"100%", height:"100%", maxHeight:"calc(100vh - 120px)" }}>
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <radialGradient id="bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#0a1a10" stopOpacity="0.3"/>
          <stop offset="100%" stopColor="#060a0d" stopOpacity="0"/>
        </radialGradient>
      </defs>

      {/* Grid lines */}
      {[100,200,300,400].map(x => (
        <line key={`v${x}`} x1={x} y1="0" x2={x} y2="400" stroke="#008751" strokeWidth="0.3" strokeDasharray="3,8" opacity="0.2"/>
      ))}
      {[100,200,300].map(y => (
        <line key={`h${y}`} x1="0" y1={y} x2="470" y2={y} stroke="#008751" strokeWidth="0.3" strokeDasharray="3,8" opacity="0.2"/>
      ))}

      {/* State polygons */}
      {regions.map(r => {
        const count = stateCounts[r.name] || 0;
        const isSelected = selectedState === r.name;
        return (
          <path
            key={r.name}
            d={r.d}
            fill={isSelected ? "rgba(0,135,81,0.4)" : getColor(r.name)}
            stroke={isSelected ? "#00a862" : "#1a3828"}
            strokeWidth={isSelected ? 1.5 : 0.8}
            className="marker"
            onClick={() => onStateClick(r.name)}
            style={{ transition: "fill 0.3s, stroke 0.3s" }}
          />
        );
      })}

      {/* Incident markers on map */}
      {incidents.slice(0, 15).map((inc, i) => {
        const coords = STATE_COORDS[inc.state];
        if (!coords) return null;
        // Spread markers slightly by index
        const spread = 8;
        const offsetX = ((i * 7) % spread) - spread/2;
        const offsetY = ((i * 13) % spread) - spread/2;
        const cat = CATEGORIES[inc.category];
        const color = cat?.color || "#6b7a8d";

        // Convert lat/lng to our SVG coordinate space (approximate)
        const svgX = ((coords.lng - 2.5) / 12.5) * 420 + 30 + offsetX;
        const svgY = 400 - ((coords.lat - 4.0) / 10.5) * 360 + offsetY;

        return (
          <g key={inc.id} transform={`translate(${svgX},${svgY})`} className="marker">
            <circle r="12" fill={color} opacity="0.06" className="marker-pulse"/>
            <circle r="5" fill={color} stroke="rgba(255,255,255,0.2)" strokeWidth="1"
              filter="url(#glow)" opacity="0.9"/>
          </g>
        );
      })}

      {/* Nigeria label */}
      <text x="235" y="390" textAnchor="middle"
        fontFamily="DM Mono, monospace" fontSize="8" fill="#008751" opacity="0.5"
        letterSpacing="3">NIGERIA</text>
    </svg>
  );
}

// ── REPORT FORM ───────────────────────────────────────────────────────────────
function ReportForm({ onSubmitted }) {
  const [form, setForm] = useState({ category:"", state:"", lga:"", description:"", reporter_type:"citizen" });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const valid = form.category && form.state && form.description.trim().length >= 10;

  async function submit() {
    setSubmitting(true);
    try {
      await fetch(`${API}/incidents`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
    } catch {}
    setTimeout(() => { setDone(true); setSubmitting(false); onSubmitted?.(); }, 800);
  }

  if (done) return (
    <div style={{ textAlign:"center", padding:"30px 10px" }}>
      <div style={{ fontSize:36, marginBottom:12 }}>✅</div>
      <div style={{ fontFamily:"'Syne',sans-serif", fontWeight:700, fontSize:16, marginBottom:8 }}>Report Submitted</div>
      <div style={{ fontSize:12, color:"var(--m)", marginBottom:16 }}>Anonymised and logged. Thank you.</div>
      <button className="btn-submit" onClick={() => setDone(false)}>Report Another</button>
    </div>
  );

  return (
    <div className="report-form">
      <div className="anon-notice">🔒 <span>Your identity is <strong>fully anonymised</strong> before storage. No phone or personal data is ever logged.</span></div>

      <div className="field-grp">
        <label className="field-lbl">Incident Category *</label>
        <select className="field-sel" value={form.category} onChange={e => setForm({...form, category:e.target.value})}>
          <option value="">Select...</option>
          {Object.entries(CATEGORIES).map(([k,v]) => (
            <option key={k} value={k}>{v.icon} {v.label}</option>
          ))}
        </select>
      </div>

      <div className="field-grp">
        <label className="field-lbl">State *</label>
        <select className="field-sel" value={form.state} onChange={e => setForm({...form, state:e.target.value})}>
          <option value="">Select state...</option>
          {NIGERIA_STATES.map(s => <option key={s}>{s}</option>)}
        </select>
      </div>

      <div className="field-grp">
        <label className="field-lbl">LGA</label>
        <input className="field-inp" placeholder="Local Government Area" value={form.lga} onChange={e => setForm({...form, lga:e.target.value})}/>
      </div>

      <div className="field-grp">
        <label className="field-lbl">Polling Unit Code</label>
        <input className="field-inp" placeholder="e.g. LG-IKJ-031" style={{fontFamily:"'DM Mono',monospace",textTransform:"uppercase"}}
          onChange={e => setForm({...form, polling_unit_code:e.target.value.toUpperCase()})}/>
      </div>

      <div className="field-grp">
        <label className="field-lbl">Description *</label>
        <textarea className="field-ta" placeholder="What happened? Who was involved? What time?"
          value={form.description} onChange={e => setForm({...form, description:e.target.value})} maxLength={2000}/>
        <div style={{textAlign:"right",fontSize:10,color:"var(--m)"}}>{form.description.length}/2000</div>
      </div>

      <div className="field-grp">
        <label className="field-lbl">I am a...</label>
        <select className="field-sel" value={form.reporter_type} onChange={e => setForm({...form, reporter_type:e.target.value})}>
          <option value="citizen">Citizen / Voter</option>
          <option value="party_agent">Party Agent</option>
          <option value="observer">Observer (CSO)</option>
          <option value="journalist">Journalist</option>
          <option value="inec_official">INEC Official</option>
        </select>
      </div>

      <button className="btn-submit" disabled={!valid || submitting} onClick={submit}>
        {submitting ? "Submitting..." : "🚀 Submit Report"}
      </button>
    </div>
  );
}

// ── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState("feed");
  const [selectedCat, setSelectedCat] = useState("all");
  const [selectedState, setSelectedState] = useState(null);
  const [incidents, setIncidents] = useState(MOCK_INCIDENTS);
  const [stats, setStats] = useState(MOCK_STATS);
  const [liveCount, setLiveCount] = useState(0);

  // Fetch real data
  useEffect(() => {
    fetch(`${API}/incidents?per_page=30`)
      .then(r => r.json())
      .then(d => d.incidents && setIncidents(d.incidents))
      .catch(() => {});
    fetch(`${API}/stats`)
      .then(r => r.json())
      .then(d => setStats(d))
      .catch(() => {});
  }, []);

  // WebSocket live feed
  useWebSocket(useCallback(msg => {
    if (msg.event === "new_incident") {
      setIncidents(prev => [msg.data, ...prev.slice(0, 49)]);
      setStats(prev => prev ? {...prev, total: prev.total + 1, unverified: prev.unverified + 1} : prev);
      setLiveCount(c => c + 1);
    }
  }, []));

  // Filter incidents
  const filtered = incidents.filter(i => {
    if (selectedCat !== "all" && i.category !== selectedCat) return false;
    if (selectedState && i.state !== selectedState) return false;
    return true;
  });

  const ALERTS = [
    { title:"HOTSPOT — Rivers State", body:"6 violence incidents within 3km of Port Harcourt Zone 3. Escalation recommended.", meta:["09:52","AUTO-DETECT","Rivers"] },
    { title:"BVAS FAILURE — Lagos / Ogun", body:"Material failure cluster: Ikeja, Kosofe (Lagos), Abeokuta (Ogun). INEC notified.", meta:["10:18","PARTNER REPORT","4 LGAs"] },
    { title:"RESULTS PATTERN — Borno", body:"3 collation centres with missing EC8A. Matches 2019 pattern in same LGA.", meta:["17:22","AI-FLAGGED","Borno"] },
  ];

  return (
    <>
      <style>{CSS}</style>

      <div className="app">

        {/* ── NAV ── */}
        <nav>
          <div className="nav-brand">
            <div className="nav-logo">R</div>
            <div className="nav-wordmark">Re<em>Vo</em>Da</div>
          </div>
          <div className="live-pill">
            <span className="live-dot"/>
            LIVE
          </div>
          {liveCount > 0 && (
            <div style={{fontSize:10,color:"var(--acc)",fontFamily:"'DM Mono',monospace"}}>
              +{liveCount} new
            </div>
          )}
          <div className="nav-election">
            <div className="nav-election-title">2027 General Elections</div>
            <div className="nav-election-sub">Pre-Election Phase · EiE Nigeria</div>
          </div>
          <button className="btn-report-nav" onClick={() => setActiveTab("report")}>+ Report Incident</button>
        </nav>

        <div className="body">

          {/* ── SIDEBAR ── */}
          <aside className="sidebar">

            {/* Stats */}
            <div>
              <div className="sec-label">Live Statistics</div>
              <div className="stat-grid">
                <div className="stat-card"><div className="stat-num c-red">{stats?.total?.toLocaleString()}</div><div className="stat-label">Total Incidents</div></div>
                <div className="stat-card"><div className="stat-num c-acc">{stats?.unverified}</div><div className="stat-label">Unverified</div></div>
                <div className="stat-card"><div className="stat-num c-g">{stats?.verified}</div><div className="stat-label">Verified</div></div>
                <div className="stat-card"><div className="stat-num c-blue">{stats?.escalated}</div><div className="stat-label">Escalated</div></div>
              </div>
            </div>

            {/* Category filter */}
            <div>
              <div className="sec-label">Filter by Category</div>
              <div className="cat-list">
                <div className={`cat-row ${selectedCat==="all"?"active":""}`} onClick={()=>setSelectedCat("all")}>
                  <div className="cat-left"><div className="cat-dot" style={{background:"#6b7a8d"}}/>
                  <span className="cat-name">All</span></div>
                  <span className="cat-cnt">{stats?.total}</span>
                </div>
                {Object.entries(CATEGORIES).map(([k,v]) => {
                  const cnt = stats?.by_category?.find(c=>c.category===k)?.count || 0;
                  return (
                    <div key={k} className={`cat-row ${selectedCat===k?"active":""}`} onClick={()=>setSelectedCat(k)}>
                      <div className="cat-left">
                        <div className="cat-dot" style={{background:v.color}}/>
                        <span className="cat-name">{v.label}</span>
                      </div>
                      <span className="cat-cnt">{cnt}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Top states bar chart */}
            <div>
              <div className="sec-label">Top States</div>
              {stats?.by_state?.slice(0,6).map((s,i) => {
                const max = stats.by_state[0]?.count || 1;
                const colors = ["var(--red)","var(--acc)","var(--blue)","#c084fc","var(--g)","#fb923c"];
                return (
                  <div key={s.state} className="bar-row" style={{cursor:"pointer"}} onClick={()=>setSelectedState(selectedState===s.state?null:s.state)}>
                    <div className="bar-label">{s.state}</div>
                    <div className="bar-track"><div className="bar-fill" style={{width:`${(s.count/max)*100}%`,background:colors[i]}}/></div>
                    <div className="bar-val">{s.count}</div>
                  </div>
                );
              })}
            </div>

            {/* Phase */}
            <div>
              <div className="sec-label">Election Phases</div>
              <div className="phase-list">
                {[
                  {name:"Pre-Election",desc:"Early warning · prevention",status:"live"},
                  {name:"Election Day",desc:"Real-time reporting",status:"soon"},
                  {name:"Post-Election",desc:"Evidence archive",status:"soon"},
                ].map(p => (
                  <div key={p.name} className={`phase-item ${p.status==="live"?"active":""}`}>
                    <div><div className="phase-name">{p.name}</div><div className="phase-desc">{p.desc}</div></div>
                    <span className={`phase-pill ${p.status==="live"?"live-phase":"soon-phase"}`}>{p.status.toUpperCase()}</span>
                  </div>
                ))}
              </div>
            </div>

          </aside>

          {/* ── MAP ── */}
          <main className="map-area">
            <div className="map-overlay-top">
              <div className="map-crumb">🇳🇬 Nigeria {selectedState && <><span>→</span> <span>{selectedState}</span></>} {selectedCat!=="all" && <><span>→</span> <span>{CATEGORIES[selectedCat]?.label}</span></>}</div>
              <div className="map-controls">
                <button className="map-btn" title="Heat Map" onClick={()=>{}}>🔥</button>
                <button className="map-btn" title="Clear filter" onClick={()=>{setSelectedState(null);setSelectedCat("all")}}>✕</button>
                <button className="map-btn" title="Historical">📅</button>
              </div>
            </div>

            <div style={{width:"100%",height:"100%",display:"flex",alignItems:"center",justifyContent:"center",padding:"52px 20px 48px"}}>
              <NigeriaMap
                incidents={filtered}
                selectedState={selectedState}
                onStateClick={s => setSelectedState(selectedState === s ? null : s)}
              />
            </div>

            <div className="map-overlay-bot">
              <div className="map-legend">
                <span style={{fontSize:9,color:"var(--m)",fontFamily:"'DM Mono',monospace",marginRight:4}}>LEGEND</span>
                {["violence","voting_irregularity","material_availability","police_behaviour","results_verification"].map(k => (
                  <div key={k} className="leg-item">
                    <div className="leg-dot" style={{background:CATEGORIES[k].color}}/>
                    {CATEGORIES[k].label}
                  </div>
                ))}
              </div>
              <div className="map-live-badge">
                <span className="live-dot"/>
                {filtered.length} incidents · {selectedState || "All States"}
              </div>
            </div>
          </main>

          {/* ── RIGHT PANEL ── */}
          <aside className="right-panel">
            <div className="tabs">
              {["feed","alerts","report"].map(t => (
                <div key={t} className={`tab ${activeTab===t?"active":""}`} onClick={()=>setActiveTab(t)}>
                  {t === "feed" ? "Feed" : t === "alerts" ? `Alerts ${ALERTS.length}` : "Report"}
                </div>
              ))}
            </div>

            <div className="panel-body">
              {activeTab === "feed" && (
                filtered.length
                  ? filtered.slice(0,20).map(i => <IncidentCard key={i.id} incident={i} onSelect={()=>{}}/>)
                  : <div style={{textAlign:"center",padding:"40px 0",color:"var(--m)",fontSize:12}}>No incidents match current filters.</div>
              )}

              {activeTab === "alerts" && ALERTS.map((a,i) => <AlertCard key={i} alert={a}/>)}

              {activeTab === "report" && <ReportForm onSubmitted={() => setTimeout(() => setActiveTab("feed"), 2000)}/>}
            </div>
          </aside>

        </div>
      </div>
    </>
  );
}
