"""Writes a self-contained HTML dashboard: equity curve, stats, trade log with reasons."""
import csv
import html
import json
import os
import time


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def build(folder, prefix, title, start_cash, out_path, benchmark=None, note="", refresh=None):
    trades = _read(os.path.join(folder, prefix + "trades.csv"))
    eq = _read(os.path.join(folder, prefix + "equity.csv"))
    points = [{"t": r["time"], "v": float(r["equity"])} for r in eq]
    last = points[-1]["v"] if points else start_cash
    sells = [t for t in trades if t["side"] == "SELL"]
    wins = [t for t in sells if float(t["pnl"]) > 0]
    fees = sum(float(t["fee"]) for t in trades)
    peak, mdd = start_cash, 0.0
    for p in points:
        peak = max(peak, p["v"])
        mdd = max(mdd, 1 - p["v"] / peak)
    ret = last / start_cash - 1

    tiles = [
        ("Starting balance", f"${start_cash:,.2f}"),
        ("Current balance", f"${last:,.2f}"),
        ("Return", f"{ret:+.2%}"),
        ("Closed trades", f"{len(sells)}"),
        ("Win rate", f"{len(wins) / len(sells):.0%}" if sells else "—"),
        ("Max drawdown", f"{mdd:.1%}"),
        ("Fees paid", f"${fees:,.2f}"),
    ]
    if benchmark is not None:
        tiles.append(("Buy & hold BTC, same period", f"{benchmark:+.2%}"))

    rows = "".join(
        f"<tr><td>{html.escape(t['time'])}</td><td>{html.escape(t['pair'])}</td>"
        f"<td class='{t['side'].lower()}'>{t['side']}</td><td class='num'>{float(t['price']):.6g}</td>"
        f"<td class='num {'pos' if float(t['pnl']) > 0 else 'neg' if float(t['pnl']) < 0 else ''}'>"
        f"{'' if t['side'] == 'BUY' else f'{float(t[chr(112)+chr(110)+chr(108)]):+,.2f}'}</td>"
        f"<td class='num'>{float(t['equity']):,.2f}</td><td class='why'>{html.escape(t['reason'])}</td></tr>"
        for t in reversed(trades))
    tile_html = "".join(f"<div class='tile'><div class='k'>{k}</div><div class='v'>{v}</div></div>" for k, v in tiles)
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    page = TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__META__", meta) \
        .replace("__TILES__", tile_html).replace("__ROWS__", rows or "<tr><td colspan=7>No trades yet.</td></tr>") \
        .replace("__POINTS__", json.dumps(points)).replace("__START__", str(start_cash)) \
        .replace("__NOTE__", note).replace("__UPDATED__", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    with open(out_path, "w") as f:
        f.write(page)
    return out_path


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">__META__<title>__TITLE__</title>
<style>
:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--line:#2a78d6;--good:#0ca30c;--bad:#d03b3b;--banner:#fff4d6;--bannerink:#5a4300}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--line:#3987e5;--banner:#2b2410;--bannerink:#f3d98a}}
:root[data-theme="dark"]{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--line:#3987e5;--banner:#2b2410;--bannerink:#f3d98a}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--ink2);margin:0 0 14px}.banner{background:var(--banner);color:var(--bannerink);padding:10px 12px;border-radius:8px;margin-bottom:16px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:16px}
.tile{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:10px 12px}
.k{color:var(--ink2);font-size:12px}.v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:12px;margin-bottom:16px;position:relative}
.card h2{font-size:15px;margin:0 0 8px}svg{display:block;width:100%;height:280px}
#tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--surface);padding:4px 8px;border-radius:6px;font-size:12px;display:none;white-space:nowrap}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.why{color:var(--ink2);min-width:320px}.buy{color:var(--ink)}.sell{color:var(--ink)}.pos{color:var(--good)}.neg{color:var(--bad)}
</style></head><body><main>
<h1>__TITLE__</h1><p class="sub">Updated __UPDATED__ · simulated money only</p>
<div class="banner">__NOTE__</div>
<div class="tiles">__TILES__</div>
<div class="card"><h2>Equity curve (updates on every closed trade)</h2><svg id="chart" role="img" aria-label="Equity curve"></svg><div id="tip"></div></div>
<div class="card"><h2>Trade log: every trade with its reason</h2><div class="tw"><table>
<thead><tr><th>Time (UTC)</th><th>Pair</th><th>Side</th><th class="num">Fill price</th><th class="num">P&amp;L $</th><th class="num">Equity $</th><th>Reason</th></tr></thead>
<tbody>__ROWS__</tbody></table></div></div>
</main><script>
const pts=__POINTS__,start=__START__,svg=document.getElementById('chart'),tip=document.getElementById('tip');
function draw(){const W=svg.clientWidth,H=280,L=64,R=12,T=10,B=28;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const data=[{t:'start',v:start},...pts];const vs=data.map(d=>d.v);let lo=Math.min(...vs),hi=Math.max(...vs);
if(hi===lo){hi+=1;lo-=1}const pad=(hi-lo)*0.08;lo-=pad;hi+=pad;
const x=i=>L+(W-L-R)*(data.length>1?i/(data.length-1):0.5),y=v=>T+(H-T-B)*(1-(v-lo)/(hi-lo));
let s='';const css=getComputedStyle(document.documentElement),c=n=>css.getPropertyValue(n).trim();
for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4;s+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="${c('--grid')}"/>`+
`<text x="${L-6}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="${c('--muted')}">$${v.toLocaleString(undefined,{maximumFractionDigits:0})}</text>`}
s+=`<line x1="${L}" x2="${W-R}" y1="${y(start)}" y2="${y(start)}" stroke="${c('--axis')}" stroke-dasharray="4 4"/>`;
s+=`<polyline fill="none" stroke="${c('--line')}" stroke-width="2" stroke-linejoin="round" points="${data.map((d,i)=>x(i)+','+y(d.v)).join(' ')}"/>`;
if(data.length>1){s+=`<text x="${L}" y="${H-8}" font-size="11" fill="${c('--muted')}">${data[1].t}</text><text x="${W-R}" y="${H-8}" text-anchor="end" font-size="11" fill="${c('--muted')}">${data[data.length-1].t}</text>`}
s+=`<line id="xh" y1="${T}" y2="${H-B}" stroke="${c('--axis')}" visibility="hidden"/><circle id="dot" r="4" fill="${c('--line')}" stroke="${c('--surface')}" stroke-width="2" visibility="hidden"/>`;
svg.innerHTML=s;svg.onmousemove=e=>{const r=svg.getBoundingClientRect(),mx=e.clientX-r.left;
const i=Math.max(0,Math.min(data.length-1,Math.round((mx-L)/(W-L-R)*(data.length-1))));const d=data[i];
const xh=svg.querySelector('#xh'),dot=svg.querySelector('#dot');xh.setAttribute('x1',x(i));xh.setAttribute('x2',x(i));xh.setAttribute('visibility','visible');
dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(d.v));dot.setAttribute('visibility','visible');
tip.style.display='block';tip.textContent=`${d.t}: $${d.v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`;
tip.style.left=Math.min(x(i)+16,W-150)+'px';tip.style.top=(y(d.v)+20)+'px'};
svg.onmouseleave=()=>{tip.style.display='none';svg.querySelector('#xh').setAttribute('visibility','hidden');svg.querySelector('#dot').setAttribute('visibility','hidden')}}
draw();addEventListener('resize',draw);
</script></body></html>"""


# ---------------------------------------------------------------- comparison dashboard
def _epoch(s):
    return int(time.mktime(time.strptime(s, "%Y-%m-%d %H:%M")) - time.timezone)


def _json(path, default=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def build_compare(out_path, cfg):
    from .accounts import ACCOUNTS
    accts, series = [], []
    for i, (name, label) in enumerate(ACCOUNTS.items()):
        trades = _read(f"data/live_{name}_trades.csv")
        eq = _read(f"data/live_{name}_equity.csv")
        pts = [[_epoch(r["time"]), float(r["equity"])] for r in eq]
        last = pts[-1][1] if pts else cfg.starting_cash
        peak, mdd = cfg.starting_cash, 0.0
        for _, v in pts:
            peak, mdd = max(peak, v), max(mdd, 1 - v / peak)
        sells = [t for t in trades if t["side"] == "SELL"]
        st = _json(f"data/live_{name}_state.json", {}) or {}
        accts.append({"key": name, "label": label, "slot": i + 1, "equity": last,
                      "ret": last / cfg.starting_cash - 1, "closed": len(sells),
                      "win": (sum(float(t["pnl"]) > 0 for t in sells) / len(sells)) if sells else None,
                      "mdd": mdd, "open": list((st.get("positions") or {}).keys()),
                      "trades": list(reversed(trades))[:150]})
        series.append({"key": name, "label": label.split(" (")[0], "slot": i + 1, "pts": pts})

    ml = _json("data/models/ml_report.json")
    tuned = _json("data/models/tuned_params.json")
    history = _json("data/models/training_history.json", [])
    shared = _json("data/live_shared.json", {}) or {}
    preds = _read("data/live_ml_predictions.csv")
    resolved = [p for p in preds if p["ret_24h"] != ""]

    def card(rows):
        n = len(rows)
        if not n:
            return None
        r = [float(p["ret_24h"]) for p in rows]
        return {"n": n, "avg": sum(r) / n, "hit": sum(x > 0.015 for x in r) / n}

    payload = {
        "accounts": accts, "series": series, "start": cfg.starting_cash,
        "ml": ml, "tuned": tuned, "history": history,
        "report": {"approved": card([p for p in resolved if p["approved"] == "1"]),
                   "rejected": card([p for p in resolved if p["approved"] == "0"]),
                   "pending": len(preds) - len(resolved), "total": len(preds)},
        "last_run": shared.get("last_run"), "gran": cfg.granularity,
        "built": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    }
    with open(out_path, "w") as f:
        f.write(COMPARE.replace("__DATA__", json.dumps(payload).replace("</", "<\\/")))
    return out_path


COMPARE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="300">
<title>Paper Bot Lab</title>
<style>
:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#0ca30c;--bad:#d03b3b;--banner:#fff4d6;--bannerink:#5a4300;--track:#f0efec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--banner:#2b2410;--bannerink:#f3d98a;--track:#2c2c2a}}
:root[data-theme="dark"]{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--banner:#2b2410;--bannerink:#f3d98a;--track:#2c2c2a}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 2px}h2{font-size:15px;margin:0 0 10px}
.sub{color:var(--ink2);margin:0 0 12px}.banner{background:var(--banner);color:var(--bannerink);padding:10px 12px;border-radius:8px;margin-bottom:16px}
.status{display:inline-flex;gap:6px;align-items:center;font-weight:600}.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:14px;margin-bottom:16px;position:relative}
.grid3 .card{margin:0}.acct h3{margin:0 0 2px;font-size:14px;display:flex;gap:8px;align-items:center}.sw{width:12px;height:12px;border-radius:3px;flex:none}
.big{font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.kv{display:grid;grid-template-columns:1fr auto;gap:2px 10px;color:var(--ink2);font-size:13px;margin-top:8px}
.kv b{color:var(--ink);font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--good)}.neg{color:var(--bad)}.muted{color:var(--muted)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:-4px 0 8px;font-size:13px;color:var(--ink2)}.legend span{display:inline-flex;gap:6px;align-items:center}
svg.chart{display:block;width:100%;height:300px}#tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--surface);padding:6px 9px;border-radius:6px;font-size:12px;display:none;white-space:nowrap;line-height:1.5}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.bar{display:grid;grid-template-columns:minmax(120px,190px) 1fr 52px;gap:8px;align-items:center;font-size:13px;margin:5px 0}
.track{background:var(--track);border-radius:4px;height:12px;overflow:hidden}.fill{height:100%;background:var(--s1);border-radius:0 4px 4px 0}
.stat{display:flex;justify-content:space-between;border-bottom:1px solid var(--grid);padding:6px 0;font-size:13px;gap:10px}.stat b{font-variant-numeric:tabular-nums;text-align:right}
.note{font-size:13px;color:var(--ink2);margin:8px 0 0}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.tabs button{font:inherit;border:1px solid var(--grid);background:var(--page);color:var(--ink);border-radius:999px;padding:5px 12px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}
.tabs button[aria-selected=true]{border-color:var(--ink);font-weight:600}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.why{color:var(--ink2);min-width:300px}
</style></head><body><main>
<h1>Paper Bot Lab</h1><p class="sub" id="sub"></p>
<div class="banner"><b>Three bots, simulated money only.</b> Each starts with the same balance and sees the same live Coinbase prices.
They differ only in how they decide. The model retrains every Sunday. Judge them after weeks, not hours.</div>
<div class="grid3" id="accts"></div>
<div class="card"><h2>Balance over time</h2><div class="legend" id="legend"></div><svg class="chart" id="chart" role="img" aria-label="Balance of the three accounts over time"></svg><div id="tip"></div></div>
<div class="two">
 <div class="card"><h2>What the model learned</h2><div id="learned"></div></div>
 <div class="card"><h2>Model report card (live)</h2><div id="report"></div></div>
</div>
<div class="two">
 <div class="card"><h2>Self-tuning: this week's settings</h2><div id="tuned"></div></div>
 <div class="card"><h2>Training history (unseen 90-day test)</h2><div class="tw" id="hist"></div></div>
</div>
<div class="card"><h2>Trade log: every trade with its reason</h2><div class="tabs" id="tabs" role="tablist"></div><div class="tw" id="log"></div></div>
</main><script>
const D=__DATA__;const $=id=>document.getElementById(id);
const css=()=>getComputedStyle(document.documentElement),col=s=>css().getPropertyValue('--s'+s).trim();
const money=v=>'$'+v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=(v,d=1)=>v==null?'—':(v>0?'+':'')+(v*100).toFixed(d)+'%';
const cls=v=>v>0?'pos':v<0?'neg':'';const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// status line
(()=>{let s=`Updated ${D.built}`;if(D.last_run){const m=Math.round((Date.now()/1000-D.last_run)/60);const ok=m<130;
s=`<span class="status"><span class="dot" style="background:var(${ok?'--good':'--bad'})"></span>${ok?'Bot alive':'Bot may be paused'}</span> · last checked prices ${m<1?'just now':m+' min ago'}`;
const g=D.gran,nx=Math.ceil(Date.now()/1000/g)*g;s+=` · next decision candle closes ${new Date(nx*1000).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'})}`}
$('sub').innerHTML=s})();
// accounts
$('accts').innerHTML=D.accounts.map(a=>`<div class="card acct"><h3><span class="sw" style="background:var(--s${a.slot})"></span>${esc(a.label)}</h3>
<div class="big">${money(a.equity)}</div><div class="${cls(a.ret)}" style="font-weight:600">${pct(a.ret,2)}</div>
<div class="kv"><span>Closed trades</span><b>${a.closed}</b><span>Win rate</span><b>${a.win==null?'—':Math.round(a.win*100)+'%'}</b>
<span>Biggest drop</span><b>${(a.mdd*100).toFixed(1)}%</b><span>Open now</span><b>${a.open.length?esc(a.open.join(', ')):'none'}</b></div></div>`).join('');
// chart
$('legend').innerHTML=D.series.map(s=>`<span><span class="sw" style="background:var(--s${s.slot})"></span>${esc(s.label)}</span>`).join('');
const svg=$('chart'),tip=$('tip');
function draw(){const W=svg.clientWidth,H=300,L=64,R=96,T=12,B=28;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const all=D.series.flatMap(s=>s.pts);let g=`<line stroke="${css().getPropertyValue('--axis')}" x1="${L}" x2="${W-R}" y1="${H-B}" y2="${H-B}"/>`;
if(all.length<2){svg.innerHTML=g+`<text x="${W/2}" y="${H/2}" text-anchor="middle" fill="${css().getPropertyValue('--muted')}" font-size="13">The line starts after the next decision candle closes.</text>`;return}
let t0=Math.min(...all.map(p=>p[0])),t1=Math.max(...all.map(p=>p[0]));if(t1===t0)t1=t0+1;
let lo=Math.min(D.start,...all.map(p=>p[1])),hi=Math.max(D.start,...all.map(p=>p[1]));const pad=Math.max((hi-lo)*.1,D.start*.01);lo-=pad;hi+=pad;
const x=t=>L+(W-L-R)*(t-t0)/(t1-t0),y=v=>T+(H-T-B)*(1-(v-lo)/(hi-lo));const mu=css().getPropertyValue('--muted'),gr=css().getPropertyValue('--grid');
for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4;g+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="${gr}"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="${mu}">$${Math.round(v).toLocaleString()}</text>`}
g+=`<line x1="${L}" x2="${W-R}" y1="${y(D.start)}" y2="${y(D.start)}" stroke="${css().getPropertyValue('--axis')}" stroke-dasharray="4 4"/>`;
const f=t=>new Date(t*1000).toLocaleDateString([], {month:'short',day:'numeric'});g+=`<text x="${L}" y="${H-8}" font-size="11" fill="${mu}">${f(t0)}</text><text x="${W-R}" y="${H-8}" text-anchor="end" font-size="11" fill="${mu}">${f(t1)}</text>`;
const ends=[];D.series.forEach(s=>{if(!s.pts.length)return;g+=`<polyline fill="none" stroke="${col(s.slot)}" stroke-width="2" stroke-linejoin="round" points="${s.pts.map(p=>x(p[0])+','+y(p[1])).join(' ')}"/>`;
const e=s.pts[s.pts.length-1];ends.push({y:y(e[1]),x:x(e[0]),s})});
ends.sort((a,b)=>a.y-b.y);for(let i=1;i<ends.length;i++)ends[i].ly=Math.max(ends[i].y,(ends[i-1].ly??ends[i-1].y)+14);if(ends[0])ends[0].ly=ends[0].y;
ends.forEach(e=>{g+=`<circle cx="${e.x}" cy="${e.y}" r="4" fill="${col(e.s.slot)}" stroke="${css().getPropertyValue('--surface')}" stroke-width="2"/><text x="${e.x+8}" y="${e.ly+4}" font-size="11" fill="${css().getPropertyValue('--ink2')}">${esc(e.s.label.split(' ')[0])}</text>`});
g+=`<line id="xh" y1="${T}" y2="${H-B}" stroke="${css().getPropertyValue('--axis')}" visibility="hidden"/>`;svg.innerHTML=g;
svg.onmousemove=ev=>{const r=svg.getBoundingClientRect(),mx=ev.clientX-r.left;const t=t0+(mx-L)/(W-L-R)*(t1-t0);
const rows=D.series.map(s=>{let b=null;for(const p of s.pts){if(p[0]<=t+1)b=p}return b&&{s,b}}).filter(Boolean);if(!rows.length)return;
const xh=svg.querySelector('#xh');const tx=Math.max(...rows.map(r=>r.b[0]));xh.setAttribute('x1',x(tx));xh.setAttribute('x2',x(tx));xh.setAttribute('visibility','visible');
tip.style.display='block';tip.innerHTML=`${new Date(tx*1000).toLocaleString([], {month:'short',day:'numeric',hour:'numeric'})}<br>`+rows.map(r=>`<span class="sw" style="display:inline-block;width:8px;height:8px;background:${col(r.s.slot)}"></span> ${esc(r.s.label.split(' ')[0])}: ${money(r.b[1])}`).join('<br>');
tip.style.left=Math.min(mx+16,W-180)+'px';tip.style.top='40px'};svg.onmouseleave=()=>{tip.style.display='none';svg.querySelector('#xh').setAttribute('visibility','hidden')}}
draw();addEventListener('resize',draw);
// learned
(()=>{const m=D.ml;if(!m){$('learned').innerHTML='<p class="muted">No model trained yet.</p>';return}
const top=m.importances.filter(i=>i.importance>0).slice(0,8),mx=Math.max(...top.map(i=>i.importance),1e-9);
$('learned').innerHTML=`<p class="note" style="margin:0 0 8px">Signals the model relies on most (how much its accuracy drops when the signal is scrambled):</p>`+
top.map(i=>`<div class="bar"><span>${esc(i.name)}</span><div class="track"><div class="fill" style="width:${100*i.importance/mx}%"></div></div><span class="num muted">${(i.importance*100).toFixed(1)}</span></div>`).join('')+
`<div style="margin-top:10px"><div class="stat"><span>Goal</span><b>${esc(m.target)}</b></div>
<div class="stat"><span>Accuracy score on unseen ${m.unseen_days} days (AUC, 0.5 = coin flip)</span><b>${m.unseen_auc.toFixed(3)}</b></div>
<div class="stat"><span>How often it happened, any situation</span><b>${pct(m.unseen_base_rate,0).replace('+','')}</b></div>
<div class="stat"><span>How often it happened when the model approved</span><b>${pct(m.unseen_hit_rate_approved,0).replace('+','')}</b></div>
<div class="stat"><span>Trading test on unseen days: ML vs fixed rules</span><b><span class="${cls(m.trading_unseen_ml.return)}">${pct(m.trading_unseen_ml.return)}</span> vs <span class="${cls(m.trading_unseen_fixed.return)}">${pct(m.trading_unseen_fixed.return)}</span></b></div>
<div class="stat"><span>Last trained</span><b>${esc(m.trained_at)} on ${m.train_rows.toLocaleString()} examples</b></div></div>`})();
// report card
(()=>{const r=D.report,row=(k,c)=>c?`<div class="stat"><span>${k} (${c.n})</span><b><span class="${cls(c.avg)}">${pct(c.avg,2)}</span> avg 24h move · ${Math.round(c.hit*100)}% rose 1.5%+</b></div>`:`<div class="stat"><span>${k}</span><b class="muted">none yet</b></div>`;
$('report').innerHTML=`<p class="note" style="margin:0 0 8px">Every buy signal the ML bot sees gets a prediction. 24 hours later we record what actually happened. If approved signals don't beat rejected ones over time, the model isn't helping.</p>`+
row('Signals the model approved',r.approved)+row('Signals the model rejected',r.rejected)+
`<div class="stat"><span>Waiting for their 24 hours to pass</span><b>${r.pending}</b></div><p class="note">Needs ~30+ signals per row before it means much.</p>`})();
// tuned
(()=>{const t=D.tuned;if(!t){$('tuned').innerHTML='<p class="muted">Not tuned yet.</p>';return}const p=t.params;
const r=(k,a,b)=>`<div class="stat"><span>${k}</span><b>${a}</b></div>`;
$('tuned').innerHTML=r('Breakout window',p.breakout_lookback+' candles')+r('Trailing stop',p.stop_atr+' × volatility')+r('Volume needed',p.volume_spike+'× average')+
r('Picked combo: tuning year → unseen 90 days',`${pct(t.candidate_train.return)} → ${pct(t.candidate_unseen.return)}`)+
r('Default settings: tuning year → unseen 90 days',`${pct(t.default_train.return)} → ${pct(t.default_unseen.return)}`)+
`<p class="note"><b>${t.adopted?'Adopted':'Not adopted'}.</b> ${esc(t.verdict)} Tuned ${esc(t.trained_at)}.</p>`})();
// history
$('hist').innerHTML=D.history.length?`<table><thead><tr><th>Week</th><th class="num">Fixed</th><th class="num">Tuned</th><th class="num">ML</th><th class="num">AUC</th></tr></thead><tbody>`+
D.history.slice().reverse().map(h=>`<tr><td>${esc(h.date.slice(0,10))}</td><td class="num ${cls(h.unseen_fixed)}">${pct(h.unseen_fixed)}</td><td class="num ${cls(h.unseen_tuned)}">${pct(h.unseen_tuned)}</td><td class="num ${cls(h.unseen_ml)}">${pct(h.unseen_ml)}</td><td class="num">${h.auc.toFixed(3)}</td></tr>`).join('')+'</tbody></table>':'<p class="muted">No training runs yet.</p>';
// trade logs
function showLog(i){const a=D.accounts[i];[...$('tabs').children].forEach((b,j)=>b.setAttribute('aria-selected',j===i));
$('log').innerHTML=a.trades.length?`<table><thead><tr><th>Time (UTC)</th><th>Pair</th><th>Side</th><th class="num">Price</th><th class="num">P&amp;L</th><th class="num">Balance</th><th>Reason</th></tr></thead><tbody>`+
a.trades.map(t=>`<tr><td>${esc(t.time)}</td><td>${esc(t.pair)}</td><td>${t.side}</td><td class="num">${(+t.price).toPrecision(6)}</td><td class="num ${cls(+t.pnl)}">${t.side==='SELL'?(+t.pnl>0?'+':'')+(+t.pnl).toFixed(2):''}</td><td class="num">${(+t.equity).toFixed(2)}</td><td class="why">${esc(t.reason)}</td></tr>`).join('')+'</tbody></table>'
:`<p class="muted">No trades yet for ${esc(a.label)}.</p>`}
$('tabs').innerHTML=D.accounts.map((a,i)=>`<button role="tab" onclick="showLog(${i})"><span class="sw" style="background:var(--s${a.slot})"></span>${esc(a.label.split(' (')[0])}</button>`).join('');showLog(0);
</script></body></html>"""
