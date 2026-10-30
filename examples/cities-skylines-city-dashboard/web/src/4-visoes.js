// ---------- views (the game's list of info views, in the order the owner reviews the city) ----------
const rv = p => typeof p === 'function' ? p() : p;
const IC = {
  cidade: 'M3 21V9l6-4v4l6-4v16H3zm14 0V11h4v10h-4z', assessor: 'M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2zM9 19h6v2H9z', energia: 'M13 2 4 14h6l-1 8 9-12h-6z',
  agua: 'M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z', lixo: 'M8 3h8l1 2h4v2H3V5h4l1-2zM5 9h14l-1 12H6L5 9z',
  educacao: 'M12 3 1 9l11 6 9-4.9V17h2V9L12 3zM5 13.2V17c0 1.7 3.1 3 7 3s7-1.3 7-3v-3.8l-7 3.8-7-3.8z',
  felicidade: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM8 8.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm8 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zM7 14h10a5 5 0 0 1-10 0z',
  saude: 'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z', niveis: 'M3 21v-6h4v6H3zm7 0V9h4v12h-4zm7 0V3h4v18h-4z',
  trafego: 'M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11a2 2 0 0 1 2 2v5h-3v2h-3v-2H9v2H6v-2H3v-5a2 2 0 0 1 2-2zm2.2 0h9.6l-1-3H8.2l-1 3z',
  poluicao: 'M7 19a5 5 0 0 1-.6-10A6 6 0 0 1 18 8.5 4.5 4.5 0 0 1 17.5 19H7z', ruido: 'M3 9v6h4l5 5V4L7 9H3zm13 3a4 4 0 0 0-2-3.5v7a4 4 0 0 0 2-3.5zm-2-8v2a6 6 0 0 1 0 12v2a8 8 0 0 0 0-16z',
  bombeiro: 'M12 2c1 3 5 5.5 5 10.5a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5.2 1.5 1 2.5 2 3-.5-3.500 0-6.500 1-9z', crime: 'M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z',
  transporte: 'M6 3h12a2 2 0 0 1 2 2v11a2 2 0 0 1-1 1.700V20h-3v-2H8v2H5v-2.300A2 2 0 0 1 4 16V5a2 2 0 0 1 2-2zm0 3v5h12V6H6zm1.5 7.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm9 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z',
  populacao: 'M8 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM1 20v-2c0-2.700 3.600-4 7-4s7 1.300 7 4v2H1zm16 0v-2c0-1.300-.5-2.300-1.400-3.100 3 .2 7.400 1.200 7.400 3.600V20h-6z',
  conexoes: 'M4 11h12.2l-4.600-4.600L13 5l7 7-7 7-1.400-1.400 4.600-4.600H4z', terreno: 'M12 3 2 12h3v8h5v-6h4v6h5v-8h3L12 3z',
  recursos: 'M5 21c0-9 5-16 16-18-1 11-6 17-14 17l-1 1H5zm3-4c5-1 8-4 10-9-4 2-8 5-10 9z', distritos: 'M3 3h8v8H3V3zm10 0h8v5h-8V3zM3 13h5v8H3v-8zm7 0h11v8H10v-8z',
  lazer: 'M12 2 5 12h3l-3 5h6v5h2v-5h6l-3-5h3L12 2z', turismo: 'M9 4h6l1.500 2H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3.500L9 4zm3 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  emprego: 'M9 3h6a2 2 0 0 1 2 2v2h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3V5a2 2 0 0 1 2-2zm0 4h6V5H9v2z', industria: 'M2 21V10l6 4v-4l6 4V4h6v17H2z',
  dinheiro: 'M3 6h18v12H3V6zm9 2.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z', demanda: 'M4 21V8h4v13H4zm6 0V3h4v18h-4zm6 0v-9h4v9h-4z',
  historico: 'M3 3h2v16h16v2H3V3zm4 12 4-5 3 3 5-7 1.600 1.200-6.400 9-3-3-2.600 3.300L7 15z',
  dianoite: 'M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z',
  motor: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM10 2h4l.6 3 2.500 1.400 2.900-1 2 3.400-2.300 2v2.400l2.300 2-2 3.400-2.900-1-2.500 1.400-.6 3h-4l-.6-3-2.500-1.400-2.900 1-2-3.400 2.300-2v-2.400l-2.300-2 2-3.400 2.900 1L9.400 5l.6-3z'
};
const subDe = (id, padrao) => E.sub[id] || padrao;
const VISOES = [
  { g: 'General' },
  { id: 'cidade', nome: 'City', sub: 'Land use and what needs attention', modo: 'zonas' },
  { id: 'assessor', nome: 'Advisor', sub: 'Everything worth fixing, from the most serious down', modo: 'problemas' },
  { id: 'historico', nome: 'Charts', sub: 'The city over time and a snapshot of right now, full screen', modo: 'zonas', tela: 'graficos' },
  { g: 'Info views' },
  { id: 'energia', nome: 'Electricity', sub: 'Generation, consumption and who is left in the dark', modo: 'servico', servicos: ['Electricity'], probs: ['Electricity'], corOk: '#f3e3a1' },
  { id: 'agua', nome: 'Water', sub: 'Pumping, sewage and the pipe network', modo: 'servico', servicos: ['Water'], probs: ['Water', 'Sewage', 'DirtyWater', 'Flood'], corOk: '#bcd9f2' },
  { id: 'lixo', nome: 'Garbage', sub: 'Where garbage piles up and who collects it', modo: 'campo', campo: 'lixo', rampa: 'marrom', servicos: ['Garbage'], probs: ['Garbage', 'LandfillFull'] },
  { id: 'educacao', nome: 'Education', sub: 'Seats, school reach and education levels', modo: 'campo', campo: () => subDe('educacao', 'fundamental'), rampa: 'roxo', zeroRuim: true, servicos: ['Education'], subs: [['fundamental', 'Elementary'], ['medio', 'High school'], ['superior', 'University']] },
  { id: 'felicidade', nome: 'Happiness', sub: 'How satisfied the people living and working in each building are', modo: 'campo', campo: 'felicidade', rampa: 'verde', min: 40, max: 100 },
  { id: 'saude', nome: 'Healthcare', sub: 'Medical care, deathcare and the residents\' health', modo: 'campo', campo: () => subDe('saude', 'saudeCob'), rampa: 'ciano', zeroRuim: () => subDe('saude', 'saudeCob') !== 'saude', min: () => subDe('saude', 'saudeCob') === 'saude' ? 40 : 0, max: () => subDe('saude', 'saudeCob') === 'saude' ? 100 : 0, servicos: ['HealthCare'], probs: ['Death'], subs: [['saudeCob', 'Medical care'], ['funeraria', 'Deathcare'], ['saude', 'Residents\' health']] },
  { id: 'niveis', nome: 'Levels', sub: 'Level of each zoned building', modo: 'campo', campo: 'nivel', rampa: 'roxo', min: 1, max: 5 },
  { id: 'trafego', nome: 'Traffic', sub: 'Occupancy of each road segment', modo: 'trafego' },
  { id: 'poluicao', nome: 'Pollution', sub: 'Contaminated ground and who lives on it', modo: 'campo', campo: 'poluicao', rampa: 'marrom', max: 255, grade: 'poluicao', gradeCor: '#89653b', probs: ['Pollution'] },
  { id: 'ruido', nome: 'Noise pollution', sub: 'Noise reaching each building', modo: 'campo', campo: 'ruido', rampa: 'vermelho', probs: ['Noise'] },
  { id: 'bombeiro', nome: 'Fire safety', sub: 'Reach of the fire stations', modo: 'campo', campo: 'bombeiros', rampa: 'azul', zeroRuim: true, servicos: ['FireDepartment'], probs: ['Fire'] },
  { id: 'crime', nome: 'Crime', sub: 'Police reach and crime index', modo: 'campo', campo: () => subDe('crime', 'policia'), rampa: () => subDe('crime', 'policia') === 'crime' ? 'vermelho' : 'azul', zeroRuim: () => subDe('crime', 'policia') === 'policia', servicos: ['PoliceDepartment'], probs: ['Crime'], subs: [['policia', 'Police coverage'], ['crime', 'Crime index']] },
  { id: 'transporte', nome: 'Transport', sub: 'Lines, passengers and who has a stop nearby', modo: 'campo', campo: 'transporte', rampa: 'verde', zeroRuim: true, servicos: ['PublicTransport'] },
  { id: 'populacao', nome: 'Population', sub: 'How many people in each building, ages and education', modo: 'campo', campo: 'moradores', rampa: 'azul' },
  { id: 'conexoes', nome: 'Outside connections', sub: 'Ways in and out of the map, imports and exports', modo: 'outro' },
  { id: 'terreno', nome: 'Land value', sub: 'What makes buildings level up', modo: 'campo', campo: 'valorTerreno', rampa: 'ouro' },
  { id: 'recursos', nome: 'Natural resources', sub: 'Where they are and how much is being used', modo: 'outro', grade: () => subDe('recursos', 'fertil'), gradeCor: () => ({ minerio: '#2f55a4', petroleo: '#1d1d1d', fertil: '#a9841c', floresta: '#1f6b22' }[subDe('recursos', 'fertil')]), subs: [['fertil', 'Fertile land'], ['floresta', 'Forest'], ['minerio', 'Ore'], ['petroleo', 'Oil']] },
  { id: 'distritos', nome: 'Districts', sub: 'Neighbourhoods, policies and specializations', modo: 'distritos' },
  { id: 'lazer', nome: 'Leisure', sub: 'Parks and plazas within reach of each home', modo: 'campo', campo: 'lazer', rampa: 'verde', zeroRuim: true, soRes: true, servicos: ['Beautification', 'Monument'] },
  { id: 'turismo', nome: 'Tourism', sub: 'Who visits the city and what they come to see', modo: 'outro', servicos: ['Monument', 'Beautification'] },
  { id: 'emprego', nome: 'Jobs', sub: 'Jobs, unemployment and the education of those looking', modo: 'emprego', probs: ['NoWorkers', 'NoEducatedWorkers'] },
  { g: 'Economy' },
  { id: 'industria', nome: 'Commerce and industry', sub: 'Stock, raw materials and cargo', modo: 'emprego', probs: ['NoGoods', 'NoResources', 'NoPlaceforGoods', 'NoCustomers', 'NoInputProducts'] },
  { id: 'dinheiro', nome: 'Money', sub: 'Income, expenses, taxes and budget', modo: 'zonas' },
  { id: 'dianoite', nome: 'Day and night', sub: 'Usage of each service in both periods and the budget each one asks for', modo: 'zonas', tela: 'dianoite' },
  { id: 'demanda', nome: 'Demand', sub: 'Why the R, C and I bars are where they are', modo: 'zonas' },
  { g: 'Panel' },
  { id: 'motor', nome: 'Game limits', sub: 'Internal counters and simulation pace', modo: 'zonas' }
];
const V = () => VISOES.find(v => v.id === E.visao) || VISOES[1];
const nomeVisao = id => (VISOES.find(v => v.id === id) || {}).nome || id;

