"""Build the citywide-sweep progress map from sweep_state.json.

NOTE (recovered 2026-08-07): this is the DAY-1 version of the builder. Three
later improvements were made in the original session and are NOT in this copy
-- see sweep/README.md "Known gaps". Re-add them before relying on it:
  1. geometry simplification (25 m tolerance; halved 22,210 -> 10,891 vertices)
  2. self-updating copy (headline/day count/progress read from state, not
     hardcoded "537 probes" / "day 1 of ~10" as below)
  3. el.style.stroke / el.style.strokeWidth instead of setAttribute
"""
import json
import math
from pathlib import Path

import sweep as SW   # reuse the mask polygon + grid definition

SP = Path(__file__).resolve().parent
st = json.loads((SP / "sweep_state.json").read_text())
segs = st["segments"]
done = st["done"]

LAT0, LON0 = 19.080, 72.870
KM_LAT, KM_LON = 110.57, 111.32 * math.cos(math.radians(19.08))


def proj(lat, lon):
    return (round((lon - LON0) * KM_LON, 3), round(-(lat - LAT0) * KM_LAT, 3))


def dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if p != out[-1]:
            out.append(p)
    return out


out_segs = []
for sid, s in sorted(segs.items(), key=lambda kv: kv[1]["km"]):
    if not s["geom"]:
        continue
    out_segs.append({
        "id": sid[:6], "frc": s["frc"], "ff": s["ff"], "km": s["km"], "hits": s["hits"],
        "pts": dedupe([proj(a, b) for a, b in s["geom"]]),
    })

probes = [list(proj(a, b)) for a, b in done]
mask = [list(proj(a, b)) for a, b in SW.MUMBAI]
sgnp = [list(proj(la, lo)) for la, lo in
        [(SW.SGNP[0], SW.SGNP[2]), (SW.SGNP[0], SW.SGNP[3]),
         (SW.SGNP[1], SW.SGNP[3]), (SW.SGNP[1], SW.SGNP[2])]]

grid_total = len(SW.build_grid())
swept_lat_max = max(c[0] for c in done)
frontier_y = proj(swept_lat_max, LON0)[1]

n_short = sum(1 for s in out_segs if s["km"] <= 3)
n_long = sum(1 for s in out_segs if s["km"] > 10)
pct = len(done) / grid_total * 100

payload = {"segs": out_segs, "probes": probes, "mask": mask, "sgnp": sgnp,
           "frontier": round(frontier_y, 3)}
js = json.dumps(payload, separators=(",", ":"))
print("payload KB:", round(len(js) / 1024, 1))

