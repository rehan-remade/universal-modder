'use strict';
// ---------- utilities ----------
const $ = id => document.getElementById(id);
const fmt = n => (n == null || isNaN(n)) ? '–' : Math.round(n).toLocaleString('en-US');
const dec = (n, d = 1) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const din = n => '₡' + fmt(n);
function curto(n) {
  const a = Math.abs(n);
  if (a >= 1e9) return dec(n / 1e9, 2) + ' B';
  if (a >= 1e6) return dec(n / 1e6, 2) + ' M';
  if (a >= 1e4) return dec(n / 1e3, 0) + 'k';
  return fmt(n);
}
const pc = (a, b) => b > 0 ? a / b * 100 : 0;
const pct = (a, b) => fmt(pc(a, b)) + '%';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
const lim = (v, a, b) => Math.max(a, Math.min(b, v));
function dataBR(s) { const p = String(s).split('-'); return p.length === 3 ? p[2] + '/' + p[1] + '/' + p[0] : s; }

window.addEventListener('error', e => { const d = $('erro'); d.hidden = false; d.textContent = 'Page error: ' + e.message + ' (line ' + e.lineno + ')'; });

// ---------- state ----------
const E = {
  c: null,      // /api/cidade
  m: null,      // /api/mapa (decoded)
  sv: null,     // /api/servicos
  h: null,      // /api/historico
  x: null,      // numbers derived from the map (coverage etc.)
  sug: [],      // advisor suggestions
  visao: 'cidade', sub: {}, sel: null, focos: [], vivo: false, noMenu: false,
  ms: {},       // cost of each route's last collection, in ms (measured by the mod)
  ritmo: {}     // actual interval between refreshes, in s
};
let F = {};     // index of each building's fields

// ---------- vocabulary ----------
const ZONAS = {
  rb: { nome: 'Low-density residential', cor: '#8fce4e' }, ra: { nome: 'High-density residential', cor: '#3f9a2c' },
  cb: { nome: 'Low-density commercial', cor: '#72bdf2' }, ca: { nome: 'High-density commercial', cor: '#2a78d6' },
  in: { nome: 'Industry', cor: '#eda100' }, es: { nome: 'Offices', cor: '#22b3ae' },
  pq: { nome: 'Parks and plazas', cor: '#c5e3a0' }, sv: { nome: 'Public services', cor: '#6a4fb0' }
};
const ZONA_JOGO = { 2: 'rb', 3: 'ra', 4: 'cb', 5: 'ca', 6: 'in', 7: 'es' };   // ItemClass.Zone
function zonaDe(serv, sub) {
  if (serv === 'Residential') return sub.indexOf('High') >= 0 ? 'ra' : 'rb';
  if (serv === 'Commercial') return (sub.indexOf('Low') >= 0) ? 'cb' : 'ca';
  if (serv === 'Industrial') return 'in';
  if (serv === 'Office') return 'es';
  if (serv === 'Beautification') return 'pq';
  return 'sv';
}
const SERVICO = {
  Electricity: 'Electricity', Water: 'Water and sewage', Garbage: 'Garbage', HealthCare: 'Healthcare and deathcare', FireDepartment: 'Fire department', PoliceDepartment: 'Police',
  Education: 'Education', Road: 'Roads', Beautification: 'Parks and plazas', Monument: 'Unique buildings', PublicTransport: 'Transport', Residential: 'Residential',
  Commercial: 'Commercial', Industrial: 'Industry', Office: 'Offices', Citizen: 'Citizens (fees)', Tourism: 'Tourism', Disaster: 'Disasters',
  PlayerIndustry: 'Industry areas', PlayerEducation: 'Campus', Museums: 'Museums', VarsitySports: 'Sports', Fishing: 'Fishing', ServicePoint: 'Service points', Hotel: 'Hotels'
};
const PROB = {
  Electricity: 'No electricity', ElectricityNotConnected: 'Not connected to the power grid', Water: 'No water', WaterNotConnected: 'No water connection', Sewage: 'Sewage backing up',
  DirtyWater: 'Contaminated water', Flood: 'Flooding', Garbage: 'Garbage piling up', LandfillFull: 'Landfill full', Death: 'Body waiting for pickup', Crime: 'High crime',
  Fire: 'Fire', Pollution: 'Ground pollution', Noise: 'Noise', NoCustomers: 'No customers', NoGoods: 'No goods to sell', NoResources: 'No raw materials',
  NoPlaceforGoods: 'Storage full, cannot ship', NoWorkers: 'No workers', NoEducatedWorkers: 'Not enough educated workers', NoInputProducts: 'No input products',
  NoFood: 'No food', TooFewServices: 'Too few services nearby', LandValueLow: 'Low land value', TaxesTooHigh: 'Taxes too high', RoadNotConnected: 'No road access',
  LineNotConnected: 'Line not connected', TurnedOff: 'Turned off', Heating: 'No heating', Snow: 'Snow', DepotNotConnected: 'No depot', Abandoned: 'Abandoned',
  BurnedDown: 'Burned down', NoPark: 'No park area', PathNotConnected: 'No pedestrian path', NoFuel: 'No fuel', Evacuating: 'Evacuating',
  NoNaturalResources: 'Natural resource depleted', ResourceNotSelected: 'Resource not selected', StructureDamaged: 'Structure damaged', StructureVisited: 'Structure inspected'
};
function traduzProblemas(s) {
  if (!s) return [];
  const grave = /MajorProblem|FatalProblem/.test(s);
  return s.split(',').map(t => t.trim()).filter(t => t && t !== 'MajorProblem' && t !== 'FatalProblem').map(t => (PROB[t] || t) + (grave ? ' (major)' : ''));
}
const REDE_PT = {
  'Highway': 'Highway', 'HighwayRamp': 'Highway ramp', 'Basic Road': 'Two-lane road', 'Medium Road': 'Four-lane road', 'Large Road': 'Six-lane road',
  'Oneway Road': 'One-way road', 'Gravel Road': 'Gravel road', 'Train Track': 'Railway', 'Train Cargo Track': 'Cargo railway', 'Train Station Track': 'Station track',
  'Metro Track': 'Metro', 'Water Pipe': 'Water pipe', 'Pedestrian Gravel': 'Pedestrian path', 'Pedestrian Pavement': 'Pedestrian street', 'Harbor Road': 'Harbor road', 'Highway Connection': 'Highway connection', 'Large Oneway': 'One-way avenue', 'Medium Road Decoration Trees': 'Tree-lined avenue', 'Basic Road Decoration Trees': 'Tree-lined road', 'Bus Station Stop': 'Bus bay', 'Power Line': 'Power line'
};
function redePT(n) {
  const base = n.replace(/ ?(Elevated|Bridge|Tunnel|Slope)$/, '');
  const suf = / Elevated$|Elevated$/.test(n) ? ' (elevated)' : /Bridge$/.test(n) ? ' (bridge)' : /Tunnel$/.test(n) ? ' (tunnel)' : '';
  return (REDE_PT[base] || n) + suf;
}