function montarTrilho() {
  $('trilho').innerHTML = VISOES.map(v => v.g ? `<h2>${v.g}</h2>` :
    `<button class="visao" data-v="${v.id}" aria-current="${v.id === E.visao}"><span class="ic"><svg viewBox="0 0 24 24" fill-rule="evenodd" aria-hidden="true"><path d="${IC[v.id]}"/></svg></span><span class="nm">${v.nome}</span><span class="marca" data-m="${v.id}"></span></button>`).join('');
}
function pintarMarcas() {
  document.querySelectorAll('.marca').forEach(el => {
    const id = el.dataset.m;
    if (!E.c || id === 'historico') { el.className = 'marca'; el.textContent = ''; return; }
    let sev, txt;
    if (id === 'assessor') { const l = E.sug.filter(s => s.sev >= 1); sev = l.reduce((a, s) => Math.max(a, s.sev), 0); txt = l.length ? String(l.length) : '✓'; }
    else { sev = sevMax(E.sug, id); txt = ['✓', '!', '‼', '✕'][sev]; }
    el.className = 'marca s' + sev; el.textContent = txt; el.title = sev ? SEVN[sev] : 'No alerts';
    el.setAttribute('aria-label', sev ? SEVN[sev] : 'No alerts');
  });
  document.querySelectorAll('.visao').forEach(b => b.setAttribute('aria-current', b.dataset.v === E.visao));
}

function trocarVisao(id, semHash) {
  if (!VISOES.some(v => v.id === id)) id = 'cidade';
  const antes = E.visao; E.visao = id; E.focos = []; if (antes !== id) E.sel = null;
  if (!semHash) history.replaceState(null, '', '#' + id);
  $('app').classList.toggle('modo-tela', !!V().tela); E.grafFoco = null;
  reconstruir(false); pintarLegenda(); pintarMarcas(); pintarPainel(true);
  if (id === 'conexoes') ajustar([-8900, -8900, 8900, 8900]); else if (antes === 'conexoes') ajustar();
}

// ---------- legend over the map ----------
let ultimaLegenda = '';
function pintarLegenda() {
  const v = V(), el = $('legenda'), it = (cor, t, forma) => `<span class="it"><i class="cx" style="background:${cor}${forma || ''}"></i>${t}</span>`;
  let h = `<h3>${v.nome}</h3>`;
  if (v.subs) h += '<div class="seg" role="group" aria-label="Camada">' + v.subs.map(s => `<button data-sub="${s[0]}" aria-pressed="${subDe(v.id, v.subs[0][0]) === s[0]}">${s[1]}</button>`).join('') + '</div>';
  const tri = ';clip-path:polygon(50% 0,100% 100%,0 100%);border:0', bola = ';border-radius:50%;border:2.5px solid ' + DESTAQUE;
  h += '<div class="itens">';
  if (v.modo === 'zonas') h += ['rb', 'ra', 'cb', 'ca', 'in', 'es', 'pq', 'sv'].map(k => it(ZONAS[k].cor, ZONAS[k].nome)).join('');
  else if (v.modo === 'emprego') h += ['cb', 'ca', 'in', 'es', 'sv'].map(k => it(ZONAS[k].cor, ZONAS[k].nome)).join('') + it(NEUTRO, 'Homes');
  else if (v.modo === 'problemas') h += it(GRAVE, 'Major problem, abandoned or burned down') + it(SEM, 'With a warning') + it(NEUTRO, 'No warnings');
  else if (v.modo === 'trafego') h += TRAF.map((c, i) => it(c, TRAF_ROT[i])).join('');
  else if (v.modo === 'servico') h += it(v.corOk, 'Building served');
  else if (v.modo === 'campo') {
    const campo = rv(v.campo), R = RAMPAS[rv(v.rampa)], mx = rv(v.max) || (E.x ? E.x.topo[campo] : 0), mn = rv(v.min) || 0;
    h += `<span class="rampa">${campo === 'nivel' ? 'level 1' : mn ? fmt(mn) : 'low'}<span class="fx">${R.map(c => `<i style="background:${c}"></i>`).join('')}</span>${campo === 'nivel' ? 'level 5' : rv(v.max) ? fmt(mx) : 'high (' + fmt(mx) + ' or more)'}</span>`;
    if (rv(v.zeroRuim)) h += it(SEM, 'Out of reach');
    if (v.soRes) h += it(NEUTRO, 'Not residential');
  } else if (v.modo === 'distritos') {
    const ds = E.m ? E.m.distritos : [];
    h += ds.length ? ds.slice(0, 12).map(d => it(CORES_DISTRITO[(d[3] - 1) % CORES_DISTRITO.length], esc(d[0]))).join('') : '<span class="it">No district painted yet.</span>';
  } else if (v.grade) {
    const cor = rv(v.gradeCor); h += `<span class="rampa">low<span class="fx">${[.25, .45, .65, .85, 1].map(a => `<i style="background:${cor};opacity:${a}"></i>`).join('')}</span>high</span>`;
  }
  if (v.servicos) h += it('#fff', v.servicos.map(s => SERVICO[s]).join(', '), bola);
  if (v.probs) h += it(GRAVE, 'Building with the problem', tri);
  if (v.id === 'conexoes') h += it('#fff', 'R road, T train, A air, N naval', bola) + it(GRAVE, 'Not connected to the city', ';border-radius:50%');
  h += '</div>';
  if (v.modo === 'zonas' || v.modo === 'emprego') h += '<p>Lighter squares are zoned lots that are still empty. The dashed line marks the map tiles already purchased.</p>';
  if (v.modo === 'campo' && rv(v.zeroRuim)) h += '<p>Reach follows the roads: the darker, the closer and the better served.</p>';
  if (h !== ultimaLegenda) { ultimaLegenda = h; el.innerHTML = h; }
}