HTML = r"""<title>Mumbai segment sweep - Colaba to Dahisar</title>
<style>
  :root {
    --ground:#f2f4f2; --surface:#fbfcfa; --map-bg:#e9ece8;
    --ink:#0f1518; --ink-2:#454f53; --muted:#79848a; --rule:#dde2dd;
    --short:#0d8a66; --mid:#b07a12; --long:#c0442c; --probe:#8d989b; --pending:#b9c2c0;
    --shadow:0 1px 2px rgba(15,21,24,.06), 0 8px 24px -12px rgba(15,21,24,.18);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ground:#0c1013; --surface:#141b1f; --map-bg:#090d10;
      --ink:#e9edeb; --ink-2:#a5b0b4; --muted:#6d7880; --rule:#222c31;
      --short:#31c99b; --mid:#e0a63c; --long:#f06e50; --probe:#4c585d; --pending:#2b363b;
      --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
    }
  }
  :root[data-theme="dark"] {
    --ground:#0c1013; --surface:#141b1f; --map-bg:#090d10;
    --ink:#e9edeb; --ink-2:#a5b0b4; --muted:#6d7880; --rule:#222c31;
    --short:#31c99b; --mid:#e0a63c; --long:#f06e50; --probe:#4c585d; --pending:#2b363b;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
  }
  :root[data-theme="light"] {
    --ground:#f2f4f2; --surface:#fbfcfa; --map-bg:#e9ece8;
    --ink:#0f1518; --ink-2:#454f53; --muted:#79848a; --rule:#dde2dd;
    --short:#0d8a66; --mid:#b07a12; --long:#c0442c; --probe:#8d989b; --pending:#b9c2c0;
    --shadow:0 1px 2px rgba(15,21,24,.06), 0 8px 24px -12px rgba(15,21,24,.18);
  }
  * { box-sizing:border-box; }
  .wrap { background:var(--ground); color:var(--ink);
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    font-size:15px; line-height:1.55; padding:28px 22px 40px; min-height:100%; }
  .inner { max-width:1080px; margin:0 auto; display:flex; flex-direction:column; gap:22px; }
  .mono { font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace; }
  .eyebrow { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }
  h1 { font-size:clamp(22px,3.4vw,31px); line-height:1.18; margin:6px 0 0;
       font-weight:640; letter-spacing:-.018em; text-wrap:balance; }
  .lede { color:var(--ink-2); max-width:64ch; margin:10px 0 0; }
  .lede b { color:var(--ink); font-weight:620; }

  .prog { display:flex; flex-direction:column; gap:6px; }
  .track { height:7px; border-radius:99px; background:var(--pending); overflow:hidden; }
  .fill { height:100%; background:var(--short); border-radius:99px; }
  .prow { display:flex; justify-content:space-between; font-size:12px; color:var(--muted); }

  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:1px;
           background:var(--rule); border:1px solid var(--rule); border-radius:9px; overflow:hidden; }
  .stat { background:var(--surface); padding:13px 15px; }
  .stat .n { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:25px; font-weight:600;
             letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
  .stat .k { font-size:12px; color:var(--muted); margin-top:1px; }
  .stat.good .n { color:var(--short); }
  .stat.bad .n { color:var(--long); }

  .panel { background:var(--surface); border:1px solid var(--rule); border-radius:11px;
           box-shadow:var(--shadow); overflow:hidden; }
  .bar { display:flex; flex-wrap:wrap; align-items:center; gap:12px; padding:11px 14px;
         border-bottom:1px solid var(--rule); }
  .toggle { display:flex; gap:2px; background:var(--ground); border:1px solid var(--rule);
            border-radius:7px; padding:2px; }
  .toggle button { font:inherit; font-size:12.5px; font-weight:550; color:var(--ink-2);
    background:transparent; border:0; border-radius:5px; padding:5px 12px; cursor:pointer; }
  .toggle button[aria-pressed="true"] { background:var(--surface); color:var(--ink); box-shadow:var(--shadow); }
  .toggle button:focus-visible { outline:2px solid var(--short); outline-offset:1px; }
  .legend { display:flex; flex-wrap:wrap; gap:14px; margin-left:auto; font-size:12px; color:var(--ink-2); }
  .legend span { display:inline-flex; align-items:center; gap:6px; }
  .swatch { width:16px; height:3px; border-radius:2px; display:inline-block; }

  .mapbox { position:relative; background:var(--map-bg); }
  svg { display:block; width:100%; height:auto; }
  .seg { fill:none; stroke-linecap:round; stroke-linejoin:round; cursor:pointer;
         transition:opacity .12s ease; }
  .seg.dim { opacity:.14; }
  .probe { fill:var(--probe); }
  .maskline { fill:none; stroke:var(--muted); stroke-dasharray:5 5; opacity:.75; }
  .sgnpline { fill:none; stroke:var(--muted); stroke-dasharray:2 4; opacity:.5; }
  .frontier { stroke:var(--short); stroke-dasharray:6 4; opacity:.85; }
  .scalebar path { stroke:var(--ink-2); fill:none; }
  .scalebar text { fill:var(--ink-2); font-family:ui-monospace,Menlo,Consolas,monospace; }
  .maplabel { fill:var(--muted); font-family:ui-monospace,Menlo,Consolas,monospace; }

  .tip { position:absolute; pointer-events:none; opacity:0; transform:translate(-50%,-115%);
         background:var(--ink); color:var(--ground); padding:6px 9px; border-radius:6px;
         font-size:11.5px; font-family:ui-monospace,Menlo,Consolas,monospace;
         white-space:nowrap; transition:opacity .1s ease; z-index:5; }
  .tip.on { opacity:1; }

  .tablewrap { overflow:auto; max-height:420px; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th, td { text-align:left; padding:7px 14px; border-bottom:1px solid var(--rule); white-space:nowrap; }
  th { font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
       font-weight:600; position:sticky; top:0; background:var(--surface); z-index:2; }
  td.num { text-align:right; font-family:ui-monospace,Menlo,Consolas,monospace;
           font-variant-numeric:tabular-nums; }
  tbody tr { cursor:pointer; }
  tbody tr:hover, tbody tr.hot { background:color-mix(in srgb, var(--short) 10%, transparent); }
  .pill { display:inline-block; padding:1px 7px; border-radius:99px; font-size:11px; font-weight:600;
          font-family:ui-monospace,Menlo,Consolas,monospace; }
  .pill.s { color:var(--short); background:color-mix(in srgb,var(--short) 15%,transparent); }
  .pill.m { color:var(--mid);   background:color-mix(in srgb,var(--mid) 17%,transparent); }
  .pill.l { color:var(--long);  background:color-mix(in srgb,var(--long) 15%,transparent); }
  .cap { color:var(--muted); font-size:12.5px; padding:10px 14px; border-top:1px solid var(--rule); }
  .note { color:var(--ink-2); font-size:13.5px; max-width:70ch; }
  .note strong { color:var(--ink); }
  @media (prefers-reduced-motion:reduce){ *{transition:none!important;} }
</style>

<div class="wrap"><div class="inner">

  <header>
    <div class="eyebrow">Jam Genome &middot; citywide sweep &middot; day 1 of ~10</div>
    <h1>__NSEG__ road segments found in the first 8 km north of Navy Nagar</h1>
    <p class="lede">Sweeping Greater Mumbai on a 260&nbsp;m grid to enumerate every distinct TomTom
    road segment. Day one covered <b>Colaba through Malabar Hill to Mahalaxmi</b> &mdash; 537 probes,
    <b>__NSEG__ segments</b>, __NSHORT__ of them short enough to measure a single junction. South
    Mumbai's street grid is far richer than the highway corridors: here <b>__PCTSHORT__% are usable</b>,
    against almost none on the WEH mainline.</p>
  </header>

  <div class="prog">
    <div class="track"><div class="fill" style="width:__PCT__%"></div></div>
    <div class="prow"><span>537 of __GRIDTOTAL__ grid cells probed</span><span>__PCT__% complete</span></div>
  </div>

  <div class="stats">
    <div class="stat"><div class="n">537</div><div class="k">probes, zero errors</div></div>
    <div class="stat"><div class="n">__NSEG__</div><div class="k">distinct segments</div></div>
    <div class="stat good"><div class="n">__NSHORT__</div><div class="k">usable &mdash; under 3 km</div></div>
    <div class="stat bad"><div class="n">__NLONG__</div><div class="k">blobs over 10 km</div></div>
  </div>

  <div class="panel">
    <div class="bar">
      <div class="toggle" role="group" aria-label="Map view">
        <button id="bZoom" aria-pressed="true">Swept so far</button>
        <button id="bFull" aria-pressed="false">Whole sweep area</button>
      </div>
      <div class="legend">
        <span><i class="swatch" style="background:var(--short)"></i>&le; 3 km</span>
        <span><i class="swatch" style="background:var(--mid)"></i>3&ndash;10 km</span>
        <span><i class="swatch" style="background:var(--long)"></i>&gt; 10 km</span>
        <span><i class="swatch" style="background:var(--probe);height:5px;width:5px;border-radius:50%"></i>probe</span>
      </div>
    </div>
    <div class="mapbox" id="mapbox">
      <svg id="map" role="img" aria-label="Map of road segments found so far in the Mumbai sweep"></svg>
      <div class="tip mono" id="tip"></div>
    </div>
    <div class="cap" id="cap">Grey dots are the 537 probe points. Hover any segment for its length.</div>
  </div>

  <p class="note"><strong>What the two views show:</strong> <em>Swept so far</em> is day one's territory
  &mdash; the dense tangle of short green segments is South Mumbai's street grid, exactly the resolution
  this project needs. <em>Whole sweep area</em> pulls back to the full Colaba&ndash;Dahisar mask: the
  dashed outline is everything still to probe, the green line marks the frontier, and the long red
  segments already reach far past it, because a single segment can span half the city.</p>

  <div class="panel">
    <div class="tablewrap">
      <table>
        <thead><tr><th>Segment</th><th>Class</th><th class="num">Length</th>
        <th class="num">Free-flow</th><th class="num">Probes</th><th>Verdict</th></tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="cap">All __NSEG__ segments, shortest first. FRC = TomTom road class
    (FRC1 motorway &rarr; FRC7 minor). &ldquo;Probes&rdquo; = how many grid points landed on it.</div>
  </div>

</div></div>

<script>
const D = __DATA__;
const svg=document.getElementById('map'), tip=document.getElementById('tip'),
      mapbox=document.getElementById('mapbox'), tbody=document.getElementById('tbody');
const NS='http://www.w3.org/2000/svg';
const cls=km=>km<=3?'short':(km<=10?'mid':'long');
const col=km=>'var(--'+cls(km)+')';

const pv=[]; D.probes.forEach(p=>pv.push(p));
const sv=[]; D.segs.forEach(s=>s.pts.forEach(p=>sv.push(p)));
const mv=D.mask;
function bbox(pts,pad){return {x0:Math.min(...pts.map(p=>p[0]))-pad,x1:Math.max(...pts.map(p=>p[0]))+pad,
                               y0:Math.min(...pts.map(p=>p[1]))-pad,y1:Math.max(...pts.map(p=>p[1]))+pad};}
const zoomBox=bbox(pv,0.6), fullBox=bbox(mv.concat(sv),0.8);
function fit(b,r){let w=b.x1-b.x0,h=b.y1-b.y0,cx=(b.x0+b.x1)/2,cy=(b.y0+b.y1)/2;
  if(w/h<r)w=h*r;else h=w/r;return{x0:cx-w/2,y0:cy-h/2,w,h};}
const poly=pts=>pts.map(p=>p[0]+','+p[1]).join(' ');

function draw(mode){
  const ratio = mode==='zoom' ? 1.15 : 0.60;
  const vb=fit(mode==='zoom'?zoomBox:fullBox, ratio);
  svg.setAttribute('viewBox',`${vb.x0} ${vb.y0} ${vb.w} ${vb.h}`);
  svg.style.aspectRatio=ratio;
  svg.replaceChildren();

  if(mode==='full'){
    const m=document.createElementNS(NS,'polygon');
    m.setAttribute('points',poly(D.mask)); m.setAttribute('class','maskline');
    m.setAttribute('vector-effect','non-scaling-stroke'); m.style.strokeWidth=1.4; svg.appendChild(m);
    const g=document.createElementNS(NS,'polygon');
    g.setAttribute('points',poly(D.sgnp)); g.setAttribute('class','sgnpline');
    g.setAttribute('vector-effect','non-scaling-stroke'); g.style.strokeWidth=1.2; svg.appendChild(g);
    const f=document.createElementNS(NS,'line');
    f.setAttribute('x1',vb.x0); f.setAttribute('x2',vb.x0+vb.w);
    f.setAttribute('y1',D.frontier); f.setAttribute('y2',D.frontier);
    f.setAttribute('class','frontier'); f.setAttribute('vector-effect','non-scaling-stroke');
    f.style.strokeWidth=1.5; svg.appendChild(f);
    const t=document.createElementNS(NS,'text');
    t.setAttribute('x',vb.x0+vb.w*0.03); t.setAttribute('y',D.frontier-vb.h*0.008);
    t.setAttribute('class','maplabel'); t.style.fontSize=(vb.h*0.018)+'px';
    t.textContent='frontier - swept below this line'; svg.appendChild(t);
  }

  D.probes.forEach(p=>{
    const c=document.createElementNS(NS,'circle');
    c.setAttribute('cx',p[0]); c.setAttribute('cy',p[1]);
    c.setAttribute('r',vb.w*(mode==='zoom'?0.0022:0.0016));
    c.setAttribute('class','probe'); svg.appendChild(c);
  });

  [...D.segs].sort((a,b)=>b.km-a.km).forEach(s=>{
    const el=document.createElementNS(NS,'polyline');
    el.setAttribute('points',poly(s.pts));
    el.setAttribute('class','seg'); el.setAttribute('data-id',s.id);
    el.style.stroke=col(s.km);
    el.style.strokeWidth=(s.km<=3?2.4:1.7);
    el.setAttribute('vector-effect','non-scaling-stroke');
    el.addEventListener('pointerenter',()=>hot(s.id));
    el.addEventListener('pointermove',e=>place(e,s));
    el.addEventListener('pointerleave',cool);
    svg.appendChild(el);
  });

  const km = mode==='zoom'?1:5;
  const g=document.createElementNS(NS,'g'); g.setAttribute('class','scalebar');
  const x=vb.x0+vb.w*0.06, y=vb.y0+vb.h*0.95;
  const ln=document.createElementNS(NS,'path');
  ln.setAttribute('d',`M${x} ${y} h${km} M${x} ${y-vb.h*.012} v${vb.h*.024} M${x+km} ${y-vb.h*.012} v${vb.h*.024}`);
  ln.setAttribute('vector-effect','non-scaling-stroke'); ln.style.strokeWidth=1.2;
  const tx=document.createElementNS(NS,'text');
  tx.setAttribute('x',x); tx.setAttribute('y',y-vb.h*.022);
  tx.style.fontSize=(vb.h*0.024)+'px'; tx.textContent=km+' km';
  g.appendChild(ln); g.appendChild(tx); svg.appendChild(g);
}

function hot(id){
  svg.querySelectorAll('.seg').forEach(e=>e.classList.toggle('dim',e.dataset.id!==id));
  tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('hot'));
  const row=tbody.querySelector('tr[data-id="'+id+'"]');
  if(row){row.classList.add('hot'); row.scrollIntoView({block:'nearest'});}
}
function cool(){
  svg.querySelectorAll('.seg').forEach(e=>e.classList.remove('dim'));
  tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('hot'));
  tip.classList.remove('on');
}
function place(e,s){
  const r=mapbox.getBoundingClientRect();
  tip.style.left=(e.clientX-r.left)+'px'; tip.style.top=(e.clientY-r.top)+'px';
  tip.textContent=`${s.id} · ${s.frc} · ${s.km} km · ${s.ff} km/h free-flow`;
  tip.classList.add('on');
}

D.segs.forEach(s=>{
  const c=cls(s.km);
  const tr=document.createElement('tr'); tr.dataset.id=s.id;
  tr.innerHTML='<td class="mono">'+s.id+'</td><td class="mono">'+s.frc+'</td>'+
    '<td class="num">'+s.km.toFixed(2)+' km</td><td class="num">'+s.ff+'</td>'+
    '<td class="num">'+s.hits+'</td>'+
    '<td><span class="pill '+c[0]+'">'+(c==='short'?'usable':c==='mid'?'coarse':'unusable')+'</span></td>';
  tr.addEventListener('pointerenter',()=>hot(s.id));
  tr.addEventListener('pointerleave',cool);
  tbody.appendChild(tr);
});

const bZoom=document.getElementById('bZoom'), bFull=document.getElementById('bFull'),
      cap=document.getElementById('cap');
function setMode(m){
  bZoom.setAttribute('aria-pressed',m==='zoom'); bFull.setAttribute('aria-pressed',m!=='zoom');
  cap.textContent = m==='zoom'
    ? 'Grey dots are the 537 probe points. Hover any segment for its length.'
    : 'Dashed outline = full Colaba-Dahisar sweep area; inner dashes = national park, skipped.';
  draw(m);
}
bZoom.addEventListener('click',()=>setMode('zoom'));
bFull.addEventListener('click',()=>setMode('full'));
setMode('zoom');
window.addEventListener('resize',()=>setMode(bZoom.getAttribute('aria-pressed')==='true'?'zoom':'full'));
</script>
"""

HTML = (HTML.replace("__DATA__", js)
            .replace("__NSEG__", str(len(out_segs)))
            .replace("__NSHORT__", str(n_short))
            .replace("__NLONG__", str(n_long))
            .replace("__PCTSHORT__", str(round(n_short / len(out_segs) * 100)))
            .replace("__GRIDTOTAL__", f"{grid_total:,}")
            .replace("__PCT__", f"{pct:.1f}"))

dest = SP / "sweep_map.html"
dest.write_text(HTML, encoding="utf-8")
print("wrote", dest, round(len(HTML) / 1024, 1), "KB")
print(f"segments={len(out_segs)} short={n_short} long={n_long} pct={pct:.1f}")