// ---------- data ----------
async function pega(rota) { const r = await fetch('/api/' + rota, { cache: 'no-store' }); return r.json(); }
// Same, but returns the text (to skip the work when nothing changed) and records how much the collection cost inside the game.
async function pegaTexto(rota) {
  const r = await fetch('/api/' + rota, { cache: 'no-store' }), ms = r.headers.get('X-Coleta-Ms');
  if (ms != null) E.ms[rota] = +ms;
  return r.text();
}
const espera = ms => new Promise(r => setTimeout(r, ms));
const amostra = s => { let h = s.length; for (let i = 0; i < s.length; i += 61) h = (h * 31 + s.charCodeAt(i)) | 0; return h; };
function b64(s) { const b = atob(s || ''); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }

const COBERTURAS = ['bombeiros', 'policia', 'saudeCob', 'funeraria', 'fundamental', 'medio', 'superior', 'transporte', 'lazer'];
const ESCALAVEIS = COBERTURAS.concat(['valorTerreno', 'ruido', 'crime', 'lixo', 'moradores']);

function prepararMapa(m) {
  F = {}; m.camposPredio.forEach((n, i) => F[n] = i);
  m.tipos = m.tiposRede.map(t => { const p = t.split('|'); return { nome: p[0], serv: p[1], hw: +p[2] }; });
  m.cls = m.classes.map(c => { const p = c.split('/'); return { s: p[0], sub: p[1], z: zonaDe(p[0], p[1]), zoneado: /^(Residential|Commercial|Industrial|Office)$/.test(p[0]) }; });
  const t = m.terreno;
  const r = t.recursos;
  t.chave = [m.caixa.join(','), amostra(t.alturas), amostra(t.agua), r ? amostra(r.floresta) + amostra(r.arvores) : 0].join('|');   // changes only when the terrain, the water or the forest change
  t.h = b64(t.alturas); t.w = b64(t.agua);
  if (r) ['minerio', 'petroleo', 'fertil', 'floresta', 'arvores', 'poluicao'].forEach(k => r[k] = b64(r[k]));
  const g = m.gradeDistritos;
  if (g) { g.d = g.distritos ? b64(g.distritos) : null; g.p = g.parques ? b64(g.parques) : null; }
  // derived numbers: coverage of zoned buildings, scales (90th percentile) and useful counts
  const x = { cob: {}, cobRes: {}, topo: {}, zon: 0, res: 0, resPoluidos: 0, resBarulho: 0, semBombeiro: 0 };
  const vals = {}; ESCALAVEIS.forEach(k => vals[k] = []);
  COBERTURAS.forEach(k => { x.cob[k] = 0; x.cobRes[k] = 0; });
  for (const b of m.predios) {
    const c = m.cls[b[F.classe]];
    if (!c.zoneado) continue;
    x.zon++;
    const res = c.s === 'Residential';
    if (res) { x.res++; if (b[F.poluicao] >= 40) x.resPoluidos++; if (b[F.ruido] >= 100) x.resBarulho++; }
    for (const k of COBERTURAS) if (b[F[k]] > 0) { x.cob[k]++; if (res) x.cobRes[k]++; }
    for (const k of ESCALAVEIS) if (b[F[k]] > 0) vals[k].push(b[F[k]]);
  }
  for (const k of ESCALAVEIS) { const v = vals[k].sort((a, b) => a - b); x.topo[k] = v.length ? Math.max(1, v[Math.floor(v.length * 0.9)]) : 1; }
  E.x = x;
  return m;
}