// ---------- panel ----------
let GRUPOS = [];
function numBR(s) { return parseFloat(String(s).replace(/[.\s]/g, '').replace(',', '.')) || 0; }
function tabelaServicos(servs, titulo) {
  if (!E.sv) return '';
  const lista = E.sv.predios.filter(p => servs.indexOf(p[2]) >= 0);
  if (!lista.length) return `<h2>${titulo || 'Facilities'}</h2><p class="nota">No facility of this service in the city.</p>`;
  const g = new Map();
  for (const p of lista) { let o = g.get(p[1]); if (!o) { o = { nome: p[1], l: [], custo: 0, prob: 0, off: 0 }; g.set(p[1], o); } o.l.push(p); o.custo += p[7]; if (p[5]) o.prob++; if (!p[9]) o.off++; }
  const grupos = [...g.values()].sort((a, b) => b.custo - a.custo), base = GRUPOS.length;
  let h = `<h2>${titulo || 'Facilities'}</h2><table class="tb"><thead><tr><th>Building</th><th class="n">Qty</th><th class="n">Cost/week</th></tr></thead><tbody>`;
  grupos.forEach((o, i) => {
    GRUPOS.push(o.l.map(p => [p[3], p[4]]));
    const ag = new Map();
    for (const p of o.l) for (const l of String(p[6]).split('\n')) {
      const mm = l.match(/^(.*?):\s*([\d.,]+)\s*(?:\/\s*([\d.,]+))?\s*(.*)$/); if (!mm || /na cidade|Velocidade|Intensidade/.test(mm[1])) continue;
      const a = ag.get(mm[1]) || { a: 0, b: mm[3] != null ? 0 : null, u: mm[4] }; a.a += numBR(mm[2]); if (mm[3] != null) a.b = (a.b || 0) + numBR(mm[3]); ag.set(mm[1], a);
    }
    const linhas = [...ag.entries()].slice(0, 3).map(e => `${esc(e[0])}: ${fmt(e[1].a)}${e[1].b != null ? ' of ' + fmt(e[1].b) : ''} ${esc(e[1].u || '')}`);
    h += `<tr class="cl" data-grupo="${base + i}" title="Mostrar no mapa"><td><b>${esc(o.nome)}</b><small>${linhas.join('<br>')}${o.prob ? '<br>' + o.prob + ' with a warning' : ''}${o.off ? '<br>' + o.off + ' turned off' : ''}</small></td><td class="n">${fmt(o.l.length)}</td><td class="n">${din(o.custo)}</td></tr>`;
  });
  return h + `</tbody></table><p class="nota">Click a row to see where they are. Approximate upkeep, ${din(grupos.reduce((a, o) => a + o.custo, 0))} per week in total.</p>`;
}
function cobLinha(rot, k, res) { const x = E.x; if (!x || !x.zon) return ''; return ln(rot, res ? pct(x.cobRes[k], x.res) + ' of the homes' : pct(x.cob[k], x.zon) + ' of the buildings'); }
function hist(col) { if (!E.h || !E.h.linhas) return { d: [], v: [] }; const i = E.h.colunas.indexOf(col), L = E.h.linhas.map(l => l.split(',')); return { d: L.map(l => l[0]), v: L.map(l => +l[i]) }; }
function grafHist(id, titulo, cols, o) { const s = cols.map(c => ({ r: c[1], v: hist(c[0]).v, cor: c[2] })); return grafico(id, titulo, s, hist('pop').d, o) + '<button class="lk" data-ir="historico">See the charts full screen</button>'; }
const COR_NIVEL = ['#cabdea', '#ad9adc', '#8d74cb', '#6e53b5', '#37256c'];
const ZCEL = { ResidentialLow: 'rb', ResidentialHigh: 'ra', CommercialLow: 'cb', CommercialHigh: 'ca', Industrial: 'in', Office: 'es' };

