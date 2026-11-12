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