// ---------- HTML components for the panel ----------
const ln = (r, v) => `<div class="ln"><span>${r}</span><b>${v}</b></div>`;
function medidor(rotulo, uso, cap, unid, inverso) {
  // inverted: fuller is better (e.g. treatment vs sick does not use this)
  const p = cap > 0 ? uso / cap * 100 : (uso > 0 ? 100 : 0);
  const s = cap <= 0 && uso > 0 ? 3 : p >= 97 ? 3 : p >= 88 ? 2 : p >= 80 ? 1 : 0;
  return `<div class="med"><div class="tp"><b>${rotulo}</b><span>${fmt(uso)} of ${fmt(cap)} ${unid || ''} (${fmt(p)}%)</span></div>
    <div class="tr" role="img" aria-label="${rotulo}: ${fmt(p)}% in use"><i class="s${s}" style="width:${lim(p, 0, 100)}%"></i></div></div>`;
}
function barras(itens, o) {
  o = o || {};
  const max = o.max || Math.max(1, ...itens.map(i => Math.abs(i.v)));
  return '<div class="bars">' + itens.map(i => `<span class="rt" title="${esc(i.r)}">${esc(i.r)}</span>
    <span class="bx" title="${esc(i.r)}: ${o.fmt ? o.fmt(i.v) : fmt(i.v)}"><i style="width:${lim(Math.abs(i.v) / max * 100, 0, 100)}%;background:${i.cor || o.cor || '#3b79a8'}"></i></span>
    <span class="vl">${o.fmt ? o.fmt(i.v) : fmt(i.v)}${i.extra ? ' <small class="nota">' + i.extra + '</small>' : ''}</span>`).join('') + '</div>';
}
function empilhada(partes, o) {
  o = o || {};
  const tot = partes.reduce((a, p) => a + p.v, 0) || 1;
  return `<div class="emp" role="img" aria-label="${esc(partes.map(p => p.r + ' ' + fmt(pc(p.v, tot)) + '%').join(', '))}">` +
    partes.filter(p => p.v > 0).map(p => `<i style="flex:${p.v};background:${p.cor}" title="${esc(p.r)}: ${o.fmt ? o.fmt(p.v) : fmt(p.v)} (${fmt(pc(p.v, tot))}%)"></i>`).join('') + '</div>' +
    '<div class="leg">' + partes.map(p => `<span><i style="background:${p.cor}"></i>${esc(p.r)} ${o.fmt ? o.fmt(p.v) : fmt(p.v)}${o.semPct ? '' : ' (' + fmt(pc(p.v, tot)) + '%)'}</span>`).join('') + '</div>';
}
const SEVN = ['Tip', 'Warning', 'Serious', 'Critical'];
function cartaoSug(s, i) {
  return `<div class="sug s${s.sev}"><h3><em>${SEVN[s.sev]}</em><span>${esc(s.titulo)}</span></h3><p>${s.texto}</p>` +
    (s.foco ? `<button data-foco="${i}">Show on map</button>` : '') + (s.irPara ? `<button data-ir="${s.irPara}">Open ${esc(nomeVisao(s.irPara))}</button>` : '') + '</div>';
}
function sugestoesDe(area) {
  const l = E.sug.map((s, i) => [s, i]).filter(p => p[0].area === area).sort((a, b) => b[0].sev - a[0].sev);
  if (!l.length) return '<h2>Diagnosis</h2><p class="nota">Nothing to point out here right now.</p>';
  return '<h2>Diagnosis and suggestions</h2>' + l.map(p => cartaoSug(p[0], p[1])).join('');
}