const PAINEIS = {
  cidade(c) {
    const D = c.dinheiro, saldo = D.receita - D.despesa, top = E.sug.map((s, i) => [s, i]).filter(p => p[0].sev >= 1).sort((a, b) => b[0].sev - a[0].sev).slice(0, 5);
    const celulas = Object.keys(ZCEL).filter(k => c.zonas[k]).map(k => ({ r: ZONAS[ZCEL[k]].nome, v: c.zonas[k][0] - c.zonas[k][1], cor: ZONAS[ZCEL[k]].cor }));
    const vazias = Object.keys(ZCEL).reduce((a, k) => a + (c.zonas[k] ? c.zonas[k][1] : 0), 0);
    return ln('Population', fmt(c.populacao.total)) + ln('Cash', din(D.caixa)) + ln('Weekly balance', (saldo >= 0 ? '+' : '−') + din(Math.abs(saldo))) + ln('Happiness', c.populacao.felicidade + '%') +
      ln('Unemployment', c.populacao.desempregoPct + '%') + ln('Average land value', '₡' + c.ambiente.valorTerreno + '/m²') + ln('Map tiles purchased', c.geral.lotes + ' of ' + c.geral.lotesMax) + ln('Buildings', fmt(c.predios.total)) +
      '<h2>What needs attention</h2>' + (top.length ? top.map(p => cartaoSug(Object.assign({ irPara: p[0].area === 'cidade' ? null : p[0].area }, p[0]), p[1])).join('') + `<button class="lk" data-ir="assessor">See all ${E.sug.length} observations in the Advisor</button>` : '<p class="nota">No alerts at the moment.</p>') +
      '<h2>Zoned land use</h2>' + empilhada(celulas.concat([{ r: 'Zoned and empty', v: vazias, cor: '#b7c2ca' }]), { fmt: v => fmt(v) + ' cells' }) +
      grafHist('gpop', 'Population', [['pop', 'Inhabitants']], { zero: true }) + sugestoesDe('cidade');
  },
  assessor(c) {
    const n = [0, 1, 2, 3].map(s => E.sug.filter(x => x.sev === s).length), ord = E.sug.map((s, i) => [s, i]).sort((a, b) => b[0].sev - a[0].sev);
    const P = Object.entries(c.predios.problemas).sort((a, b) => b[1][0] - a[1][0]);
    GRUPOS_PROB = P.map(p => p[0]);
    return `<p>${n[3]} critical, ${n[2]} serious, ${n[1]} warning(s) and ${n[0]} tip(s). On the map, every building with a warning is highlighted.</p>` +
      ord.map(p => cartaoSug(Object.assign({ irPara: p[0].area === 'cidade' ? null : p[0].area }, p[0]), p[1])).join('') +
      '<h2>Building warnings right now</h2>' + (P.length ? '<table class="tb"><thead><tr><th>Warning</th><th class="n">Buildings</th><th class="n">Major</th></tr></thead><tbody>' +
        P.map((p, i) => `<tr class="cl" data-prob="${i}" title="Mostrar no mapa"><td>${esc(PROB[p[0]] || p[0])}</td><td class="n">${fmt(p[1][0])}</td><td class="n">${fmt(p[1][1] + p[1][2])}</td></tr>`).join('') + '</tbody></table>' : '<p class="nota">No building with a warning.</p>');
  },
  energia(c) {
    const [u, cap] = c.infra.energia;
    return medidor('Generation in use', u / 1000, cap / 1000, 'MW') + ln('Consumption', fmt(u / 1000) + ' MW') + ln('Available generation', fmt(cap / 1000) + ' MW') + ln('Headroom', fmt((cap - u) / 1000) + ' MW') +
      ln('Spent on electricity', din((c.dinheiro.porServico.Electricity || [0, 0])[1]) + ' per week') + (c.infra.aquecimento[1] ? medidor('Heating', c.infra.aquecimento[0] / 1000, c.infra.aquecimento[1] / 1000, 'MW') : '') +
      sugestoesDe('energia') + tabelaServicos(['Electricity'], 'Power plants');
  },
  agua(c) {
    const I = c.infra;
    return medidor('Pumped water in use', I.agua[0], I.agua[1], 'm³/week') + medidor('Sewage drained', I.esgoto[0], I.esgoto[1], 'm³/week') + (I.reservaAgua[1] ? medidor('Reservoirs', I.reservaAgua[0], I.reservaAgua[1], 'm³') : '') +
      ln('Pollution in the distributed water', I.poluicaoAgua + '%') + ln('Spent on water and sewage', din((c.dinheiro.porServico.Water || [0, 0])[1]) + ' per week') + sugestoesDe('agua') + tabelaServicos(['Water'], 'Pumps, towers and sewage');
  },
  lixo(c) {
    const L = c.infra.lixo;
    return medidor('Landfills in use', L.acumulado, L.capacidadeAterros, '') + '<h2>Produced and burned per week</h2>' +
      barras([{ r: 'Garbage produced', v: L.producaoSemanal, cor: '#89653b' }, { r: 'Burning capacity', v: L.incineracaoSemanal, cor: '#3b79a8' }]) +
      ln('Buildings with garbage piled up', fmt((c.predios.problemas.Garbage || [0])[0])) + ln('Garbage budget', c.dinheiro.orcamento.Garbage[0] + '%') + ln('Spent on garbage', din((c.dinheiro.porServico.Garbage || [0, 0])[1]) + ' per week') +
      sugestoesDe('lixo') + tabelaServicos(['Garbage'], 'Landfills and incinerators');
  },
  educacao(c) {
    const Ed = c.servicos.educacao, P = c.populacao, x = E.x;
    const nivel = (k, rot) => medidor(rot + ' (people of school age for the seats)', Ed[k][0], Ed[k][1], 'seats');
    return nivel('fundamental', 'Elementary') + nivel('medio', 'High school') + nivel('superior', 'University') + (Ed.bibliotecas[1] ? ln('Library visitors', fmt(Ed.bibliotecas[0]) + ' of ' + fmt(Ed.bibliotecas[1])) : '') +
      '<h2>School reach</h2>' + cobLinha('Elementary', 'fundamental', true) + cobLinha('High school', 'medio', true) + cobLinha('University', 'superior', true) +
      '<h2>Education of the population</h2>' + barras([{ r: 'Uneducated', v: P.semEstudo.pessoas }, { r: 'Elementary', v: P.fundamental.pessoas }, { r: 'High school', v: P.medio.pessoas }, { r: 'University degree', v: P.superior.pessoas }], { cor: '#6e53b5' }) +
      ln('Spent on education', din((c.dinheiro.porServico.Education || [0, 0])[1]) + ' per week') + ln('Education budget', c.dinheiro.orcamento.Education[0] + '%') + sugestoesDe('educacao') + tabelaServicos(['Education'], 'Schools, universities and libraries');
  },
  felicidade(c) {
    const S = c.setores;
    return ln('Overall happiness', c.populacao.felicidade + '%') + '<h2>By sector</h2>' + barras([{ r: 'Residents', v: S.residencial.felicidade }, { r: 'Commercial', v: S.comercial.felicidade }, { r: 'Industry', v: S.industrial.felicidade }, { r: 'Offices', v: S.escritorios.felicidade }], { max: 100, fmt: v => v + '%', cor: '#43943c' }) +
      sugestoesDe('felicidade') + grafHist('gfel', 'Happiness over time', [['felicidade', 'Happiness']], { min: 0, max: 100, fmt: v => fmt(v) + '%' });
  },
  saude(c) {
    const S = c.servicos.saude, Fu = c.servicos.funeraria;
    return medidor('Treatment places in use', S.doentes, S.capacidadeTratamento, '') + ln('Average health of the residents', S.saudeMedia + '%') + ln('Life expectancy', c.populacao.expectativa + ' years') + cobLinha('Medical care reach', 'saudeCob') +
      '<h2>Deathcare</h2>' + ln('Bodies waiting for pickup', fmt(Fu.corposAguardando)) + ln('Buildings with the warning', fmt((c.predios.problemas.Death || [0])[0])) + ln('Deaths this week', fmt(c.populacao.mortes)) + ln('Cremation capacity', fmt(Fu.cremacaoSemanal) + ' per week') +
      (Fu.capacidadeCemiterios ? medidor('Cemeteries in use', Fu.sepultados, Fu.capacidadeCemiterios, 'graves') : '') + cobLinha('Deathcare reach', 'funeraria') +
      ln('Spent on healthcare and deathcare', din((c.dinheiro.porServico.HealthCare || [0, 0])[1]) + ' per week') + sugestoesDe('saude') + tabelaServicos(['HealthCare'], 'Clinics, hospitals, crematoriums and cemeteries');
  },
  niveis(c) {
    const S = c.setores, um = (k, rot, n) => S[k].predios ? `<h2>${rot} (${fmt(S[k].predios)} buildings)</h2>` + empilhada(S[k].niveis.slice(0, n).map((v, i) => ({ r: 'Level ' + (i + 1), v, cor: COR_NIVEL[i] })), { fmt: v => v + '%', semPct: true }) : '';
    return um('residencial', 'Residential', 5) + um('comercial', 'Commercial', 3) + um('industrial', 'Industry', 3) + um('escritorios', 'Offices', 3) + sugestoesDe('niveis');
  },
  trafego(c) {
    const T = c.transito, tipos = Object.entries(T.porTipo).sort((a, b) => b[1][1] - a[1][1]).slice(0, 10);
    GRUPOS_VIA = T.piores.map(p => [p[4], p[5]]);
    return ln('Average road occupancy', T.media + '%') + ln('Road segments', fmt(T.trechos)) + ln('Above 50%', fmt(T.acima50)) + ln('Jammed (90% or more)', fmt(T.acima90)) + ln('Vehicles on the road', fmt(T.veiculos)) + ln('Parked cars', fmt(T.estacionados)) +
      sugestoesDe('trafego') + '<h2>Average occupancy by road type</h2>' + barras(tipos.map(t => ({ r: redePT(t[0]), v: t[1][1], extra: fmt(t[1][0]) + ' segments' })), { max: 100, fmt: v => v + '%', cor: '#bf423b' }) +
      '<h2>Busiest segments</h2><table class="tb"><thead><tr><th>Road</th><th>Type</th><th class="n">Occupancy</th></tr></thead><tbody>' +
      T.piores.slice(0, 25).map((p, i) => `<tr class="cl" data-via="${i}" title="Mostrar no mapa"><td>${esc(p[2] || '(unnamed)')}</td><td>${esc(redePT(p[3]))}</td><td class="n">${p[1]}%</td></tr>`).join('') + '</tbody></table>';
  },
  poluicao(c) {
    const x = E.x;
    return ln('Average ground pollution', c.ambiente.poluicaoSolo + '%') + (x ? ln('Residential buildings on polluted ground', fmt(x.resPoluidos) + ' of ' + fmt(x.res)) : '') + ln('Buildings with a pollution warning', fmt((c.predios.problemas.Pollution || [0])[0])) + ln('Water pollution', c.infra.poluicaoAgua + '%') +
      '<p class="nota">The brown stain on the map is contaminated ground. Generic industry, incinerators, landfills and coal or oil power plants are the sources.</p>' + sugestoesDe('poluicao');
  },
  ruido(c) {
    const x = E.x;
    return ln('Buildings with a noise warning', fmt((c.predios.problemas.Noise || [0])[0])) + (x ? ln('Homes with loud noise', fmt(x.resBarulho) + ' of ' + fmt(x.res)) : '') + sugestoesDe('ruido');
  },
  bombeiro(c) {
    return cobLinha('Fire department reach', 'bombeiros') + ln('Buildings on fire', fmt((c.predios.problemas.Fire || [0])[0])) + ln('Burned-down buildings', fmt(c.predios.queimados)) + ln('Spent on the fire department', din((c.dinheiro.porServico.FireDepartment || [0, 0])[1]) + ' per week') +
      sugestoesDe('bombeiro') + tabelaServicos(['FireDepartment'], 'Fire houses and stations');
  },
  crime(c) {
    const Po = c.servicos.policia;
    return ln('Crime rate', Po.taxaCrime + '%') + medidor('Jail cells in use', Po.presos, Po.celas, '') + cobLinha('Police reach', 'policia') + ln('Buildings with high crime', fmt((c.predios.problemas.Crime || [0])[0])) +
      ln('Spent on police', din((c.dinheiro.porServico.PoliceDepartment || [0, 0])[1]) + ' per week') + sugestoesDe('crime') + tabelaServicos(['PoliceDepartment'], 'Police stations') + grafHist('gcri', 'Crime rate over time', [['crime', 'Crime']], { zero: true, fmt: v => fmt(v) + '%' });
  },
  transporte(c) {
    const Tr = c.transporte, modos = { Bus: 'Bus', Metro: 'Metro', Train: 'Train', Ship: 'Ship', Airplane: 'Airplane', Taxi: 'Taxi', Tram: 'Tram', Monorail: 'Monorail', CableCar: 'Cable car', EvacuationBus: 'Evacuation bus', Pedestrian: 'On foot', TouristBus: 'Tourist bus', Helicopter: 'Helicopter', Trolleybus: 'Trolleybus', Fishing: 'Fishing', Post: 'Mail', HotAirBalloon: 'Balloon' };
    const pass = Object.entries(Tr.passageiros).map(e => ({ r: modos[e[0]] || e[0], v: e[1][0] + e[1][1], extra: fmt(e[1][1]) + ' tourists' }));
    const [rec, des] = c.dinheiro.porServico.PublicTransport || [0, 0];
    return ln('Lines inside the city', fmt(Tr.linhas.length)) + cobLinha('Homes with a stop nearby', 'transporte', true) + ln('Ticket income', din(rec) + ' per week') + ln('Transport cost', din(des) + ' per week') +
      sugestoesDe('transporte') + '<h2>Passengers per week</h2>' + (pass.length ? barras(pass, { cor: '#1baf7a' }) : '<p class="nota">Nobody used public transport last week.</p>') +
      '<h2>Lines</h2>' + (Tr.linhas.length ? '<table class="tb"><thead><tr><th>Line</th><th>Type</th><th class="n">Stops</th><th class="n">Passengers</th></tr></thead><tbody>' + Tr.linhas.map(l => `<tr><td>${esc(l[2])}${l[6] ? '' : '<small>incomplete</small>'}</td><td>${esc(modos[l[1]] || l[1])}</td><td class="n">${l[3]}</td><td class="n">${fmt(l[4] + l[5])}</td></tr>`).join('') + '</tbody></table>' : '<p class="nota">No line created. The lines you draw in the game show up here and on the map, in the colour they have in the game.</p>') +
      tabelaServicos(['PublicTransport'], 'Stations and terminals');
  },
  populacao(c) {
    const P = c.populacao, S = c.setores.residencial, id = ['Children', 'Teens', 'Young adults', 'Adults', 'Seniors'];
    return ln('Inhabitants', fmt(P.total)) + ln('Births this week', fmt(P.nascimentos)) + ln('Deaths this week', fmt(P.mortes)) + ln('Life expectancy', P.expectativa + ' years') +
      medidor('Homes occupied', S.total - S.vazios, S.total, '') + '<h2>Ages</h2>' + barras(P.idades.map((v, i) => ({ r: id[i], v, extra: pct(v, P.total) }))) +
      '<h2>Education level</h2>' + barras([{ r: 'Uneducated', v: P.semEstudo.pessoas }, { r: 'Elementary', v: P.fundamental.pessoas }, { r: 'High school', v: P.medio.pessoas }, { r: 'University degree', v: P.superior.pessoas }].map(o => Object.assign(o, { extra: pct(o.v, P.total) })), { cor: '#6e53b5' }) +
      sugestoesDe('populacao') + grafHist('gpop2', 'Population over time', [['pop', 'Inhabitants']], { zero: true });
  },
  conexoes(c) {
    const nomes = { Rodovia: 'Highway', Train: 'Railway', Plane: 'Air route', Ship: 'Ship route' }, Cx = c.comercioExterior;
    const prod = [['mercadorias', 'Goods'], ['agricola', 'Agricultural'], ['madeira', 'Lumber'], ['minerio', 'Ore'], ['petroleo', 'Oil'], ['peixe', 'Fish'], ['correio', 'Mail']];
    GRUPOS_CON = c.conexoes.map(k => [lim(k[1], -8640, 8640), lim(k[2], -8640, 8640)]);
    return `<p>The map shows the whole region (${dec(17.28, 1)} km across). The city only trades people and cargo with the rest of the world through these points.</p>` +
      '<table class="tb"><thead><tr><th>Connection</th><th>Direction</th><th>Linked to the city</th></tr></thead><tbody>' +
      c.conexoes.map((k, i) => `<tr class="cl" data-con="${i}"><td>${nomes[k[0]] || esc(k[0])}</td><td>${k[3] && k[4] ? 'in and out' : k[3] ? 'in' : 'out'}</td><td>${k[5] === 1 ? 'yes' : k[5] === 0 ? '<b style="color:#b02a2a">no</b>' : 'depends on a station'}</td></tr>`).join('') + '</tbody></table>' +
      sugestoesDe('conexoes') + '<h2>Imports per week</h2>' + barras(prod.map(p => ({ r: p[1], v: Cx.importa[p[0]] })).filter(p => p.v > 0), { cor: '#eb6834', fmt: curto }) +
      '<h2>Exports per week</h2>' + (prod.some(p => Cx.exporta[p[0]] > 0) ? barras(prod.map(p => ({ r: p[1], v: Cx.exporta[p[0]] })).filter(p => p.v > 0), { cor: '#2a78d6', fmt: curto }) : '<p class="nota">The city exports nothing at the moment.</p>');
  },
  terreno(c) {
    return ln('Average land value', '₡' + c.ambiente.valorTerreno + '/m²') + (c.distritos.length ? '<h2>By district</h2>' + barras(c.distritos.map(d => ({ r: d[1], v: d[3] })).sort((a, b) => b.v - a.v), { cor: '#a9841c', fmt: v => '₡' + v }) : '') +
      '<p class="nota">It rises with parks, schools, healthcare, police, fire stations and transport nearby. It falls with pollution, noise, crime and garbage.</p>' + sugestoesDe('terreno') + grafHist('gvt', 'Land value over time', [['valorTerreno', 'Value']], { zero: true, fmt: v => '₡' + fmt(v) });
  },
  recursos(c) {
    const R = c.ambiente.recursos, I = c.industria, n = [['soloFertil', 'Fertile land', '#a9841c'], ['floresta', 'Forest', '#1f6b22'], ['minerio', 'Ore', '#2f55a4'], ['petroleo', 'Oil', '#1d1d1d']];
    return '<p>Switch the layer in the map legend to see where each resource sits inside and around your tiles.</p><h2>Usage in the purchased tiles</h2>' +
      n.map(k => R[k[0]][1] > 0 ? medidorNeutro(k[1], R[k[0]][0], R[k[0]][1], k[2]) : ln(k[1], 'none in your tiles')).join('') +
      '<h2>Industry by type</h2>' + barras([['generica', 'Generic'], ['agricola', 'Agricultural'], ['florestal', 'Forestry'], ['minerio', 'Mining'], ['petroleo', 'Oil']].map(k => ({ r: k[1], v: I[k[0]][0], extra: I[k[0]][0] ? 'productivity ' + I[k[0]][1] + '%' : '' })), { fmt: v => fmt(v) + ' cells' }) + sugestoesDe('recursos');
  },
  distritos(c) {
    const pol = c.dinheiro.politicas;
    return ln('Districts created', fmt(c.distritos.length)) + ln('Park, industry or campus areas', fmt(c.parques)) + sugestoesDe('distritos') +
      (c.distritos.length ? '<h2>Districts</h2><table class="tb"><thead><tr><th>District</th><th class="n">Pop.</th><th class="n">Land</th><th class="n">Happy</th><th class="n">Crime</th></tr></thead><tbody>' +
        c.distritos.map(d => `<tr class="cl" data-dist="${d[7]},${d[8]}"><td><b>${esc(d[1])}</b>${d[6] && d[6] !== 'None' ? '<small>' + esc(d[6]) + '</small>' : ''}</td><td class="n">${fmt(d[2])}</td><td class="n">₡${d[3]}</td><td class="n">${d[4]}%</td><td class="n">${d[5]}%</td></tr>`).join('') + '</tbody></table>' : '') +
      '<h2>City-wide policies</h2>' + (pol.length ? '<p>' + pol.map(esc).join(', ') + '</p>' : '<p class="nota">No active policy.</p>');
  },
  lazer(c) {
    return cobLinha('Homes with leisure nearby', 'lazer', true) + ln('Parks and plazas', fmt(c.predios.porServico.Beautification || 0)) + ln('Unique buildings', fmt(c.predios.porServico.Monument || 0)) + ln('Spent on parks', din((c.dinheiro.porServico.Beautification || [0, 0])[1]) + ' per week') +
      sugestoesDe('lazer') + tabelaServicos(['Beautification'], 'Parks and plazas');
  },
  turismo(c) {
    const P = c.populacao, t = P.turistas, vis = P.visitasTuristas;
    return ln('Tourists in the city', fmt(t[0] + t[1] + t[2])) + ln('Visits this week', fmt(vis[0] + vis[1] + vis[2])) + ln('Tourism income', din((c.dinheiro.porServico.Tourism || [0, 0])[0]) + ' per week') +
      '<h2>Tourists by wealth</h2>' + barras([{ r: 'Low wealth', v: t[0] }, { r: 'Medium wealth', v: t[1] }, { r: 'High wealth', v: t[2] }], { cor: '#e87ba4' }) + sugestoesDe('turismo') + tabelaServicos(['Monument'], 'Unique buildings') + tabelaServicos(['Beautification'], 'Parks and plazas');
  },
  emprego(c) {
    const P = c.populacao, S = c.setores, D = c.demanda, niv = [['semEstudo', 'Uneducated'], ['fundamental', 'Elementary'], ['medio', 'High school'], ['superior', 'University degree']];
    const set = [['comercial', 'Commercial', 'ca'], ['industrial', 'Industry', 'in'], ['escritorios', 'Offices', 'es'], ['publico', 'Public service', 'sv']];
    return ln('Unemployment', P.desempregoPct + '%') + ln('Unemployed', fmt(D.desempregados)) + ln('Open jobs', fmt(D.vagasLivres)) + ln('Total jobs', fmt(D.empregos)) +
      '<h2>Unemployed by education level</h2>' + barras(niv.map(n => ({ r: n[1], v: P[n[0]].desempregados, extra: 'of ' + fmt(P[n[0]].aptos) + ' eligible' })), { cor: '#d03b3b' }) +
      '<h2>Jobs by sector</h2>' + empilhada(set.map(s => ({ r: s[1], v: S[s[0]].total, cor: ZONAS[s[2]].cor }))) +
      '<h2>Open jobs by sector</h2>' + barras(set.map(s => ({ r: s[1], v: S[s[0]].vazios, cor: ZONAS[s[2]].cor }))) + sugestoesDe('emprego') +
      grafHist('gdes', 'Unemployment over time', [['desemprego', 'Unemployment']], { zero: true, fmt: v => fmt(v) + '%' });
  },
  industria(c) {
    const Cx = c.comercioExterior, S = c.setores, P = c.predios.problemas, k = n => fmt((P[n] || [0])[0]);
    return ln('Commercial jobs', fmt(S.comercial.total)) + ln('Industrial jobs', fmt(S.industrial.total)) + ln('Office jobs', fmt(S.escritorios.total)) + ln('Goods imported', curto(Cx.importa.mercadorias) + ' per week') +
      '<h2>Supply warnings</h2>' + ln('Shops with no goods', k('NoGoods')) + ln('Shops with no customers', k('NoCustomers')) + ln('Factories with no raw materials', k('NoResources')) + ln('Factories with full storage', k('NoPlaceforGoods')) +
      sugestoesDe('industria') + '<h2>Imports per week</h2>' + barras([['mercadorias', 'Goods'], ['agricola', 'Agricultural'], ['madeira', 'Lumber'], ['minerio', 'Ore'], ['petroleo', 'Oil']].map(p => ({ r: p[1], v: Cx.importa[p[0]] })), { cor: '#eb6834', fmt: curto });
  },
  dinheiro(c) {
    const D = c.dinheiro, saldo = D.receita - D.despesa, e = Object.entries(D.porServico);
    const rec = e.filter(x => x[1][0] > 0).sort((a, b) => b[1][0] - a[1][0]).map(x => ({ r: SERVICO[x[0]] || x[0], v: x[1][0], extra: pct(x[1][0], D.receita) }));
    const des = e.filter(x => x[1][1] > 0).sort((a, b) => b[1][1] - a[1][1]).map(x => ({ r: SERVICO[x[0]] || x[0], v: x[1][1], extra: pct(x[1][1], D.despesa) }));
    const imp = { ResidencialBaixa: 'Low-density residential', ResidencialAlta: 'High-density residential', ComercialBaixa: 'Low-density commercial', ComercialAlta: 'High-density commercial', Industria: 'Industry', Escritorios: 'Offices' };
    return ln('Cash', din(D.caixa)) + ln('Income per week', din(D.receita)) + ln('Expenses per week', din(D.despesa)) + ln('Weekly balance', (saldo >= 0 ? '+' : '−') + din(Math.abs(saldo))) + sugestoesDe('dinheiro') +
      '<h2>Where the income comes from</h2>' + barras(rec, { cor: '#1baf7a', fmt: din }) + '<h2>Where the expenses go</h2>' + barras(des, { cor: '#eb6834', fmt: din }) +
      '<h2>Taxes</h2>' + Object.keys(imp).map(k => ln(imp[k], D.impostos[k] + '%')).join('') + '<h2>Service budgets (day and night)</h2><button class="lk" data-ir="dianoite">Compare day and night usage</button>' + Object.entries(D.orcamento).map(o => ln(SERVICO[o[0]] || o[0], o[1][0] + '%' + (o[1][1] !== o[1][0] ? ' and ' + o[1][1] + '%' : ''))).join('') +
      grafHist('gcx', 'Cash over time', [['caixa', 'Cash']], { fmt: v => '₡' + curto(v) }) + grafHist('grd', 'Income and expenses per week', [['receita', 'Income', '#1baf7a'], ['despesa', 'Expenses', '#eb6834']], { zero: true, fmt: v => '₡' + curto(v) });
  },
  demanda(c) {
    const D = c.demanda, z = c.zonas;
    return '<h2>Demand right now</h2>' + barras([{ r: 'Residential', v: D.r, cor: '#5fbf3a' }, { r: 'Commercial', v: D.c, cor: '#4aa3e8' }, { r: 'Industry and offices', v: D.w, cor: '#f0a71e' }], { max: 100, fmt: v => v + '%' }) +
      ln('Unemployed', fmt(D.desempregados)) + ln('Open jobs', fmt(D.vagasLivres)) + ln('Empty homes', fmt(c.setores.residencial.vazios)) + ln('Tax effect (R, C, I)', [D.ajusteImpostoR, D.ajusteImpostoC, D.ajusteImpostoW].join(', ')) +
      '<p class="nota">Residential rises when there are open jobs and not enough homes. Industry and offices rise when people are out of work. Commercial follows residents, tourists and the goods available.</p>' + sugestoesDe('demanda') +
      '<h2>Zoned cells</h2><table class="tb"><thead><tr><th>Zone</th><th class="n">Total</th><th class="n">Empty</th></tr></thead><tbody>' + Object.keys(ZCEL).filter(k => z[k]).map(k => `<tr><td>${ZONAS[ZCEL[k]].nome}</td><td class="n">${fmt(z[k][0])}</td><td class="n">${fmt(z[k][1])}</td></tr>`).join('') + '</tbody></table>' +
      grafHist('gdem', 'Demand over time', [['demR', 'Residential', '#5fbf3a'], ['demC', 'Commercial', '#4aa3e8'], ['demW', 'Industry and offices', '#f0a71e']], { min: 0, max: 100, fmt: v => fmt(v) + '%' });
  },
  historico(c) {
    const n = E.h && E.h.linhas ? E.h.linhas.length : 0;
    return `<p class="nota">${n} sample(s) recorded, one per in-game week while the game runs with the mod enabled. They live in one CSV file per city, in the CityDashboard folder of the game's data directory.</p>` +
      grafHist('h1', 'Population', [['pop', 'Inhabitants']], { zero: true }) + grafHist('h2', 'Cash', [['caixa', 'Cash']], { fmt: v => '₡' + curto(v) }) +
      grafHist('h3', 'Income and expenses per week', [['receita', 'Income', '#1baf7a'], ['despesa', 'Expenses', '#eb6834']], { zero: true, fmt: v => '₡' + curto(v) }) +
      grafHist('h4', 'Demand', [['demR', 'Residential', '#5fbf3a'], ['demC', 'Commercial', '#4aa3e8'], ['demW', 'Industry and offices', '#f0a71e']], { min: 0, max: 100, fmt: v => fmt(v) + '%' }) +
      grafHist('h5', 'Homes and jobs', [['moradias', 'Homes'], ['empregos', 'Jobs']], { zero: true }) + grafHist('h6', 'Unemployment', [['desemprego', 'Unemployment']], { zero: true, fmt: v => fmt(v) + '%' }) +
      grafHist('h7', 'Happiness', [['felicidade', 'Happiness']], { min: 0, max: 100, fmt: v => fmt(v) + '%' }) + grafHist('h8', 'Land value', [['valorTerreno', 'Value']], { zero: true, fmt: v => '₡' + fmt(v) }) + grafHist('h9', 'Crime rate', [['crime', 'Crime']], { zero: true, fmt: v => fmt(v) + '%' });
  },
  motor(c) {
    const nomes = { predios: 'Buildings', trechosDeRede: 'Road, rail and pipe segments', nos: 'Network nodes', blocosDeZona: 'Zone blocks', veiculos: 'Vehicles on the road', estacionados: 'Parked cars', cidadaos: 'Citizens', pedestresAtivos: 'People on the move', arvores: 'Trees', linhas: 'Transport lines', distritos: 'Districts' };
    const G = c.geral;
    return ln('Simulation', G.pausado ? 'paused' : 'speed ' + G.velocidade) + ln('Measured pace', G.diasPorSegundo > 0 ? dec(G.diasPorSegundo, 2) + ' in-game day per second' : 'measuring') +
      '<h2>Internal game limits</h2><p class="nota">The game has a fixed ceiling for each kind of object. Near the ceiling, things stop appearing without warning.</p>' +
      Object.entries(c.limites).map(e => medidor(nomes[e[0]] || e[0], e[1][0], e[1][1], '')).join('') + sugestoesDe('motor') +
      '<h2>Cost of this panel</h2>' + ['cidade', 'mapa', 'servicos'].map(k => ln({ cidade: 'City numbers', mapa: 'Map', servicos: 'Service buildings' }[k], (E.ms[k] != null ? fmt(E.ms[k]) + ' ms of collection' : 'collection not measured') + (E.ritmo[k] ? ', every ' + dec(E.ritmo[k], 1) + ' s' : ''))).join('') +
      '<p class="nota">The collection runs on the simulation thread, not the render thread: it causes no stutter on screen. If it gets expensive, the page spaces the requests out by itself.</p>' +
      '<h2>About this panel</h2><p class="nota">The mod only reads. It builds nothing, does not touch the money and does not change the simulation. Data is collected when this page asks for it; with the tab closed, the cost is zero.</p>';
  }
};
let GRUPOS_PROB = [], GRUPOS_VIA = [], GRUPOS_CON = [];
function medidorNeutro(rotulo, uso, cap, cor) {
  const p = pc(uso, cap);
  return `<div class="med"><div class="tp"><b>${rotulo}</b><span>${fmt(p)}% used</span></div><div class="tr" role="img" aria-label="${rotulo}: ${fmt(p)}% used"><i style="width:${lim(p, 0, 100)}%;background:${cor}"></i></div></div>`;
}

