// ---------- map ----------
const RAMPAS = {
  azul: ['#cfe1f5', '#a9c9ec', '#7fafe0', '#5693d1', '#3476bb', '#1d589a', '#0f3c74'],
  verde: ['#d8edd0', '#b6dca8', '#8fc77f', '#66b05a', '#43943c', '#297527', '#145517'],
  laranja: ['#fbe0c9', '#f6c399', '#f0a36a', '#e58240', '#cf6423', '#a64a15', '#78340d'],
  roxo: ['#e3dcf4', '#cabdea', '#ad9adc', '#8d74cb', '#6e53b5', '#523a93', '#37256c'],
  vermelho: ['#f8d9d5', '#f0b5af', '#e58d85', '#d7645c', '#bf423b', '#992b27', '#6c1a19'],
  ouro: ['#f5e9bd', '#ecd78a', '#dfc058', '#cba432', '#a9841c', '#806312', '#56410b'],
  ciano: ['#cfecee', '#a3d9dd', '#72c2c8', '#43a8b0', '#248991', '#136a72', '#084a51'],
  marrom: ['#ece0d1', '#d9c4a9', '#c2a47e', '#a88357', '#89653b', '#664927', '#432e18']
};
const NEUTRO = '#cfd5d9', SEM = '#ec835a', GRAVE = '#d03b3b', DESTAQUE = '#14283a';
const CORES_DISTRITO = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
const TRAF = ['#b7c2ca', '#f0b5af', '#e58d85', '#d7645c', '#bf423b', '#8a1f1c'];
const TRAF_ROT = ['free (up to 20%)', '20–40%', '40–60%', '60–80%', '80–95%', 'jammed (95% or more)'];
const binTraf = d => d < 20 ? 0 : d < 40 ? 1 : d < 60 ? 2 : d < 80 ? 3 : d < 95 ? 4 : 5;

const M = { k: 0.1, cx: 0, cz: 0, W: 100, H: 100, dpr: 1, base: null, grade: null, pred: [], pontos: [], marc: [], vaz: [], redes: [], idx: null, ajustado: false, pedido: false };
const cv = $('mapa'), ctx = cv.getContext('2d');

const w2s = (x, z) => [(x - M.cx) * M.k + M.W / 2, (M.cz - z) * M.k + M.H / 2];
const s2w = (px, py) => [(px - M.W / 2) / M.k + M.cx, M.cz - (py - M.H / 2) / M.k];
function mundo() { const d = M.dpr; ctx.setTransform(M.k * d, 0, 0, -M.k * d, (M.W / 2 - M.cx * M.k) * d, (M.H / 2 + M.cz * M.k) * d); }
function tela() { ctx.setTransform(M.dpr, 0, 0, M.dpr, 0, 0); }
function pedir() { if (M.pedido) return; M.pedido = true; requestAnimationFrame(() => { M.pedido = false; desenhar(); }); }

function ajustar(caixa) {
  const c = caixa || (E.m ? E.m.caixa : [-960, -960, 960, 960]);
  M.cx = (c[0] + c[2]) / 2; M.cz = (c[1] + c[3]) / 2;
  M.k = Math.min(M.W / (c[2] - c[0]), M.H / (c[3] - c[1])) * 0.98;
  pedir();
}
function irPara(x, z, k) { M.cx = x; M.cz = z; if (k && M.k < k) M.k = k; pedir(); }
function zoom(f, px, py) {
  if (px == null) { px = M.W / 2; py = M.H / 2; }
  const antes = s2w(px, py);
  M.k = lim(M.k * f, Math.min(M.W, M.H) / 19000, 9);
  const depois = s2w(px, py);
  M.cx += antes[0] - depois[0]; M.cz += antes[1] - depois[1];
  pedir();
}

