/* Maqueta de la feature 017. Caso ficticio (P4). Las fotos que se suben quedan solo en este
   navegador (almacenamiento local); en 8000 se guardan en el equipo, por usuario, nunca en GitHub. */
(() => {
  'use strict';
  const root = document.documentElement;
  const Q = new URLSearchParams(location.search);
  const THUMB = Q.has('thumb');
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (THUMB) root.classList.add('thumb');
  let cur = -1, run = null;
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } } };

  // ---------- Datos del caso ----------
  const OF = [
    { n: 1, name: 'Nutrición Canina Austral S.A.', short: 'Austral', cuit: '30-00000001-0', total: 16054000, gar: 'Póliza', garM: 802700, docs: 9, falta: [] },
    { n: 2, name: 'Agroalimentos Río Seco S.R.L.', short: 'Río Seco', cuit: '30-00000002-0', total: 13952400, gar: 'Pagaré', garM: 697620, docs: 7, falta: ['Hoja de compliance', 'DJ de intereses'] },
    { n: 3, name: 'Mascotas del Litoral S.A.', short: 'Litoral', cuit: '30-00000003-0', total: 16485000, gar: 'Póliza', garM: 659400, docs: 7, falta: ['Hoja de compliance', 'Fichas técnicas R5 y R6'] },
  ];
  const EST = 15800000;
  const GROUPS = [['F', 'Formales'], ['C', 'Económicos'], ['T', 'Técnicos'], ['X', 'Con información externa']];
  const REQ = [
    ['F-01', 'Planilla de cotización firmada (Anexo II)', 'ok ok ok'], ['F-02', 'Inscripción vigente en el registro de proveedores', 'ok ok ok'], ['F-03', 'Declaración jurada de intereses', 'ok pe ok'],
    ['F-04', 'Mantenimiento de oferta por 60 días', 'ok ok ok'], ['F-05', 'Constancia de CUIT', 'ok ok ok'], ['F-06', 'Poder suficiente del firmante', 'ok nd ok'],
    ['C-01', 'Garantía de mantenimiento del 5 %', 'ok ok no'], ['C-02', 'Cotización completa por renglón', 'ok ok ok'], ['C-03', 'Precios en pesos con IVA incluido', 'ok ok ok'], ['C-04', 'Precio unitario y total coinciden', 'nd ok ok'],
    ['T-01', 'Proteína bruta mínima del 22 % (R1 y R2)', 'ok nd ok'], ['T-02', 'Registro del producto ante SENASA', 'ok no ok'], ['T-03', 'Vencimiento de 12 meses o más', 'nd ok nd'], ['T-04', 'Envases según renglón', 'ok ok ok'],
    ['T-05', 'Ficha técnica por renglón', 'ok no nd'], ['T-06', 'Dieta gastrointestinal veterinaria (R5)', 'ok ok pe'], ['T-07', 'Dieta renal veterinaria (R6)', 'ok no pe'], ['T-08', 'Entrega dentro de 10 días hábiles', 'no ok ok'],
    ['X-01', 'Habilidad para contratar', 'ok pe pe'], ['X-02', 'Sin deuda previsional', 'ok pe pe'], ['X-03', 'Sin sanciones como proveedor', 'ok pe pe'], ['X-04', 'Sin juicios con el organismo', 'ok pe pe'], ['X-05', 'Sin registro de empleadores sancionados', 'pe pe pe'],
  ].map(([id, txt, s]) => ({ id, txt, g: id[0], s: s.split(' ') }));
  const ORD = ['ok', 'no', 'nd', 'pe'];
  const STN = { ok: 'Cumple', no: 'No cumple', nd: 'No determinado', pe: 'Pendiente' };
  OF.forEach((o, k) => { o.cnt = { ok: 0, no: 0, nd: 0, pe: 0 }; REQ.forEach(r => o.cnt[r.s[k]]++); o.states = REQ.map(r => r.s[k]); });
  const ALLC = { ok: 0, no: 0, nd: 0, pe: 0 }; OF.forEach(o => ORD.forEach(s => ALLC[s] += o.cnt[s]));
  const low = [...OF].sort((a, b) => a.total - b.total)[0];
  const SECS = [['procedimiento', 'Procedimiento'], ['pliego', 'Pliego y matriz'], ['ofertas', 'Ofertas'], ['evaluacion', 'Evaluación y dictamen'], ['normativas', 'Normativas']];
  // Pendientes: [sección, texto, detalle, acción, abre]
  const TODO = [
    [0, 'Aprobar la respuesta a la consulta N.º 2', 'Novedad del Portal del 06/10. Queda en Ofertas.', 'ok', 'Aprobar la carga'],
    [1, 'Tomar el Anexo III del Portal', 'Modelo de DJ de intereses; el Portal lo lista y no se tomó.', 'btn', 'Tomar del Portal'],
    [1, 'Revisar los 3 cambios de la versión 3 de la matriz', 'Los trajo la Circular N.º 2 (muestras a pedido).', 'open:matriz', 'Revisar'],
    [2, 'Subir la hoja de compliance de las ofertas 2 y 3', 'Sin ella, 10 requisitos externos quedan pendientes.', 'btn', 'Subir'],
    [2, 'Subir las fichas técnicas R5 y R6 de la oferta 3', 'Sin ellas, T-06 y T-07 quedan pendientes.', 'btn', 'Subir'],
    [2, 'Subir la DJ de intereses de la oferta 2', 'Requisito F-03.', 'btn', 'Subir'],
    [3, 'Responder 2 preguntas de la evaluación', 'El poder de la oferta 2 y el vencimiento del R3 de la oferta 3.', 'open:preguntas', 'Responder'],
    [3, 'Decidir 2 descartes propuestos', 'Oferta 3 por la garantía; oferta 2 por el renglón 6.', 'open:descartes', 'Decidir'],
    [3, 'Aprobar el dictamen publicado en el Portal', 'Publicado el 06/10/2026.', 'ok', 'Aprobar la carga'],
    [4, 'Subir la norma de montos 2026', 'El pliego la cita y no está cargada (ficticia).', 'btn', 'Subir'],
  ].map(([s, t, d, a, l], i) => ({ i, s, t, d, a, l, done: false }));
  const STATE = [
    ['Datos, 6 renglones, cronograma y garantías', 'Aprobar 1 novedad del Portal'],
    ['Pliego, Anexos I y II, matriz de 23 requisitos (versión 3)', 'Anexo III y revisar 3 cambios'],
    ['3 ofertas, 23 documentos y 4 circulares', '2 hojas de compliance y 3 documentos'],
    ['Propuesta de 3 ofertas × 23 requisitos, orden económico, informe técnico (9 de 16 págs.)', '2 preguntas, 2 descartes y aprobar el dictamen'],
    ['4 normas validadas y la consulta', 'La norma de montos 2026'],
  ];

  // ---------- Utilidades ----------
  const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const money = n => '$ ' + n.toLocaleString('es-AR');
  const mill = n => '$ ' + (n / 1e6).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' M';
  const pc = (a, b) => (a / b * 100).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' %';
  const ic = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
  const I = { down: ic('M6 9l6 6 6-6'), up: ic('M12 16V4M7 9l5-5 5 5M5 20h14'), portal: ic('M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9z'), check: ic('M5 12.5l4.5 4.5L19 7.5'), sun: ic('M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z'), moon: ic('M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5z'), photo: ic('M4 7h3l2-2h6l2 2h3v12H4zM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z'), out: ic('M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10'), x: ic('M6 6l12 12M18 6L6 18'), plus: ic('M12 5v14M5 12h14'), arrow: ic('M5 12h14M13 6l6 6-6 6') };
  const SYM = { ok: 'M5 8.4l2.1 2.1L11.2 6', no: 'M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8', nd: 'M6.3 6.4a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.3M8 11.5v.1', pe: 'M8 4.8V8l2 1.3' };
  const ico = s => `<span class="st st-${s}" role="img" aria-label="${STN[s]}" data-n="${STN[s]}" tabindex="0"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="8"/><path d="${SYM[s]}"/></svg></span>`;
  const scol = s => `var(--${s})`;
  const leg = () => `<div class="leg">${ORD.map(s => `<span><i class="sw" style="--c:${scol(s)}"></i>${STN[s]}</span>`).join('')}</div>`;
  const tagS = (c, t) => `<span class="tag ${c}">${t}</span>`;

  // ---------- Mosaicos ----------
  const donut = o => { let acc = 0; const seg = ORD.map(s => { const v = o.cnt[s] / 23 * 100, off = 25 - acc; acc += v; return v ? `<circle cx="21" cy="21" r="15.9" fill="none" stroke="${scol(s)}" stroke-width="5" stroke-dasharray="${Math.max(v - 1.4, .1)} ${100 - Math.max(v - 1.4, .1)}" stroke-dashoffset="${off}"/>` : ''; }).join(''); return `<svg class="donut" viewBox="0 0 42 42">${seg}<text x="21" y="24.5" text-anchor="middle">${o.cnt.ok}/23</text></svg>`; };
  const lolli = () => { const s = [...OF].sort((a, b) => a.total - b.total), x0 = 13e6, x1 = 17e6, W = 520, L = 70, R = 92, X = v => L + (v - x0) / (x1 - x0) * (W - L - R); return `<svg class="lolli" viewBox="0 0 ${W} 132" width="100%" style="max-width:600px;display:block">${[13e6, 14e6, 15e6, 16e6, 17e6].map(v => `<line x1="${X(v)}" x2="${X(v)}" y1="14" y2="112" stroke="var(--line)" stroke-dasharray="2 4"/><text x="${X(v)}" y="128" text-anchor="middle">${v / 1e6} M</text>`).join('')}<line x1="${X(EST)}" x2="${X(EST)}" y1="8" y2="112" stroke="var(--ink-3)" stroke-width="1.5"/><text x="${X(EST) + 4}" y="12">estimado</text>${s.map((o, k) => { const y = 34 + k * 32; return `<text class="n" x="0" y="${y + 4}">${o.short}</text><line x1="${L}" x2="${X(o.total)}" y1="${y}" y2="${y}" stroke="${k ? 'var(--s2)' : 'var(--ink)'}" stroke-width="2"/><circle cx="${X(o.total)}" cy="${y}" r="6" fill="${k ? 'var(--bg)' : 'var(--lime)'}" stroke="${k ? 'var(--s2)' : 'var(--ink)'}" stroke-width="2"/><text x="${X(o.total) + 12}" y="${y + 4}" style="fill:var(--ink)">${mill(o.total)}</text>`; }).join('')}</svg>`; };
  const T = {
    orden: () => ({ h: 'Orden económico', ch: lolli(), sub: `La más baja, <b>${low.short}</b>, cotiza <span class="hl">${pc(EST - low.total, EST)} menos</span> que el estimado.`, d: 'economico' }),
    plazos: () => ({ h: 'Plazos importantes', ch: `<ul class="plazos"><li><b>22/09</b>Apertura</li><li class="now"><b>21/10</b>Hoy</li><li><b>21/11</b>Vence el mantenimiento de las ofertas</li><li class="fut"><b>—</b>Dictamen de la Comisión</li></ul>`, d: 'cronograma' }),
    masbaja: () => ({ h: 'La más baja', big: mill(low.total).replace(' M', '<small>M</small>'), sub: `<b>${low.short}</b> · ${pc(EST - low.total, EST)} por debajo del estimado`, d: 'economico' }),
    resultado: () => ({ h: 'Resultado por oferta', sub: 'Requisitos que cumple cada una, según la propuesta del sistema', ch: `<div class="donuts">${OF.map(o => `<figure>${donut(o)}Oferta ${o.n} · ${o.short}</figure>`).join('')}</div>${leg()}`, d: 'matriz' }),
    preguntas: () => ({ h: 'Preguntas a la Comisión', big: '2', sub: 'Sin responder · 1 respondida', d: 'preguntas' }),
    avance: () => ({ h: 'Avance por sección', ch: `<div class="bars">${[['Procedimiento', 100], ['Pliego y matriz', 75], ['Ofertas', 70], ['Evaluación', 55], ['Normativas', 80]].map(([n, p]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${p}%;--c:${p === 100 ? 'var(--lime)' : 'var(--ink)'}"></i></span><span>${p} %</span></div>`).join('')}</div>`, d: 'pendientes' }),
    requisitos: () => ({ h: 'Matriz de cumplimiento', big: '23<small>requisitos</small>', sub: 'Versión 3 · <b>3 cambios</b> por revisar', ch: `<div class="stk">${GROUPS.map(([g], k) => `<i style="flex:${REQ.filter(r => r.g === g).length};--c:${['var(--ink)', 'var(--s2)', 'var(--s3)', 'var(--ext)'][k]}"></i>`).join('')}</div><div class="leg">${GROUPS.map(([g, n], k) => `<span><i class="sw" style="--c:${['var(--ink)', 'var(--s2)', 'var(--s3)', 'var(--ext)'][k]}"></i>${n} ${REQ.filter(r => r.g === g).length}</span>`).join('')}</div>`, d: 'matriz' }),
    documentos: () => ({ h: 'Documentos del pliego', big: '3<small>de 4</small>', sub: 'Falta el <b>Anexo III</b>; el Portal lo publica', d: 'documentos' }),
    versiones: () => ({ h: 'Versiones de la matriz', big: 'v3', sub: 'La Circular N.º 2 agrega las muestras', d: 'versiones' }),
    heat: () => ({ h: 'Cumplimiento por tipo y oferta', ch: `<table class="tbl" style="font-size:.8125rem"><thead><tr><th></th>${OF.map(o => `<th class="r">${o.short}</th>`).join('')}</tr></thead><tbody>${GROUPS.map(([g, n]) => { const rs = REQ.filter(r => r.g === g); return `<tr><td>${n}</td>${OF.map((o, k) => { const ok = rs.filter(r => r.s[k] === 'ok').length; return `<td class="r"><span class="num" style="display:inline-block;min-width:3.25rem;padding:.25rem .5rem;border-radius:6px;background:color-mix(in srgb,var(--ok) ${Math.round(ok / rs.length * 55)}%,var(--bg))">${ok}/${rs.length}</span></td>`; }).join('')}</tr>`; }).join('')}</tbody></table>`, d: 'matriz' }),
    ofertas: () => ({ h: 'Ofertas del acta', big: '3', sub: 'Apertura del 22/09/2026', ch: `<div class="mini-cols">${OF.map(o => `<i class="${o === low ? 'hl' : ''}" style="--h:${o.total / 17e6 * 100}%" title="${o.short}: ${money(o.total)}"></i>`).join('')}</div><div class="leg">${OF.map(o => `<span>${o.short} ${mill(o.total)}</span>`).join('')}</div>`, d: 'ofertas' }),
    compliance: () => ({ h: 'Hojas de compliance', big: '1<small>de 3</small>', sub: '10 requisitos externos esperan la hoja de las ofertas 2 y 3', d: 'ofertas' }),
    docofertas: () => ({ h: 'Documentación de las ofertas', big: '23<small>de 27</small>', sub: 'Faltan 4 documentos en las ofertas 2 y 3', ch: `<div class="bars">${OF.map(o => `<div class="r"><span>Oferta ${o.n}</span><span class="trk"><i style="--p:${o.docs / 9 * 100}%;--c:${o.docs === 9 ? 'var(--lime)' : 'var(--ink)'}"></i></span><span>${o.docs}/9</span></div>`).join('')}</div>`, d: 'ofertas' }),
    informe: () => ({ h: 'Informe técnico IT-07/2026', big: '9<small>de 16 págs.</small>', sub: 'El sistema lo está leyendo', ch: `<span class="trk"><i style="--p:56%;--c:var(--lime)"></i></span>`, d: 'informe' }),
    dictamen: () => ({ h: 'Dictamen', big: '<span style="font-size:1.75rem">Pendiente</span>', sub: 'El Portal publicó uno el 06/10; falta aprobar la carga', d: 'dictamen' }),
    descartes: () => ({ h: 'Descartes propuestos', big: '2', sub: 'Oferta 3 por la garantía; oferta 2 por el renglón 6', d: 'descartes' }),
    nocumple: () => ({ h: 'No cumple', big: String(ALLC.no), sub: 'Celdas de la matriz en las tres ofertas', d: 'matriz:no' }),
    nodet: () => ({ h: 'No determinado', big: String(ALLC.nd), sub: 'Sin fundamento recuperable todavía', d: 'matriz:nd' }),
    normas: () => ({ h: 'Normas que lo rigen', big: '4<small>de 6</small>', sub: 'Validadas · falta la de montos 2026', d: 'normas' }),
    citas: () => ({ h: 'Citas del pliego', big: '14<small>de 15</small>', sub: 'Encontradas en la normativa cargada', ch: `<div class="bars">${[['Disp. 247/2022', 9], ['Dto. 1023/2001', 2], ['Dto. 202/2017', 2], ['Ejemplo N.º 1', 1], ['Montos 2026', 1]].map(([n, v]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${v / 9 * 100}%;--c:${n === 'Montos 2026' ? 'var(--nd)' : 'var(--ink)'}"></i></span><span>${v}</span></div>`).join('')}</div>`, d: 'citas' }),
    regimen: () => ({ h: 'Régimen que rige', big: '<span style="font-size:1.75rem">Disp. 247/2022</span>', sub: 'Por la autorización del 14/08/2026; la 297/03 no aplica', d: 'normas' }),
    consulta: () => ({ h: 'Consulta de normativa', sub: 'Cada respuesta cita norma, artículo y versión', ch: `<span style="margin-top:.5rem;padding:.875rem 1rem;border-radius:12px;background:var(--bg);color:var(--ink-3);display:flex;justify-content:space-between;align-items:center">¿Qué plazo de mantenimiento de oferta fija el régimen?${I.arrow}</span>`, d: 'consulta' }),
  };
  const tile = (k, c = '') => { const t = T[k](); return `<button class="tile ${c}" data-d="${t.d}" aria-expanded="false"><span class="th"><span>${t.h}</span><span class="go">${I.down}</span></span>${t.big ? `<span class="big">${t.big}</span>` : ''}${t.sub && t.big ? `<span class="sub">${t.sub}</span>` : ''}${t.ch ? `<span class="ch">${t.ch}</span>` : ''}${t.sub && !t.big ? `<span class="sub">${t.sub}</span>` : ''}</button>`; };
  const board = l => `<div class="board">${l.map(([k, c]) => tile(k, c)).join('')}</div>`;

  // ---------- Detalles ----------
  const D = {
    pendientes: () => ['Avance por sección', 'Qué hay y qué falta en cada una', `<table class="tbl"><thead><tr><th>Sección</th><th>Hay</th><th>Falta</th></tr></thead><tbody>${SECS.map(([, n], i) => `<tr><td><b style="font-weight:600">${n}</b></td><td style="color:var(--ink-2)">${STATE[i][0]}</td><td>${STATE[i][1]}</td></tr>`).join('')}</tbody></table>`],
    cronograma: () => ['Cronograma completo', 'Del Portal y del pliego', `<table class="tbl"><tbody>${[['20/08/2026', 'Publicación en el Portal'], ['10/09/2026', 'Circular N.º 1 (modificatoria)'], ['15/09/2026', 'Fin de consultas · Circular N.º 2'], ['22/09/2026 11:00', 'Apertura de ofertas'], ['06/10/2026', 'El Portal publica un dictamen'], ['21/10/2026', '<b>Hoy</b>: informe técnico en lectura'], ['21/11/2026', 'Vence el mantenimiento de las ofertas (60 días desde la apertura)'], ['—', 'Dictamen de la Comisión']].map(([d, t]) => `<tr><td class="num" style="width:10rem;color:var(--ink-2)">${d}</td><td>${t}</td></tr>`).join('')}</tbody></table>`],
    economico: () => { const s = [...OF].sort((a, b) => a.total - b.total); return ['Orden económico', `Monto estimado: ${money(EST)}`, `<table class="tbl"><thead><tr><th>Orden</th><th>Oferta</th><th class="r">Total</th><th class="r">Frente al estimado</th><th class="r">Sobre la más baja</th></tr></thead><tbody>${s.map((o, k) => `<tr><td>${k + 1}.º</td><td><b style="font-weight:600">${o.short}</b> · oferta ${o.n}</td><td class="r num">${money(o.total)}</td><td class="r num">${o.total < EST ? '−' : '+'} ${pc(Math.abs(o.total - EST), EST)}</td><td class="r num">${k ? '+ ' + pc(o.total - s[0].total, s[0].total) : tagS('lime', 'la más baja')}</td></tr>`).join('')}</tbody></table>`]; },
    matriz: f => ['Matriz de cumplimiento', 'Versión 3 · pase el mouse sobre un ícono para ver el estado', `<div class="filters" role="group" aria-label="Filtrar">${[['all', 'Todos'], ['no', 'No cumple'], ['nd', 'No determinado'], ['pe', 'Pendiente']].map(([k, n]) => `<button class="fb" data-f="${k}" aria-pressed="${(f || 'all') === k}">${n}</button>`).join('')}</div><table class="tbl"><thead><tr><th>Requisito</th>${OF.map(o => `<th class="r">Oferta ${o.n} · ${o.short}</th>`).join('')}</tr></thead><tbody>${GROUPS.map(([g, n]) => `<tr class="g" data-g="${g}"><td colspan="4">${n} · ${REQ.filter(r => r.g === g).length}</td></tr>` + REQ.filter(r => r.g === g).map(r => `<tr class="rq" data-g="${g}" data-s="${r.s.join(' ')}"><td><span style="color:var(--ink-3);font-size:.75rem;display:inline-block;width:2.75rem">${r.id}</span>${r.txt}</td>${r.s.map(s => `<td class="r">${ico(s)}</td>`).join('')}</tr>`).join('')).join('')}</tbody></table>${leg()}`],
    documentos: () => ['Documentos del pliego', '3 de 4 leídos', `<table class="tbl"><tbody>${[['Pliego de bases y condiciones particulares', '18 págs. · Portal, 20/08', 'ok', 'Leído'], ['Anexo I · Especificaciones técnicas', '6 págs. · Portal, 20/08', 'ok', 'Leído'], ['Anexo II · Planilla de cotización', '2 págs. · Portal, 20/08', 'ok', 'Leído']].map(([a, b, s, e]) => `<tr><td><b style="font-weight:600">${a}</b><div style="font-size:.8125rem;color:var(--ink-2)">${b}</div></td><td class="r">${tagS(s, e)}</td></tr>`).join('')}<tr><td><b style="font-weight:600">Anexo III · Modelo de DJ de intereses</b><div style="font-size:.8125rem;color:var(--ink-2)">El Portal lo lista y no se tomó</div></td><td class="r"><button class="btn sm">${I.portal}Tomar del Portal</button></td></tr></tbody></table>`],
    versiones: () => ['Versiones de la matriz', 'Cada circular modificatoria abre una versión', `<table class="tbl"><tbody><tr><td>v1 · 12/09/2026</td><td>Pliego original</td><td class="r">${tagS('ok', 'Validada')}</td></tr><tr><td>v2 · 16/09/2026</td><td>Circular N.º 1: cambia el plazo de entrega</td><td class="r">${tagS('ok', 'Validada')}</td></tr><tr><td>v3 · en revisión</td><td>Circular N.º 2: agrega muestras a pedido</td><td class="r">${tagS('nd', '3 cambios por revisar')}</td></tr></tbody></table>`],
    ofertas: () => ['Las tres ofertas del acta', 'Apertura del 22/09/2026 11:00', `<div style="overflow-x:auto"><table class="cmp"><thead><tr><th></th>${OF.map(o => `<th><small>Oferta ${o.n}</small><b>${o.name}</b><small>CUIT ${o.cuit}</small></th>`).join('')}</tr></thead><tbody>
      <tr><th>Total cotizado</th>${OF.map(o => `<td><span class="big">${money(o.total)}</span> ${o === low ? tagS('lime', 'la más baja') : ''}</td>`).join('')}</tr>
      <tr><th>Garantía</th>${OF.map(o => { const p = o.garM / o.total, bad = p < .0499; return `<td class="${bad ? 'bad' : ''}">${o.gar} · ${money(o.garM)}<div style="font-size:.8125rem">${(p * 100).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %${bad ? ' · el pliego exige 5 %' : ''}</div></td>`; }).join('')}</tr>
      <tr><th>Documentos</th>${OF.map(o => `<td>${o.docs} de 9</td>`).join('')}</tr>
      <tr><th>Compliance</th>${OF.map(o => `<td>${o.falta.length ? tagS('nd', 'Sin cargar') : tagS('ok', 'Cargada')}</td>`).join('')}</tr>
      <tr><th>23 requisitos</th>${OF.map(o => `<td><div class="strip">${o.states.map(s => `<i style="--c:${scol(s)}"></i>`).join('')}</div><div style="font-size:.75rem;color:var(--ink-2);margin-top:.375rem">${o.cnt.ok} cumplen · ${o.cnt.no} no · ${o.cnt.nd} sin determinar · ${o.cnt.pe} pend.</div></td>`).join('')}</tr>
      <tr><th>Falta</th>${OF.map(o => `<td>${o.falta.join('<br>') || '<span style="color:var(--ink-2)">Nada</span>'}</td>`).join('')}</tr></tbody></table></div>`],
    informe: () => ['Informe técnico IT-07/2026', 'Área requirente · el sistema lo está leyendo', `<div class="bars" style="max-width:30rem"><div class="r"><span>Páginas leídas</span><span class="trk"><i style="--p:56%;--c:var(--lime)"></i></span><span>9/16</span></div></div><p style="margin-top:1rem;color:var(--ink-2)">Renglones 1 a 4: el área considera técnicamente aceptables las tres ofertas. Renglones 5 y 6: en lectura.</p>`],
    dictamen: () => ['Dictamen', 'El Portal publicó uno el 06/10/2026', `<div class="acts"><button class="btn p js-ok" data-todo="8">${I.check}Aprobar la carga</button><button class="btn">Ver el documento</button></div>`],
    descartes: () => ['Descartes propuestos', 'El sistema propone con su fundamento; decide la Comisión', `<div class="item"><p><b>Oferta 3 · Mascotas del Litoral S.A.</b> ${ico('no')}<br>Garantía de mantenimiento menor al 5 % exigido.</p><p class="fund"><b>Pliego, art. 6.1:</b> «garantía de mantenimiento del 5 % del monto de la oferta». <b>Oferta:</b> póliza por ${money(659400)}, el 4,0 % de ${money(16485000)}.</p><div class="acts" style="margin-top:.75rem"><button class="btn sm p js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div><div class="item"><p><b>Oferta 2 · Agroalimentos Río Seco S.R.L.</b> ${ico('no')}<br>Renglón 6 sin registro del producto ante SENASA.</p><p class="fund"><b>Anexo I, ítem 6:</b> «producto con registro vigente». <b>Oferta:</b> la ficha del R6 no informa número de registro; se leyeron sus 7 documentos y ninguno lo informa.</p><div class="acts" style="margin-top:.75rem"><button class="btn sm p js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>`],
    preguntas: () => ['Preguntas a la Comisión', '2 sin responder', `<div class="item"><p>Oferta 2: el poder no menciona la facultad de cotizar. ¿Se pide subsanación?</p><div class="acts" style="margin-top:.5rem"><button class="btn sm p">Responder</button></div></div><div class="item"><p>Oferta 3: la ficha del R3 informa 10 meses de vencimiento. ¿Se acepta?</p><div class="acts" style="margin-top:.5rem"><button class="btn sm p">Responder</button></div></div><div class="item"><p>Oferta 1: ¿la póliza cubre los 60 días de mantenimiento? ${tagS('ok', 'Respondida')}</p><p class="fund"><b>evaluador de muestra, 14/10/2026:</b> «Sí, la vigencia es de 90 días».</p></div>`],
    normas: () => ['Normas que rigen este procedimiento', 'Por la fecha de autorización (14/08/2026)', `<table class="tbl"><tbody>${[['Disposición AFIP 247/2022', 'Régimen vigente', 'ok', 'Validada'], ['Disposición AFIP 297/03', 'Régimen anterior: no aplica', '', 'No aplica'], ['Decreto Delegado 1023/2001', 'Marco nacional', 'ok', 'Validada'], ['Decreto 202/2017', 'DJ de intereses', 'ok', 'Validada'], ['Norma complementaria de ejemplo N.º 1', 'Ficticia', 'nd', 'Sin validar']].map(([a, b, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td style="color:var(--ink-2)">${b}</td><td class="r">${tagS(s, e)}</td></tr>`).join('')}<tr><td><b style="font-weight:600">Norma de montos 2026</b></td><td style="color:var(--ink-2)">Ficticia; la cita el pliego</td><td class="r"><button class="btn sm">${I.up}Subir</button></td></tr></tbody></table>`],
    citas: () => ['Citas del pliego a normas', '15 citas · 14 encontradas', `<table class="tbl"><tbody>${[['Disp. AFIP 247/2022', 9, 'ok', 'Encontrada'], ['Decreto Delegado 1023/2001', 2, 'ok', 'Encontrada'], ['Decreto 202/2017', 2, 'ok', 'Encontrada'], ['Norma de ejemplo N.º 1', 1, 'ok', 'Encontrada'], ['Norma de montos 2026', 1, 'nd', 'No cargada']].map(([a, b, s, e]) => `<tr><td>${a}</td><td class="r num">${b}</td><td class="r">${tagS(s, e)}</td></tr>`).join('')}</tbody></table>`],
    consulta: () => ['Consulta de normativa', 'Cada respuesta cita norma, artículo y versión', `<form onsubmit="return false" style="display:flex;gap:.5rem"><input value="¿Qué plazo de mantenimiento de oferta fija el régimen?" aria-label="Pregunta" style="flex:1;padding:.75rem 1rem;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)"><button class="btn p">Consultar</button></form><p class="fund" style="margin-top:1rem"><b>Respuesta de muestra.</b> La real cita artículo y versión; sin fundamento recuperable, el resultado es «no determinado».</p>`],
  };
  const detailHTML = key => { const [k, f] = key.split(':'); const [h, s, b] = D[k](f); return `<div class="dt" data-f="${f || 'all'}"><h2>${h}</h2><p class="dsub">${s}</p>${b}</div>`; };

  // ---------- Pendientes ----------
  const todoRow = t => `<li data-i="${t.i}" class="${t.done ? 'done' : ''}">${ico(t.done ? 'ok' : (t.a === 'ok' ? 'nd' : 'pe'))}<div><div class="t">${t.t}</div><div class="d">${t.d}</div></div>${t.s === cur ? '<span></span>' : `<button class="sec" data-go="${t.s}">${SECS[t.s][1]}</button>`}${t.done ? `<span class="tag ok">Hecho</span>` : t.a === 'ok' ? `<button class="btn sm p js-ok" data-todo="${t.i}">${I.check}${t.l}</button>` : t.a.startsWith('open:') ? `<button class="btn sm" data-open="${t.a.slice(5)}">${t.l}</button>` : `<button class="btn sm">${t.l === 'Subir' ? I.up : I.portal}${t.l}</button>`}</li>`;
  const todoBlock = sec => { const list = TODO.filter(t => sec === undefined || t.s === sec); const left = list.filter(t => !t.done).length; return `<section class="todo" data-sec="${sec === undefined ? 'all' : sec}"><div class="todo-h"><h2>${sec === undefined ? 'Para hacer en el procedimiento' : 'Para hacer en esta sección'}</h2><span>${left ? `${left} pendiente${left > 1 ? 's' : ''}` : 'Nada pendiente'}</span></div><ul>${list.map(todoRow).join('') || '<li class="empty">Nada pendiente en esta sección.</li>'}</ul></section>`; };
  const refreshTodos = () => { $$('.todo').forEach(el => { const s = el.dataset.sec; el.outerHTML = todoBlock(s === 'all' ? undefined : +s); }); SECS.forEach((_, i) => { const c = $(`[data-count="${i}"]`), n = TODO.filter(t => t.s === i && !t.done).length; c.textContent = n; c.hidden = !n; }); const g = TODO.filter(t => !t.done).length; $$('[data-total]').forEach(e => { e.textContent = g; }); };

  // ---------- Fotos ----------
  const HOUSE = { bn: 'img/biblioratos-bn.jpg' };
  const tono = 'bn'; // decisión del 2026-10-21: todas las fotos en blanco y negro
  let fotos = store.get('evaluon-fotos', []);
  let lastPhoto = -1;
  const pool = () => fotos.length ? fotos.map(f => f[tono]) : [HOUSE[tono]];
  function pickPhoto() { const p = pool(); let k = Math.floor(Math.random() * p.length); if (p.length > 1 && k === lastPhoto) k = (k + 1) % p.length; lastPhoto = k; return { src: p[k], mine: fotos.length > 0 }; }
  function showPhoto() { const hero = $('.page.on .hero'); if (!hero) return; const box = $('.photo-bg', hero); const { src, mine } = pickPhoto(); const old = $('img', box); const img = new Image(); img.alt = ''; img.src = src; img.className = THUMB ? '' : 'enter'; img.onload = () => { if (old) old.remove(); box.prepend(img); }; $('.who-photo', hero).textContent = mine ? 'Foto de su perfil' : 'Foto de la casa'; }
  // Normalización: mismo brillo, contraste, saturación y tono para todas (en 8000 se hace al subir, en el servidor)
  function normalize(file) {
    return new Promise((ok, fail) => {
      const url = URL.createObjectURL(file); const im = new Image();
      im.onload = () => {
        const W = Math.min(1600, im.naturalWidth), H = Math.round(im.naturalHeight * W / im.naturalWidth);
        const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'); x.drawImage(im, 0, 0, W, H);
        const d = x.getImageData(0, 0, W, H), p = d.data, n = W * H, hist = new Uint32Array(256), Y = new Uint8ClampedArray(n);
        for (let i = 0; i < n; i++) { const y = .2126 * p[i * 4] + .7152 * p[i * 4 + 1] + .0722 * p[i * 4 + 2]; Y[i] = y; hist[Y[i]]++; }
        let lo = 0, hi = 255, acc = 0; for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc > n * .02) { lo = v; break; } } acc = 0; for (let v = 255; v >= 0; v--) { acc += hist[v]; if (acc > n * .02) { hi = v; break; } }
        const span = Math.max(1, hi - lo), out = {};
        const curve = v => { let t = Math.min(1, Math.max(0, (v - lo) / span)); t = t * t * (3 - 2 * t) * .35 + t * .65; return t; };
        for (const mode of ['bn']) {
          const o = x.createImageData(W, H), q = o.data;
          for (let i = 0; i < n; i++) {
            const t = curve(Y[i]); let r, g, b;
            if (mode === 'bn') { r = g = b = 12 + t * 236; }
            else { const s = t < .5 ? t * 2 : (t - .5) * 2, A = t < .5 ? [58, 50, 40] : [196, 184, 160], B = t < .5 ? [196, 184, 160] : [244, 236, 220]; r = A[0] + (B[0] - A[0]) * s; g = A[1] + (B[1] - A[1]) * s; b = A[2] + (B[2] - A[2]) * s; }
            q[i * 4] = r; q[i * 4 + 1] = g; q[i * 4 + 2] = b; q[i * 4 + 3] = 255;
          }
          x.putImageData(o, 0, 0); out[mode] = c.toDataURL('image/jpeg', .78);
        }
        x.drawImage(im, 0, 0, W, H); out.original = c.toDataURL('image/jpeg', .6);
        URL.revokeObjectURL(url); ok(out);
      };
      im.onerror = () => fail(new Error('No se pudo leer la imagen'));
      im.src = url;
    });
  }

  // ---------- Páginas ----------
  const ACT = [`<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`, `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`, `<button class="btn">${I.portal}Agregar desde el Portal</button><button class="btn p">${I.up}Subir archivos</button>`, `<button class="btn">Exportar</button><button class="btn p">${I.portal}Tomar el dictamen</button>`, `<button class="btn p">${I.up}Subir archivo</button>`];
  const stateLine = i => `<div class="state"><span><i class="dot"></i>Hay: <b>${STATE[i][0]}</b></span><span><i class="dot falta"></i>Falta: <b>${STATE[i][1]}</b></span></div>`;
  const BOARDS = [
    null,
    [['requisitos', 'w2'], ['documentos'], ['versiones'], ['heat', 'w4']],
    [['ofertas', 'w2'], ['masbaja', 'dark'], ['compliance'], ['docofertas', 'w2'], ['orden', 'w2']],
    [['resultado', 'w2'], ['informe'], ['dictamen'], ['descartes'], ['preguntas'], ['nocumple'], ['nodet']],
    [['normas'], ['citas', 'w2'], ['regimen'], ['consulta', 'w4']],
  ];
  const SUBS = ['', 'La matriz la propone el sistema desde el pliego y sus circulares; cada versión la valida la Comisión.', 'Del acta de apertura del Portal; los documentos los sube la Comisión.', 'El sistema propone con su fundamento; la Comisión decide.', 'Rige la Disposición 247/2022 por la fecha de autorización.'];
  function ingreso() {
    return `<section class="hero"><div class="photo-bg" aria-hidden="true"></div><span class="who-photo">Foto de la casa</span>
      <div class="hero-in"><h1>Alimento balanceado para perros</h1><p class="sub">Contratación Directa N.º 99/2026 · Expediente EX-2026-00000099-DEMO · autorizada el 14/08/2026</p>
      <div class="nums"><div><b>${mill(EST)}</b><span>monto estimado</span></div><div><b>3</b><span>ofertas</span></div><div><b>${mill(low.total)}</b><span>la más baja: ${low.short}</span></div><div><b>76 %</b><span>avance</span></div><div><b>31 días</b><span>vence el mantenimiento (21/11)</span></div><div><b><span class="hl" data-total>10</span></b><span>pendientes</span></div></div>
      <div class="acts">${ACT[0]}</div></div></section>
      ${stateLine(0)}<div style="height:1rem"></div>
      <section class="run" hidden aria-live="polite"><div class="t">Evaluando las ofertas<small class="where">oferta 2 de 3 · requisito 14 de 23</small></div><div class="pct num">0 %</div><div class="meter"><i style="--p:0%"></i></div><ol></ol></section>
      ${todoBlock()}
      ${board([['orden', 'w2'], ['plazos', 'w2'], ['resultado', 'w2'], ['descartes'], ['preguntas']])}`;
  }
  const page = i => i === 0 ? ingreso() : `<header class="ph"><div><h1>${SECS[i][1]}</h1><p style="color:var(--ink-2);margin-top:.5rem;max-width:62ch">${SUBS[i]}</p>${stateLine(i)}</div><div class="acts">${ACT[i]}</div></header>${todoBlock(i)}${board(BOARDS[i])}`;
  function fotosPage() {
    const slots = Array.from({ length: 10 }, (_, k) => fotos[k] ? `<div class="slot"><img src="${fotos[k][tono]}" alt="Foto ${k + 1} de su perfil"><button class="del" data-del="${k}" aria-label="Quitar la foto ${k + 1}">${I.x}</button></div>` : k === fotos.length ? `<button class="slot add" data-add>${I.plus}<br>Subir una foto<br><small>${10 - fotos.length} lugares libres</small></button>` : `<div class="slot empty" aria-hidden="true"></div>`).join('');
    const last = fotos[fotos.length - 1];
    return `<div class="fotos"><h1>Mis fotos</h1><p class="intro">Fotos que aparecen en el ingreso de cada procedimiento, una al azar cada vez que cambia la pantalla. Puede subir hasta 10. Todas se pasan a blanco y negro al subirlas, con el mismo brillo y contraste, para que combinen con la pantalla. Quedan en el equipo y solo las ve usted.</p>
      <div class="slots">${slots}</div>
      ${last ? `<div class="compare"><figure><img src="${last.original}" alt="">Como la subió</figure><figure><img src="${last[tono]}" alt="">Como se ve en EVALUON</figure></div>` : `<p style="margin-top:1.25rem;color:var(--ink-2);font-size:.875rem">Sin fotos propias se muestra la foto de la casa.</p>`}
      <input type="file" accept="image/jpeg,image/png,image/webp" hidden id="up"></div>`;
  }

  // ---------- Armado ----------
  const mark = `<a class="mark" href="#procedimiento" aria-label="EVALUON"><img class="m-claro" src="img/logotipo-claro.svg" alt="EVALUON" height="34"><img class="m-negro" src="img/logotipo-negro.svg" alt="EVALUON" height="34"></a>`;
  const nav = `<nav class="nav" role="tablist" aria-label="Secciones"><span class="ind" aria-hidden="true"></span>${SECS.map(([k, l], i) => `<button class="tab" role="tab" id="tab-${k}" aria-controls="pg-${k}" aria-selected="false" tabindex="-1" data-i="${i}">${l}<span class="c" data-count="${i}"></span></button>`).join('')}</nav>`;
  const right = `<div class="right"><button class="busy" title="Ver el avance"><span class="ring"></span><span>Evaluando · <b class="num">0 %</b></span></button><div class="theme" role="group" aria-label="Tema"><button data-theme="claro" aria-label="Gris y blanco">${I.sun}</button><button data-theme="negro" aria-label="Negro">${I.moon}</button></div><div class="me"><button class="av" aria-haspopup="menu" aria-expanded="false" aria-label="Su perfil">EM</button><div class="menu" role="menu"><div class="who"><b>evaluador de muestra</b>Comisión Evaluadora</div><button role="menuitem" data-fotos>${I.photo}Mis fotos</button><button role="menuitem">${I.out}Salir</button></div></div></div>`;
  document.body.className = 'noanim';
  document.body.innerHTML = `<header class="top"><div class="top-in">${mark}${nav}${right}</div></header><nav class="path" aria-label="Camino"></nav><main class="stage-wrap"><div class="stage">${SECS.map(([k], i) => `<section class="page" role="tabpanel" id="pg-${k}" aria-labelledby="tab-${k}">${page(i)}</section>`).join('')}<section class="page" id="pg-fotos" aria-label="Mis fotos"></section></div></main><div class="toast" role="status"></div>`;
  const pgs = SECS.map(([k]) => $('#pg-' + k)).concat($('#pg-fotos'));
  const tabs = $$('.tab'), ind = $('.ind'), stageEl = $('.stage');
  const toast = $('.toast'); let tt = 0; const say = m => { toast.textContent = m; toast.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => toast.classList.remove('on'), 1800); };
  refreshTodos();

  // Tema
  const setTheme = t => { root.dataset.theme = t === 'negro' ? 'negro' : ''; if (t !== 'negro') delete root.dataset.theme; $$('.theme button').forEach(b => b.setAttribute('aria-pressed', b.dataset.theme === t)); store.set('evaluon-tema', t); };
  setTheme(Q.get('tema') || store.get('evaluon-tema', 'claro'));

  // Camino
  function setPath(i) {
    const proc = `<a href="#procedimiento">CD 99/2026 · Alimento balanceado para perros</a>`;
    $('.path').innerHTML = i === 5 ? `<span>Mi perfil</span><span class="sep">›</span><b>Mis fotos</b>` : `<a href="#">Procedimientos</a><span class="sep">›</span>${i === 0 ? `<b>CD 99/2026 · Alimento balanceado para perros</b>` : `${proc}<span class="sep">›</span><b>${SECS[i][1]}</b>`}`;
  }

  // Pase de página entre secciones (en 8000: transiciones entre páginas en CSS)
  const E = { io: 'cubic-bezier(.65,0,.35,1)' };
  run = null;
  const settle = () => { if (!run) return; const r = run; run = null; r.a.forEach(a => { try { a.cancel(); } catch (e) { /* */ } }); r.done(); };
  function turn(out, inn, dir) {
    if (REDUCE) return [inn.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 140, fill: 'both' })];
    const d = 440, mk = (el, a, b) => { const s = document.createElement('div'); s.className = 'shade'; s.style.background = 'linear-gradient(90deg,rgba(0,0,0,.03),rgba(0,0,0,.28))'; el.appendChild(s); return s.animate([{ opacity: a }, { opacity: b }], { duration: d, easing: E.io, fill: 'both' }); };
    if (dir > 0) { out.style.zIndex = 3; out.style.transformOrigin = '0 50%'; return [out.animate([{ transform: 'rotateY(0)' }, { transform: 'rotateY(-90deg)' }], { duration: d, easing: E.io, fill: 'both' }), mk(out, 0, .6)]; }
    inn.style.zIndex = 3; inn.style.transformOrigin = '0 50%'; return [inn.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0)' }], { duration: d, easing: E.io, fill: 'both' }), mk(inn, .6, 0)];
  }
  function go(to, opt = {}) {
    if (to === cur) return; settle(); closeInline();
    const from = cur; cur = to;
    tabs.forEach((t, k) => { t.setAttribute('aria-selected', k === to); t.tabIndex = k === to ? 0 : -1; });
    if (to < 5) { ind.style.opacity = 1; ind.style.width = tabs[to].offsetWidth + 'px'; ind.style.transform = `translateX(${tabs[to].offsetLeft}px)`; } else ind.style.opacity = 0;
    if (to === 5) pgs[5].innerHTML = fotosPage(); else refreshTodos();
    setPath(to);
    if (!opt.hash) history.replaceState(null, '', '#' + (to === 5 ? 'fotos' : SECS[to][0]));
    if (from < 0 || THUMB) { pgs.forEach(p => p.classList.remove('on')); pgs[to].classList.add('on'); showPhoto(); return; }
    if (scrollY > 0) scrollTo({ top: 0, behavior: 'instant' });
    const out = pgs[from], inn = pgs[to]; out.classList.add('leaving'); inn.classList.add('on');
    const a = turn(out, inn, to > from ? 1 : -1);
    const me = run = { a, done() { out.classList.remove('on', 'leaving'); [out, inn].forEach(p => { p.style.zIndex = ''; p.style.transformOrigin = ''; $$(':scope > .shade', p).forEach(s => s.remove()); }); } };
    Promise.all(a.map(x => x.finished)).then(() => { if (run !== me) return; run = null; a.forEach(x => x.cancel()); me.done(); }).catch(() => {});
    showPhoto();
  }

  // Detalle que se despliega debajo del mosaico
  let openTile = null;
  function closeInline() { $$('.inline-detail').forEach(d => d.remove()); if (openTile) openTile.setAttribute('aria-expanded', 'false'); openTile = null; }
  function inline(t) {
    if (openTile === t) { const d = $('.inline-detail'); d.classList.remove('open'); t.setAttribute('aria-expanded', 'false'); openTile = null; setTimeout(() => d.remove(), REDUCE ? 0 : 340); return; }
    closeInline();
    const sib = $$('.tile', t.parentElement), top = t.offsetTop, row = sib.filter(x => x.offsetTop < top + t.offsetHeight && x.offsetTop + x.offsetHeight > top);
    const d = document.createElement('div'); d.className = 'inline-detail'; d.innerHTML = `<div>${detailHTML(t.dataset.d)}</div>`;
    (row[row.length - 1] || t).after(d); t.setAttribute('aria-expanded', 'true'); openTile = t;
    const f = $('.dt', d).dataset.f; if (f !== 'all') filterM($('.dt', d), f);
    requestAnimationFrame(() => requestAnimationFrame(() => d.classList.add('open')));
  }
  function filterM(w, f) { $$('.fb[data-f]', w).forEach(x => x.setAttribute('aria-pressed', x.dataset.f === f)); $$('tr.rq', w).forEach(tr => tr.classList.toggle('hide', !(f === 'all' || tr.dataset.s.split(' ').includes(f)))); $$('tr.g', w).forEach(g => g.classList.toggle('hide', !$$(`tr.rq[data-g="${g.dataset.g}"]:not(.hide)`, w).length)); }
  function openFrom(key) { const t = $(`.page.on .tile[data-d="${key}"]`); if (t) { inline(t); t.scrollIntoView({ block: 'center', behavior: REDUCE ? 'auto' : 'smooth' }); } }

  // ---------- Eventos ----------
  tabs.forEach((t, i) => t.addEventListener('click', () => go(i)));
  $('.nav').addEventListener('keydown', e => { const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!d) return; e.preventDefault(); const n = ((cur > 4 ? 0 : cur) + d + 5) % 5; go(n); tabs[n].focus(); });
  document.addEventListener('click', async e => {
    const el = e.target;
    const menuBtn = el.closest('.av'), menu = $('.menu');
    if (menuBtn) { const on = !menu.classList.contains('on'); menu.classList.toggle('on', on); menuBtn.setAttribute('aria-expanded', on); return; }
    if (!el.closest('.menu')) { menu.classList.remove('on'); $('.av').setAttribute('aria-expanded', 'false'); }
    if (el.closest('[data-fotos]')) { menu.classList.remove('on'); go(5); return; }
    const th = el.closest('.theme button'); if (th) { setTheme(th.dataset.theme); return; }
    if (el.closest('.busy')) { go(0); return; }
    const tl = el.closest('.tile'); if (tl && !el.closest('.dt')) { inline(tl); return; }
    const g = el.closest('[data-go]'); if (g) { go(+g.dataset.go); return; }
    const op = el.closest('[data-open]'); if (op) { const k = op.dataset.open, sec = { matriz: 1, preguntas: 3, descartes: 3 }[k]; if (cur !== sec) { go(sec); setTimeout(() => openFrom(k), REDUCE ? 0 : 480); } else openFrom(k); return; }
    const ok = el.closest('.js-ok');
    if (ok && !ok.dataset.done) { ok.dataset.done = '1'; if (ok.dataset.todo !== undefined) { TODO[+ok.dataset.todo].done = true; refreshTodos(); say('Listo: quedó registrado con su usuario y la fecha'); } else { ok.classList.remove('p'); ok.classList.add('done'); ok.innerHTML = I.check + 'Descarte aceptado'; } return; }
    const f = el.closest('.fb[data-f]'); if (f) { filterM(f.closest('.dt'), f.dataset.f); return; }
    if (el.closest('[data-add]')) { $('#up').click(); return; }
    const del = el.closest('[data-del]'); if (del) { fotos.splice(+del.dataset.del, 1); store.set('evaluon-fotos', fotos); pgs[5].innerHTML = fotosPage(); say('Foto quitada'); return; }
    const a = el.closest('a[href^="#"]'); if (a && a.getAttribute('href') !== '#') { e.preventDefault(); const k = a.getAttribute('href').slice(1); const i = SECS.findIndex(([s]) => s === k); if (i >= 0) go(i); }
  });
  document.addEventListener('change', async e => {
    if (e.target.id !== 'up' || !e.target.files[0]) return;
    if (fotos.length >= 10) { say('Ya tiene 10 fotos: quite una para subir otra'); return; }
    try { const n = await normalize(e.target.files[0]); fotos.push(n); if (!store.set('evaluon-fotos', fotos)) { fotos.pop(); say('No hay lugar en este navegador para otra foto'); } else say('Foto agregada y ajustada al tono de EVALUON'); } catch (err) { say(err.message); }
    pgs[5].innerHTML = fotosPage();
  });
  addEventListener('resize', () => { if (cur < 5) { ind.style.width = tabs[cur].offsetWidth + 'px'; ind.style.transform = `translateX(${tabs[cur].offsetLeft}px)`; } });
  addEventListener('hashchange', () => { const h = location.hash.slice(1); const i = h === 'fotos' ? 5 : SECS.findIndex(([s]) => s === h); if (i >= 0) go(i, { hash: true }); });

  // ---------- Proceso largo simulado (en 8000: el avance que ya calcula el sistema) ----------
  const runBox = $('.run'), busy = $('.busy');
  const steps = ['Leyó la oferta 2: 7 documentos', 'Requisito 12 de 23: «Registro ante SENASA» · no cumple', 'Requisito 13 de 23: «Vencimiento» · cumple', 'Requisito 14 de 23: «Envases» · en curso'];
  let p = THUMB ? 58 : 41, req = 14;
  function paint() { $('.pct', runBox).textContent = Math.round(p) + ' %'; $('.meter i', runBox).style.setProperty('--p', p + '%'); $('.where', runBox).textContent = `oferta 2 de 3 · requisito ${req} de 23`; $('ol', runBox).innerHTML = steps.slice(-3).map((s, k, a) => `<li><b>${['hace 1 min', 'hace 30 s', 'ahora'][k + 3 - a.length]}</b>${s}</li>`).join(''); busy.style.setProperty('--p', p + '%'); $('b', busy).textContent = Math.round(p) + ' %'; }
  runBox.hidden = false; busy.classList.add('on'); paint();
  if (!THUMB) setInterval(() => { if (p >= 100) { p = 38; req = 9; say('Terminó la evaluación de las ofertas (simulación: vuelve a empezar)'); } else { p = Math.min(100, p + 3.5); if (req < 23) { req++; steps.push(`Requisito ${req} de 23 · en curso`); } } paint(); }, 2200);

  // ---------- Inicio ----------
  const h = location.hash.slice(1); go(h === 'fotos' ? 5 : Math.max(0, SECS.findIndex(([s]) => s === h)), { hash: true });
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { if (cur < 5) { ind.style.width = tabs[cur].offsetWidth + 'px'; ind.style.transform = `translateX(${tabs[cur].offsetLeft}px)`; } requestAnimationFrame(() => document.body.classList.remove('noanim')); });
  if (Q.get('open')) setTimeout(() => openFrom(Q.get('open')), 50);
})();