function cartaoSel() {
  const o = E.sel, m = E.m; if (!o || !m) return '';
  let h;
  if (o.s) {
    const t = m.tipos[o.s[6]], n = o.s[9] != null && o.s[9] >= 0 ? m.ruas[o.s[9]] : '';
    h = `<h3><span>${esc(n || redePT(t.nome))}</span><button data-fechar aria-label="Close">×</button></h3>` + ln('Type', esc(redePT(t.nome))) + (t.serv === 'Road' ? ln('Road occupancy', o.s[7] + '%') : '');
  } else {
    const b = o.b, c = m.cls[b[F.classe]], sv = E.sv ? E.sv.predios.find(p => p[0] === b[F.id]) : null;
    h = `<h3><span>${esc(c.zoneado ? ZONAS[c.z].nome + ', level ' + b[F.nivel] : m.nomes[b[F.nome]] || SERVICO[c.s] || c.s)}</span><button data-fechar aria-label="Close">×</button></h3>`;
    const ps = traduzProblemas(m.problemas[b[F.problema]]);
    if (ps.length) h += `<p style="color:#b02a2a;font-weight:700;margin:0 0 4px">${esc(ps.join(', '))}</p>`;
    if (sv) h += `<pre>${esc(sv[6])}</pre>` + ln('Upkeep', '≈ ' + din(sv[7]) + ' per week') + (sv[8] ? ln('Jobs', fmt(sv[8])) : '') + (sv[9] ? '' : ln('State', 'turned off'));
    if (c.zoneado) h += ln(c.s === 'Residential' ? 'Residents' : 'Workers', b[F.moradores]) + ln('Happiness', b[F.felicidade] + '%') + ln('Healthcare', b[F.saude] + '%');
    h += ln('Land value', '₡' + b[F.valorTerreno]) + ln('Ground pollution', fmt(b[F.poluicao] / 2.55) + '%') + ln('Noise', b[F.ruido]) + ln('Garbage piling up', fmt(b[F.lixo]));
    const dist = b[F.distrito] ? (m.distritos.find(d => d[3] === b[F.distrito]) || [])[0] : null;
    if (dist) h += ln('District', esc(dist));
    h += '<h2 style="margin-top:10px">What reaches this building</h2>' + COBERTURAS.map(k => ln(rotuloCampo(k), b[F[k]] > 0 ? fmt(b[F[k]]) : '<span style="color:#b02a2a">out of reach</span>')).join('');
  }
  return `<div id="sel">${h}</div>`;
}

