// ---------- full-screen views: Charts and Day and night (they take the place of the map and the panel) ----------
E.faixa = 'tudo'; E.grafFoco = null; E.dn = null;
const FAIXAS = [['tudo', 'All'], ['10a', '10 years'], ['2a', '2 years'], ['6m', '6 months']];
const dinC = v => '₡' + curto(v), pctF = v => fmt(v) + '%';
const GRAFICOS_TELA = [
  { id: 'tPop', t: 'Population', s: [['pop', 'Inhabitants', '#2a78d6']], o: { zero: true } },
  { id: 'tCaixa', t: 'Cash', s: [['caixa', 'Cash', '#1baf7a']], o: { fmt: dinC } },
  { id: 'tRecDes', t: 'Income and expenses per week', s: [['receita', 'Income', '#1baf7a'], ['despesa', 'Expenses', '#eb6834']], o: { zero: true, fmt: dinC } },
  { id: 'tSaldo', t: 'Weekly balance', s: [['__saldo', 'Balance', '#2a78d6']], o: { zero: true, fmt: dinC } },
  { id: 'tDem', t: 'Demand', s: [['demR', 'Residential', '#3f9a2c'], ['demC', 'Commercial', '#2a78d6'], ['demW', 'Industry and offices', '#eda100']], o: { min: 0, max: 100, fmt: pctF } },
  { id: 'tMorEmp', t: 'Homes and jobs', s: [['moradias', 'Homes', '#3f9a2c'], ['empregos', 'Jobs', '#6250d6']], o: { zero: true } },
  { id: 'tDes', t: 'Unemployment', s: [['desemprego', 'Unemployment', '#eb6834']], o: { zero: true, fmt: pctF } },
  { id: 'tFel', t: 'Happiness', s: [['felicidade', 'Happiness', '#1baf7a']], o: { min: 0, max: 100, fmt: pctF } },
  { id: 'tVt', t: 'Land value', s: [['valorTerreno', 'Value', '#a9841c']], o: { zero: true, fmt: v => '₡' + fmt(v) } },
  { id: 'tCri', t: 'Crime rate', s: [['crime', 'Crime', '#6250d6']], o: { zero: true, fmt: pctF } }
];
function linhasHist() {
  if (!E.h || !E.h.linhas || !E.h.linhas.length) return [];
  const L = E.h.linhas.map(l => l.split(',')), dias = { '10a': 3650, '2a': 730, '6m': 183 }[E.faixa];
  if (!dias) return L;
  const ini = new Date(L[L.length - 1][0]).getTime() - dias * 864e5, r = L.filter(l => new Date(l[0]).getTime() >= ini);
  return r.length >= 2 ? r : L.slice(-2);
}
// replaces the content only when it changes (does not drop a tooltip or a click halfway)
let cacheTela = {};
function poe(id, html) { if (cacheTela[id] === html) return; cacheTela[id] = html; const el = $(id); if (el) el.innerHTML = html; }
function esqueleto(v, html) { const c = $('telaCorpo'); if (c.dataset.v === v) return; c.dataset.v = v; c.innerHTML = html; cacheTela = {}; $('tela').scrollTop = 0; }
const cartao = (t, corpo, extra) => `<section class="cartao"><header><h2>${t}</h2>${extra || ''}</header>${corpo}</section>`;
const corUso = p => p >= 97 ? '#d03b3b' : p >= 88 ? '#ec835a' : p >= 80 ? '#c98d00' : '#3b79a8';

