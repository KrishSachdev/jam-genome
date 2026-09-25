#!/usr/bin/env python3
"""Build dashboard.html — a self-contained interactive view of the dataset.

Everything is embedded: no CDN, no server, no build step. Open the file and it
works, online or off. Four linked panels that share one selection:

  map        50 points in real geography, sized and coloured by congestion
  heatmap    point x hour of day, hover for the exact value
  detail     the selected point's daily profile and day-by-day history
  table      sortable ranking, click-through to select

Usage:  python analysis/dashboard.py
"""
import csv
import json
import math

import pandas as pd

from episodes import ROOT, load_raw

OUT = ROOT / "dashboard.html"
SPLIT = pd.Timestamp("2026-08-20").date()
THRESH = 0.5

LAT0, LON0 = 19.08, 72.87
KM_LAT, KM_LON = 110.57, 111.32 * math.cos(math.radians(19.08))


def roles():
    out = {}
    with open(ROOT / "corridors.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["point_id"]] = {
                "lat": float(r["lat"]), "lon": float(r["lon"]),
                "name": r["name"], "corridor": r["corridor"],
            }
    return out


def build_era(g, meta):
    days = g["slot_ist"].dt.date.nunique()
    g = g.copy()
    g["hour"] = g["slot_ist"].dt.hour
    g["wd"] = g["slot_ist"].dt.dayofweek < 5
    g["date"] = g["slot_ist"].dt.date.astype(str)

    agg = g.groupby("point_id").agg(
        mean=("speed_ratio", "mean"),
        p05=("speed_ratio", lambda s: s.quantile(0.05)),
        cong=("speed_ratio", lambda s: (s < THRESH).sum()),
        slots=("speed_ratio", "size"),
    )
    agg["congH"] = agg["cong"] * 0.5 / days

    hourly = g.groupby(["point_id", "hour"])["speed_ratio"].mean().unstack()
    wd = g[g["wd"]].groupby(["point_id", "hour"])["speed_ratio"].mean().unstack()
    we = g[~g["wd"]].groupby(["point_id", "hour"])["speed_ratio"].mean().unstack()
    daily = g.groupby(["point_id", "date"])["speed_ratio"].mean().unstack()

    meta_pts = roles()
    pts = []
    for pid, r in agg.sort_values("congH", ascending=False).iterrows():
        m = meta_pts.get(pid, {})
        lat, lon = m.get("lat"), m.get("lon")
        pts.append({
            "id": pid,
            "name": m.get("name", pid),
            "role": m.get("corridor", "?"),
            "x": round((lon - LON0) * KM_LON, 2) if lon else None,
            "y": round(-(lat - LAT0) * KM_LAT, 2) if lat else None,
            "congH": round(float(r["congH"]), 2),
            "mean": round(float(r["mean"]), 3),
            "p05": round(float(r["p05"]), 3),
        })

    def row(fr, pid):
        if pid not in fr.index:
            return None
        v = fr.loc[pid]
        return [None if pd.isna(x) else round(float(x), 3) for x in v]

    return {
        "meta": meta,
        "days": days,
        "points": pts,
        "hours": {p["id"]: row(hourly, p["id"]) for p in pts},
        "wd": {p["id"]: row(wd, p["id"]) for p in pts},
        "we": {p["id"]: row(we, p["id"]) for p in pts},
        "dates": [str(d) for d in sorted(g["date"].unique())],
        "daily": {p["id"]: row(daily, p["id"]) for p in pts},
    }


def main():
    df = load_raw()
    A = df[df["slot_ist"].dt.date <= SPLIT]
    B = df[df["slot_ist"].dt.date > SPLIT]

    payload = {
        "A": build_era(A, f"{A['slot_ist'].min():%d %b} – {A['slot_ist'].max():%d %b %Y}"),
        "B": build_era(B, f"{B['slot_ist'].min():%d %b} – {B['slot_ist'].max():%d %b %Y}"),
    }
    js = json.dumps(payload, separators=(",", ":"))
    print("payload KB:", round(len(js) / 1024, 1))

    html = TEMPLATE.replace("__DATA__", js)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({len(html)/1024:.0f} KB)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jam Genome — Mumbai traffic explorer</title>