let ultimoHTML = '';
$('painel').addEventListener('pointerdown', () => { E.segura = true; });
window.addEventListener('pointerup', () => { if (E.segura) { E.segura = false; setTimeout(pintarPainel, 0); } });
window.addEventListener('pointercancel', () => { E.segura = false; });
function pintarPainel(topo) {
  const v = V(), corpo = $('corpo');
  if (v.tela) return pintarTela(topo);
  $('pTitulo').textContent = v.nome; $('pSub').textContent = v.sub || '';
  let h;
  if (!E.c) h = `<p class="nota">${E.noMenu ? 'The game is at the menu. Load or create a city and this page fills itself in.' : 'Waiting for the game to answer at 127.0.0.1:19680.'}</p>`;
  else { GRUPOS = []; h = cartaoSel() + PAINEIS[v.id](E.c); }
  if (h === ultimoHTML && !topo) return;
  if (!topo && (E.segura || document.querySelector('.graf:hover'))) return;   // does not replace the content in the middle of a click or while a chart is being read
  const pos = corpo.scrollTop; ultimoHTML = h; corpo.innerHTML = h; corpo.scrollTop = topo ? 0 : pos;
}
function focar(pts) {
  E.focos = pts || []; if (!E.focos.length) return pedir();
  const xs = E.focos.map(p => p[0]), zs = E.focos.map(p => p[1]), x1 = Math.min(...xs), x2 = Math.max(...xs), z1 = Math.min(...zs), z2 = Math.max(...zs);
  const mg = Math.max(350, (x2 - x1) * 0.15, (z2 - z1) * 0.15); ajustar([x1 - mg, z1 - mg, x2 + mg, z2 + mg]);
}
document.addEventListener('click', ev => {
  const t = ev.target, q = s => t.closest && t.closest(s);
  let el;
  if ((el = q('.visao'))) return trocarVisao(el.dataset.v);
  if ((el = q('[data-ir]'))) return trocarVisao(el.dataset.ir);
  if ((el = q('[data-sub]'))) { E.sub[E.visao] = el.dataset.sub; reconstruir(false); pintarLegenda(); return; }
  if ((el = q('[data-foco]'))) { const s = E.sug[+el.dataset.foco]; if (s && s.area !== E.visao && s.area !== 'cidade' && E.visao !== 'assessor') trocarVisao(s.area); return focar(s && s.foco); }
  if ((el = q('[data-grupo]'))) return focar(GRUPOS[+el.dataset.grupo]);
  if ((el = q('[data-prob]'))) return focar(ondeProb(GRUPOS_PROB[+el.dataset.prob]));
  if ((el = q('[data-via]'))) { const p = GRUPOS_VIA[+el.dataset.via]; E.focos = [p]; return irPara(p[0], p[1], 1.1); }
  if ((el = q('[data-con]'))) { E.focos = [GRUPOS_CON[+el.dataset.con]]; return pedir(); }
  if ((el = q('[data-dist]'))) { const p = el.dataset.dist.split(',').map(Number); return irPara(p[0], p[1], 0.5); }
  if (q('[data-fechar]')) { E.sel = null; pedir(); pintarPainel(); }
  if ((el = q('[data-faixa]'))) { E.faixa = el.dataset.faixa; cacheTela.telaEvo = ''; return pintarTela(); }
  if (q('[data-todos]')) { E.grafFoco = null; cacheTela.telaEvo = ''; return pintarTela(true); }
  if ((el = q('#telaEvo [data-cartao]'))) { E.grafFoco = E.grafFoco ? null : el.dataset.cartao; cacheTela.telaEvo = ''; return pintarTela(true); }
});

