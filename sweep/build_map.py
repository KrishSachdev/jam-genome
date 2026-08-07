"""Build the segment-resolution map artifact from the Kalanagar grid scan.

Input: segments.json, written by gridscan.py in this folder.
"""
import json
import math
from pathlib import Path

SP = Path(__file__).resolve().parent
data = json.loads((SP / "segments.json").read_text())
segs = data["segments"]
probes = data["probes"]
lat0, lon0 = data["center"]
HALF = data["half"]

KM_LAT = 110.57
KM_LON = 111.32 * math.cos(math.radians(lat0))


def proj(lat, lon):
    return (round((lon - lon0) * KM_LON, 3), round(-(lat - lat0) * KM_LAT, 3))


out_segs = []
for s in sorted(segs, key=lambda s: s["len_km"]):
    pts = [proj(a, b) for a, b in s["geom"]]
    # drop consecutive duplicates after rounding
    ded = [pts[0]]
    for p in pts[1:]:
        if p != ded[-1]:
            ded.append(p)
    out_segs.append({
        "id": s["seg"][:6],
        "frc": s["frc"],
        "ff": s["ff_speed"],
        "km": s["len_km"],
        "hits": s["hits"],
        "pts": ded,
    })

out_probes = [proj(p["lat"], p["lon"]) + (p["seg"][:6],) for p in probes]
box_half_x = HALF * KM_LON
box_half_y = HALF * KM_LAT

payload = {
    "segs": out_segs,
    "probes": [[x, y, s] for x, y, s in out_probes],
    "box": [round(box_half_x, 3), round(box_half_y, 3)],
}
js = json.dumps(payload, separators=(",", ":"))
print("payload KB:", round(len(js) / 1024, 1))

n_short = sum(1 for s in out_segs if s["km"] <= 3)
n_long = sum(1 for s in out_segs if s["km"] > 10)
longest = max(s["km"] for s in out_segs)