// line chart (SVG) with a crosshair and a tooltip on hover
const CORES_SERIE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'];
function grafico(id, titulo, series, datas, o) {
  o = o || {};
  const W = 370, H = 120, L = 60, Rg = 8, T = 8, B = 18;
  const todos = [].concat(...series.map(s => s.v)).filter(v => isFinite(v));
  if (datas.length < 2) return `<h2>${titulo}</h2><p class="nota">Not enough points yet: the panel records one sample per in-game week while the game runs.</p>`;
  let mn = o.zero ? 0 : Math.min(...todos), mx = Math.max(...todos);
  if (o.max != null) mx = o.max; if (o.min != null) mn = o.min;
  if (mx === mn) { mx += 1; mn -= o.zero ? 0 : 1; }
  const X = i => L + (W - L - Rg) * i / (datas.length - 1), Y = v => T + (H - T - B) * (1 - (v - mn) / (mx - mn));
  const f = o.fmt || curto;
  let g = '';
  for (let k = 0; k <= 2; k++) { const v = mn + (mx - mn) * k / 2, y = Y(v); g += `<line x1="${L}" x2="${W - Rg}" y1="${y}" y2="${y}" stroke="#d3dee6" stroke-width="1"/><text class="eixo" x="${L - 5}" y="${y + 3.5}" text-anchor="end">${f(v)}</text>`; }
  g += `<text class="eixo" x="${L}" y="${H - 3}">${dataBR(datas[0])}</text><text class="eixo" x="${W - Rg}" y="${H - 3}" text-anchor="end">${dataBR(datas[datas.length - 1])}</text>`;
  series.forEach((s, k) => { g += `<path d="${s.v.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join('')}" fill="none" stroke="${s.cor || CORES_SERIE[k]}" stroke-width="2" stroke-linejoin="round"/>`; });
  const leg = series.length > 1 ? '<div class="leg">' + series.map((s, k) => `<span><i style="background:${s.cor || CORES_SERIE[k]}"></i>${esc(s.r)}</span>`).join('') + '</div>' : '';
  GRAFS[id] = { series, datas, X, f, L, W, Rg };
  return `<h2>${titulo}</h2>${leg}<div class="graf" data-graf="${id}"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(titulo)}">${g}<line class="regua" y1="${T}" y2="${H - B}" stroke="#14283a" stroke-width="1" visibility="hidden"/></svg><div class="tip" hidden></div></div>`;
}
const GRAFS = {};
/** "Nice" axis limits and step (1, 2, 2.5, 5 × a power of 10). */
function escalaBoa(mn, mx, n) {
  if (mx === mn) mx = mn + 1;
  const bruto = (mx - mn) / n, p = Math.pow(10, Math.floor(Math.log10(bruto))), f = bruto / p, passo = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  return { mn: Math.floor(mn / passo + 1e-9) * passo, mx: Math.ceil(mx / passo - 1e-9) * passo, passo };
}
const mesAno = s => { const p = String(s).split('-'); return p.length === 3 ? p[1] + '/' + p[0] : s; };
/** Card with a large line chart, for the charts screen. o.foco = enlarged version (a single chart). */
function graficoGrande(id, titulo, series, datas, o) {
  o = o || {};
  const foco = !!o.foco, W = foco ? 1200 : 640, H = foco ? 430 : 250, L = foco ? 86 : 74, Rg = 18, T = 14, B = 30, f = o.fmt || curto;
  if (datas.length < 2) return `<section class="cartao" data-cartao="${id}"><header><h2>${titulo}</h2></header><p class="nota">Not enough points yet: the panel records one sample per in-game week while the game runs.</p></section>`;
  const todos = [].concat(...series.map(s => s.v)).filter(v => isFinite(v));
  let mn = Math.min(...todos), mx = Math.max(...todos);
  if (o.zero) { mn = Math.min(0, mn); mx = Math.max(0, mx); }
  const e = (o.min != null && o.max != null) ? { mn: o.min, mx: o.max, passo: (o.max - o.min) / 4 } : escalaBoa(mn, mx, 4);
  const n = datas.length, X = i => L + (W - L - Rg) * i / (n - 1), Y = v => T + (H - T - B) * (1 - (lim(v, e.mn, e.mx) - e.mn) / (e.mx - e.mn));
  let g = '';
  for (let v = e.mn; v <= e.mx + e.passo / 1e6; v += e.passo) {
    const y = Y(v).toFixed(1), zero = Math.abs(v) < e.passo / 1e6;
    g += `<line x1="${L}" x2="${W - Rg}" y1="${y}" y2="${y}" stroke="${zero ? '#8fa3b3' : '#dbe4ea'}" stroke-width="1"/><text class="eixo" x="${L - 9}" y="${+y + 4.5}" text-anchor="end">${f(Math.abs(v) < e.passo / 1e6 ? 0 : v)}</text>`;
  }
  const nt = Math.min(foco ? 8 : 5, n);
  for (let k = 0; k < nt; k++) { const i = Math.round(k * (n - 1) / (nt - 1)); g += `<text class="eixo" x="${X(i).toFixed(1)}" y="${H - 8}" text-anchor="${k === 0 ? 'start' : k === nt - 1 ? 'end' : 'middle'}">${mesAno(datas[i])}</text>`; }
  const base = Y(lim(0, e.mn, e.mx)).toFixed(1);
  series.forEach((s, k) => {
    const cor = s.cor || CORES_SERIE[k], d = s.v.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join('');
    if (series.length === 1) g += `<path d="${d}L${X(n - 1).toFixed(1)} ${base}L${X(0).toFixed(1)} ${base}Z" fill="${cor}" opacity=".1"/>`;
    g += `<path d="${d}" fill="none" stroke="${cor}" stroke-width="${foco ? 3 : 2.5}" stroke-linejoin="round" stroke-linecap="round"/>`;
    g += `<circle cx="${X(n - 1).toFixed(1)}" cy="${Y(s.v[n - 1]).toFixed(1)}" r="${foco ? 5 : 4}" fill="${cor}" stroke="#fff" stroke-width="2"/>`;
  });
  let cab, leg = '';
  if (series.length === 1) {
    const a = series[0].v[0], b = series[0].v[n - 1], dif = b - a;
    cab = `<div class="agora"><b>${f(b)}</b><span>${dif === 0 ? 'no change' : (dif > 0 ? '▲ ' : '▼ ') + f(Math.abs(dif))} since ${mesAno(datas[0])}</span></div>`;
  } else {
    cab = '';
    leg = '<div class="leg">' + series.map((s, k) => `<span><i style="background:${s.cor || CORES_SERIE[k]}"></i>${esc(s.r)}<b>${f(s.v[n - 1])}</b></span>`).join('') + '</div>';
  }
  GRAFS[id] = { series, datas, X, f, L, W, Rg };
  return `<section class="cartao" data-cartao="${id}" title="${foco ? 'Click to go back to all charts' : 'Click to enlarge'}"><header><h2>${titulo}</h2>${cab}</header>${leg}<div class="graf grande" data-graf="${id}"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(titulo)}">${g}<line class="regua" y1="${T}" y2="${H - B}" stroke="#14283a" stroke-width="1" visibility="hidden"/></svg><div class="tip" hidden></div></div></section>`;
}
document.addEventListener('pointermove', ev => {
  const el = ev.target.closest && ev.target.closest('.graf');
  document.querySelectorAll('.graf .tip').forEach(t => { if (!el || t.parentNode !== el) { t.hidden = true; t.parentNode.querySelector('.regua').setAttribute('visibility', 'hidden'); } });
  if (!el) return;
  const G = GRAFS[el.dataset.graf]; if (!G) return;
  const r = el.querySelector('svg').getBoundingClientRect();
  const vx = (ev.clientX - r.left) / r.width * G.W;
  const i = lim(Math.round((vx - G.L) / (G.W - G.L - G.Rg) * (G.datas.length - 1)), 0, G.datas.length - 1);
  const rg = el.querySelector('.regua'); rg.setAttribute('x1', G.X(i)); rg.setAttribute('x2', G.X(i)); rg.setAttribute('visibility', 'visible');
  const tip = el.querySelector('.tip'); tip.hidden = false;
  tip.innerHTML = '<b>' + dataBR(G.datas[i]) + '</b> ' + G.series.map(s => esc(s.r) + ' ' + G.f(s.v[i])).join(' | ');
  const px = G.X(i) / G.W * r.width;
  tip.style.left = lim(px - tip.offsetWidth / 2, 0, r.width - tip.offsetWidth) + 'px';
});
