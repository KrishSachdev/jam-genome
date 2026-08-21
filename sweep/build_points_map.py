"""Map the proposed monitoring points over the swept segment network.

Shows three things at once:
  * the clean segment network, faint, as context
  * the CURRENT 36 points, split by whether they actually record jams
  * the PROPOSED new points, split by my read of whether they are worth using

The categories for proposed points are judgement, not measurement -- the
sweep never recorded live speeds, so "keep" means "a real arterial where a
jam would be visible", not "a road observed to jam".
"""
import csv
import json
import math
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent

LAT0, LON0 = 19.080, 72.870
KM_LAT, KM_LON = 110.57, 111.32 * math.cos(math.radians(19.08))

# roads that are genuinely fast seafront/expressway routes which rarely jam --
# they score well structurally but waste monitoring budget
SEAFRONT = ("sambhaji maharaj marg", "netaji subhash marg", "sea link")
# lanes and local streets that should not be monitoring points
MINOR = ("lane", "sewri fort", "din quarry", "atmaram sawant", "dattapada",
         "eksar road", "behram baug", "siddheshwar talao", "mohanlal parikh",
         "altamount", "azad maidan")


def categorise(name):
    low = name.lower()
    if any(k in low for k in SEAFRONT):
        return "seafront"
    if any(k in low for k in MINOR):
        return "minor"
    return "keep"


def proj(lat, lon):
    return (round((lon - LON0) * KM_LON, 3), round(-(lat - LAT0) * KM_LAT, 3))


def simplify(pts, tol=0.05):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        span = math.hypot(dx, dy)
        wd, wk = -1.0, None
        for k in range(i + 1, j):
            x0, y0 = pts[k]
            d = (math.hypot(x0 - x1, y0 - y1) if span == 0
                 else abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / span)
            if d > wd:
                wd, wk = d, k
        if wd > tol:
            keep[wk] = True
            stack += [(i, wk), (wk, j)]
    return [p for p, k in zip(pts, keep) if k]


# ---- segment network (faint context) --------------------------------------
st = json.loads((SP / "sweep_state.json").read_text())
net = []
for s in st["segments"].values():
    if not s["geom"] or not s["ff"] or not (0.1 <= s["km"] <= 3 and s["ff"] >= 10):
        continue
    pts = simplify([proj(a, b) for a, b in s["geom"]])
    if len(pts) > 1:
        net.append(pts)

# ---- current points, split by whether they record jams --------------------
jams = {}
lt = ROOT / "analysis" / "outputs" / "league_table.csv"
if lt.exists():
    for r in csv.DictReader(lt.open(encoding="utf-8")):
        jams[r["point_id"]] = int(r["congested_slots"])

current = []
for pt in csv.DictReader((ROOT / "corridors.csv").open(encoding="utf-8")):
    n = jams.get(pt["point_id"], 0)
    x, y = proj(float(pt["lat"]), float(pt["lon"]))
    current.append({"x": x, "y": y, "name": pt["name"], "id": pt["point_id"],
                    "slots": n, "live": n > 0})

# ---- proposed points ------------------------------------------------------
proposed = []
for r in csv.DictReader((SP / "proposed_corridors.csv").open(encoding="utf-8")):
    if r["notes"].startswith("existing point"):
        continue
    x, y = proj(float(r["lat"]), float(r["lon"]))
    proposed.append({"x": x, "y": y, "name": r["name"], "id": r["point_id"],
                     "cat": categorise(r["name"])})

counts = {c: sum(1 for p in proposed if p["cat"] == c) for c in ("keep", "seafront", "minor")}
dead = sum(1 for c in current if not c["live"])
payload = json.dumps({"net": net, "cur": current, "prop": proposed},
                     separators=(",", ":"))
print("payload KB:", round(len(payload) / 1024, 1))