// ---------- bottom bar ----------
function pintarBarra() {
  const c = E.c, el = $('barra');
  const vivo = `<div class="fim"><small><span id="vivo" class="${E.vivo ? 'on' : ''}"></span>${E.vivo ? (E.noMenu ? 'game at the menu' : 'live' + (E.ritmo.mapa ? ', map every ' + dec(E.ritmo.mapa, E.ritmo.mapa < 10 ? 1 : 0) + ' s' : '')) : 'no connection to the game'}</small></div>`;
  if (!c) { el.innerHTML = '<div class="cid"><b>City Dashboard</b><span>Cities: Skylines</span></div>' + vivo; return; }
  const D = c.dinheiro, saldo = D.receita - D.despesa, dm = c.demanda, G = c.geral;
  const b = (v, cor, r) => `<div title="${r}: ${v}%"><i style="height:${lim(v, 0, 100)}%;background:${cor}"></i></div>`;
  el.innerHTML = `<div class="cid"><b>${esc(G.cidade)}</b><span>${dataBR(G.data)}, ${G.pausado ? 'paused' : 'speed ' + G.velocidade}</span></div>
    <div class="rci" role="img" aria-label="Demand: residential ${dm.r}%, commercial ${dm.c}%, industry and offices ${dm.w}%">${b(dm.r, 'var(--res)', 'Residential')}${b(dm.c, 'var(--com)', 'Commercial')}${b(dm.w, 'var(--ind)', 'Industry and offices')}<span>R ${dm.r}<br>C ${dm.c}<br>I ${dm.w}</span></div>
    <div class="bl"><b>${din(D.caixa)}</b><small class="${saldo >= 0 ? 'pos' : 'neg'}">${saldo >= 0 ? '+' : '−'}${din(Math.abs(saldo))} per week</small></div>
    <div class="bl"><b>${fmt(c.populacao.total)}</b><small>inhabitants</small></div>
    <div class="bl"><b>${c.populacao.felicidade}%</b><small>happiness</small></div>
    <div class="bl"><b>${c.populacao.desempregoPct}%</b><small>unemployment</small></div>` + vivo;
}