<style>
:root{--bg:#f2f4f2;--surface:#fbfcfa;--panel:#e9ece8;--ink:#0f1518;--ink2:#454f53;
 --muted:#79848a;--rule:#dde2dd;--accent:#2a78d6;--good:#0d8a66;--warn:#b07a12;--bad:#c0442c;
 --shadow:0 1px 2px rgba(15,21,24,.06),0 8px 24px -12px rgba(15,21,24,.18)}
@media(prefers-color-scheme:dark){:root{--bg:#0c1013;--surface:#141b1f;--panel:#090d10;
 --ink:#e9edeb;--ink2:#a5b0b4;--muted:#6d7880;--rule:#222c31;--accent:#3987e5;
 --good:#31c99b;--warn:#e0a63c;--bad:#f06e50;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:26px 20px 48px;display:flex;flex-direction:column;gap:18px}
.eyebrow{font:11px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
h1{font-size:clamp(21px,3.2vw,30px);margin:7px 0 0;font-weight:640;letter-spacing:-.02em}
.lede{color:var(--ink2);max-width:70ch;margin:9px 0 0}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.toggle{display:flex;gap:2px;background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:2px}
.toggle button{font:inherit;font-size:12.5px;font-weight:550;color:var(--ink2);background:none;border:0;border-radius:6px;padding:6px 13px;cursor:pointer}
.toggle button[aria-pressed=true]{background:var(--surface);color:var(--ink);box-shadow:var(--shadow)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);border-radius:10px;overflow:hidden}
.stat{background:var(--surface);padding:12px 14px}
.stat .n{overflow-wrap:anywhere;font:600 24px/1.1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat .k{font-size:12px;color:var(--muted);margin-top:3px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
.ph{padding:11px 14px;border-bottom:1px solid var(--rule);display:flex;justify-content:space-between;align-items:center;gap:10px}
.ph h2{font-size:13.5px;margin:0;font-weight:620}
.ph .hint{font-size:11.5px;color:var(--muted)}
.body{padding:10px 12px 14px;position:relative}
svg{display:block;width:100%;height:auto;overflow:visible}
.tip{position:fixed;pointer-events:none;opacity:0;transform:translate(-50%,-135%);background:var(--ink);color:var(--bg);
 padding:6px 9px;border-radius:6px;font:11.5px/1.35 ui-monospace,Menlo,Consolas,monospace;white-space:pre;z-index:9;transition:opacity .1s}
.tip.on{opacity:1}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:var(--ink2);padding:0 14px 10px}
.legend i{width:11px;height:11px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 12px;border-bottom:1px solid var(--rule);white-space:nowrap}
th{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--surface);cursor:pointer;user-select:none}
th:hover{color:var(--ink)}
td.num{text-align:right;font-family:ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
tbody tr{cursor:pointer}
tbody tr:hover{background:color-mix(in srgb,var(--accent) 9%,transparent)}
tbody tr.sel{background:color-mix(in srgb,var(--accent) 16%,transparent)}
.tablewrap{overflow:auto;max-height:420px}
.note{color:var(--ink2);font-size:13.5px;max-width:75ch}
.note b{color:var(--ink)}
.pill{display:inline-block;padding:1px 7px;border-radius:99px;font:600 11px ui-monospace,Menlo,Consolas,monospace}
</style></head><body>
<div class="wrap">
<header>
  <div class="eyebrow">Jam Genome · Mumbai traffic explorer</div>
  <h1 id="title">Mumbai congestion, measured every 30 minutes</h1>
  <p class="lede">Segment speeds from the TomTom Traffic Flow API. Congestion is
  <b>speed ÷ free-flow speed</b>; below <b>0.5</b> counts as congested. Click any point on the
  map, heatmap or table to inspect it. Everything is linked.</p>
</header>

<div class="bar">
  <div class="toggle" role="group" aria-label="Era">
    <button id="bB" aria-pressed="true">Era B — 50 points</button>
    <button id="bA" aria-pressed="false">Era A — 36 points</button>
  </div>
  <span class="hint" id="span" style="color:var(--muted);font-size:12px"></span>
</div>

<div class="stats" id="stats"></div>

<div class="grid">
  <div class="panel">
    <div class="ph"><h2>Where the jams are</h2><span class="hint">bigger + redder = worse</span></div>
    <div class="body"><svg id="map" role="img" aria-label="Map of monitoring points"></svg></div>
    <div class="legend">
      <span><i style="background:var(--good)"></i>under 0.5 h/day</span>
      <span><i style="background:var(--warn)"></i>0.5–2 h/day</span>
      <span><i style="background:var(--bad)"></i>over 2 h/day congested</span>
      <span><i style="background:var(--muted)"></i>never congested</span>
    </div>
  </div>
  <div class="panel">
    <div class="ph"><h2 id="detTitle">Pick a point</h2><span class="hint">weekday vs weekend</span></div>
    <div class="body"><svg id="detail" role="img" aria-label="Selected point profile"></svg></div>
    <div class="legend">
      <span><i style="background:var(--accent)"></i>weekday</span>
      <span><i style="background:var(--good)"></i>weekend</span>
      <span><i style="background:var(--muted)"></i>city average</span>
    </div>
  </div>
</div>

<div class="panel">
  <div class="ph"><h2>Every point, hour by hour</h2><span class="hint">hover a cell for the value · click a row to select</span></div>
  <div class="body"><svg id="heat" role="img" aria-label="Heatmap of points by hour"></svg></div>
</div>

<div class="panel">
  <div class="ph"><h2>Day by day</h2><span class="hint">selected point vs city average</span></div>
  <div class="body"><svg id="days" role="img" aria-label="Daily history"></svg></div>
</div>

<div class="panel">
  <div class="ph"><h2>Ranking</h2><span class="hint">click a column to sort</span></div>
  <div class="tablewrap"><table><thead><tr>
    <th data-k="id">Point</th><th data-k="role">Role</th>
    <th data-k="congH" class="num">Congested h/day</th>
    <th data-k="mean" class="num">Mean ratio</th>
    <th data-k="p05" class="num">5th pct</th>
  </tr></thead><tbody id="tbody"></tbody></table></div>
</div>

<p class="note"><b>How to read the ratio.</b> 1.00 means traffic is moving at the road's
normal free-flow speed. 0.50 means half that speed — the congestion threshold. 0.25 means
crawling at a quarter of normal.</p>
</div>
<div class="tip" id="tip"></div>

<script>
const D=__DATA__;
const NS="http://www.w3.org/2000/svg";
let era="B", sel=null, sortK="congH", sortDir=-1;
const $=id=>document.getElementById(id);
const el=(n,a={})=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;};
const tip=$("tip");
function showTip(ev,txt){tip.textContent=txt;tip.style.left=ev.clientX+"px";tip.style.top=ev.clientY+"px";tip.classList.add("on");}
function hideTip(){tip.classList.remove("on");}
const col=v=>v==null?"var(--muted)":v<0.5?"var(--bad)":v<0.75?"var(--warn)":"var(--good)";
/* mean ratio barely varies between points, so severity is keyed to congested
   hours per day instead -- that is the metric with real spread. */
const sev=h=>h>=2?"var(--bad)":h>=0.5?"var(--warn)":h>0?"var(--good)":"var(--muted)";

function cur(){return D[era];}
function pts(){return cur().points;}

/* ---------- stats ---------- */
function drawStats(){
  const p=pts(), d=cur();
  const live=p.filter(x=>x.congH>0).length;
  const worst=p[0];
  const slots=d.dates.length;
  $("stats").innerHTML=[
    [p.length,"points"],
    [d.days+" days","of collection"],
    [live+"/"+p.length,"points that see jams"],
    [worst.congH.toFixed(1)+" h","worst point per day"],
    [`<span style="font-size:15px">${worst.id}</span>`,"that point"],
  ].map(([n,k])=>`<div class="stat"><div class="n">${n}</div><div class="k">${k}</div></div>`).join("");
  $("span").textContent=d.meta;
}

/* ---------- map ---------- */
function drawMap(){
  const svg=$("map"); svg.replaceChildren();
  const P=pts().filter(p=>p.x!=null);
  const xs=P.map(p=>p.x), ys=P.map(p=>p.y), pad=1.6;
  const x0=Math.min(...xs)-pad,x1=Math.max(...xs)+pad,y0=Math.min(...ys)-pad,y1=Math.max(...ys)+pad;
  let w=x1-x0,h=y1-y0; const ratio=1.0;
  if(w/h<ratio){const cx=(x0+x1)/2;w=h*ratio;svg.setAttribute("viewBox",`${cx-w/2} ${y0} ${w} ${h}`);}
  else {const cy=(y0+y1)/2;h=w/ratio;svg.setAttribute("viewBox",`${x0} ${cy-h/2} ${w} ${h}`);}
  svg.style.aspectRatio=ratio;
  const maxC=Math.max(...P.map(p=>p.congH),0.5);
  P.slice().sort((a,b)=>a.congH-b.congH).forEach(p=>{
    const r=w*0.006+w*0.018*Math.sqrt(p.congH/maxC);
    const c=el("circle",{cx:p.x,cy:p.y,r:r,class:"pt"});
    c.style.fill=sev(p.congH); c.style.fillOpacity=.82;
    c.style.stroke=sel===p.id?"var(--ink)":"var(--surface)";
    c.style.strokeWidth=w*(sel===p.id?0.004:0.0018);
    c.style.cursor="pointer";
    c.addEventListener("pointermove",e=>showTip(e,`${p.id}\n${p.congH.toFixed(2)} congested h/day\nmean ratio ${p.mean.toFixed(2)}`));
    c.addEventListener("pointerleave",hideTip);
    c.addEventListener("click",()=>select(p.id));
    svg.appendChild(c);
  });
}

/* ---------- heatmap ---------- */
function drawHeat(){
  const svg=$("heat"); svg.replaceChildren();
  const P=pts(), H=cur().hours;
  const rowH=13, labW=124, cellW=26, top=18;
  const W=labW+24*cellW, Ht=top+P.length*rowH+8;
  svg.setAttribute("viewBox",`0 0 ${W} ${Ht}`); svg.style.aspectRatio=W/Ht;
  for(let hh=0;hh<24;hh+=2){
    const t=el("text",{x:labW+hh*cellW+cellW/2,y:12,"text-anchor":"middle"});
    t.style.font="10px ui-monospace,monospace"; t.style.fill="var(--muted)";
    t.textContent=String(hh).padStart(2,"0"); svg.appendChild(t);
  }
  P.forEach((p,i)=>{
    const y=top+i*rowH;
    const lab=el("text",{x:labW-6,y:y+rowH-3.5,"text-anchor":"end"});
    lab.style.font="10px ui-monospace,monospace";
    lab.style.fill=sel===p.id?"var(--ink)":"var(--ink2)";
    lab.style.fontWeight=sel===p.id?"700":"400";
    lab.style.cursor="pointer";
    lab.textContent=p.id.length>19?p.id.slice(0,18)+"…":p.id;
    lab.addEventListener("click",()=>select(p.id));
    svg.appendChild(lab);
    const row=H[p.id]||[];
    for(let hh=0;hh<24;hh++){
      const v=row[hh];
      const r=el("rect",{x:labW+hh*cellW,y:y,width:cellW-1,height:rowH-1});
      r.style.fill=v==null?"var(--panel)":shade(v);
      r.style.cursor="pointer";
      r.addEventListener("pointermove",e=>showTip(e,`${p.id}\n${String(hh).padStart(2,"0")}:00 · ratio ${v==null?"—":v.toFixed(2)}`));
      r.addEventListener("pointerleave",hideTip);
      r.addEventListener("click",()=>select(p.id));
      svg.appendChild(r);
    }
  });
}
function shade(v){
  const t=Math.max(0,Math.min(1,(1-v)/0.7));           // 1.0 -> pale, 0.3 -> dark
  const stops=["#cde2fb","#9ec5f4","#6da7ec","#3987e5","#256abf","#184f95","#0d366b"];
  return stops[Math.min(stops.length-1,Math.floor(t*stops.length))];
}

/* ---------- detail ---------- */
function drawDetail(){
  const svg=$("detail"); svg.replaceChildren();
  const W=520,H=300,L=40,R=12,T=14,B=30;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`); svg.style.aspectRatio=W/H;
  const X=h=>L+h*(W-L-R)/23, Y=v=>T+(1-(v-0.3)/0.75)*(H-T-B);
  [0.4,0.6,0.8,1.0].forEach(v=>{
    const ln=el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v)}); ln.style.stroke="var(--rule)"; svg.appendChild(ln);
    const t=el("text",{x:L-6,y:Y(v)+3,"text-anchor":"end"}); t.style.font="10px ui-monospace,monospace";
    t.style.fill="var(--muted)"; t.textContent=v.toFixed(1); svg.appendChild(t);
  });
  const th=el("line",{x1:L,x2:W-R,y1:Y(0.5),y2:Y(0.5)});
  th.style.stroke="var(--bad)"; th.style.strokeDasharray="4 4"; th.style.opacity=".5"; svg.appendChild(th);
  for(let hh=0;hh<24;hh+=4){
    const t=el("text",{x:X(hh),y:H-10,"text-anchor":"middle"});
    t.style.font="10px ui-monospace,monospace"; t.style.fill="var(--muted)";
    t.textContent=String(hh).padStart(2,"0"); svg.appendChild(t);
  }
  const P=pts(), avg=[];
  for(let hh=0;hh<24;hh++){
    const vals=P.map(p=>(cur().hours[p.id]||[])[hh]).filter(v=>v!=null);
    avg.push(vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null);
  }
  line(svg,avg,X,Y,"var(--muted)",1.4,"4 3");
  if(sel){
    line(svg,cur().we[sel]||[],X,Y,"var(--good)",2);
    line(svg,cur().wd[sel]||[],X,Y,"var(--accent)",2.4);
    const p=P.find(x=>x.id===sel);
    $("detTitle").textContent=sel+" — "+(p?p.congH.toFixed(2)+" congested h/day":"");
  } else { $("detTitle").textContent="Pick a point (city average shown)"; }
}
function line(svg,arr,X,Y,colour,w,dash){
  const pts=[]; arr.forEach((v,i)=>{if(v!=null)pts.push(`${X(i)},${Y(Math.max(0.3,Math.min(1.05,v)))}`);});
  if(pts.length<2)return;
  const pl=el("polyline",{points:pts.join(" ")});
  pl.style.fill="none"; pl.style.stroke=colour; pl.style.strokeWidth=w;
  pl.style.strokeLinejoin="round"; pl.style.strokeLinecap="round";
  if(dash)pl.style.strokeDasharray=dash;
  svg.appendChild(pl);
}

/* ---------- daily ---------- */
function drawDays(){
  const svg=$("days"); svg.replaceChildren();
  const d=cur(), n=d.dates.length;
  const W=1000,H=190,L=40,R=12,T=12,B=34;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`); svg.style.aspectRatio=W/H;
  const X=i=>L+(n<2?0:i*(W-L-R)/(n-1)), Y=v=>T+(1-(v-0.4)/0.65)*(H-T-B);
  [0.5,0.7,0.9].forEach(v=>{
    const ln=el("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v)}); ln.style.stroke="var(--rule)"; svg.appendChild(ln);
    const t=el("text",{x:L-6,y:Y(v)+3,"text-anchor":"end"}); t.style.font="10px ui-monospace,monospace";
    t.style.fill="var(--muted)"; t.textContent=v.toFixed(1); svg.appendChild(t);
  });
  const P=d.points, avg=d.dates.map((_,i)=>{
    const vals=P.map(p=>(d.daily[p.id]||[])[i]).filter(v=>v!=null);
    return vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null;});
  line(svg,avg,X,Y,"var(--muted)",1.6,"4 3");
  if(sel)line(svg,d.daily[sel]||[],X,Y,"var(--accent)",2.2);
  d.dates.forEach((ds,i)=>{
    if(n>14&&i%Math.ceil(n/12)!==0)return;
    const t=el("text",{x:X(i),y:H-12,"text-anchor":"middle"});
    t.style.font="9.5px ui-monospace,monospace"; t.style.fill="var(--muted)";
    t.textContent=ds.slice(5); svg.appendChild(t);
  });
  d.dates.forEach((ds,i)=>{
    const hit=el("rect",{x:X(i)-6,y:T,width:12,height:H-T-B});
    hit.style.fill="transparent"; hit.style.cursor="crosshair";
    hit.addEventListener("pointermove",e=>{
      const a=avg[i], s=sel?(d.daily[sel]||[])[i]:null;
      showTip(e,`${ds}\ncity avg ${a==null?"—":a.toFixed(3)}`+(sel?`\n${sel} ${s==null?"—":s.toFixed(3)}`:""));
    });
    hit.addEventListener("pointerleave",hideTip);
    svg.appendChild(hit);
  });
}

/* ---------- table ---------- */
function drawTable(){
  const tb=$("tbody"); tb.innerHTML="";
  const rows=pts().slice().sort((a,b)=>{
    const x=a[sortK],y=b[sortK];
    if(typeof x==="string")return sortDir*x.localeCompare(y);
    return sortDir*(x-y);
  });
  rows.forEach(p=>{
    const tr=document.createElement("tr");
    if(p.id===sel)tr.className="sel";
    tr.innerHTML=`<td style="font-family:ui-monospace,monospace">${p.id}</td>`+
      `<td><span class="pill" style="color:${sev(p.congH)}">${p.role}</span></td>`+
      `<td class="num">${p.congH.toFixed(2)}</td>`+
      `<td class="num">${p.mean.toFixed(2)}</td>`+
      `<td class="num">${p.p05.toFixed(2)}</td>`;
    tr.addEventListener("click",()=>select(p.id));
    tb.appendChild(tr);
  });
}
document.querySelectorAll("th[data-k]").forEach(th=>{
  th.addEventListener("click",()=>{
    const k=th.dataset.k;
    if(k===sortK)sortDir*=-1; else {sortK=k;sortDir=k==="id"||k==="role"?1:-1;}
    drawTable();
  });
});

/* ---------- wiring ---------- */
function select(id){ sel=(sel===id?null:id); drawAll(); }
function drawAll(){ drawStats(); drawMap(); drawHeat(); drawDetail(); drawDays(); drawTable(); }
function setEra(e){
  era=e; sel=null;
  $("bB").setAttribute("aria-pressed",e==="B"); $("bA").setAttribute("aria-pressed",e==="A");
  drawAll();
}
$("bB").addEventListener("click",()=>setEra("B"));
$("bA").addEventListener("click",()=>setEra("A"));
window.addEventListener("resize",()=>{drawMap();drawHeat();});
setEra("B");
</script></body></html>
"""


if __name__ == "__main__":
    main()