function cartoesAgora(c) {
  if (!c) return '';
  const I = c.infra, S = c.servicos, P = c.populacao, St = c.setores, D = c.dinheiro, Ed = S.educacao, T = c.transito, Cx = c.comercioExterior;
  const uso = [['Electricity', I.energia], ['Water', I.agua], ['Sewage', I.esgoto], ['Landfills', [I.lixo.acumulado, I.lixo.capacidadeAterros]], ['Garbage burning', [I.lixo.producaoSemanal, I.lixo.incineracaoSemanal]],
    ['Hospital beds', [S.saude.doentes, S.saude.capacidadeTratamento]], ['Cemeteries', [S.funeraria.sepultados, S.funeraria.capacidadeCemiterios]], ['Jail cells', [S.policia.presos, S.policia.celas]],
    ['Elementary school', Ed.fundamental], ['High school', Ed.medio], ['University', Ed.superior]]
    .filter(u => u[1][1] > 0).map(u => ({ r: u[0], v: pc(u[1][0], u[1][1]), cor: corUso(pc(u[1][0], u[1][1])) }));
  const idades = ['Children', 'Teens', 'Young adults', 'Adults', 'Seniors'], niv = [['semEstudo', 'Uneducated'], ['fundamental', 'Elementary'], ['medio', 'High school'], ['superior', 'University degree']];
  const set = [['comercial', 'Commercial', 'ca'], ['industrial', 'Industry', 'in'], ['escritorios', 'Offices', 'es'], ['publico', 'Public service', 'sv']];
  const e = Object.entries(D.porServico), rec = e.filter(x => x[1][0] > 0).sort((a, b) => b[1][0] - a[1][0]).map(x => ({ r: SERVICO[x[0]] || x[0], v: x[1][0], extra: pct(x[1][0], D.receita) }));
  const des = e.filter(x => x[1][1] > 0).sort((a, b) => b[1][1] - a[1][1]).map(x => ({ r: SERVICO[x[0]] || x[0], v: x[1][1], extra: pct(x[1][1], D.despesa) }));
  const nivel = (k, rot, n) => St[k].predios ? `<p class="sub">${rot}, ${fmt(St[k].predios)} buildings</p>` + empilhada(St[k].niveis.slice(0, n).map((v, i) => ({ r: 'Level ' + (i + 1), v, cor: COR_NIVEL[i] })), { fmt: v => v + '%', semPct: true }) : '';
  const vias = Object.entries(T.porTipo).sort((a, b) => b[1][1] - a[1][1]).slice(0, 8).map(t => ({ r: redePT(t[0]), v: t[1][1], extra: fmt(t[1][0]) + ' segments' }));
  const prod = [['mercadorias', 'Goods'], ['agricola', 'Agricultural'], ['madeira', 'Lumber'], ['minerio', 'Ore'], ['petroleo', 'Oil'], ['peixe', 'Fish']];
  const imp = prod.map(p => ({ r: p[1], v: Cx.importa[p[0]] })).filter(p => p.v > 0), exp = prod.map(p => ({ r: p[1], v: Cx.exporta[p[0]] })).filter(p => p.v > 0);
  const avisos = Object.entries(c.predios.problemas).sort((a, b) => b[1][0] - a[1][0]).slice(0, 10).map(p => ({ r: PROB[p[0]] || p[0], v: p[1][0], extra: (p[1][1] + p[1][2]) ? (p[1][1] + p[1][2]) + ' major' : '' }));
  const zon = Object.keys(ZCEL).filter(k => c.zonas[k]).map(k => ({ r: ZONAS[ZCEL[k]].nome, v: c.zonas[k][0] - c.zonas[k][1], cor: ZONAS[ZCEL[k]].cor, extra: fmt(c.zonas[k][1]) + ' empty' }));
  const vazio = '<p class="nota">Nothing to show yet.</p>';
  return cartao('Capacity in use', uso.length ? barras(uso, { max: 100, fmt: pctF }) : vazio) +
    cartao('Ages', barras(P.idades.map((v, i) => ({ r: idades[i], v, extra: pct(v, P.total) })), { cor: '#2a78d6' })) +
    cartao('Education level', barras(niv.map(n => ({ r: n[1], v: P[n[0]].pessoas, extra: pct(P[n[0]].pessoas, P.total) })), { cor: '#6e53b5' })) +
    cartao('Unemployed by education level', barras(niv.map(n => ({ r: n[1], v: P[n[0]].desempregados, extra: 'of ' + fmt(P[n[0]].aptos) + ' eligible' })), { cor: '#eb6834' })) +
    cartao('Jobs by sector', barras(set.map(s => ({ r: s[1], v: St[s[0]].total, cor: ZONAS[s[2]].cor, extra: fmt(St[s[0]].vazios) + ' open' })))) +
    cartao('Where the income comes from', rec.length ? barras(rec, { cor: '#1baf7a', fmt: din }) : vazio) +
    cartao('Where the expenses go', des.length ? barras(des, { cor: '#eb6834', fmt: din }) : vazio) +
    cartao('Building levels', (nivel('residencial', 'Residential', 5) + nivel('comercial', 'Commercial', 3) + nivel('industrial', 'Industry', 3) + nivel('escritorios', 'Offices', 3)) || vazio) +
    cartao('Zoned cells in use', zon.length ? barras(zon, { fmt: v => fmt(v) }) : vazio) +
    cartao('Average road occupancy', vias.length ? barras(vias, { max: 100, fmt: pctF, cor: '#bf423b' }) : vazio) +
    cartao('Imports and exports per week', (imp.length ? '<p class="sub">Imports</p>' + barras(imp, { cor: '#eb6834', fmt: curto }) : '') + (exp.length ? '<p class="sub">Exports</p>' + barras(exp, { cor: '#2a78d6', fmt: curto }) : '') || vazio) +
    cartao('Building warnings right now', avisos.length ? barras(avisos, { cor: '#d03b3b' }) : '<p class="nota">No building with a warning.</p>');
}