HTML = """<title>Where Mumbai's traffic data actually has resolution</title>
<style>
  :root {
    --ground:#f2f4f2; --surface:#fbfcfa; --map-bg:#e9ece8;
    --ink:#0f1518; --ink-2:#454f53; --muted:#79848a; --rule:#dde2dd;
    --short:#0d8a66; --mid:#b07a12; --long:#c0442c; --probe:#a9b2b4;
    --shadow:0 1px 2px rgba(15,21,24,.06), 0 8px 24px -12px rgba(15,21,24,.18);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ground:#0c1013; --surface:#141b1f; --map-bg:#090d10;
      --ink:#e9edeb; --ink-2:#a5b0b4; --muted:#6d7880; --rule:#222c31;
      --short:#31c99b; --mid:#e0a63c; --long:#f06e50; --probe:#3c474c;
      --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
    }
  }
  :root[data-theme="dark"] {
    --ground:#0c1013; --surface:#141b1f; --map-bg:#090d10;
    --ink:#e9edeb; --ink-2:#a5b0b4; --muted:#6d7880; --rule:#222c31;
    --short:#31c99b; --mid:#e0a63c; --long:#f06e50; --probe:#3c474c;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
  }
  :root[data-theme="light"] {
    --ground:#f2f4f2; --surface:#fbfcfa; --map-bg:#e9ece8;
    --ink:#0f1518; --ink-2:#454f53; --muted:#79848a; --rule:#dde2dd;
    --short:#0d8a66; --mid:#b07a12; --long:#c0442c; --probe:#a9b2b4;
    --shadow:0 1px 2px rgba(15,21,24,.06), 0 8px 24px -12px rgba(15,21,24,.18);
  }

  * { box-sizing:border-box; }
  .wrap {
    background:var(--ground); color:var(--ink);
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    font-size:15px; line-height:1.55;
    padding:28px 22px 40px; min-height:100%;
  }
  .inner { max-width:1080px; margin:0 auto; display:flex; flex-direction:column; gap:22px; }

  .mono { font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace; }
  .eyebrow {
    font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
    font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted);
  }
  h1 { font-size:clamp(22px,3.4vw,31px); line-height:1.18; margin:6px 0 0;
       font-weight:640; letter-spacing:-.018em; text-wrap:balance; }
  .lede { color:var(--ink-2); max-width:64ch; margin:10px 0 0; }
  .lede b { color:var(--ink); font-weight:620; }

  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1px;
           background:var(--rule); border:1px solid var(--rule); border-radius:9px; overflow:hidden; }
  .stat { background:var(--surface); padding:13px 15px; }
  .stat .n { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
             font-size:25px; font-weight:600; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
  .stat .k { font-size:12px; color:var(--muted); margin-top:1px; }
  .stat.good .n { color:var(--short); }
  .stat.bad .n { color:var(--long); }

  .panel { background:var(--surface); border:1px solid var(--rule); border-radius:11px;
           box-shadow:var(--shadow); overflow:hidden; }
  .bar { display:flex; flex-wrap:wrap; align-items:center; gap:12px;
         padding:11px 14px; border-bottom:1px solid var(--rule); }
  .toggle { display:flex; gap:2px; background:var(--ground); border:1px solid var(--rule);
            border-radius:7px; padding:2px; }
  .toggle button {
    font:inherit; font-size:12.5px; font-weight:550; color:var(--ink-2);
    background:transparent; border:0; border-radius:5px; padding:5px 12px; cursor:pointer;
  }
  .toggle button[aria-pressed="true"] { background:var(--surface); color:var(--ink); box-shadow:var(--shadow); }
  .toggle button:focus-visible { outline:2px solid var(--short); outline-offset:1px; }

  .legend { display:flex; flex-wrap:wrap; gap:14px; margin-left:auto; font-size:12px; color:var(--ink-2); }
  .legend span { display:inline-flex; align-items:center; gap:6px; }
  .swatch { width:16px; height:3px; border-radius:2px; display:inline-block; }

  .mapbox { position:relative; background:var(--map-bg); }
  svg { display:block; width:100%; height:auto; }
  .seg { fill:none; stroke-linecap:round; stroke-linejoin:round; cursor:pointer;
         transition:stroke-width .12s ease, opacity .12s ease; }
  .seg.dim { opacity:.16; }
  .probe { fill:var(--probe); }
  .boxline { fill:none; stroke:var(--muted); stroke-dasharray:4 4; stroke-width:1; opacity:.8; }
  .scalebar line, .scalebar path { stroke:var(--ink-2); stroke-width:1.2; }
  .scalebar text { fill:var(--ink-2); font-size:10px;
                   font-family:ui-monospace,Menlo,Consolas,monospace; }

  .tip { position:absolute; pointer-events:none; opacity:0; transform:translate(-50%,-115%);
         background:var(--ink); color:var(--ground); padding:6px 9px; border-radius:6px;
         font-size:11.5px; font-family:ui-monospace,Menlo,Consolas,monospace;
         white-space:nowrap; transition:opacity .1s ease; z-index:5; }
  .tip.on { opacity:1; }

  .tablewrap { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th, td { text-align:left; padding:7px 14px; border-bottom:1px solid var(--rule); white-space:nowrap; }
  th { font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
       font-weight:600; position:sticky; top:0; background:var(--surface); }
  td.num { text-align:right; font-family:ui-monospace,Menlo,Consolas,monospace;
           font-variant-numeric:tabular-nums; }
  tbody tr { cursor:pointer; }
  tbody tr:hover, tbody tr.hot { background:color-mix(in srgb, var(--short) 9%, transparent); }
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
    <div class="eyebrow">Jam Genome &middot; segment resolution probe &middot; 26 Jul 2026</div>
    <h1>100 probes over one Mumbai junction returned __NSEG__ distinct road segments</h1>
    <p class="lede">Every reading TomTom returns belongs to a whole <b>road segment</b>, not to the
    coordinate you asked about. Segment length is therefore the real resolution limit. Probing a
    2.4&nbsp;km box around Kalanagar on a 260&nbsp;m grid found __NSEG__ different segments &mdash;
    <b>__NSHORT__ of them short enough to watch a single junction</b>, and __NLONG__ that sprawl past
    10&nbsp;km and average a whole highway into one number.</p>
  </header>

  <div class="stats">
    <div class="stat"><div class="n">100</div><div class="k">probe points, 260 m apart</div></div>
    <div class="stat"><div class="n">__NSEG__</div><div class="k">distinct segments hit</div></div>
    <div class="stat good"><div class="n">__NSHORT__</div><div class="k">usable &mdash; under 3 km</div></div>
    <div class="stat bad"><div class="n">__LONGEST__ km</div><div class="k">longest single segment</div></div>
  </div>

  <div class="panel">
    <div class="bar">
      <div class="toggle" role="group" aria-label="Map view">
        <button id="bZoom" aria-pressed="true">Study box</button>
        <button id="bFull" aria-pressed="false">True extent</button>
      </div>
      <div class="legend">
        <span><i class="swatch" style="background:var(--short)"></i>&le; 3 km</span>
        <span><i class="swatch" style="background:var(--mid)"></i>3&ndash;10 km</span>
        <span><i class="swatch" style="background:var(--long)"></i>&gt; 10 km</span>
        <span><i class="swatch" style="background:var(--probe);height:6px;width:6px;border-radius:50%"></i>probe</span>
      </div>
    </div>
    <div class="mapbox" id="mapbox">
      <svg id="map" role="img" aria-label="Map of distinct TomTom road segments around Kalanagar junction"></svg>
      <div class="tip mono" id="tip"></div>
    </div>
    <div class="cap" id="cap">Dashed square = the 2.4 km probe box. Hover any segment for its length.</div>
  </div>

  <p class="note"><strong>Read it this way:</strong> in <em>Study box</em> the short segments pack
  tightly around the junction &mdash; that is the resolution you want, and it is available. Switch to
  <em>True extent</em> and the same four red segments unfurl across 22 km of Mumbai. A point dropped on
  one of those reports the average of an entire highway, which is why Kalanagar currently logs zero
  congested slots.</p>

  <div class="panel">
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>Segment</th><th>Class</th><th class="num">Length</th><th class="num">Free-flow</th>
          <th class="num">Probes</th><th>Verdict</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="cap">FRC = TomTom road class. FRC1 motorway, FRC2 arterial, FRC4 local road.
    &ldquo;Probes&rdquo; is how many of the 100 grid points landed on that segment.</div>
  </div>

</div></div>

<script>
const D = __DATA__;
const svg = document.getElementById('map'), tip = document.getElementById('tip'),
      mapbox = document.getElementById('mapbox'), tbody = document.getElementById('tbody');
const NS = 'http://www.w3.org/2000/svg';
const cls = km => km <= 3 ? 'short' : (km <= 10 ? 'mid' : 'long');
const col = km => 'var(--' + cls(km) + ')';

let all = [];
D.segs.forEach(s => { s.pts.forEach(p => all.push(p)); });
const pad = 0.35;
const fullBox = {
  x0: Math.min(...all.map(p=>p[0])) - pad, x1: Math.max(...all.map(p=>p[0])) + pad,
  y0: Math.min(...all.map(p=>p[1])) - pad, y1: Math.max(...all.map(p=>p[1])) + pad
};
const zoomBox = { x0:-D.box[0]-.25, x1:D.box[0]+.25, y0:-D.box[1]-.25, y1:D.box[1]+.25 };

function aspectFit(b, targetRatio){
  let w = b.x1-b.x0, h = b.y1-b.y0, cx=(b.x0+b.x1)/2, cy=(b.y0+b.y1)/2;
  if (w/h < targetRatio) w = h*targetRatio; else h = w/targetRatio;
  return {x0:cx-w/2, y0:cy-h/2, w, h};
}

function draw(mode){
  const ratio = mode==='zoom' ? 1.35 : 0.62;
  const vb = aspectFit(mode==='zoom' ? zoomBox : fullBox, ratio);
  svg.setAttribute('viewBox', `${vb.x0} ${vb.y0} ${vb.w} ${vb.h}`);
  svg.style.aspectRatio = ratio;
  svg.replaceChildren();

  const box = document.createElementNS(NS,'rect');
  box.setAttribute('x',-D.box[0]); box.setAttribute('y',-D.box[1]);
  box.setAttribute('width',D.box[0]*2); box.setAttribute('height',D.box[1]*2);
  box.setAttribute('class','boxline'); box.setAttribute('vector-effect','non-scaling-stroke');
  svg.appendChild(box);

  if (mode==='zoom'){
    D.probes.forEach(p=>{
      const c=document.createElementNS(NS,'circle');
      c.setAttribute('cx',p[0]); c.setAttribute('cy',p[1]);
      c.setAttribute('r', vb.w*0.0035); c.setAttribute('class','probe');
      svg.appendChild(c);
    });
  }

  [...D.segs].sort((a,b)=>b.km-a.km).forEach(s=>{
    const el=document.createElementNS(NS,'polyline');
    el.setAttribute('points', s.pts.map(p=>p[0]+','+p[1]).join(' '));
    el.setAttribute('class','seg'); el.setAttribute('data-id', s.id);
    el.style.stroke = col(s.km);
    el.style.strokeWidth = (s.km<=3 ? 2.6 : 1.9);
    el.setAttribute('vector-effect','non-scaling-stroke');
    el.addEventListener('pointerenter', e=>hot(s.id, e));
    el.addEventListener('pointermove', e=>place(e, s));
    el.addEventListener('pointerleave', cool);
    svg.appendChild(el);
  });

  // scale bar: 1 km in zoom, 5 km in full
  const km = mode==='zoom' ? 1 : 5;
  const g=document.createElementNS(NS,'g'); g.setAttribute('class','scalebar');
  const x=vb.x0+vb.w*0.06, y=vb.y0+vb.h*0.94;
  const ln=document.createElementNS(NS,'path');
  ln.setAttribute('d',`M${x} ${y} h${km} M${x} ${y-vb.h*.012} v${vb.h*.024} M${x+km} ${y-vb.h*.012} v${vb.h*.024}`);
  ln.setAttribute('vector-effect','non-scaling-stroke'); ln.setAttribute('fill','none');
  const tx=document.createElementNS(NS,'text');
  tx.setAttribute('x',x); tx.setAttribute('y',y-vb.h*.022); tx.textContent=km+' km';
  tx.style.fontSize=(vb.h*0.028)+'px';
  g.appendChild(ln); g.appendChild(tx); svg.appendChild(g);
}

function hot(id){
  svg.querySelectorAll('.seg').forEach(e=>e.classList.toggle('dim', e.dataset.id!==id));
  const row=tbody.querySelector(`tr[data-id="${id}"]`);
  tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('hot'));
  if(row) row.classList.add('hot');
}
function cool(){
  svg.querySelectorAll('.seg').forEach(e=>e.classList.remove('dim'));
  tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('hot'));
  tip.classList.remove('on');
}
function place(e, s){
  const r=mapbox.getBoundingClientRect();
  tip.style.left=(e.clientX-r.left)+'px'; tip.style.top=(e.clientY-r.top)+'px';
  tip.textContent=`${s.id} · ${s.frc} · ${s.km} km · ${s.ff} km/h free-flow`;
  tip.classList.add('on');
}

D.segs.forEach(s=>{
  const c=cls(s.km);
  const tr=document.createElement('tr'); tr.dataset.id=s.id;
  tr.innerHTML = `<td class="mono">${s.id}</td><td class="mono">${s.frc}</td>`+
    `<td class="num">${s.km.toFixed(2)} km</td><td class="num">${s.ff}</td>`+
    `<td class="num">${s.hits}</td>`+
    `<td><span class="pill ${c[0]}">${c==='short'?'usable':(c==='mid'?'coarse':'unusable')}</span></td>`;
  tr.addEventListener('pointerenter',()=>hot(s.id));
  tr.addEventListener('pointerleave',cool);
  tbody.appendChild(tr);
});

const bZoom=document.getElementById('bZoom'), bFull=document.getElementById('bFull');
const cap=document.getElementById('cap');
function setMode(m){
  bZoom.setAttribute('aria-pressed', m==='zoom'); bFull.setAttribute('aria-pressed', m!=='zoom');
  cap.textContent = m==='zoom'
    ? 'Dashed square = the 2.4 km probe box. Hover any segment for its length.'
    : 'Same segments, drawn to their true length. The dashed square is the probe box, now tiny.';
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
            .replace("__LONGEST__", f"{longest:.1f}"))

dest = SP / "segment_map.html"
dest.write_text(HTML, encoding="utf-8")
print("wrote", dest, round(len(HTML) / 1024, 1), "KB")