HTML = r"""<title>Jam Genome - proposed monitoring points</title>
<style>
  :root{
    --ground:#f2f4f2;--surface:#fbfcfa;--map-bg:#e9ece8;--ink:#0f1518;--ink-2:#454f53;
    --muted:#79848a;--rule:#dde2dd;--net:#c8cfc9;
    --keep:#0d8a66;--seafront:#b07a12;--minor:#c0442c;--live:#2a78d6;--deadpt:#8d5bd6;
    --shadow:0 1px 2px rgba(15,21,24,.06),0 8px 24px -12px rgba(15,21,24,.18);
  }
  @media (prefers-color-scheme:dark){:root{
    --ground:#0c1013;--surface:#141b1f;--map-bg:#090d10;--ink:#e9edeb;--ink-2:#a5b0b4;
    --muted:#6d7880;--rule:#222c31;--net:#2c3438;
    --keep:#31c99b;--seafront:#e0a63c;--minor:#f06e50;--live:#3987e5;--deadpt:#9085e9;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6);}}
  :root[data-theme="dark"]{
    --ground:#0c1013;--surface:#141b1f;--map-bg:#090d10;--ink:#e9edeb;--ink-2:#a5b0b4;
    --muted:#6d7880;--rule:#222c31;--net:#2c3438;
    --keep:#31c99b;--seafront:#e0a63c;--minor:#f06e50;--live:#3987e5;--deadpt:#9085e9;}
  :root[data-theme="light"]{
    --ground:#f2f4f2;--surface:#fbfcfa;--map-bg:#e9ece8;--ink:#0f1518;--ink-2:#454f53;
    --muted:#79848a;--rule:#dde2dd;--net:#c8cfc9;
    --keep:#0d8a66;--seafront:#b07a12;--minor:#c0442c;--live:#2a78d6;--deadpt:#8d5bd6;}
  *{box-sizing:border-box}
  .wrap{background:var(--ground);color:var(--ink);min-height:100%;padding:26px 20px 38px;
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    font-size:15px;line-height:1.55}
  .inner{max-width:1060px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
  .eyebrow{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;
    letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
  h1{font-size:clamp(21px,3.2vw,29px);line-height:1.2;margin:6px 0 0;font-weight:640;
     letter-spacing:-.018em;text-wrap:balance}
  .lede{color:var(--ink-2);max-width:64ch;margin:10px 0 0}
  .lede b{color:var(--ink);font-weight:620}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
    background:var(--rule);border:1px solid var(--rule);border-radius:9px;overflow:hidden}
  .stat{background:var(--surface);padding:12px 14px}
  .stat .n{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:24px;font-weight:600;
    font-variant-numeric:tabular-nums;letter-spacing:-.02em}
  .stat .k{font-size:12px;color:var(--muted);margin-top:1px}
  .panel{background:var(--surface);border:1px solid var(--rule);border-radius:11px;
    box-shadow:var(--shadow);overflow:hidden}
  .bar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:10px 14px;
    border-bottom:1px solid var(--rule)}
  .legend{display:flex;flex-wrap:wrap;gap:13px;font-size:12px;color:var(--ink-2)}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
  .sq{width:10px;height:10px;display:inline-block;transform:rotate(45deg)}
  .mapbox{position:relative;background:var(--map-bg)}
  svg{display:block;width:100%;height:auto}
  .netline{fill:none;stroke:var(--net);stroke-width:1;stroke-linecap:round}
  .pt{cursor:pointer}
  .tip{position:absolute;pointer-events:none;opacity:0;transform:translate(-50%,-130%);
    background:var(--ink);color:var(--ground);padding:6px 9px;border-radius:6px;
    font-size:11.5px;font-family:ui-monospace,Menlo,Consolas,monospace;white-space:nowrap;
    transition:opacity .1s;z-index:5;max-width:320px}
  .tip.on{opacity:1}
  .cap{color:var(--muted);font-size:12.5px;padding:10px 14px;border-top:1px solid var(--rule)}
  .tablewrap{overflow:auto;max-height:360px}
  table{border-collapse:collapse;width:100%;font-size:13px}
  th,td{text-align:left;padding:6px 14px;border-bottom:1px solid var(--rule);white-space:nowrap}
  th{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
     font-weight:600;position:sticky;top:0;background:var(--surface);z-index:2}
  .pill{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;font-weight:600;
    font-family:ui-monospace,Menlo,Consolas,monospace}
  .pill.keep{color:var(--keep);background:color-mix(in srgb,var(--keep) 15%,transparent)}
  .pill.seafront{color:var(--seafront);background:color-mix(in srgb,var(--seafront) 18%,transparent)}
  .pill.minor{color:var(--minor);background:color-mix(in srgb,var(--minor) 15%,transparent)}
  .note{color:var(--ink-2);font-size:13.5px;max-width:70ch}
  .note strong{color:var(--ink)}
  @media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
<div class="wrap"><div class="inner">
  <header>
    <div class="eyebrow">Jam Genome &middot; point selection review</div>
    <h1>Where the __NKEEP__ worth-keeping proposals sit &mdash; and where __NDEAD__ current points are blind</h1>
    <p class="lede">Grey lines are every usable road segment the sweep found. Circles are the
    <b>points you monitor today</b>: blue ones record real jams, purple ones have recorded
    <b>zero congestion in 29 days</b> because they sit on segments too long to show one.
    Diamonds are the <b>proposed additions</b>, coloured by whether they are worth using.
    Hover anything for its name.</p>
  </header>
  <div class="stats">
    <div class="stat"><div class="n" style="color:var(--live)">__NLIVE__</div><div class="k">current points that work</div></div>
    <div class="stat"><div class="n" style="color:var(--deadpt)">__NDEAD__</div><div class="k">current points recording nothing</div></div>
    <div class="stat"><div class="n" style="color:var(--keep)">__NKEEP__</div><div class="k">proposals worth keeping</div></div>
    <div class="stat"><div class="n" style="color:var(--minor)">__NREJECT__</div><div class="k">proposals to reject</div></div>
  </div>
  <div class="panel">
    <div class="bar"><div class="legend">
      <span><i class="dot" style="background:var(--live)"></i>current &mdash; records jams</span>
      <span><i class="dot" style="background:var(--deadpt)"></i>current &mdash; blind</span>
      <span><i class="sq" style="background:var(--keep)"></i>proposed &mdash; keep</span>
      <span><i class="sq" style="background:var(--seafront)"></i>proposed &mdash; rarely jams</span>
      <span><i class="sq" style="background:var(--minor)"></i>proposed &mdash; minor lane</span>
    </div></div>
    <div class="mapbox" id="mapbox">
      <svg id="map" role="img" aria-label="Map of current and proposed Mumbai monitoring points"></svg>
      <div class="tip" id="tip"></div>
    </div>
    <div class="cap">Every grey line is a road segment short enough (0.1&ndash;3 km) to measure one junction.</div>
  </div>
  <p class="note"><strong>How to read it:</strong> purple circles are the problem &mdash; famous
  chokepoints like Kalanagar and Amar Mahal that have logged no congestion at all. Almost every one
  has grey segments running right past it, meaning the fix is a small coordinate nudge rather than a
  new point. The amber diamonds cluster on Marine Drive and the Sea Link: fast roads that score well
  structurally but rarely jam, which is the limit of ranking without live speed data.</p>
  <div class="panel"><div class="tablewrap"><table>
    <thead><tr><th>Proposed point</th><th>Road</th><th>Verdict</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table></div><div class="cap">Verdict is judgement from road names, not measurement.</div></div>
</div></div>
<script>
const D=__DATA__;
const svg=document.getElementById('map'),tip=document.getElementById('tip'),
      mapbox=document.getElementById('mapbox'),tbody=document.getElementById('tbody');
const NS='http://www.w3.org/2000/svg';
let all=[];D.net.forEach(l=>l.forEach(p=>all.push(p)));
D.cur.concat(D.prop).forEach(p=>all.push([p.x,p.y]));
const pad=0.7;
const b={x0:Math.min(...all.map(p=>p[0]))-pad,x1:Math.max(...all.map(p=>p[0]))+pad,
         y0:Math.min(...all.map(p=>p[1]))-pad,y1:Math.max(...all.map(p=>p[1]))+pad};
const ratio=0.62;
let w=b.x1-b.x0,h=b.y1-b.y0,cx=(b.x0+b.x1)/2,cy=(b.y0+b.y1)/2;
if(w/h<ratio)w=h*ratio;else h=w/ratio;
const vb={x0:cx-w/2,y0:cy-h/2,w,h};
svg.setAttribute('viewBox',`${vb.x0} ${vb.y0} ${vb.w} ${vb.h}`);
svg.style.aspectRatio=ratio;
D.net.forEach(l=>{const e=document.createElementNS(NS,'polyline');
  e.setAttribute('points',l.map(p=>p[0]+','+p[1]).join(' '));
  e.setAttribute('class','netline');e.setAttribute('vector-effect','non-scaling-stroke');
  svg.appendChild(e);});
function show(e,txt){const r=mapbox.getBoundingClientRect();
  tip.style.left=(e.clientX-r.left)+'px';tip.style.top=(e.clientY-r.top)+'px';
  tip.textContent=txt;tip.classList.add('on');}
function hide(){tip.classList.remove('on');}
D.cur.forEach(p=>{const c=document.createElementNS(NS,'circle');
  c.setAttribute('cx',p.x);c.setAttribute('cy',p.y);c.setAttribute('r',vb.w*0.006);
  c.setAttribute('class','pt');c.style.fill=p.live?'var(--live)':'var(--deadpt)';
  c.style.stroke='var(--map-bg)';c.style.strokeWidth=vb.w*0.0016;
  c.addEventListener('pointermove',e=>show(e,`${p.id} - ${p.live?p.slots+' congested slots':'NO congestion recorded'}`));
  c.addEventListener('pointerleave',hide);svg.appendChild(c);});
D.prop.forEach(p=>{const s=vb.w*0.0055;
  const e=document.createElementNS(NS,'rect');
  e.setAttribute('x',p.x-s);e.setAttribute('y',p.y-s);
  e.setAttribute('width',s*2);e.setAttribute('height',s*2);
  e.setAttribute('transform',`rotate(45 ${p.x} ${p.y})`);
  e.setAttribute('class','pt');e.style.fill='var(--'+p.cat+')';
  e.style.stroke='var(--map-bg)';e.style.strokeWidth=vb.w*0.0014;
  e.addEventListener('pointermove',ev=>show(ev,p.name));
  e.addEventListener('pointerleave',hide);svg.appendChild(e);});
const label={keep:'keep',seafront:'rarely jams',minor:'minor lane'};
D.prop.slice().sort((a,b)=>a.cat.localeCompare(b.cat)).forEach(p=>{
  const tr=document.createElement('tr');
  tr.innerHTML=`<td style="font-family:ui-monospace,monospace">${p.id}</td><td>${p.name}</td>`+
    `<td><span class="pill ${p.cat}">${label[p.cat]}</span></td>`;
  tbody.appendChild(tr);});
</script>
"""

HTML = (HTML.replace("__DATA__", payload)
            .replace("__NKEEP__", str(counts["keep"]))
            .replace("__NREJECT__", str(counts["seafront"] + counts["minor"]))
            .replace("__NDEAD__", str(dead))
            .replace("__NLIVE__", str(len(current) - dead)))

dest = SP / "points_map.html"
dest.write_text(HTML, encoding="utf-8")
print(f"wrote {dest} {round(len(HTML)/1024,1)} KB")
print(f"keep={counts['keep']} seafront={counts['seafront']} minor={counts['minor']} dead_current={dead}")
