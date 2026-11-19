// ---------- advisor: rules that read the numbers and say what to do ----------
// severity: 3 critical, 2 serious, 1 warning, 0 tip (does not light an alert in the rail)
function onde(fn, max) {
  const r = []; if (!E.m) return r;
  for (const b of E.m.predios) { if (fn(b, E.m.cls[b[F.classe]], E.m.problemas[b[F.problema]])) { r.push([b[F.x], b[F.z]]); if (r.length >= (max || 120)) break; } }
  return r;
}
const ondeProb = (...ks) => onde((b, c, p) => p && ks.some(k => p.indexOf(k) >= 0));

function regras(c) {
  const R = [], x = E.x, m = E.m;
  const add = (area, sev, titulo, texto, foco, irPara) => R.push({ area, sev, titulo, texto, foco: foco && foco.length ? foco : null, irPara });
  const P = c.predios.problemas, np = k => P[k] ? P[k][0] : 0, ng = k => P[k] ? P[k][1] + P[k][2] : 0;
  const pop = c.populacao.total, D = c.dinheiro, orc = k => D.orcamento[k] ? D.orcamento[k][0] : 100;
  const gasto = k => D.porServico[k] ? D.porServico[k][1] : 0;
  const cobre = k => x && x.zon ? pc(x.cob[k], x.zon) : null, cobreRes = k => x && x.res ? pc(x.cobRes[k], x.res) : null;
  if (pop === 0 && c.setores.residencial.predios === 0) {   // freshly opened map: the buildings that exist belong to the map itself
    add('cidade', 0, 'Newly founded city', 'Start by connecting a road to the highway, zone a small residential neighbourhood and add water (pump upstream, sewage downstream) and electricity. The panel starts pointing out the rest as the city grows.');
    return R;
  }

  // ----- electricity
  const [eu, ec] = c.infra.energia, ep = pc(eu, ec);
  if (ec === 0) add('energia', 3, 'The city generates no electricity', 'No power plant is running. Without electricity buildings are abandoned within a few weeks.');
  else if (ep >= 97) add('energia', 3, 'Power grid at its limit', `${fmt(eu / 1000)} MW consumed out of ${fmt(ec / 1000)} MW generated (${fmt(ep)}%). Any new neighbourhood causes a blackout: build generation before zoning.`);
  else if (ep >= 88) add('energia', 2, 'Little electricity headroom', `${fmt(ep)}% of the generation in use. Leave at least 15% of headroom: wind and solar vary with the wind and the time of day.`);
  else if (ep >= 80) add('energia', 1, 'Electricity headroom shrinking', `${fmt(ep)}% of the generation in use. Plan the next power plant.`);
  else if (ep < 50 && pop > 3000) add('energia', 0, 'Spare generation', `Only ${fmt(ep)}% of the generation is used: ${fmt((ec - eu) / 1000)} MW sitting idle. Electricity costs ${din(gasto('Electricity'))} per week; you can turn plants off (the on/off button on the building) and turn them back on when the city grows.`);
  const semLuz = np('Electricity') + np('ElectricityNotConnected');
  if (semLuz) add('energia', semLuz > 20 ? 3 : 2, `${fmt(semLuz)} buildings without electricity`, ep < 95 ? 'There is spare generation, so it is a connection problem: electricity only passes from building to building when they nearly touch (about 20 m). An isolated neighbourhood needs a power line to the grid.' : 'Not enough generation to serve everyone.', ondeProb('Electricity'));

  // ----- water
  const [au, ac] = c.infra.agua, [su, sc] = c.infra.esgoto, ap = pc(au, ac), sp = pc(su, sc);
  if (ac === 0 && pop > 0) add('agua', 3, 'No water supply', 'Build a pumping station upstream or a water tower on clean ground.');
  else if (ap >= 97) add('agua', 3, 'Water at its limit', `${fmt(ap)}% of the supply in use (${fmt(au)} of ${fmt(ac)} m³ per week). Expand before zoning.`);
  else if (ap >= 88) add('agua', 2, 'Little water headroom', `${fmt(ap)}% of the supply in use. Every new high-density neighbourhood uses tens of thousands of m³ per week.`);
  if (sc === 0 && pop > 0) add('agua', 3, 'No sewage outlet', 'Without an outlet the sewage backs up into the buildings and people get sick.');
  else if (sp >= 97) add('agua', 3, 'Sewage at its limit', `${fmt(sp)}% of the sewage capacity in use. Add outlets downstream of the water intake, or treatment plants.`);
  else if (sp >= 88) add('agua', 2, 'Little sewage headroom', `${fmt(sp)}% of the sewage capacity in use.`);
  if (c.infra.poluicaoAgua > 0) add('agua', 3, 'Contaminated water in the network', `${c.infra.poluicaoAgua}% pollution in the distributed water. Common causes: a water intake downstream of a sewage outlet (check which way the river flows) or a water tower on ground polluted by industry. This causes waves of sickness and death.`, ondeProb('DirtyWater'));
  if (m) {
    const torres = onde((b, cl) => cl.s === 'Water' && b[F.poluicao] > 10 && /Torre|Tower/i.test(m.nomes[b[F.nome]] || ''));
    if (torres.length) add('agua', 3, `${torres.length} water tower(s) on polluted ground`, 'A water tower draws water from the ground: with pollution underneath, it contaminates the whole network. Move it to clean ground or move the industry away.', torres);
  }
  const semAgua = np('Water') + np('WaterNotConnected'), semEsg = np('Sewage');
  if (semAgua) add('agua', semAgua > 20 ? 3 : 2, `${fmt(semAgua)} buildings without water`, ap < 95 ? 'The supply is enough, so there is no pipe nearby: each pipe serves about 80 m to each side.' : 'Not enough water supply.', ondeProb('Water'));
  if (semEsg) add('agua', 2, `${fmt(semEsg)} buildings with sewage backing up`, 'Check that the pipes of those blocks reach a sewage outlet.', ondeProb('Sewage'));

  // ----- garbage
  const L = c.infra.lixo, cheio = pc(L.acumulado, L.capacidadeAterros), nLixo = np('Garbage');
  if (L.producaoSemanal > 0 && L.incineracaoSemanal === 0 && L.capacidadeAterros === 0) add('lixo', 3, 'There is no garbage collection', 'No landfill or incinerator. Piled-up garbage drags down health and happiness and leads to abandonment.');
  else if (L.producaoSemanal > L.incineracaoSemanal) {
    const falta = L.producaoSemanal - L.incineracaoSemanal, sobra = L.capacidadeAterros - L.acumulado;
    if (cheio >= 95 || sobra <= 0) add('lixo', 3, 'The garbage has nowhere to go', `The city produces ${fmt(L.producaoSemanal)} per week and burns ${fmt(L.incineracaoSemanal)}; the landfills are full. It is short ${fmt(falta)} per week of incineration.`);
    else add('lixo', sobra / falta < 30 ? 2 : 1, 'The landfills are filling up', `${fmt(falta)} of garbage per week is left over beyond what is burned; at this pace the landfills fill up in ${fmt(sobra / falta)} weeks. Add incineration or recycling.`);
  } else if (L.producaoSemanal > 0 && L.incineracaoSemanal < L.producaoSemanal * 1.15) add('lixo', 1, 'Incineration with almost no headroom', `It burns ${fmt(L.incineracaoSemanal)} for ${fmt(L.producaoSemanal)} produced per week. The next neighbourhood already goes over the limit.`);
  if (cheio >= 95 && L.capacidadeAterros > 0 && L.producaoSemanal <= L.incineracaoSemanal) add('lixo', nLixo ? 2 : 1, 'Landfills full', `The landfills hold ${curto(L.acumulado)} of ${curto(L.capacidadeAterros)}. A full landfill takes nothing more and its trucks stay parked, so the area around it goes uncollected even with spare incineration. Open each landfill and use "Empty": the contents go to the incinerators and the landfill collects again.`, onde((b, cl, p) => p.indexOf('LandfillFull') >= 0));
  if (nLixo) add('lixo', ng('Garbage') > 10 || nLixo > 80 ? 3 : nLixo > 15 ? 2 : 1, `${fmt(nLixo)} buildings with garbage piled up`, `${ng('Garbage')} in a major state. When the total capacity is enough, this is trucks not arriving: the facility is too far, traffic is jammed on the way or the budget was cut. Spread incinerators along the edges of each area (outside residential neighbourhoods, because of the pollution) instead of putting them all in one corner.`, ondeProb('Garbage'));
  if (orc('Garbage') < 100) add('lixo', nLixo || cheio >= 95 ? 2 : 1, `Garbage budget at ${orc('Garbage')}%`, 'Below 100% each facility processes less and sends out fewer trucks. With buildings piling up garbage, it is worth going back to 100% or more.');

  // ----- healthcare and deathcare
  const S = c.servicos.saude, Fu = c.servicos.funeraria, nMorte = np('Death');
  if (S.capacidadeTratamento === 0 && pop > 500) add('saude', 3, 'No medical care', 'There is no clinic or hospital. Sick people without treatment die early.');
  else if (S.doentes > S.capacidadeTratamento) add('saude', 3, 'More sick people than beds', `${fmt(S.doentes)} sick for ${fmt(S.capacidadeTratamento)} treatment places.`);
  else if (pc(S.doentes, S.capacidadeTratamento) >= 85) add('saude', 2, 'Almost every bed taken', `${fmt(S.doentes)} sick for ${fmt(S.capacidadeTratamento)} places.`);
  const pDoente = pc(S.doentes, pop);
  if (pDoente >= 1) add('saude', pDoente >= 4 ? 3 : pDoente >= 2 ? 2 : 1, `${fmt(S.doentes)} sick residents (${dec(pDoente)}% of the population)`, 'A bed treats, it does not prevent. What makes people sick: piled-up garbage, ground pollution, noise, contaminated water and bodies left uncollected. Fix the cause in its own view; parks and healthcare nearby speed up recovery.', null);
  if (S.saudeMedia > 0 && S.saudeMedia < 70) add('saude', S.saudeMedia < 55 ? 2 : 1, `Average health at ${S.saudeMedia}%`, 'Below 70% life expectancy drops and homes stop levelling up.');
  if (Fu.corposAguardando > 0 || nMorte) {
    const sobraCrem = Fu.cremacaoSemanal >= c.populacao.mortes * 1.2 || (Fu.capacidadeCemiterios - Fu.sepultados) > Fu.corposAguardando * 2;
    const sev = (pc(Fu.corposAguardando, pop) >= 1 || ng('Death') > 30) ? 3 : (nMorte >= 25 || pc(Fu.corposAguardando, pop) >= 0.3) ? 2 : 1;
    add('saude', sev, `${fmt(Fu.corposAguardando)} bodies waiting for pickup`, `${fmt(nMorte)} buildings with the warning (${ng('Death')} major). ` + (sobraCrem
      ? `The capacity exists (cremation of ${fmt(Fu.cremacaoSemanal)} per week for ${fmt(c.populacao.mortes)} deaths): what is missing is the hearse getting there. Switch to "Deathcare" on the map: buildings in orange are out of reach of any crematorium or cemetery. Put a crematorium inside those patches and check the traffic on the way.`
      : `The capacity is small: cremation of ${fmt(Fu.cremacaoSemanal)} per week for ${fmt(c.populacao.mortes)} deaths. Add crematoriums (they do not fill up, unlike cemeteries).`), ondeProb('Death'));
  }
  if (Fu.capacidadeCemiterios > 0 && pc(Fu.sepultados, Fu.capacidadeCemiterios) >= 90) add('saude', 1, 'Cemeteries almost full', `${fmt(Fu.sepultados)} of ${fmt(Fu.capacidadeCemiterios)} graves taken. A full cemetery stops collecting; use "Empty" to send the bodies to the crematoriums.`);
  if (cobre('saudeCob') != null && cobre('saudeCob') < 75) add('saude', cobre('saudeCob') < 50 ? 2 : 1, `Healthcare reaches ${fmt(cobre('saudeCob'))}% of the buildings`, 'The rest is too far from a clinic for the ambulance to arrive in time. Reach follows the roads: a small clinic in every neighbourhood covers more than one big hospital in a single spot.');
  if (cobre('funeraria') != null && cobre('funeraria') < 75) add('saude', cobre('funeraria') < 50 ? 2 : 1, `Deathcare reaches ${fmt(cobre('funeraria'))}% of the buildings`, 'It is in the buildings out of reach that the bodies pile up.');
  if (S.capacidadeTratamento > S.doentes * 4 && gasto('HealthCare') > D.despesa * 0.15 && sevMax(R, 'saude') < 2) add('saude', 0, 'Healthcare is oversized', `${fmt(S.capacidadeTratamento)} places for ${fmt(S.doentes)} sick people, costing ${din(gasto('HealthCare'))} per week (${pct(gasto('HealthCare'), D.despesa)} of the expenses). Redundant units can be turned off, as long as the coverage on the map holds.`);

  // ----- education
  const Ed = c.servicos.educacao;
  [['fundamental', 'Elementary school', 'elementary schools'], ['medio', 'High school', 'high schools'], ['superior', 'University', 'universities']].forEach(n => {
    const [prec, cap, taxa] = Ed[n[0]];
    if (prec > 0 && cap === 0) add('educacao', 2, `${n[1]}: no seats at all`, `${fmt(prec)} people of school age and no seats.`);
    else if (prec > cap) add('educacao', cap < prec * 0.7 ? 2 : 1, `${n[1]}: ${fmt(prec - cap)} seats short`, `${fmt(prec)} people of school age for ${fmt(cap)} seats.` + (n[0] === 'superior' ? ' Before expanding, check under Jobs whether there is work for the graduates.' : ''));
    else if (cap > prec * 3 && cap > 3000) add('educacao', 0, `${n[1]}: seats to spare`, `${fmt(cap)} seats for ${fmt(prec)} people of school age. Redundant ${n[2]} can be turned off to save upkeep.`);
  });
  if (cobreRes('fundamental') != null && cobreRes('fundamental') < 70 && Ed.fundamental[1] > 0) add('educacao', cobreRes('fundamental') < 45 ? 2 : 1, `Only ${fmt(cobreRes('fundamental'))}% of the homes have an elementary school within reach`, 'Children only attend a school close by: a spare seat on the other side of the city does not help. Spread small elementary schools inside each residential neighbourhood and group high schools and universities in a hub with transport.');
  if (orc('Education') < 100) add('educacao', 0, `Education budget at ${orc('Education')}%`, 'Below 100% each school takes fewer students.');
  if (gasto('Education') > D.despesa * 0.28) add('educacao', 0, 'Education is the biggest expense', `${din(gasto('Education'))} per week (${pct(gasto('Education'), D.despesa)} of the expenses).`);

  // ----- happiness
  const fel = c.populacao.felicidade, St = c.setores;
  const setFel = [['residencial', 'residents'], ['comercial', 'commerce'], ['industrial', 'industry'], ['escritorios', 'offices']].filter(s => St[s[0]].predios > 0).sort((a, b) => St[a[0]].felicidade - St[b[0]].felicidade);
  if (fel < 60) add('felicidade', 2, `Overall happiness at ${fel}%`, 'Below 60% buildings do not level up and tax income falls. See the most frequent warnings in the Advisor.');
  else if (fel < 75) add('felicidade', 1, `Overall happiness at ${fel}%`, setFel.length ? `The least satisfied sector is ${setFel[0][1]} (${St[setFel[0][0]].felicidade}%).` : '');
  if (setFel.length && St[setFel[0][0]].felicidade < 70 && fel >= 75) add('felicidade', 0, `The least happy sector is ${setFel[0][1]} (${St[setFel[0][0]].felicidade}%)`, setFel[0][0] === 'comercial' ? 'Commerce is unhappy without customers, without goods or with high crime.' : setFel[0][0] === 'industrial' ? 'Industry is unhappy without workers, without raw materials or when it cannot ship its production.' : 'See the warnings on that sector\'s buildings on the map.');

  // ----- levels
  const nv = (s, i) => St[s].niveis[i];
  if (St.industrial.predios > 20 && nv('industrial', 0) >= 80) add('niveis', 1, `${nv('industrial', 0)}% of the industry is at level 1`, 'Industry levels up with educated workers and with fire and police coverage nearby. At level 3 it pollutes less and pays more tax. If all the educated workforce goes to offices, industry is left behind.');
  if (St.comercial.predios > 20 && nv('comercial', 2) < 40) add('niveis', 0, `Only ${nv('comercial', 2)}% of the commerce reached level 3`, 'Commerce levels up with land value, wealthy customers (educated residents) and services nearby.');
  if (St.residencial.predios > 20 && nv('residencial', 3) + nv('residencial', 4) < 40) add('niveis', 1, `Only ${nv('residencial', 3) + nv('residencial', 4)}% of the homes are at levels 4 and 5`, 'Homes level up with the residents\' education and land value: a school within reach, parks, healthcare, fire, police and transport nearby; pollution, noise and crime hold them back.');
  if (St.escritorios.predios > 20 && nv('escritorios', 2) < 30) add('niveis', 0, `Only ${nv('escritorios', 2)}% of the offices are at level 3`, 'Offices level up with university-educated workers and services nearby.');

  // ----- traffic
  const T = c.transito;
  if (T.trechos > 0) {
    const nomes = [], vistos = {};
    for (const p of T.piores) { const n = p[2] || redePT(p[3]); if (!vistos[n]) { vistos[n] = 1; nomes.push(n); } if (nomes.length >= 6) break; }
    const focos = T.piores.filter(p => p[1] >= 90).map(p => [p[4], p[5]]);
    if (T.acima90 >= 5) add('trafego', T.acima90 > T.trechos * 0.04 ? 3 : T.acima90 > T.trechos * 0.015 ? 2 : 1, `${fmt(T.acima90)} road segments jammed`, `Out of ${fmt(T.trechos)} segments, ${fmt(T.acima90)} are at 90% occupancy or more and ${fmt(T.acima50)} above 50%. Worst: ${esc(nomes.join(', '))}. Quick wins: remove the traffic light at the end of highway ramps (the queue backs up onto the highway), give each neighbourhood more than one entrance and never connect an ordinary road straight onto the highway lanes.`, focos);
    const rod = T.piores.filter(p => /Highway/.test(p[3]) && p[1] >= 90).length;
    if (rod >= 4) add('trafego', 2, `${rod} highway segments jammed`, 'A stopped highway chokes imports, exports and the arrival of new residents. Look for the exit causing the queue: almost always a short ramp that ends at an intersection.', T.piores.filter(p => /Highway/.test(p[3]) && p[1] >= 90).map(p => [p[4], p[5]]));
  }

  // ----- pollution and noise
  if (x && x.resPoluidos) add('poluicao', x.resPoluidos > x.res * 0.05 ? 2 : 1, `${fmt(x.resPoluidos)} residential buildings on polluted ground`, 'Residents on polluted ground get sick and the building does not level up. Separate industry from housing with a strip of offices or commerce, and put incinerators and dirty power plants downwind, away from homes.', onde((b, cl) => cl.s === 'Residential' && b[F.poluicao] >= 40));
  if (np('Pollution') && !(x && x.resPoluidos)) add('poluicao', 1, `${fmt(np('Pollution'))} buildings complain about pollution`, '', ondeProb('Pollution'));
  if (np('Noise')) add('ruido', np('Noise') > 100 || ng('Noise') > 15 ? 2 : 1, `${fmt(np('Noise'))} buildings complain about noise`, `${ng('Noise')} in a major state. Noise comes from wide avenues, highways, commerce and industry. Trees along the road, sound barriers on the highway and offices as a buffer strip fix it; the heavy traffic ban policy in the district also helps.`, ondeProb('Noise'));

  // ----- fire department
  const cb = cobre('bombeiros');
  if (cb != null && pop > 500) {
    if (cb < 60) add('bombeiro', 2, `Fire stations reach only ${fmt(cb)}% of the buildings`, 'A building without coverage burns down before the truck arrives and does not level up. Reach follows the road network: a small fire house per neighbourhood responds faster than one big station in a corner.');
    else if (cb < 88) add('bombeiro', 1, `Fire stations reach ${fmt(cb)}% of the buildings`, 'The buildings in orange on the map are out of reach. A small fire house in each patch fixes it.');
  }
  if (np('Fire')) add('bombeiro', 2, `${fmt(np('Fire'))} buildings on fire right now`, '', ondeProb('Fire'));
  if (c.predios.queimados) add('bombeiro', 1, `${fmt(c.predios.queimados)} burned-down buildings`, 'Bulldoze the ruins so the lot can be used again.', onde((b, cl, p) => p.indexOf('BurnedDown') >= 0));

  // ----- crime
  const Po = c.servicos.policia;
  if (Po.taxaCrime >= 20) add('crime', 2, `Crime rate at ${Po.taxaCrime}%`, 'High crime drags down happiness and commerce. Unemployment and lack of education feed crime; a police station only contains it.');
  else if (Po.taxaCrime >= 10) add('crime', 1, `Crime rate at ${Po.taxaCrime}%`, '');
  if (Po.celas > 0 && pc(Po.presos, Po.celas) >= 90) add('crime', 1, 'Jail cells almost full', `${fmt(Po.presos)} prisoners for ${fmt(Po.celas)} cells. A prison frees up the police stations.`);
  if (np('Crime')) add('crime', ng('Crime') > 10 ? 2 : 1, `${fmt(np('Crime'))} buildings with high crime`, 'Check whether they are outside police coverage (orange on the map).', ondeProb('Crime'));
  const cp = cobre('policia');
  if (cp != null && cp < 70 && pop > 500) add('crime', cp < 45 ? 2 : 1, `Police reach ${fmt(cp)}% of the buildings`, 'The buildings in orange on the map are out of reach of any police station.');

  // ----- public transport
  const Tr = c.transporte, internas = Tr.linhas.filter(l => l[6]);
  if (pop > 4000 && internas.length === 0) add('transporte', pop > 30000 ? 3 : 2, 'No transport line inside the city', `With ${fmt(pop)} inhabitants, every trip is by car or on foot. Start with buses linking the densest residential neighbourhoods to the job hubs and the station; above some 50 thousand inhabitants, a metro between the centres takes thousands of cars off the avenues. Short, straight lines with stops every 300 to 400 m work better than one line that loops around the city.`);
  const incompletas = Tr.linhas.filter(l => !l[6]);
  if (incompletas.length) add('transporte', 1, `${incompletas.length} line(s) that do not close the loop`, `An incomplete line does not run: ${esc(incompletas.map(l => l[2]).slice(0, 5).join(', '))}.`);
  const vazias = internas.filter(l => l[4] + l[5] === 0);
  if (vazias.length) add('transporte', 0, `${vazias.length} line(s) with no passengers`, `${esc(vazias.map(l => l[2]).slice(0, 5).join(', '))}. Check that the stops are near homes at one end and jobs at the other.`);
  const ct = cobreRes('transporte');
  if (ct != null && internas.length > 0 && ct < 50) add('transporte', 1, `Only ${fmt(ct)}% of the homes have a stop nearby`, 'The buildings in orange on the map are too far from any stop.');

  // ----- population
  const id = c.populacao.idades, idosos = pc(id[4], pop);
  if (pop > 2000 && idosos >= 30) add('populacao', 1, `${fmt(idosos)}% of the population is elderly`, 'Neighbourhoods zoned all at once age together and die together (the "death wave"), overloading deathcare. Zone in smaller steps to mix the ages.');
  if (c.populacao.mortes > c.populacao.nascimentos * 1.5 && pop > 2000) add('populacao', 0, 'More deaths than births', `${fmt(c.populacao.mortes)} deaths and ${fmt(c.populacao.nascimentos)} births this week. The city only grows with people arriving from outside.`);
  if (St.residencial.total > 0 && pc(St.residencial.vazios, St.residencial.total) >= 8) add('populacao', 0, `${fmt(St.residencial.vazios)} empty homes`, 'There are homes to spare: zoning more residential now brings nobody. What does is open jobs and unobstructed outside connections.');

  // ----- outside connections
  const soltas = c.conexoes.filter(k => k[5] === 0);
  if (soltas.length) add('conexoes', 2, `${soltas.length} highway connection(s) not linked to the city`, 'These map entrances belong to a highway system that does not touch your road network. Import trucks that spawn there never arrive: commerce and industry run out of stock. A bridge or ramp joining the two systems fixes it.', soltas.map(k => [lim(k[1], -8640, 8640), lim(k[2], -8640, 8640)]));
  const tipos = {}; c.conexoes.forEach(k => tipos[k[0]] = 1);
  const semUso = ['Train', 'Ship', 'Plane'].filter(t => tipos[t] && !(c.predios.porServico.PublicTransport > 0 && Tr.passageiros[t === 'Plane' ? 'Airplane' : t]));
  if (semUso.length && pop > 8000) add('conexoes', 0, 'Unused outside connections', `The map offers ${esc(semUso.map(t => ({ Train: 'a railway', Ship: 'a ship route', Plane: 'an air route' }[t])).join(', '))} with no passenger traffic. The arrival of residents and tourists is limited by the connections: train station, harbor and airport add up.`);

  // ----- commerce and industry
  const Cx = c.comercioExterior;
  if (np('NoGoods')) add('industria', np('NoGoods') > 40 ? 3 : np('NoGoods') > 8 ? 2 : 1, `${fmt(np('NoGoods'))} shops with no goods`, `The city imports ${curto(Cx.importa.mercadorias)} of goods per week. A shop with no stock closes and takes the jobs with it. Either there is too much commerce for the local industry, or the cargo does not arrive: check the traffic at the highway entrances, unlinked connections and whether there is a cargo train terminal. Industry near the entrances supplies better.`, ondeProb('NoGoods'));
  if (np('NoResources') + np('NoInputProducts')) add('industria', np('NoResources') > 15 ? 2 : 1, `${fmt(np('NoResources') + np('NoInputProducts'))} factories with no raw materials`, 'Raw materials come from outside by truck, train or ship. Local specialized industry (forestry, farming, ore) reduces that dependency.', ondeProb('NoResources', 'NoInputProducts'));
  if (np('NoPlaceforGoods')) add('industria', 1, `${fmt(np('NoPlaceforGoods'))} factories with full storage`, 'They produce and cannot deliver: not enough commerce buying, or the truck cannot get out (traffic, no cargo terminal).', ondeProb('NoPlaceforGoods'));
  if (np('NoCustomers')) add('industria', np('NoCustomers') > 20 ? 2 : 1, `${fmt(np('NoCustomers'))} shops with no customers`, 'There is too much commerce for the population, or the shops are far from where people live and pass by.', ondeProb('NoCustomers'));
  if (np('NoWorkers') + np('NoEducatedWorkers')) add('emprego', np('NoWorkers') > 20 ? 2 : 1, `${fmt(np('NoWorkers') + np('NoEducatedWorkers'))} buildings with no workers`, np('NoEducatedWorkers') ? 'Some of them ask for more educated people: offices and high-level industry need high school and university graduates.' : 'There are not enough working-age residents, or they cannot get there (traffic, no transport).', ondeProb('NoWorkers', 'NoEducatedWorkers'));
  if (St.comercial.total > 0 && St.industrial.total > 0 && St.comercial.total > St.industrial.total * 2.5 && Cx.importa.mercadorias > 100000) add('industria', 1, 'A lot of commerce for little industry', `${fmt(St.comercial.total)} commercial jobs for ${fmt(St.industrial.total)} industrial ones: almost all goods are imported (${curto(Cx.importa.mercadorias)} per week) and depend on cargo traffic.`);

  // ----- jobs
  const des = c.populacao.desempregoPct, Dm = c.demanda, sup = c.populacao.superior.desempregados;
  if (des >= 20) add('emprego', 3, `Unemployment at ${des}%`, `${fmt(Dm.desempregados)} unemployed for ${fmt(Dm.vagasLivres)} open jobs. High unemployment zeroes residential demand and feeds crime.`);
  else if (des >= 10) add('emprego', 2, `Unemployment at ${des}%`, `${fmt(Dm.desempregados)} unemployed for ${fmt(Dm.vagasLivres)} open jobs.`);
  else if (des >= 6) add('emprego', 1, `Unemployment at ${des}%`, `${fmt(Dm.desempregados)} unemployed for ${fmt(Dm.vagasLivres)} open jobs.`);
  if (Dm.desempregados > 200 && sup > Dm.desempregados * 0.55) add('emprego', des >= 10 ? 2 : 1, 'Unemployment is concentrated among graduates', `${fmt(sup)} of the ${fmt(Dm.desempregados)} unemployed have a university degree. The city educates more people than it has qualified jobs for. Zone offices (they hire graduates and do not pollute), let industry level up and hold back new universities until jobs catch up.`);
  if (Dm.vagasLivres > Dm.desempregados * 2 && Dm.vagasLivres > 500) add('emprego', 1, `${fmt(Dm.vagasLivres)} jobs with nobody to fill them`, 'Workers are missing: zone residential (residential demand should be high) and check that residents can get to work.');

  // ----- money
  const saldo = D.receita - D.despesa;
  if (saldo < 0) { const sem = D.caixa / -saldo; add('dinheiro', sem < 25 ? 3 : 2, `The city loses ${din(-saldo)} per week`, `At this pace the cash of ${din(D.caixa)} runs out in ${fmt(sem)} weeks. See below which services weigh the most and which are oversized.`); }
  else if (D.receita > 0 && saldo < D.receita * 0.03) add('dinheiro', 1, 'Weekly balance close to zero', `${din(saldo)} is left from an income of ${din(D.receita)}. Any new service pushes it into the red.`);
  const imp = Object.entries(D.impostos), altos = imp.filter(i => i[1] > 12), baixos = imp.filter(i => i[1] < 9);
  if (altos.length) add('dinheiro', altos.some(i => i[1] > 14) ? 2 : 1, 'Tax above 12%', 'Above 12% the zone\'s happiness and demand start to fall; a very high tax leads to buildings being abandoned.');
  else if (baixos.length && saldo < D.receita * 0.1) add('dinheiro', 0, 'There is room to raise taxes', 'Up to 12% the tax barely affects happiness or demand.');
  const desp = Object.entries(D.porServico).filter(e => e[1][1] > 0).sort((a, b) => b[1][1] - a[1][1]);
  if (desp.length && desp[0][1][1] > D.despesa * 0.3) add('dinheiro', 0, `${SERVICO[desp[0][0]] || desp[0][0]} takes ${pct(desp[0][1][1], D.despesa)} of the expenses`, `${din(desp[0][1][1])} per week. Open that service's view to see whether there is spare capacity.`);

  // ----- demand
  const zv = k => c.zonas[k] ? c.zonas[k][1] : 0, vR = zv('ResidentialLow') + zv('ResidentialHigh'), vC = zv('CommercialLow') + zv('CommercialHigh'), vW = zv('Industrial') + zv('Office');
  const explica = (nome, val, vaz, zona) => {
    if (val >= 40 && vaz < 40) add('demanda', 1, `High ${nome} demand and no free lot`, `Demand at ${val}% and only ${fmt(vaz)} empty ${zona} zone cells. Zone more.`);
    else if (val >= 40 && vaz > 400) add('demanda', 0, `High ${nome} demand, but there are already ${fmt(vaz)} empty cells`, 'The game raises buildings at a fixed pace: each new building uses up a bit of demand, which rebuilds slowly. Zoning even more does not speed it up; high density yields more people per building.');
  };
  explica('residential', Dm.r, vR, 'residential'); explica('commercial', Dm.c, vC, 'commercial'); explica('industry and office', Dm.w, vW, 'industrial or office');
  if (Dm.r < 15 && pop > 1000) add('demanda', 0, 'Why nobody wants to move here', (Dm.desempregados > Dm.vagasLivres ? `There are ${fmt(Dm.desempregados)} unemployed for ${fmt(Dm.vagasLivres)} open jobs: without spare jobs residential demand does not rise. ` : '') + (St.residencial.vazios > 200 ? `There are already ${fmt(St.residencial.vazios)} empty homes. ` : '') + (Dm.ajusteImpostoR < 0 ? 'The residential tax is taking demand away. ' : '') + 'Create jobs (offices, industry, commerce with stock) and the green bar comes back.');
  if (Dm.ajusteImpostoC < 0 || Dm.ajusteImpostoW < 0 || Dm.ajusteImpostoR < 0) add('demanda', 0, 'Tax reducing demand', `Tax effect: residential ${Dm.ajusteImpostoR}, commercial ${Dm.ajusteImpostoC}, industry and offices ${Dm.ajusteImpostoW} points.`);

  // ----- land value, leisure, tourism
  const vt = c.ambiente.valorTerreno;
  if (pop > 2000 && vt < 25) add('terreno', 1, `Low average land value (₡${vt}/m²)`, 'Land value is what makes homes and commerce level up. It rises with parks, services and transport nearby; it falls with pollution, noise and crime.');
  const cl = cobreRes('lazer');
  if (cl != null && pop > 2000 && cl < 65) add('lazer', cl < 40 ? 2 : 1, `Only ${fmt(cl)}% of the homes have leisure nearby`, 'A small park on every block is worth more than one big park far away: the effect is local. The homes in orange on the map have none.');
  const tur = c.populacao.turistas.reduce((a, b) => a + b, 0), vis = c.populacao.visitasTuristas.reduce((a, b) => a + b, 0);
  if (pop > 10000 && tur < pop * 0.02) add('turismo', 1, 'Little tourism', `${fmt(tur)} tourists in the city. Tourists arrive by train, ship and plane and look for unique buildings, parks and leisure commerce.`);
  if (pop > 10000 && (c.predios.porServico.Monument || 0) > 0 && c.distritos.length === 0) add('turismo', 0, 'Give tourism an address', `${fmt(tur)} tourists and ${fmt(vis)} visits this week, but the attractions are scattered around the city. Group unique buildings and parks in a walkable area near the station or the harbor, create a district there with the tourism or leisure commercial specialization and link it by transport. It becomes a place, not a list of buildings.`);

  // ----- natural resources
  const Rn = c.ambiente.recursos, nomesR = { minerio: 'ore', petroleo: 'oil', floresta: 'forest', soloFertil: 'fertile land' };
  const disp = Object.keys(nomesR).filter(k => Rn[k][1] > 0), usados = disp.filter(k => Rn[k][0] > 0);
  if (disp.length && !usados.length && pop > 3000) add('recursos', 1, 'No natural resource in use', `The purchased tiles hold ${esc(disp.map(k => nomesR[k]).join(', '))}. Open the layers on the map to see where they are, paint a district over the patch, apply the matching industrial specialization and zone industry inside it. Forest and fertile land never run out and do not pollute the ground; ore and oil pay more, but they deplete.`);
  disp.forEach(k => { if ((k === 'minerio' || k === 'petroleo') && Rn[k][0] > Rn[k][1] * 0.8) add('recursos', 1, `${nomesR[k]} almost fully extracted`, 'When it runs out, that district\'s industry starts importing the raw material.'); });

  // ----- districts
  if (pop > 3000 && c.distritos.length === 0) add('distritos', 1, 'No district created', 'A district is the tool for treating each neighbourhood differently: taxes and policies per area (heavy traffic ban in residential areas, smoke detectors, recycling), industry and commerce specialization, and names on the map. Start by painting the residential neighbourhoods, the commercial centre and the industrial zone.');
  else if (c.distritos.length > 0 && c.distritos.every(d => !d[6] || d[6] === 'None')) add('distritos', 0, 'Districts without a specialization', 'No district uses an industrial or commercial specialization. That is how natural resources and tourism enter the economy.');
  if (pop > 10000 && D.politicas.length < 2) add('distritos', 0, 'Few active policies', 'City-wide or per-district policies tune consumption, traffic and services at a small cost.');

  // ----- city (general) and game engine
  if (c.predios.abandonados) add('cidade', c.predios.abandonados > 30 ? 2 : 1, `${fmt(c.predios.abandonados)} abandoned buildings`, 'Abandonment comes from a missing basic service, high taxes, or a lack of workers or customers. Bulldoze so the lot can be used again once the cause is fixed.', onde((b, cl, p) => p.indexOf('Abandoned') >= 0));
  if (c.geral.lotes < c.geral.lotesMax && D.caixa > 500000 && pop > 20000) add('cidade', 0, 'There is cash to buy tiles', `${din(D.caixa)} in cash and ${c.geral.lotes} tiles purchased.`);
  const nomesL = { predios: 'buildings', trechosDeRede: 'road, rail and pipe segments', nos: 'network nodes', blocosDeZona: 'zone blocks', veiculos: 'vehicles on the road', estacionados: 'parked cars', cidadaos: 'citizens', pedestresAtivos: 'people on the move', arvores: 'trees', linhas: 'transport lines', distritos: 'distritos' };
  Object.entries(c.limites).forEach(e => { const p = pc(e[1][0], e[1][1]); if (p >= 75) add('motor', p >= 92 ? 2 : 1, `${nomesL[e[0]] || e[0]} limit at ${fmt(p)}%`, `${fmt(e[1][0])} of ${fmt(e[1][1])}. On reaching the limit the game simply stops creating that kind of object` + (e[0] === 'veiculos' ? ': services stop dispatching trucks and ambulances. Public transport and less cargo traffic relieve it.' : '.')); });
  if (!c.geral.pausado && c.geral.diasPorSegundo > 0 && c.geral.velocidade === 3 && c.geral.diasPorSegundo < 0.35) add('motor', 0, 'Slow simulation', `At maximum speed the game advances ${dec(c.geral.diasPorSegundo, 2)} day per second. With a large city the limit is the processor, not the graphics card.`);
  regrasDN(add, c);   // day and night budgets (35-telas.js)
  return R;
}
function sevMax(lista, area) { return lista.filter(s => s.area === area).reduce((a, s) => Math.max(a, s.sev), 0); }