const COL_PT = { data: 'Date', pop: 'Population', caixa: 'Cash', receita: 'Income', despesa: 'Expenses', demR: 'Dem. R', demC: 'Dem. C', demW: 'Dem. I', desemprego: 'Unemployment %', felicidade: 'Happiness %', empregos: 'Jobs', moradias: 'Homes', valorTerreno: 'Land value', crime: 'Crime %' };
function pintarGraficos() {
  esqueleto('graficos', '<h2 class="sec" id="telaEvoT">Over time</h2><div class="grade" id="telaEvo"></div><div id="telaResto"><h2 class="sec">Right now</h2><div class="grade" id="telaAgora"></div><details id="telaTabela"><summary>Data table</summary><div id="telaTabelaIn"></div></details></div>');
  const L = linhasHist(), cols = E.h ? E.h.colunas : [], iR = cols.indexOf('receita'), iD = cols.indexOf('despesa');
  const col = n => n === '__saldo' ? L.map(l => +l[iR] - +l[iD]) : L.map(l => +l[cols.indexOf(n)]), datas = L.map(l => l[0]);
  $('telaTitulo').textContent = 'Charts';
  poe('telaSub', E.h && E.h.linhas && E.h.linhas.length ? `${esc(E.h.cidade || '')}: ${fmt(E.h.linhas.length)} samples, one per in-game week. Click a chart to enlarge it.` : 'History starts being recorded when the game runs with a city loaded.');
  poe('telaBotoes', (E.grafFoco ? '<button class="volta" data-todos>See all charts</button>' : '') + '<div class="seg" role="group" aria-label="Period">' + FAIXAS.map(f => `<button data-faixa="${f[0]}" aria-pressed="${E.faixa === f[0]}">${f[1]}</button>`).join('') + '</div>');
  const lista = E.grafFoco ? GRAFICOS_TELA.filter(g => g.id === E.grafFoco) : GRAFICOS_TELA, evo = $('telaEvo');
  evo.classList.toggle('foco', !!E.grafFoco); $('telaEvoT').hidden = !!E.grafFoco; $('telaResto').hidden = !!E.grafFoco;
  if (!evo.querySelector('.graf:hover') || !cacheTela.telaEvo)
    poe('telaEvo', lista.map(g => graficoGrande(g.id, g.t, g.s.map(s => ({ r: s[1], v: col(s[0]), cor: s[2] })), datas, Object.assign({ foco: !!E.grafFoco }, g.o))).join(''));
  if (E.grafFoco) return;
  poe('telaAgora', cartoesAgora(E.c));
  poe('telaTabelaIn', L.length ? '<table class="tb"><thead><tr>' + cols.map((c, i) => `<th class="${i ? 'n' : ''}">${COL_PT[c] || c}</th>`).join('') + '</tr></thead><tbody>' +
    L.slice(-200).reverse().map(l => '<tr>' + l.map((v, i) => `<td class="${i ? 'n' : ''}">${i ? fmt(+v) : dataBR(v)}</td>`).join('') + '</tr>').join('') + '</tbody></table>' : '<p class="nota">No samples yet.</p>');
}