// ---------- refresh cycle ----------
function aviso(t, s) { const a = $('aviso'); if (!t) { a.hidden = true; return; } a.hidden = false; a.innerHTML = `<b>${t}</b>${s || ''}`; }
async function cicloCidade() {
  try {
    const c = JSON.parse(await pegaTexto('cidade')); E.vivo = true;
    if (c.erro) { $('erro').hidden = false; $('erro').textContent = 'The mod answered with an error: ' + c.erro; }
    else if (!c.carregado) { E.noMenu = true; E.c = null; aviso('The game is at the menu', 'Load or create a city. This page fills itself in.'); }
    else { E.noMenu = false; E.c = c; E.sug = regras(c); aviso(null); $('erro').hidden = true; document.title = c.geral.cidade + ' – City Dashboard'; }
  } catch (e) { E.vivo = false; if (!E.c) aviso('No connection to the game', 'Open Cities: Skylines. With the City Dashboard mod enabled, this page comes back by itself.'); }
  pintarBarra(); pintarMarcas(); pintarPainel();
}
let textoMapa = '';
async function cicloMapa() {
  if (V().tela && E.m) return;   // full-screen view open: the map is not visible
  try {
    const txt = await pegaTexto('mapa');
    if (txt === textoMapa) return;            // nothing changed in the game: redo nothing
    const m = JSON.parse(txt); if (!m.carregado || m.erro) return;
    textoMapa = txt;
    const sel = E.sel ? (E.sel.b ? ['b', E.sel.b[F.id]] : ['s', E.sel.s[8]]) : null;
    E.m = prepararMapa(m); reconstruir(true);
    if (sel) { if (sel[0] === 'b') { const b = m.predios.find(p => p[F.id] === sel[1]); E.sel = b ? { b } : null; } else { const s = m.redes.find(p => p[8] === sel[1]); E.sel = s ? { s } : null; } }
    if (!M.ajustado || M.cidade !== (E.c && E.c.geral.cidade)) {
      M.ajustado = true; M.cidade = E.c && E.c.geral.cidade;
      if (E.visao === 'conexoes') ajustar([-8900, -8900, 8900, 8900]); else ajustar();
      // optional URL shortcuts: ?x=...&z=...&zoom=2 opens the map at a point; ?sub=funeraria picks the layer
      const q = new URLSearchParams(location.search);
      if (q.get('zoom')) irPara(+q.get('x') || M.cx, +q.get('z') || M.cz, 0), M.k = +q.get('zoom');
      if (q.get('sub')) { E.sub[E.visao] = q.get('sub'); reconstruir(false); }
    }
    if (E.c) { E.sug = regras(E.c); pintarMarcas(); pintarPainel(); }
    pintarLegenda();
  } catch (e) { if (E.vivo) { $('erro').hidden = false; $('erro').textContent = 'Error while building the map: ' + e.message; console.error(e); } }
}
async function cicloServicos() { try { const s = JSON.parse(await pegaTexto('servicos')); if (s.carregado && !s.erro) E.sv = s; } catch (e) { } pintarPainel(); }
async function cicloHistorico() { try { E.h = await pega('historico'); } catch (e) { } pintarPainel(); }
async function cicloDN() {
  try {
    const r = await fetch('/api/dianoite', { cache: 'no-store' });
    if (r.status === 404) E.dn = { semRota: true };          // old mod still in the game's memory
    else { const j = await r.json(); E.dn = j.carregado ? j : null; }
  } catch (e) { }
  if (V().tela === 'dianoite') pintarTela();
}

// Each loop waits for the previous request to finish before scheduling the next. The interval grows by itself if the
// collection gets expensive: at most ~5% of the game's time goes to the panel, even in a huge city. A hidden tab asks for nothing.
async function laco(nome, fn, base) {
  let ultimo = 0;
  for (;;) {
    if (document.visibilityState === 'visible' || !ultimo) {
      const t0 = performance.now();
      await fn();
      const gasto = performance.now() - t0;
      if (ultimo) E.ritmo[nome] = (t0 - ultimo) / 1000;
      ultimo = t0;
      const intervalo = Math.max(base, gasto * 3, (E.ms[nome] || 0) * 20);   // from the start of one request to the start of the next
      await espera(Math.max(0, intervalo - gasto));
    } else await espera(500);
  }
}
montarTrilho();
E.visao = VISOES.some(v => v.id === location.hash.slice(1)) ? location.hash.slice(1) : 'cidade';
$('app').classList.toggle('modo-tela', !!V().tela);
pintarLegenda(); pintarBarra(); pintarMarcas(); pintarPainel(true);
window.addEventListener('hashchange', () => trocarVisao(location.hash.slice(1), true));
(async function () {
  await cicloCidade(); await cicloMapa(); await cicloServicos(); await cicloHistorico(); await cicloDN();
  await espera(1000);
  laco('cidade', cicloCidade, 2000); laco('mapa', cicloMapa, 2000); laco('servicos', cicloServicos, 6000); laco('historico', cicloHistorico, 5000); laco('dianoite', cicloDN, 4000);
})();