function hex(c) { return [parseInt(c.substr(1, 2), 16), parseInt(c.substr(3, 2), 16), parseInt(c.substr(5, 2), 16)]; }
function mist(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

/** Shaded relief + water + forest, in an image the size of the terrain grid. */
function montarBase() {
  const t = E.m.terreno, r = t.recursos, natural = V().modo === 'zonas';
  const chave = natural + '|' + t.chave;
  if (M.base && M.baseChave === chave) return;
  M.baseChave = chave;
  const c = document.createElement('canvas'); c.width = t.nx; c.height = t.nz;
  const g = c.getContext('2d'), im = g.createImageData(t.nx, t.nz), d = im.data;
  const baixo = hex(natural ? '#cddcb2' : '#e4e6e0'), alto = hex(natural ? '#ebe3c9' : '#f1f0ea'), mata = hex(natural ? '#86ad72' : '#cdd6c6'), agua = hex(natural ? '#8cc0e4' : '#bfd3e2'), aguaF = hex(natural ? '#6aa6d6' : '#aac4d8');
  const esc = (t.hmax - t.hmin) / 255, x1 = E.m.caixa[0], z1 = E.m.caixa[1];
  const H = (a, b) => t.h[lim(b, 0, t.nz - 1) * t.nx + lim(a, 0, t.nx - 1)] * esc;
  for (let b = 0; b < t.nz; b++) for (let a = 0; a < t.nx; a++) {
    const i = b * t.nx + a, o = i * 4;
    let cor;
    if (t.w[i]) {
      // lighter shore: counts land neighbours
      const borda = !t.w[lim(b, 0, t.nz - 1) * t.nx + lim(a - 1, 0, t.nx - 1)] || !t.w[lim(b, 0, t.nz - 1) * t.nx + lim(a + 1, 0, t.nx - 1)] || !t.w[lim(b - 1, 0, t.nz - 1) * t.nx + a] || !t.w[lim(b + 1, 0, t.nz - 1) * t.nx + a];
      cor = borda ? agua : aguaF;
    } else {
      cor = mist(baixo, alto, lim(t.h[i] / 150, 0, 1));
      if (r) {
        const rx = Math.floor((x1 + a * t.passo - r.x0) / r.passo), rz = Math.floor((z1 + b * t.passo - r.z0) / r.passo);
        if (rx >= 0 && rz >= 0 && rx < r.nx && rz < r.nz) { const f = Math.max(r.floresta[rz * r.nx + rx], r.arvores[rz * r.nx + rx]) / 255; if (f > 0.04) cor = mist(cor, mata, lim(f * 1.6, 0, 0.9)); }
      }
      const dx = (H(a + 1, b) - H(a - 1, b)) / (2 * t.passo), dz = (H(a, b + 1) - H(a, b - 1)) / (2 * t.passo);
      const s = lim(1 + (dz - dx) * 0.9, 0.72, 1.16);   // light coming from the north-west
      cor = [cor[0] * s, cor[1] * s, cor[2] * s];
    }
    d[o] = cor[0]; d[o + 1] = cor[1]; d[o + 2] = cor[2]; d[o + 3] = 255;
  }
  g.putImageData(im, 0, 0);
  M.base = c;
}

/** Grid layer of the view: natural resource, ground pollution or district areas. */
function montarGrade() {
  M.grade = null;
  const v = V(), m = E.m, r = m.terreno.recursos;
  const pintar = (nx, nz, fn) => {
    const c = document.createElement('canvas'); c.width = nx; c.height = nz;
    const g = c.getContext('2d'), im = g.createImageData(nx, nz), d = im.data;
    for (let i = 0; i < nx * nz; i++) { const p = fn(i); if (p) { d[i * 4] = p[0]; d[i * 4 + 1] = p[1]; d[i * 4 + 2] = p[2]; d[i * 4 + 3] = p[3]; } }
    g.putImageData(im, 0, 0); return c;
  };
  if (v.grade && r) {
    const arr = r[rv(v.grade)], cor = hex(rv(v.gradeCor) || '#89653b');
    if (!arr) return;
    M.grade = { img: pintar(r.nx, r.nz, i => arr[i] > 6 ? [cor[0], cor[1], cor[2], lim(60 + arr[i] * 0.75, 0, 235)] : null), x: r.x0, z: r.z0, w: r.nx * r.passo, h: r.nz * r.passo };
  } else if (v.modo === 'distritos' && m.gradeDistritos && (m.gradeDistritos.d || m.gradeDistritos.p)) {
    const g = m.gradeDistritos, cores = CORES_DISTRITO.map(hex);
    M.grade = {
      img: pintar(g.nx, g.nz, i => {
        const di = g.d ? g.d[i] : 0, pk = g.p ? g.p[i] : 0;
        if (di) { const c = cores[(di - 1) % cores.length]; return [c[0], c[1], c[2], 120]; }
        if (pk) return [20, 40, 58, 70];
        return null;
      }), x: m.caixa[0] - g.passo / 2, z: m.caixa[1] - g.passo / 2, w: g.nx * g.passo, h: g.nz * g.passo
    };
  }
}

function retangulo(p, x, z, a, hw, hl) {
  const c = Math.cos(a), s = Math.sin(a), ax = c * hw, az = s * hw, bx = s * hl, bz = -c * hl;
  p.moveTo(x - ax - bx, z - az - bz); p.lineTo(x + ax - bx, z + az - bz); p.lineTo(x + ax + bx, z + az + bz); p.lineTo(x - ax + bx, z - az + bz); p.closePath();
}

/** Colour of a building in the current view. Returns [colour, dot?] — dot = a mark visible from far away. */
function corPredio(b, v) {
  const m = E.m, c = m.cls[b[F.classe]], pr = m.problemas[b[F.problema]];
  const doServico = v.servicos && v.servicos.indexOf(c.s) >= 0;
  let ponto = null;
  if (v.probs && pr) { for (const k of v.probs) if (pr.indexOf(k) >= 0) { ponto = /Major|Fatal/.test(pr) ? GRAVE : SEM; break; } }
  if (v.modo === 'problemas') {
    if (!pr) return [NEUTRO, null];
    const g = /Major|Fatal|Abandoned|BurnedDown/.test(pr);
    return [g ? GRAVE : SEM, g ? GRAVE : SEM];
  }
  if (v.modo === 'zonas') return [ZONAS[c.z].cor, ponto];
  if (v.modo === 'emprego') return [c.s === 'Residential' ? NEUTRO : ZONAS[c.z].cor, ponto];
  if (!c.zoneado) return [doServico ? DESTAQUE : NEUTRO, ponto];
  if (v.modo === 'servico') return [ponto || v.corOk, ponto];
  if (v.modo === 'campo') {
    const campo = rv(v.campo), R = RAMPAS[rv(v.rampa)], val = b[F[campo]], fixo = rv(v.max);
    if (v.soRes && c.s !== 'Residential') return [NEUTRO, ponto];
    const mn = rv(v.min) || 0, mx = fixo || E.x.topo[campo] || 1;
    if (val <= mn && !fixo) return [rv(v.zeroRuim) ? SEM : '#eceff1', ponto];
    return [R[lim(Math.round((val - mn) / (mx - mn) * (R.length - 1)), 0, R.length - 1)], ponto];
  }
  return [ponto ? ponto : '#e3e8eb', ponto];   // traffic, districts, resources: buildings stay discreet
}

function montarPredios() {
  const m = E.m, v = V(), grupos = new Map();
  M.pontos = []; M.marc = [];
  for (const b of m.predios) {
    const r = corPredio(b, v), c = m.cls[b[F.classe]];
    let p = grupos.get(r[0]); if (!p) { p = new Path2D(); grupos.set(r[0], p); }
    retangulo(p, b[F.x], b[F.z], b[F.ang] / 100, b[F.larg] * 4 - 0.7, b[F.comp] * 4 - 0.7);
    if (r[1]) M.pontos.push([b[F.x], b[F.z], r[1]]);
    if (!c.zoneado && v.servicos && v.servicos.indexOf(c.s) >= 0) M.marc.push(b);
  }
  // draws the neutral ones first, the strong colours last
  M.pred = [...grupos.entries()].sort((a, b) => (a[0] === NEUTRO ? -1 : 0) - (b[0] === NEUTRO ? -1 : 0));
}

function montarVazias() {
  const z = E.m.zonasVazias || [], g = {};
  for (let i = 0; i < z.length; i += 4) {
    const k = ZONA_JOGO[z[i + 3]]; if (!k) continue;
    if (!g[k]) g[k] = new Path2D();
    retangulo(g[k], z[i], z[i + 1], z[i + 2] / 100, 3.5, 3.5);
  }
  M.vaz = Object.keys(g).map(k => [ZONAS[k].cor, g[k]]);
}

function grupoRede(t) {
  if (t.serv === 'Water') return 'cano';
  if (t.serv === 'Electricity') return 'fio';
  if (t.serv === 'Beautification') return 'trilha';
  if (t.serv === 'PublicTransport') return /Metro/.test(t.nome) ? 'metro' : 'trem';
  return /Highway/.test(t.nome) ? 'rodovia' : 'rua';
}
function montarRedes() {
  const m = E.m, trafego = V().modo === 'trafego', mapa = new Map();
  for (const s of m.redes) {
    const t = m.tipos[s[6]], g = grupoRede(t), bin = trafego && t.serv === 'Road' ? binTraf(s[7]) : 0;
    const chave = s[6] + ':' + bin;
    let o = mapa.get(chave);
    if (!o) { o = { t, g, bin, alto: /Elevated|Bridge/.test(t.nome) ? 1 : 0, p: new Path2D() }; mapa.set(chave, o); }
    o.p.moveTo(s[0], s[1]);
    o.p.quadraticCurveTo(2 * s[2] - (s[0] + s[4]) / 2, 2 * s[3] - (s[1] + s[5]) / 2, s[4], s[5]);
  }
  const ordem = { trilha: 0, cano: 1, fio: 1, trem: 2, metro: 2, rua: 3, rodovia: 4 };
  M.redes = [...mapa.values()].sort((a, b) => (a.alto - b.alto) || (ordem[a.g] - ordem[b.g]) || (a.bin - b.bin) || (a.t.hw - b.t.hw));
}

/** Spatial index (96 m cells) to find the building or road under the cursor. */
function montarIndice() {
  const m = E.m, idx = new Map(), C = 96;
  const poe = (x, z, o) => { const k = Math.floor(x / C) + ',' + Math.floor(z / C); let a = idx.get(k); if (!a) { a = []; idx.set(k, a); } if (a.indexOf(o) < 0) a.push(o); };
  for (const b of m.predios) {
    const r = Math.hypot(b[F.larg], b[F.comp]) * 4, o = { b };
    for (let dx = -r; dx <= r; dx += C / 2) for (let dz = -r; dz <= r; dz += C / 2) poe(b[F.x] + dx, b[F.z] + dz, o);
    poe(b[F.x] + r, b[F.z] + r, o);
  }
  for (const s of m.redes) {
    const o = { s }, cx = 2 * s[2] - (s[0] + s[4]) / 2, cz = 2 * s[3] - (s[1] + s[5]) / 2;
    o.pts = [];
    for (let i = 0; i <= 6; i++) { const t = i / 6, u = 1 - t; const x = u * u * s[0] + 2 * u * t * cx + t * t * s[4], z = u * u * s[1] + 2 * u * t * cz + t * t * s[5]; o.pts.push([x, z]); poe(x, z, o); }
  }
  M.idx = idx;
}
function achar(wx, wz) {
  if (!M.idx) return null;
  const a = M.idx.get(Math.floor(wx / 96) + ',' + Math.floor(wz / 96)); if (!a) return null;
  for (const o of a) if (o.b) {
    const b = o.b, an = b[F.ang] / 100, c = Math.cos(an), s = Math.sin(an), dx = wx - b[F.x], dz = wz - b[F.z];
    if (Math.abs(dx * c + dz * s) <= b[F.larg] * 4 && Math.abs(dx * s - dz * c) <= b[F.comp] * 4) return o;
  }
  let melhor = null, md = 1e9;
  for (const o of a) if (o.s) {
    const t = E.m.tipos[o.s[6]]; if (t.serv === 'Water' && V().id !== 'agua') continue;
    const tol = Math.max(t.hw, 5 / M.k);
    for (let i = 0; i < o.pts.length - 1; i++) {
      const p = o.pts[i], q = o.pts[i + 1], vx = q[0] - p[0], vz = q[1] - p[1], l2 = vx * vx + vz * vz || 1;
      const u = lim(((wx - p[0]) * vx + (wz - p[1]) * vz) / l2, 0, 1), d = Math.hypot(wx - p[0] - u * vx, wz - p[1] - u * vz);
      if (d <= tol && d < md) { md = d; melhor = o; }
    }
  }
  return melhor;
}

function reconstruir(tudo) {
  if (!E.m) return;
  if (tudo) { montarIndice(); montarVazias(); }
  montarBase(); montarGrade(); montarPredios(); montarRedes();
  pedir();
}

// ---------- drawing ----------
function texto(t, x, y, o) {
  o = o || {};
  ctx.font = (o.peso || 600) + ' ' + (o.tam || 11) + 'px ' + getComputedStyle(document.body).fontFamily;
  ctx.textAlign = o.alinha || 'center'; ctx.textBaseline = 'middle';
  ctx.lineWidth = o.halo || 3; ctx.strokeStyle = o.fundo || 'rgba(255,255,255,.9)'; ctx.lineJoin = 'round';
  ctx.strokeText(t, x, y); ctx.fillStyle = o.cor || '#22384b'; ctx.fillText(t, x, y);
}

function desenhar() {
  const { W, H, k } = M, m = E.m, v = V();
  tela(); ctx.fillStyle = '#aebbc5'; ctx.fillRect(0, 0, W, H);
  if (!m || !M.base) return;
  const natural = v.modo === 'zonas', t = m.terreno, cx = m.caixa;
  mundo();
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(M.base, cx[0] - t.passo / 2, cx[1] - t.passo / 2, t.nx * t.passo, t.nz * t.passo);
  const gradePorCima = v.modo === 'distritos' || v.id === 'recursos';   // these layers tint the buildings too
  const pintaGrade = () => { if (!M.grade) return; ctx.imageSmoothingEnabled = v.modo !== 'distritos'; ctx.drawImage(M.grade.img, M.grade.x, M.grade.z, M.grade.w, M.grade.h); ctx.imageSmoothingEnabled = true; };
  if (!gradePorCima) pintaGrade();
  // purchased map tiles
  const L = m.lotes, meio = L.lado / 2, lp = new Path2D();
  for (const q of L.comprados) lp.rect((q[0] - meio) * 1920, (q[1] - meio) * 1920, 1920, 1920);
  ctx.setLineDash([10 / k, 7 / k]); ctx.lineWidth = 1.3 / k; ctx.strokeStyle = 'rgba(20,40,58,.5)'; ctx.stroke(lp); ctx.setLineDash([]);
  // zoned lots that are still empty
  if ($('cVazias').checked && (v.modo === 'zonas' || v.modo === 'emprego') && k > 0.12) {
    ctx.globalAlpha = 0.42; for (const g of M.vaz) { ctx.fillStyle = g[0]; ctx.fill(g[1]); } ctx.globalAlpha = 1;
    if (k > 1.6) { ctx.lineWidth = 0.6 / k; for (const g of M.vaz) { ctx.strokeStyle = g[0]; ctx.stroke(g[1]); } }
  }
  // buildings
  for (const g of M.pred) { ctx.fillStyle = g[0]; ctx.fill(g[1]); }
  if (k > 1.1) { ctx.lineWidth = 0.7 / k; ctx.strokeStyle = 'rgba(20,40,58,.32)'; for (const g of M.pred) ctx.stroke(g[1]); }
  if (gradePorCima) pintaGrade();
  // networks
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  const estrada = M.redes.filter(r => r.g === 'rua' || r.g === 'rodovia');
  for (const r of M.redes) {
    if (r.g === 'trilha') { ctx.lineWidth = Math.max(2.5, 1 / k); ctx.strokeStyle = natural ? '#cbb893' : '#c9c4b8'; ctx.stroke(r.p); }
    else if ((r.g === 'cano' && v.id === 'agua') || (r.g === 'fio' && v.id === 'energia')) { ctx.lineWidth = 1.8 / k; ctx.strokeStyle = r.g === 'cano' ? '#1d5f93' : '#8a5a00'; ctx.stroke(r.p); }
    else if (r.g === 'trem' || r.g === 'metro') {
      ctx.lineWidth = Math.max(4, 2.4 / k); ctx.strokeStyle = '#4f5d68'; ctx.stroke(r.p);
      ctx.lineWidth = Math.max(2, 1 / k); ctx.strokeStyle = '#f4f6f7'; ctx.setLineDash([Math.max(10, 6 / k), Math.max(10, 6 / k)]); ctx.stroke(r.p); ctx.setLineDash([]);
    }
  }
  for (const alto of [0, 1]) {
    for (const r of estrada) if (r.alto === alto) { ctx.lineWidth = Math.max(r.t.hw * 2, 1.2 / k) + (k > 0.6 ? 3 : 2.2) / k; ctx.strokeStyle = r.g === 'rodovia' && natural ? '#a8842a' : (v.modo === 'trafego' ? '#7c8891' : '#7f8c96'); ctx.stroke(r.p); }
    for (const r of estrada) if (r.alto === alto) {
      ctx.lineWidth = Math.max(r.t.hw * 2, 1.2 / k);
      ctx.strokeStyle = v.modo === 'trafego' ? TRAF[r.bin] : (r.g === 'rodovia' ? (natural ? '#ffdf8a' : '#fbf3d6') : '#ffffff');
      ctx.stroke(r.p);
    }
  }
  tela();
  // transport lines
  if ($('cLinhas').checked && m.linhas.length && (natural || v.id === 'transporte')) {
    for (const l of m.linhas) {
      const p = l[2]; if (p.length < 4) continue;
      ctx.beginPath();
      for (let i = 0; i < p.length; i += 2) { const s = w2s(p[i], p[i + 1]); if (i) ctx.lineTo(s[0], s[1]); else ctx.moveTo(s[0], s[1]); }
      ctx.closePath(); ctx.lineWidth = 5; ctx.strokeStyle = '#ffffff'; ctx.stroke(); ctx.lineWidth = 3; ctx.strokeStyle = l[1]; ctx.stroke();
      for (let i = 0; i < p.length; i += 2) { const s = w2s(p[i], p[i + 1]); ctx.beginPath(); ctx.arc(s[0], s[1], 3.5, 0, 7); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = l[1]; ctx.stroke(); }
    }
  }
  // marks: the view's service buildings and the buildings with the view's problem
  if ($('cServ').checked && k < 1.4) for (const b of M.marc) {
    const s = w2s(b[F.x], b[F.z]); if (s[0] < -9 || s[1] < -9 || s[0] > W + 9 || s[1] > H + 9) continue;
    ctx.beginPath(); ctx.arc(s[0], s[1], 4.5, 0, 7); ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.lineWidth = 2.2; ctx.strokeStyle = DESTAQUE; ctx.stroke();
  }
  if (k < 1.4) for (const p of M.pontos) {
    const s = w2s(p[0], p[1]); if (s[0] < -9 || s[1] < -9 || s[0] > W + 9 || s[1] > H + 9) continue;
    ctx.beginPath(); ctx.moveTo(s[0], s[1] - 5); ctx.lineTo(s[0] + 4.6, s[1] + 3.6); ctx.lineTo(s[0] - 4.6, s[1] + 3.6); ctx.closePath();
    ctx.fillStyle = p[2]; ctx.fill(); ctx.lineWidth = 1.2; ctx.strokeStyle = '#fff'; ctx.stroke();
  }
  // outside connections
  if (E.c && (v.id === 'conexoes' || k < 0.09)) for (const c of E.c.conexoes) {
    const s = w2s(lim(c[1], -8640, 8640), lim(c[2], -8640, 8640));
    const ruim = c[5] === 0;
    ctx.beginPath(); ctx.arc(s[0], s[1], 8, 0, 7); ctx.fillStyle = ruim ? GRAVE : '#ffffff'; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = ruim ? '#fff' : DESTAQUE; ctx.stroke();
    texto(({ Rodovia: 'R', Train: 'T', Plane: 'A', Ship: 'N' }[c[0]] || '?'), s[0], s[1] + 0.5, { tam: 10, peso: 800, halo: 0.01, cor: ruim ? '#fff' : DESTAQUE });
  }
  // selection and focus rings
  const anel = (x, z, cor, r) => { const s = w2s(x, z); ctx.beginPath(); ctx.arc(s[0], s[1], r, 0, 7); ctx.lineWidth = 5; ctx.strokeStyle = '#fff'; ctx.stroke(); ctx.lineWidth = 2.5; ctx.strokeStyle = cor; ctx.stroke(); };
  for (const f of E.focos) anel(f[0], f[1], GRAVE, 13);
  if (E.sel) { const p = E.sel.b ? [E.sel.b[F.x], E.sel.b[F.z]] : [E.sel.s[2], E.sel.s[3]]; anel(p[0], p[1], '#1d5f93', Math.max(12, (E.sel.b ? Math.hypot(E.sel.b[F.larg], E.sel.b[F.comp]) * 4 : 14) * k + 5)); }
  // labels
  const ocup = new Set(), livre = (x, y, w) => { const a = Math.floor((x - w / 2) / 60), b = Math.floor((x + w / 2) / 60), r = Math.floor(y / 15); for (let i = a; i <= b; i++) if (ocup.has(i + ',' + r)) return false; for (let i = a; i <= b; i++) ocup.add(i + ',' + r); return true; };
  for (const d of m.distritos) { const s = w2s(d[1], d[2]); if (livre(s[0], s[1], d[0].length * 8)) texto(d[0], s[0], s[1], { tam: 13.5, peso: 800, cor: '#14283a', halo: 4 }); }
  if (k > 1.7) for (const b of (v.servicos ? M.marc : m.predios)) {
    if (b[F.nome] < 0) continue;
    const s = w2s(b[F.x], b[F.z]); if (s[0] < 0 || s[1] < 0 || s[0] > W || s[1] > H) continue;
    const n = m.nomes[b[F.nome]]; if (livre(s[0], s[1], n.length * 7.5 + 20)) texto(n, s[0], s[1], { tam: 11, peso: 700 });
  }
  if ($('cRuas').checked && k > 0.85) {
    const postos = {};
    for (const s of m.redes) {
      if (s[9] == null || s[9] < 0) continue;
      const a = w2s(s[0], s[1]), b = w2s(s[4], s[5]), c = w2s(s[2], s[3]);
      if (c[0] < 0 || c[1] < 0 || c[0] > W || c[1] > H) continue;
      const n = m.ruas[s[9]], comp = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (comp < n.length * 4.2) continue;
      const l = postos[s[9]] || (postos[s[9]] = []);
      if (l.some(p => Math.hypot(p[0] - c[0], p[1] - c[1]) < 330)) continue;
      if (!livre(c[0], c[1], Math.abs(Math.cos(Math.atan2(b[1] - a[1], b[0] - a[0]))) * n.length * 6.5 + 20)) continue;
      l.push(c);
      let an = Math.atan2(b[1] - a[1], b[0] - a[0]); if (an > Math.PI / 2) an -= Math.PI; if (an < -Math.PI / 2) an += Math.PI;
      ctx.save(); ctx.translate(c[0], c[1]); ctx.rotate(an); texto(n, 0, 0, { tam: 10.5, peso: 600, cor: '#3b4c5a', halo: 2.6 }); ctx.restore();
    }
  }
  // scale bar
  const alvo = 110 / k, passos = [20, 50, 100, 200, 500, 1000, 2000, 5000], um = passos.reduce((a, p) => p <= alvo ? p : a, 20);
  $('escala').innerHTML = `<span style="width:${Math.round(um * k)}px"></span>${um >= 1000 ? um / 1000 + ' km' : um + ' m'}`;
}

// ---------- interaction ----------
function dicaDe(o) {
  const m = E.m, v = V();
  if (o.s) {
    const t = m.tipos[o.s[6]], n = o.s[9] != null && o.s[9] >= 0 ? m.ruas[o.s[9]] : '';
    return `<b>${esc(n || redePT(t.nome))}</b>${n ? `<div class="l"><span>Type</span><span>${esc(redePT(t.nome))}</span></div>` : ''}` +
      (t.serv === 'Road' ? `<div class="l"><span>Road occupancy</span><span>${o.s[7]}%</span></div>` : '');
  }
  const b = o.b, c = m.cls[b[F.classe]];
  let h = `<b>${esc(c.zoneado ? ZONAS[c.z].nome + ', level ' + b[F.nivel] : m.nomes[b[F.nome]] || SERVICO[c.s] || c.s)}</b>`;
  if (!c.zoneado) h += `<div class="l"><span>Service</span><span>${esc(SERVICO[c.s] || c.s)}</span></div>`;
  const campo = v.modo === 'campo' ? rv(v.campo) : null;
  if (campo && c.zoneado) h += `<div class="l"><span>${esc(rotuloCampo(campo))}</span><span>${fmt(b[F[campo]])}${b[F[campo]] <= 0 && rv(v.zeroRuim) ? ' (out of reach)' : ''}</span></div>`;
  if (c.zoneado) h += `<div class="l"><span>${c.s === 'Residential' ? 'Residents' : 'Workers'}</span><span>${b[F.moradores]}</span></div><div class="l"><span>Happiness</span><span>${b[F.felicidade]}%</span></div>`;
  const ps = traduzProblemas(m.problemas[b[F.problema]]);
  if (ps.length) h += `<div class="pb">${esc(ps.join(', '))}</div>`;
  return h;
}
const CAMPO_ROT = {
  valorTerreno: 'Land value', ruido: 'Noise', bombeiros: 'Fire coverage', policia: 'Police coverage', saudeCob: 'Healthcare coverage', funeraria: 'Deathcare coverage',
  fundamental: 'Elementary school reach', medio: 'High school reach', superior: 'University reach', transporte: 'Public transport access', lazer: 'Leisure nearby',
  crime: 'Crime index', lixo: 'Garbage piling up', poluicao: 'Ground pollution', felicidade: 'Happiness', saude: 'Health of the occupants', moradores: 'People in the building', nivel: 'Level'
};
const rotuloCampo = c => CAMPO_ROT[c] || c;

(function () {
  const ptrs = new Map(); let moveu = false, pin = 0;
  cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.offsetX, e.offsetY]); moveu = false; cv.classList.add('arrastando'); $('dica').hidden = true; if (ptrs.size === 2) { const p = [...ptrs.values()]; pin = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); } });
  cv.addEventListener('pointermove', e => {
    const ant = ptrs.get(e.pointerId);
    if (ant) {
      const dx = e.offsetX - ant[0], dy = e.offsetY - ant[1];
      if (Math.abs(dx) + Math.abs(dy) > 2) moveu = true;
      ptrs.set(e.pointerId, [e.offsetX, e.offsetY]);
      if (ptrs.size === 1) { M.cx -= dx / M.k; M.cz += dy / M.k; pedir(); }
      else if (ptrs.size === 2) { const p = [...ptrs.values()], d = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); if (pin > 0) zoom(d / pin, (p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2); pin = d; }
      return;
    }
    if (!E.m) return;
    const w = s2w(e.offsetX, e.offsetY), o = achar(w[0], w[1]), d = $('dica');
    if (!o) { d.hidden = true; return; }
    d.innerHTML = dicaDe(o); d.hidden = false;
    d.style.left = lim(e.offsetX + 14, 4, M.W - d.offsetWidth - 4) + 'px';
    d.style.top = lim(e.offsetY + 14, 4, M.H - d.offsetHeight - 4) + 'px';
  });
  const solta = e => {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId); if (!ptrs.size) cv.classList.remove('arrastando');
    if (!moveu && e.type === 'pointerup' && E.m) { const w = s2w(e.offsetX, e.offsetY); E.sel = achar(w[0], w[1]); E.focos = []; pedir(); pintarPainel(); }
  };
  cv.addEventListener('pointerup', solta); cv.addEventListener('pointercancel', solta);
  cv.addEventListener('pointerleave', () => { $('dica').hidden = true; });
  cv.addEventListener('wheel', e => { e.preventDefault(); zoom(Math.exp(-e.deltaY * 0.0016), e.offsetX, e.offsetY); }, { passive: false });
  cv.addEventListener('dblclick', e => zoom(1.8, e.offsetX, e.offsetY));
  cv.addEventListener('keydown', e => {
    const p = 80 / M.k;
    if (e.key === 'ArrowLeft') M.cx -= p; else if (e.key === 'ArrowRight') M.cx += p; else if (e.key === 'ArrowUp') M.cz += p; else if (e.key === 'ArrowDown') M.cz -= p;
    else if (e.key === '+' || e.key === '=') return zoom(1.4); else if (e.key === '-') return zoom(1 / 1.4); else if (e.key === '0') return ajustar(); else return;
    e.preventDefault(); pedir();
  });
  $('zMais').onclick = () => zoom(1.5); $('zMenos').onclick = () => zoom(1 / 1.5); $('zTudo').onclick = () => ajustar();
  ['cRuas', 'cVazias', 'cLinhas', 'cServ'].forEach(id => $(id).onchange = pedir);
  new ResizeObserver(() => {
    const r = $('palco').getBoundingClientRect();
    M.W = Math.max(50, r.width); M.H = Math.max(50, r.height); M.dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(M.W * M.dpr); cv.height = Math.round(M.H * M.dpr);
    if (E.m && !M.ajustado) { M.ajustado = true; ajustar(); }
    pedir();
  }).observe($('palco'));
})();