// ---------- day and night ----------
// How much of the nominal capacity a budget delivers (the game's formula): 50% → 25%, 80% → 64%, 100% → 100%, 120% → 116%, 150% → 125%.
const taxaOrc = b => b < 100 ? (b * b + 99) / 100 : b > 150 ? 125 : b - (100 - b) * (100 - b) / 100;
function orcamentoPara(taxa) { for (let b = 50; b <= 150; b++) if (taxaOrc(b) >= taxa) return b; return 150; }
const FRACAO = [0.625, 0.375];   // 15 h of day and 9 h of night on the game clock
const PERIODO = ['during the day', 'at night'], COR_DN = ['#eda100', '#2f55a4'];
const ITENS_DN = [
  { serv: 'Electricity', nome: 'Electricity', piso: 50, m: [['energia', 'Generation in use', v => fmt(v / 1000) + ' MW']] },
  { serv: 'Water', nome: 'Water and sewage', piso: 50, m: [['agua', 'Pumped water in use', v => curto(v) + ' m³/week'], ['esgoto', 'Sewage drained', v => curto(v) + ' m³/week']] },
  { serv: 'Garbage', nome: 'Garbage', piso: 50, m: [['lixo', 'Burning capacity in use', v => curto(v) + '/week'], ['vLixo', 'Garbage trucks on the road', v => dec(v, 1)]] },
  { serv: 'HealthCare', nome: 'Healthcare and deathcare', piso: 90, m: [['saude', 'Hospital beds in use', v => fmt(v)], ['vSaude', 'Ambulances on the road', v => dec(v, 1)], ['vFuneraria', 'Hearses on the road', v => dec(v, 1)]] },
  { serv: 'FireDepartment', nome: 'Fire department', piso: 90, m: [['vBombeiro', 'Fire trucks on the road', v => dec(v, 1)]] },
  { serv: 'PoliceDepartment', nome: 'Police', piso: 90, m: [['vPolicia', 'Police cars on the road', v => dec(v, 1)], ['celas', 'Jail cells in use', v => fmt(v), true]] },
  { serv: 'Education', nome: 'Education', piso: 90, m: [['ensino', 'People of school age for the seats', v => fmt(v)]] },
  { serv: 'Road', nome: 'Roads', piso: 90, m: [['vRuas', 'Maintenance trucks on the road', v => dec(v, 1)]] }
];
/** Compares day and night and works out the suggested budget for each period, item by item. */
function analisarDN(c, dn) {
  if (!c || !dn || !dn.itens) return [];
  const fases = dn.ciclo ? [0, 1] : [0];
  return ITENS_DN.map(it => {
    const orc = c.dinheiro.orcamento[it.serv] || [100, 100], gasto = (c.dinheiro.porServico[it.serv] || [0, 0])[1];
    const porPonto = gasto / (dn.ciclo ? FRACAO[0] * orc[0] + FRACAO[1] * orc[1] : orc[0]);   // weekly cost of each budget point
    const met = it.m.map(m => ({ ch: m[0], rot: m[1], f: m[2], info: !!m[3], fase: fases.map(p => { const x = dn.itens[m[0]] ? dn.itens[m[0]][p] : null; return x && x[1] > 0 ? { dem: x[0], cap: x[1], uso: x[0] / x[1] * 100, pico: Math.max(x[2], x[0] / x[1] * 100) } : null; }) }));
    const rec = fases.map(p => {
      if (dn.amostras[p] < 30) return { p, estado: 'measuring' };
      let precisa = 0, quem = null;
      for (const m of met) { const x = m.fase[p]; if (!x || m.info) continue; const t = x.pico / 100 * taxaOrc(orc[p]) / 0.85; if (t > precisa) { precisa = t; quem = m; } }
      if (!quem) return { p, estado: 'semMedida' };
      const bruto = Math.ceil(orcamentoPara(precisa) / 5) * 5, alvo = lim(bruto, it.piso, 150), atual = orc[p];
      const r = { p, atual, alvo, quem, pico: quem.fase[p].pico, falta: precisa > 122, noPiso: bruto < it.piso && it.piso > 50, custo: porPonto * (dn.ciclo ? FRACAO[p] : 1) * (alvo - atual) };
      r.estado = Math.abs(alvo - atual) < 5 ? 'manter' : alvo > atual ? 'subir' : 'baixar';
      return r;
    });
    return { it, orc, gasto, met, rec };
  }).filter(a => a.met.some(m => m.fase.some(Boolean)) || a.gasto > 0);
}
function textoRec(a, r) {
  const quando = PERIODO[r.p], nome = a.it.nome;
  if (r.estado === 'measuring') return { sev: 0, t: `Measuring ${quando}`, x: 'There is not a minute of running game in this period yet. Let the game run and the recommendation shows up.' };
  if (r.estado === 'semMedida') return { sev: 0, t: `No measurement ${quando}`, x: 'The city has no facilities of this service with measurable usage yet.' };
  const uso = `${r.quem.rot.toLowerCase()} reaches ${fmt(r.pico)}% ${quando}`;
  if (r.estado === 'manter') return { sev: 0, t: `${quando[0].toUpperCase() + quando.slice(1)}: keep at ${r.atual}%`, x: `Right-sized: ${uso}.` + (r.noPiso ? ' Capacity alone would allow a deeper cut, but the budget also shrinks the service\'s reach on the map.' : '') };
  if (r.estado === 'subir') return { sev: r.pico >= 100 ? 2 : 1, t: `${quando[0].toUpperCase() + quando.slice(1)}: raise from ${r.atual}% to ${r.alvo}%`, x: `${uso[0].toUpperCase() + uso.slice(1)}. ` + (r.falta ? 'Even at the maximum the budget only yields 125% of the capacity: besides raising it, more facilities are needed. ' : '') + (r.custo > 0 ? `Costs about ${din(r.custo)} more per week.` : '') };
  return { sev: 0, t: `${quando[0].toUpperCase() + quando.slice(1)}: can be lowered from ${r.atual}% to ${r.alvo}%`, x: `${uso[0].toUpperCase() + uso.slice(1)}, with room to spare. Saves about ${din(-r.custo)} per week.` + (r.noPiso ? ' I do not suggest less than that because the budget also shrinks the service\'s reach.' : ''), economia: -r.custo };
}
/** Feeds the advisor: increases become alerts, cuts become a single tip. */
function regrasDN(add, c) {
  const an = analisarDN(c, E.dn); let economia = 0;
  for (const a of an) for (const r of a.rec) {
    const t = textoRec(a, r);
    if (r.estado === 'subir') add('dianoite', t.sev, `${a.it.nome}: ${t.t.toLowerCase()}`, t.x);
    if (r.estado === 'baixar') economia += t.economia;
  }
  if (economia > 0) add('dianoite', 0, `Budgets with room to spare: about ${din(economia)} per week`, 'Some services have spare capacity in one of the periods. The Day and night screen shows which ones and how far to lower them.');
}
function pintarDiaNoite() {
  esqueleto('dianoite', '<div id="dnResumo"></div><div class="grade" id="dnGrade"></div><div id="dnRodape"></div>');
  $('telaTitulo').textContent = 'Day and night';
  poe('telaBotoes', '');
  const dn = E.dn, c = E.c;
  if (dn && dn.semRota) { poe('telaSub', ''); poe('dnResumo', '<p class="aviso-tela"><b>This screen needs the newer version of the mod.</b> It is already installed, but the game only loads it on start: save, quit to desktop and open the game again. The rest of the panel keeps working as it is.</p>'); poe('dnGrade', ''); poe('dnRodape', ''); return; }
  if (!dn || !c) { poe('telaSub', 'Waiting for the game.'); poe('dnResumo', ''); poe('dnGrade', ''); poe('dnRodape', ''); return; }
  const min = p => fmt(dn.amostras[p] * dn.segundosPorAmostra / 60), an = analisarDN(c, dn), h = Math.floor(dn.hora), mi = Math.floor((dn.hora - h) * 60);
  poe('telaSub', 'Usage of each service in both periods and the budget each one asks for. In the game, the setting is under Economy, Budget tab: every service has one slider with a sun and one with a moon.');
  let economia = 0, reforcos = 0;
  const cartoes = an.map(a => {
    const corpo = a.met.filter(m => m.fase.some(Boolean)).map(m => `<p class="sub">${m.rot}</p>` + barras(m.fase.map((x, p) => x ? { r: p ? 'Night' : 'Day', v: x.uso, cor: COR_DN[p], extra: `peak ${fmt(x.pico)}%, average ${m.f(x.dem)}` } : null).filter(Boolean), { max: 100, fmt: pctF })).join('');
    const recs = a.rec.map(r => { const t = textoRec(a, r); if (r.estado === 'baixar') economia += t.economia; if (r.estado === 'subir') reforcos++; return `<div class="sug s${t.sev}"><h3><span>${t.t}</span></h3><p>${t.x}</p></div>`; }).join('');
    return cartao(a.it.nome, (corpo || '<p class="nota">No facilities with measurable usage.</p>') + recs, `<div class="orc">budget ${dn.ciclo ? `day<b>${a.orc[0]}%</b>night<b>${a.orc[1]}%</b>` : `<b>${a.orc[0]}%</b>`}${a.gasto ? din(a.gasto) + '/week' : ''}</div>`);
  });
  const t = dn.itens.trafego, mv = dn.itens.movimento;
  if (dn.ciclo && (t[0][0] + t[1][0] > 0 || mv[0][0] + mv[1][0] > 0)) cartoes.push(cartao('City activity', '<p class="sub">Average road occupancy</p>' + barras([{ r: 'Day', v: t[0][0], cor: COR_DN[0] }, { r: 'Night', v: t[1][0], cor: COR_DN[1] }], { max: 100, fmt: v => dec(v, 1) + '%' }) +
    '<p class="sub">People on the move</p>' + barras([{ r: 'Day', v: mv[0][0], cor: COR_DN[0] }, { r: 'Night', v: mv[1][0], cor: COR_DN[1] }]) + '<p class="nota">For comparison only: the roads budget has no capacity measure.</p>'));
  poe('dnResumo', (dn.ciclo ? '' : '<p class="aviso-tela">The day/night cycle is turned off in the game options: only the day budget applies, and that is the one shown here.</p>') +
    `<div class="resumo-dn"><div><b>${dn.ciclo ? (dn.noite ? 'Night' : 'Day') + ', ' + String(h).padStart(2, '0') + ':' + String(mi).padStart(2, '0') : 'No cycle'}</b><span>in the game right now</span></div>
     <div><b>${min(0)} min${dn.ciclo ? ' and ' + min(1) + ' min' : ''}</b><span>measured ${dn.ciclo ? 'by day and by night' : ''} with the game running</span></div>
     <div><b>${reforcos}</b><span>period(s) asking for more budget</span></div><div><b>${din(economia)}</b><span>per week of slack that could be cut</span></div></div>`);
  poe('dnGrade', cartoes.join(''));
  poe('dnRodape', `<p class="nota" style="max-width:110ch">How to read it: the bar is the average usage over the last minutes of each period, and the peak is the highest recent value. The suggestion sizes the budget so the peak sits at 85% of the capacity. The maths follows the game's rule: below 100% the capacity falls with the square (an 80% budget yields 64%), and above 100% it yields less and less (150% yields 125%), while the cost follows the budget in a straight line. After moving a slider, wait a few in-game minutes for the average to catch up. Parks, unique buildings and transport have no capacity measure, so they are left out. A paused game does not count.</p>`);
}
function pintarTela(topo) { if (V().tela === 'dianoite') pintarDiaNoite(); else pintarGraficos(); if (topo) $('tela').scrollTop = 0; }
window.addEventListener('keydown', e => { if (e.key === 'Escape' && E.grafFoco) { E.grafFoco = null; pintarTela(true); } });
