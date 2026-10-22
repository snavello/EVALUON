/* Motor de la ronda 3. Primer nivel de cada sección: un tablero con información agregada.
   Al hacer clic en un mosaico se abre su detalle según la versión: cajón lateral, ventana
   nueva, expandido en el lugar, ventana modal o panel dividido. Caso ficticio (P4). */
(() => {
  'use strict';
  const root = document.documentElement;
  const ALL = window.VERSIONES;
  const Q = new URLSearchParams(location.search);
  const N = +(root.dataset.v || Q.get('v') || 1);
  const V = ALL[N - 1];
  const THUMB = Q.has('thumb');
  const DETAIL_PAGE = root.dataset.page === 'detalle';
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (THUMB) root.classList.add('thumb');

  // ---------- Tema ----------
  if (V.fonts) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = 'https://fonts.googleapis.com/css2?' + V.fonts + '&display=swap'; document.head.appendChild(l); }
  const st = document.createElement('style');
  st.textContent = ':root{' + Object.entries(V.t).map(([k, v]) => `--${k}:${v}`).join(';') + '}' + (V.css || '');
  document.head.appendChild(st);
  if (V.dark) root.style.colorScheme = 'dark';

  // ---------- Datos ----------
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
  const TABS = [['procedimiento', 'Procedimiento', 2], ['pliego', 'Pliego y matriz', 1], ['ofertas', 'Ofertas', 4], ['evaluacion', 'Evaluación y dictamen', 2], ['normativas', 'Normativas', 1]];
  const REN = [['Adulto raza grande, bolsa de 20 kg', 120], ['Adulto raza mediana, bolsa de 15 kg', 80], ['Cachorro, bolsa de 15 kg', 40], ['Senior, bolsa de 15 kg', 30], ['Dieta gastrointestinal, 10 kg', 20], ['Dieta renal, 10 kg', 12]];

  // ---------- Utilidades ----------
  const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const money = n => '$ ' + n.toLocaleString('es-AR');
  const mill = n => '$ ' + (n / 1e6).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' M';
  const pc = (a, b, d = 1) => (a / b * 100).toLocaleString('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d }) + ' %';
  const ic = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
  const I = { right: ic('M5 12h14M13 6l6 6-6 6'), out: ic('M7 17L17 7M9 7h8v8'), down: ic('M6 9l6 6 6-6'), x: ic('M6 6l12 12M18 6L6 18'), up: ic('M12 16V4M7 9l5-5 5 5M5 20h14'), portal: ic('M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9z'), check: ic('M5 12.5l4.5 4.5L19 7.5'), back: ic('M19 12H5M11 18l-6-6 6-6') };
  const SYM = { ok: 'M5 8.4l2.1 2.1L11.2 6', no: 'M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8', nd: 'M6.3 6.4a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.3M8 11.5v.1', pe: 'M8 4.8V8l2 1.3' };
  const ico = s => `<span class="st st-${s}" role="img" aria-label="${STN[s]}" data-n="${STN[s]}" tabindex="0"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="8"/><path d="${SYM[s]}"/></svg></span>`;
  const scol = s => `var(--${s})`;
  const leg = () => `<div class="leg">${ORD.map(s => `<span><i class="sw" style="--c:${scol(s)}"></i>${STN[s]}</span>`).join('')}</div>`;
  const low = [...OF].sort((a, b) => a.total - b.total)[0];

  // ---------- Mosaicos del primer nivel ----------
  const donut = (o, size = 42) => { let acc = 0; const seg = ORD.map(s => { const v = o.cnt[s] / 23 * 100, off = 25 - acc; acc += v; return v ? `<circle cx="21" cy="21" r="15.9" fill="none" stroke="${scol(s)}" stroke-width="5" stroke-dasharray="${Math.max(v - 1.4, .1)} ${100 - Math.max(v - 1.4, .1)}" stroke-dashoffset="${off}"/>` : ''; }).join(''); return `<svg class="donut" viewBox="0 0 ${size} ${size}">${seg}<text x="21" y="24.5" text-anchor="middle">${o.cnt.ok}/23</text></svg>`; };
  const T = {
    avance: () => ({ h: 'Avance del procedimiento', big: '76 %', sub: 'Lo cargado y validado en las cinco secciones', ch: `<div class="bars">${[['Procedimiento', 100], ['Pliego y matriz', 75], ['Ofertas', 70], ['Evaluación', 55], ['Normativas', 80]].map(([n, p]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${p}%;--c:${p === 100 ? 'var(--lime)' : 'var(--ink)'}"></i></span><span>${p} %</span></div>`).join('')}</div>`, d: 'pendientes' }),
    pendientes: () => ({ h: 'Para hacer', big: '7', sub: '<span class="hl">2</span> novedades del Portal para aprobar · 5 documentos por cargar', ch: `<div class="bars">${[['Novedades', 2], ['Pliego', 1], ['Ofertas', 3], ['Normativas', 1]].map(([n, v]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${v / 3 * 100}%"></i></span><span>${v}</span></div>`).join('')}</div>`, d: 'pendientes' }),
    apertura: () => ({ h: 'Desde la apertura', big: '29<small>días</small>', sub: 'Apertura el 22/09/2026 11:00', ch: `<div class="sparkdots" title="Publicación, circulares, apertura, dictamen en el Portal, hoy, dictamen de la Comisión"><i></i><i></i><i></i><i></i><i></i><i class="now"></i><i class="f"></i></div>`, d: 'cronograma' }),
    estimado: () => ({ h: 'Monto estimado', big: mill(EST).replace(' M', '<small>M</small>'), sub: `La más baja cotiza <span class="hl">${pc(EST - low.total, EST)} menos</span>`, d: 'economico' }),
    renglones: () => ({ h: 'Renglones', big: '6', sub: '302 unidades en total', ch: `<div class="mini-cols">${REN.map(([, q]) => `<i style="--h:${q / 120 * 100}%"></i>`).join('')}</div>`, d: 'renglones' }),
    novedades: () => ({ h: 'Novedades del Portal', big: '2', sub: 'Respuesta a la consulta N.º 2 y un dictamen, del 06/10. Nada entra sin aprobación.', d: 'novedades' }),
    regimen: () => ({ h: 'Régimen que rige', big: '<span style="font-size:1.75rem">Disp. 247/2022</span>', sub: 'Por la autorización del 14/08/2026; la 297/03 no aplica', d: 'normas' }),
    requisitos: () => ({ h: 'Matriz de cumplimiento', big: '23<small>requisitos</small>', sub: 'Versión 3 · <b>3 cambios</b> por revisar', ch: `<div class="stk">${GROUPS.map(([g], k) => `<i style="flex:${REQ.filter(r => r.g === g).length};--c:${['var(--ink)', 'var(--s2)', 'var(--s3)', 'var(--ext)'][k]}"></i>`).join('')}</div><div class="leg">${GROUPS.map(([g, n], k) => `<span><i class="sw" style="--c:${['var(--ink)', 'var(--s2)', 'var(--s3)', 'var(--ext)'][k]}"></i>${n} ${REQ.filter(r => r.g === g).length}</span>`).join('')}</div>`, d: 'matriz' }),
    documentos: () => ({ h: 'Documentos del pliego', big: '3<small>de 4</small>', sub: 'Falta el <b>Anexo III</b>; el Portal lo publica', d: 'documentos' }),
    versiones: () => ({ h: 'Versiones de la matriz', big: 'v3', sub: 'La Circular N.º 2 agrega las muestras', ch: `<div class="sparkdots"><i></i><i></i><i class="now"></i></div>`, d: 'versiones' }),
    heat: () => ({ h: 'Cumplimiento por tipo y oferta', ch: `<table class="tbl" style="font-size:.8125rem"><thead><tr><th></th>${OF.map(o => `<th class="r">${o.short}</th>`).join('')}</tr></thead><tbody>${GROUPS.map(([g, n]) => { const rs = REQ.filter(r => r.g === g); return `<tr><td>${n}</td>${OF.map((o, k) => { const ok = rs.filter(r => r.s[k] === 'ok').length, p = ok / rs.length; return `<td class="r"><span style="display:inline-block;min-width:3.25rem;padding:.25rem .5rem;border-radius:6px;background:color-mix(in srgb,var(--ok) ${Math.round(p * 55)}%,var(--heat-0,#fff));font-variant-numeric:tabular-nums">${ok}/${rs.length}</span></td>`; }).join('')}</tr>`; }).join('')}</tbody></table>`, d: 'matriz' }),
    ofertas: () => ({ h: 'Ofertas del acta', big: '3', sub: 'Apertura del 22/09/2026', ch: `<div class="mini-cols">${OF.map(o => `<i class="${o === low ? 'hl' : ''}" style="--h:${o.total / 17e6 * 100}%" title="${o.short}: ${money(o.total)}"></i>`).join('')}</div><div class="leg">${OF.map(o => `<span>${o.short} ${mill(o.total)}</span>`).join('')}</div>`, d: 'ofertas' }),
    masbaja: () => ({ h: 'La más baja', big: mill(low.total).replace(' M', '<small>M</small>'), sub: `<b>${low.short}</b> · ${pc(EST - low.total, EST)} por debajo del estimado`, d: 'economico' }),
    docofertas: () => ({ h: 'Documentación de las ofertas', big: '23<small>de 27</small>', sub: 'Faltan 4: compliance de 2 y 3, DJ de la 2, fichas R5 y R6 de la 3', ch: `<div class="bars">${OF.map(o => `<div class="r"><span>Oferta ${o.n}</span><span class="trk"><i style="--p:${o.docs / 9 * 100}%;--c:${o.docs === 9 ? 'var(--lime)' : 'var(--ink)'}"></i></span><span>${o.docs}/9</span></div>`).join('')}</div>`, d: 'ofertas' }),
    compliance: () => ({ h: 'Hojas de compliance', big: '1<small>de 3</small>', sub: '10 requisitos externos esperan la hoja de las ofertas 2 y 3', d: 'ofertas' }),
    resultado: () => ({ h: 'Resultado por oferta', sub: 'Requisitos que cumple cada una', ch: `<div class="donuts">${OF.map(o => `<figure>${donut(o)}Oferta ${o.n} · ${o.short}</figure>`).join('')}</div>${leg()}`, d: 'matriz' }),
    nocumple: () => ({ h: 'No cumple', big: String(ALLC.no), sub: 'Celdas de la matriz en las tres ofertas', d: 'matriz:no' }),
    nodet: () => ({ h: 'No determinado', big: String(ALLC.nd), sub: 'Sin fundamento recuperable todavía', d: 'matriz:nd' }),
    descartes: () => ({ h: 'Descartes propuestos', big: '2', sub: 'Oferta 3 por garantía; oferta 2 por el renglón 6', d: 'descartes' }),
    preguntas: () => ({ h: 'Preguntas a la Comisión', big: '2', sub: 'Sin responder · 1 respondida', d: 'preguntas' }),
    informe: () => ({ h: 'Informe técnico IT-07/2026', big: '9<small>de 16 págs.</small>', sub: 'El sistema lo está leyendo', ch: `<span class="trk"><i style="--p:56%;--c:var(--lime)"></i></span>`, d: 'informe' }),
    orden: () => ({ h: 'Orden económico', ch: (() => { const s = [...OF].sort((a, b) => a.total - b.total), x0 = 13e6, x1 = 17e6, W = 520, L = 70, R = 92, X = v => L + (v - x0) / (x1 - x0) * (W - L - R); return `<svg class="lolli" viewBox="0 0 ${W} 132" width="100%" style="max-width:${W * 1.15}px;display:block">${[13e6, 14e6, 15e6, 16e6, 17e6].map(v => `<line x1="${X(v)}" x2="${X(v)}" y1="14" y2="112" stroke="var(--line)" stroke-dasharray="2 4"/><text x="${X(v)}" y="128" text-anchor="middle">${v / 1e6} M</text>`).join('')}<line x1="${X(EST)}" x2="${X(EST)}" y1="8" y2="112" stroke="var(--ink-3)" stroke-width="1.5"/><text x="${X(EST) + 4}" y="12">estimado</text>${s.map((o, k) => { const y = 34 + k * 32; return `<text class="n" x="0" y="${y + 4}">${o.short}</text><line x1="${L}" x2="${X(o.total)}" y1="${y}" y2="${y}" stroke="${k ? 'var(--s2)' : 'var(--ink)'}" stroke-width="2"/><circle cx="${X(o.total)}" cy="${y}" r="6" fill="${k ? 'var(--bg)' : 'var(--lime)'}" stroke="${k ? 'var(--s2)' : 'var(--ink)'}" stroke-width="2"/><text x="${X(o.total) + 12}" y="${y + 4}" style="fill:var(--ink)">${mill(o.total)}</text>`; }).join('')}</svg>`; })(), d: 'economico' }),
    dictamen: () => ({ h: 'Dictamen', big: '<span style="font-size:1.75rem">Pendiente</span>', sub: 'El Portal publicó uno el 06/10; no se aprobó todavía', d: 'novedades' }),
    normas: () => ({ h: 'Normas que lo rigen', big: '4<small>de 6</small>', sub: 'Validadas · falta cargar la de montos 2026', d: 'normas' }),
    citas: () => ({ h: 'Citas del pliego', big: '14<small>de 15</small>', sub: 'Encontradas en la normativa cargada', ch: `<div class="bars">${[['Disp. 247/2022', 9], ['Dto. 1023/2001', 2], ['Dto. 202/2017', 2], ['Ejemplo N.º 1', 1], ['Montos 2026', 1]].map(([n, v]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${v / 9 * 100}%;--c:${n === 'Montos 2026' ? 'var(--nd)' : 'var(--ink)'}"></i></span><span>${v}</span></div>`).join('')}</div>`, d: 'citas' }),
    consulta: () => ({ h: 'Consulta de normativa', sub: 'Cada respuesta cita norma, artículo y versión', ch: `<div style="margin-top:.5rem;padding:.875rem 1rem;border-radius:12px;background:var(--bg);color:var(--ink-3);display:flex;justify-content:space-between;align-items:center">¿Qué plazo de mantenimiento de oferta fija el régimen?${I.right}</div>`, d: 'consulta' }),
    lectura: () => ({ h: 'Lectura de documentos', big: '64<small>de 71 págs.</small>', sub: 'Pliego, ofertas e informe técnico', ch: `<div class="bars">${[['Pliego y anexos', 26, 26], ['Ofertas', 29, 29], ['Informe técnico', 9, 16]].map(([n, a, b]) => `<div class="r"><span>${n}</span><span class="trk"><i style="--p:${a / b * 100}%;--c:${a === b ? 'var(--ink)' : 'var(--lime)'}"></i></span><span>${a}/${b}</span></div>`).join('')}</div>`, d: 'documentos' }),
  };
  const goIcon = { drawer: I.right, modal: I.right, window: I.out, inline: I.down, split: I.right }[V.detail];
  const tile = (key, cls = '') => { const t = T[key](); return `<button class="tile ${cls}" data-d="${t.d}" aria-haspopup="${V.detail === 'drawer' || V.detail === 'modal' ? 'dialog' : 'false'}"${V.detail === 'inline' ? ' aria-expanded="false"' : ''}><span class="th"><span>${t.h}</span><span class="go">${goIcon}</span></span>${t.big ? `<span class="big">${t.big}</span>` : ''}${t.sub ? `<span class="sub">${t.sub}</span>` : ''}${t.ch ? `<span class="ch">${t.ch}</span>` : ''}</button>`; };
  const board = list => `<div class="board">${list.map(([k, c]) => tile(k, c)).join('')}</div>`;

  // ---------- Detalles ----------
  const tagS = (cls, t) => `<span class="tag ${cls}">${t}</span>`;
  const D = {
    pendientes: () => ['Para hacer', '7 pendientes en las cinco secciones', `<table class="tbl"><tbody>${[['nd', 'Respuesta a la consulta N.º 2', 'Novedad del Portal del 06/10 · queda en Ofertas', `<button class="btn sm js-ok">${I.check}Aprobar la carga</button>`], ['nd', 'Dictamen publicado en el Portal', 'Novedad del Portal del 06/10 · queda en Evaluación', `<button class="btn sm js-ok">${I.check}Aprobar la carga</button>`], ['pe', 'Anexo III · Modelo de DJ de intereses', 'Pliego y matriz · el Portal lo lista', `<button class="btn sm">${I.portal}Tomar del Portal</button>`], ['pe', 'Hoja de compliance de las ofertas 2 y 3', 'Ofertas · la carga una persona identificada', `<button class="btn sm">${I.up}Subir</button>`], ['pe', 'Fichas técnicas R5 y R6 de la oferta 3', 'Ofertas · sin ellas T-06 y T-07 quedan pendientes', `<button class="btn sm">${I.up}Subir</button>`], ['pe', 'DJ de intereses de la oferta 2', 'Ofertas · requisito F-03', `<button class="btn sm">${I.up}Subir</button>`], ['pe', 'Norma de montos 2026 (ficticia)', 'Normativas · el pliego la cita', `<button class="btn sm">${I.up}Subir</button>`]].map(([s, t, d, a]) => `<tr><td style="width:2rem">${ico(s)}</td><td><b style="font-weight:600">${t}</b><div style="font-size:.8125rem;color:var(--ink-2)">${d}</div></td><td class="r">${a}</td></tr>`).join('')}</tbody></table>`],
    cronograma: () => ['Cronograma', 'Fechas del Portal y del pliego', `<ul class="vt">${[['20/08/2026', 'Publicación en el Portal'], ['08/09/2026', 'Respuesta a la consulta N.º 1'], ['10/09/2026', 'Circular N.º 1 (modificatoria)'], ['15/09/2026', 'Fin de consultas · Circular N.º 2'], ['22/09/2026 11:00', 'Apertura de ofertas'], ['06/10/2026', 'El Portal publica un dictamen'], ['21/10/2026', 'Hoy: informe técnico en lectura', 'now'], ['Pendiente', 'Dictamen de la Comisión', 'fut']].map(([d, t, c]) => `<li class="${c || ''}"><b>${d}</b>${t}</li>`).join('')}</ul>`],
    economico: () => { const s = [...OF].sort((a, b) => a.total - b.total); return ['Orden económico', `Monto estimado: ${money(EST)}`, `<table class="tbl"><thead><tr><th>Orden</th><th>Oferta</th><th class="r">Total</th><th class="r">Frente al estimado</th><th class="r">Sobre la más baja</th></tr></thead><tbody>${s.map((o, k) => `<tr><td>${k + 1}.º</td><td><b style="font-weight:600">${o.short}</b> · oferta ${o.n}</td><td class="r num">${money(o.total)}</td><td class="r num">${o.total < EST ? '−' : '+'} ${pc(Math.abs(o.total - EST), EST)}</td><td class="r num">${k ? '+ ' + pc(o.total - s[0].total, s[0].total) : tagS('lime', 'la más baja')}</td></tr>`).join('')}</tbody></table>`]; },
    renglones: () => ['Renglones', '6 renglones · tomados del Portal el 07/10', `<table class="tbl"><thead><tr><th>Renglón</th><th>Descripción</th><th class="r">Cantidad</th></tr></thead><tbody>${REN.map(([d, q], k) => `<tr><td>${k + 1}</td><td>Alimento balanceado ${d.charAt(0).toLowerCase() + d.slice(1)}</td><td class="r num">${q} u.</td></tr>`).join('')}</tbody></table>`],
    novedades: () => ['Novedades del Portal', 'Última revisión: hoy 08:00. Nada entra sin su aprobación.', `<div>${[['Respuesta a la consulta N.º 2', 'Aclaratoria · publicada el 06/10/2026 · queda en Ofertas'], ['Dictamen de la Comisión Evaluadora', 'Publicado el 06/10/2026 · queda en Evaluación y dictamen']].map(([t, d]) => `<div class="item" style="display:flex;justify-content:space-between;gap:1rem;align-items:center"><div><b style="font-weight:600">${t}</b><div style="font-size:.8125rem;color:var(--ink-2)">${d}</div></div><button class="btn sm p js-ok">${I.check}Aprobar la carga</button></div>`).join('')}</div>`],
    normas: () => ['Normas que rigen este procedimiento', 'El régimen sale de la fecha de autorización (14/08/2026)', `<table class="tbl"><thead><tr><th>Norma</th><th>Qué regula</th><th>Versión</th><th class="r">Estado</th></tr></thead><tbody>${[['Disposición AFIP 247/2022', 'Régimen de contrataciones vigente', '2026-03', 'ok', 'Validada'], ['Disposición AFIP 297/03', 'Régimen anterior: no aplica', '2019-11', '', 'No aplica'], ['Decreto Delegado 1023/2001', 'Marco nacional de contrataciones', '2024-07', 'ok', 'Validada'], ['Decreto 202/2017', 'Declaración jurada de intereses', '2017-03', 'ok', 'Validada'], ['Norma complementaria de ejemplo N.º 1', 'Ficticia, para pruebas', '1', 'nd', 'Sin validar']].map(([a, b, c, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td style="color:var(--ink-2)">${b}</td><td class="num">${c}</td><td class="r">${tagS(s, e)}</td></tr>`).join('')}<tr><td><b style="font-weight:600">Norma de montos 2026</b></td><td style="color:var(--ink-2)">Ficticia; la cita el pliego</td><td>—</td><td class="r"><button class="btn sm">${I.up}Subir</button></td></tr></tbody></table>`],
    matriz: f => ['Matriz de cumplimiento', 'Versión 3 · 23 requisitos × 3 ofertas · pase el mouse sobre un ícono para ver el estado', `<div class="filters" role="group" aria-label="Filtrar">${[['all', 'Todos'], ['no', 'No cumple'], ['nd', 'No determinado'], ['pe', 'Pendiente']].map(([k, n]) => `<button class="fb" data-f="${k}" aria-pressed="${(f || 'all') === k}">${n}</button>`).join('')}</div><table class="tbl mtx"><thead><tr><th>Requisito</th>${OF.map(o => `<th class="r">Oferta ${o.n}<br><span style="color:var(--ink)">${o.short}</span></th>`).join('')}</tr></thead><tbody>${GROUPS.map(([g, n]) => `<tr class="g" data-g="${g}"><td colspan="4">${n} · ${REQ.filter(r => r.g === g).length}</td></tr>` + REQ.filter(r => r.g === g).map(r => `<tr class="rq" data-g="${g}" data-s="${r.s.join(' ')}"><td><span style="color:var(--ink-3);font-size:.75rem;display:inline-block;width:2.75rem">${r.id}</span>${r.txt}</td>${r.s.map(s => `<td class="r">${ico(s)}</td>`).join('')}</tr>`).join('')).join('')}</tbody></table>${leg()}`],
    documentos: () => ['Documentos', 'Pliego, ofertas e informe técnico', `<table class="tbl"><thead><tr><th>Documento</th><th>Origen</th><th class="r">Páginas</th><th class="r">Estado</th></tr></thead><tbody>${[['Pliego de bases y condiciones particulares', 'Portal, 20/08', '18', 'ok', 'Leído'], ['Anexo I · Especificaciones técnicas', 'Portal, 20/08', '6', 'ok', 'Leído'], ['Anexo II · Planilla de cotización', 'Portal, 20/08', '2', 'ok', 'Leído'], ['Anexo III · Modelo de DJ de intereses', 'Portal', '—', 'nd', 'Falta'], ['Ofertas (23 documentos)', 'Subidos por la Comisión', '29', 'ok', 'Leídos'], ['Informe técnico IT-07/2026', 'Subido por la Comisión', '16', 'nd', '9 de 16']].map(([a, b, c, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td style="color:var(--ink-2)">${b}</td><td class="r num">${c}</td><td class="r">${tagS(s, e)}</td></tr>`).join('')}</tbody></table>`],
    versiones: () => ['Versiones de la matriz', 'Cada circular modificatoria abre una versión', `<ul class="vt"><li><b>Versión 1 · 12/09/2026</b>Pliego original · ${tagS('ok', 'Validada')}</li><li><b>Versión 2 · 16/09/2026</b>Circular N.º 1: cambia el plazo de entrega · ${tagS('ok', 'Validada')}</li><li class="now"><b>Versión 3 · en revisión</b>Circular N.º 2: agrega muestras a pedido · ${tagS('nd', '3 cambios por revisar')}</li></ul>`],
    ofertas: () => ['Las tres ofertas del acta', 'Apertura del 22/09/2026 11:00', `<div style="overflow-x:auto"><table class="cmp"><thead><tr><th></th>${OF.map(o => `<th><small>Oferta ${o.n}</small><b>${o.name}</b><small>CUIT ${o.cuit}</small></th>`).join('')}</tr></thead><tbody>
      <tr><th>Total cotizado</th>${OF.map(o => `<td><span class="big">${money(o.total)}</span> ${o === low ? tagS('lime', 'la más baja') : ''}</td>`).join('')}</tr>
      <tr><th>Garantía</th>${OF.map(o => { const p = o.garM / o.total, bad = p < .0499; return `<td class="${bad ? 'bad' : ''}">${o.gar} · ${money(o.garM)}<div style="font-size:.8125rem">${(p * 100).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} % ${bad ? '· el pliego exige 5 %' : ''}</div></td>`; }).join('')}</tr>
      <tr><th>Documentos</th>${OF.map(o => `<td>${o.docs} de 9</td>`).join('')}</tr>
      <tr><th>Compliance</th>${OF.map(o => `<td>${o.falta.length ? tagS('nd', 'Sin cargar') : tagS('ok', 'Cargada')}</td>`).join('')}</tr>
      <tr><th>23 requisitos</th>${OF.map(o => `<td><div class="strip">${o.states.map(s => `<i style="--c:${scol(s)}"></i>`).join('')}</div><div style="font-size:.75rem;color:var(--ink-2);margin-top:.375rem">${o.cnt.ok} cumplen · ${o.cnt.no} no · ${o.cnt.nd} sin determinar · ${o.cnt.pe} pend.</div></td>`).join('')}</tr>
      <tr><th>Falta</th>${OF.map(o => `<td>${o.falta.join('<br>') || '<span style="color:var(--ink-2)">Nada</span>'}</td>`).join('')}</tr>
      <tr><th></th>${OF.map(o => `<td><button class="btn sm ${o.falta.length ? 'p' : ''}">${o.falta.length ? I.up + 'Subir lo que falta' : 'Ver ficha'}</button></td>`).join('')}</tr></tbody></table></div>`],
    descartes: () => ['Descartes propuestos', 'El sistema propone con su fundamento; decide la Comisión', `<div class="item"><div style="display:flex;justify-content:space-between;gap:1rem"><p><b>Oferta 3 · Mascotas del Litoral S.A.</b><br>Garantía de mantenimiento menor al 5 % exigido.</p>${ico('no')}</div><p class="fund"><b>Pliego, art. 6.1:</b> «garantía de mantenimiento del 5 % del monto de la oferta». <b>Oferta:</b> póliza por ${money(659400)}, el 4,0 % de ${money(16485000)}.</p><div class="acts" style="margin-top:.75rem"><button class="btn sm p js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div><div class="item"><div style="display:flex;justify-content:space-between;gap:1rem"><p><b>Oferta 2 · Agroalimentos Río Seco S.R.L.</b><br>Renglón 6 sin registro del producto ante SENASA.</p>${ico('no')}</div><p class="fund"><b>Anexo I, ítem 6:</b> «producto con registro vigente». <b>Oferta:</b> la ficha del R6 no informa número de registro; se leyeron sus 7 documentos y ninguno lo informa.</p><div class="acts" style="margin-top:.75rem"><button class="btn sm p js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>`],
    preguntas: () => ['Preguntas a la Comisión', '2 sin responder', `<div class="item"><p>Oferta 2: el poder no menciona la facultad de cotizar. ¿Se pide subsanación?</p><div class="acts" style="margin-top:.5rem"><button class="btn sm p">Responder</button>${tagS('nd', 'Sin responder')}</div></div><div class="item"><p>Oferta 3: la ficha del R3 informa 10 meses de vencimiento. ¿Se acepta?</p><div class="acts" style="margin-top:.5rem"><button class="btn sm p">Responder</button>${tagS('nd', 'Sin responder')}</div></div><div class="item"><p>Oferta 1: ¿la póliza cubre los 60 días de mantenimiento? ${tagS('ok', 'Respondida')}</p><p class="fund"><b>evaluador de muestra, 14/10/2026:</b> «Sí, la vigencia es de 90 días».</p></div>`],
    informe: () => ['Informe técnico IT-07/2026', 'Área requirente · el sistema lo está leyendo', `<div class="bars" style="max-width:30rem"><div class="r"><span>Páginas leídas</span><span class="trk"><i style="--p:56%;--c:var(--lime)"></i></span><span>9/16</span></div></div><div class="item" style="margin-top:1rem"><b>Lo leído hasta ahora</b><p style="color:var(--ink-2);font-size:.875rem;margin-top:.25rem">Renglones 1 a 4: el área considera técnicamente aceptables las tres ofertas. Renglones 5 y 6: en lectura.</p></div>`],
    citas: () => ['Citas del pliego a normas', '15 citas · 14 encontradas', `<table class="tbl"><thead><tr><th>Norma citada</th><th class="r">Citas</th><th class="r">Estado</th></tr></thead><tbody>${[['Disp. AFIP 247/2022', 9, 'ok', 'Encontrada'], ['Decreto Delegado 1023/2001', 2, 'ok', 'Encontrada'], ['Decreto 202/2017', 2, 'ok', 'Encontrada'], ['Norma complementaria de ejemplo N.º 1', 1, 'ok', 'Encontrada'], ['Norma de montos 2026', 1, 'nd', 'No cargada']].map(([a, b, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td class="r num">${b}</td><td class="r">${tagS(s, e)}</td></tr>`).join('')}</tbody></table>`],
    consulta: () => ['Consulta de normativa', 'Cada respuesta cita norma, artículo y versión', `<form onsubmit="return false" style="display:flex;gap:.5rem"><input value="¿Qué plazo de mantenimiento de oferta fija el régimen?" style="flex:1;font:inherit;padding:.75rem 1rem;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)"><button class="btn p">Consultar</button></form><div class="fund" style="margin-top:1rem"><b>Respuesta de muestra.</b> La respuesta real sale de la normativa cargada y cita artículo y versión. Sin fundamento recuperable, el resultado es «no determinado».</div>`],
  };
  const detailHTML = key => { const [k, f] = key.split(':'); const [h, s, body] = D[k](f); return `<div class="dt"><h2>${h}</h2><p class="dsub">${s}</p>${body}</div>`; };

  // ---------- Páginas de primer nivel ----------
  const PH = { procedimiento: ['Alimento balanceado para perros', 'Contratación Directa N.º 99/2026 · EX-2026-00000099-DEMO'], pliego: ['Pliego y matriz', 'La matriz la propone el sistema desde el pliego y sus circulares; cada versión la valida la Comisión.'], ofertas: ['Ofertas', 'Del acta de apertura del Portal; los documentos los sube la Comisión.'], evaluacion: ['Evaluación y dictamen', 'El sistema propone con su fundamento; la Comisión decide.'], normativas: ['Normativas', 'Rige la Disposición 247/2022 por la fecha de autorización.'] };
  const ACT = { procedimiento: `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`, pliego: `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`, ofertas: `<button class="btn">${I.portal}Agregar desde el Portal</button><button class="btn p">${I.up}Subir archivos</button>`, evaluacion: `<button class="btn">Exportar</button><button class="btn p">${I.portal}Tomar el dictamen</button>`, normativas: `<button class="btn p">${I.up}Subir archivo</button>` };
  function pageHTML(k) {
    const list = V.tabs[k];
    if (k === 'procedimiento' && V.hero === 'photo') return `<section class="hero" style="background-image:url('${V.photo}')"><div class="hin"><h1>${PH[k][0]}</h1><p>${PH[k][1]}</p><div class="nums"><div><b>${mill(EST)}</b><span>estimado</span></div><div><b>3</b><span>ofertas</span></div><div><b>29 días</b><span>desde la apertura</span></div></div><div class="acts">${ACT[k]}</div></div></section>${board(list)}`;
    if (k === 'procedimiento' && V.hero === 'split') return `<header class="ph"><div><h1>${PH[k][0]}</h1><p>${PH[k][1]}</p></div><div class="acts">${ACT[k]}</div></header><div class="splitphoto"><div class="ph-img" role="img" aria-label="Biblioratos apilados" style="background-image:url('${V.photo}')"></div>${board(V.splitTiles)}</div>${board(list)}`;
    return `<header class="ph"><div><h1>${PH[k][0]}</h1><p>${PH[k][1]}</p></div><div class="acts">${ACT[k]}</div></header>${board(list)}`;
  }

  // ---------- Armado ----------
  const mark = `<a class="mark" href="index.html" aria-label="EVALUON">EVALU<span class="on">ON</span></a>`;
  const right = `<div class="right"><button class="proc"><small>Procedimiento</small><b>CD 99/2026</b></button><span class="av" aria-hidden="true">EM</span></div>`;
  if (DETAIL_PAGE) {
    const key = Q.get('d') || 'matriz';
    document.title = 'EVALUON · detalle';
    document.body.innerHTML = `<header class="top"><div class="top-in" style="grid-template-columns:1fr auto">${mark}<div class="right"><span style="color:var(--ink-2)">CD 99/2026 · Alimento balanceado para perros</span><button class="btn sm" onclick="window.close()">${I.x}Cerrar esta ventana</button></div></div></header><main class="stage-wrap" style="max-width:68rem">${detailHTML(key)}</main>`;
    wireCommon();
    return;
  }
  document.title = `EVALUON · ${V.name}`;
  const nav = `<nav class="nav" role="tablist" aria-label="Secciones"><span class="ind" aria-hidden="true"></span>${TABS.map(([k, l, c], i) => `<button class="tab" role="tab" id="tab-${k}" aria-controls="pg-${k}" aria-selected="false" tabindex="-1" data-i="${i}">${l}<span class="c ${c ? '' : 'zero'}" data-count="${i}">${c}</span></button>`).join('')}</nav>`;
  const pages = TABS.map(([k]) => `<section class="page" role="tabpanel" id="pg-${k}" aria-labelledby="tab-${k}"><div class="lvl1">${pageHTML(k)}</div><div class="lvl2" hidden></div></section>`).join('');
  const side = V.detail === 'split' ? `<aside class="side"><h2>El procedimiento de un vistazo</h2>${[['7', 'Pendientes en las cinco secciones', 'pendientes', 1], ['29 días', 'Desde la apertura', 'cronograma'], [mill(low.total), 'La más baja: Río Seco', 'economico', 1], [String(ALLC.no), 'Celdas que no cumplen', 'matriz:no'], ['2', 'Preguntas sin responder', 'preguntas'], ['4 de 6', 'Normas validadas', 'normas']].map(([b, s, d, hl]) => `<button class="kv ${hl ? 'hl' : ''}" data-d="${d}"><b>${b}</b><span>${s}</span></button>`).join('')}</aside>` : '';
  document.body.className = `l-${V.detail} noanim`;
  document.body.innerHTML = `<header class="top"><div class="top-in">${mark}${nav}${right}</div></header><div class="frame">${side}<main class="stage-wrap"><div class="stage">${pages}</div></main></div>
    <dialog class="${V.detail === 'modal' ? 'modal' : 'drawer'}" aria-label="Detalle"><div class="dhead"><span>CD 99/2026 · detalle</span><button class="x" aria-label="Cerrar">${I.x}</button></div><div class="dbody"></div></dialog><div class="toast" role="status"></div>`;

  // ---------- Pestañas ----------
  const tabs = $$('.tab'), pgs = $$('.page'), ind = $('.ind'), stageEl = $('.stage');
  const placeInd = i => { const t = tabs[i]; ind.style.width = t.offsetWidth + 'px'; ind.style.transform = `translateX(${t.offsetLeft}px)`; };
  const E = { out: 'cubic-bezier(.16,1,.3,1)', io: 'cubic-bezier(.65,0,.35,1)', in: 'cubic-bezier(.5,0,.75,0)', drawer: 'cubic-bezier(.32,.72,0,1)' };
  const shade = (el, a, b, d, bg) => { const s = document.createElement('div'); s.className = 'shade'; s.style.background = bg; el.appendChild(s); return s.animate([{ opacity: a }, { opacity: b }], { duration: d, easing: E.io, fill: 'both' }); };
  const TR = {
    curl(out, inn, dir) { const d = 460, top = dir > 0 ? out : inn, un = dir > 0 ? inn : out; top.style.zIndex = 3; un.style.zIndex = 1; const fr = t => `polygon(0 0, ${t + 40}% 0, ${t}% 100%, 0 100%)`; const k = dir > 0 ? [100, 55, -42] : [-42, 55, 100]; return [top.animate(k.map(t => ({ clipPath: fr(t) })), { duration: d, easing: E.io, fill: 'both' }), shade(un, dir > 0 ? .25 : 0, dir > 0 ? 0 : .25, d, 'rgba(0,0,0,.4)')]; },
    fadescale(out, inn) { inn.style.zIndex = 2; return [out.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, easing: 'ease-in', fill: 'both' }), inn.animate([{ opacity: 0, transform: 'scale(1.015)' }, { opacity: 1, transform: 'none' }], { duration: 420, delay: 80, easing: E.out, fill: 'both' })]; },
    shift(out, inn, dir) { inn.style.zIndex = 2; return [out.animate([{ opacity: 1 }, { opacity: 0, transform: `translateX(${-dir * 12}px)` }], { duration: 140, easing: 'ease-in', fill: 'both' }), inn.animate([{ opacity: 0, transform: `translateX(${dir * 16}px)` }, { opacity: 1, transform: 'none' }], { duration: 260, delay: 60, easing: E.out, fill: 'both' })]; },
    turn(out, inn, dir) { const d = 440; if (dir > 0) { out.style.zIndex = 3; inn.style.zIndex = 1; out.style.transformOrigin = '0 50%'; return [out.animate([{ transform: 'rotateY(0)' }, { transform: 'rotateY(-90deg)' }], { duration: d, easing: E.io, fill: 'both' }), shade(out, 0, .55, d, 'linear-gradient(90deg,rgba(0,0,0,.04),rgba(0,0,0,.3))')]; } inn.style.zIndex = 3; out.style.zIndex = 1; inn.style.transformOrigin = '0 50%'; return [inn.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0)' }], { duration: d, easing: E.io, fill: 'both' }), shade(inn, .55, 0, d, 'linear-gradient(90deg,rgba(0,0,0,.04),rgba(0,0,0,.3))')]; },
    stack(out, inn, dir) { const d = 460; stageEl.classList.add('clip'); if (dir > 0) { inn.style.zIndex = 3; return [inn.animate([{ transform: 'translateX(100%)' }, { transform: 'none' }], { duration: d, easing: E.drawer, fill: 'both' }), out.animate([{ transform: 'none' }, { transform: 'translateX(-20%)', opacity: .4 }], { duration: d, easing: E.drawer, fill: 'both' })]; } out.style.zIndex = 3; return [out.animate([{ transform: 'none' }, { transform: 'translateX(100%)' }], { duration: d, easing: E.drawer, fill: 'both' }), inn.animate([{ transform: 'translateX(-20%)', opacity: .4 }, { transform: 'none', opacity: 1 }], { duration: d, easing: E.drawer, fill: 'both' })]; },
    fade(out, inn) { inn.style.zIndex = 2; return [inn.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 140, fill: 'both' })]; },
  };
  const TRN = { curl: 'Esquina que se despega', fadescale: 'Fundido con acercamiento', shift: 'Desplazamiento corto', turn: 'Hoja que gira', stack: 'Hoja que se desliza encima' };
  const TRO = Object.keys(TRN); let trn = V.transition;
  let cur = -1, run = null;
  const settle = () => { if (!run) return; const r = run; run = null; r.a.forEach(a => { try { a.cancel(); } catch (e) { /* */ } }); r.done(); };
  function animate(out, inn, dir) {
    settle();
    out.classList.add('leaving'); inn.classList.add('on');
    const a = (REDUCE ? TR.fade : TR[trn])(out, inn, dir);
    const me = run = { a, done() { out.classList.remove('on', 'leaving'); [out, inn].forEach(p => { p.style.zIndex = ''; p.style.transformOrigin = ''; p.style.opacity = ''; $$(':scope > .shade', p).forEach(s => s.remove()); }); stageEl.classList.remove('clip'); } };
    Promise.all(a.map(x => x.finished)).then(() => { if (run !== me) return; run = null; a.forEach(x => x.cancel()); me.done(); }).catch(() => {});
  }
  function go(to) {
    if (to === cur || to < 0 || to > 4) return;
    const from = cur; cur = to;
    tabs.forEach((t, k) => { t.setAttribute('aria-selected', k === to); t.tabIndex = k === to ? 0 : -1; }); placeInd(to);
    history.replaceState(null, '', '#' + TABS[to][0]);
    closeInline(); if (V.detail === 'split') backSplit(pgs[to], true);
    if (from < 0) { pgs.forEach(p => p.classList.remove('on')); pgs[to].classList.add('on'); return; }
    if (scrollY > 0) scrollTo({ top: 0, behavior: 'instant' });
    animate(pgs[from], pgs[to], to > from ? 1 : -1);
  }

  // ---------- Abrir el detalle ----------
  const dlg = $('dialog');
  function openDetail(key, tileEl) {
    if (V.detail === 'drawer' || V.detail === 'modal') { $('.dbody', dlg).innerHTML = detailHTML(key); dlg.showModal(); return; }
    if (V.detail === 'window') { window.open(`detalle.html?v=${N}&d=${encodeURIComponent(key)}`, '_blank', 'noopener'); return; }
    if (V.detail === 'inline') { inline(key, tileEl); return; }
    if (V.detail === 'split') { const pg = pgs[cur], l2 = $('.lvl2', pg); l2.innerHTML = `<button class="back">${I.back}Volver al resumen de ${TABS[cur][1]}</button>${detailHTML(key)}`; const l1 = $('.lvl1', pg); l1.hidden = true; l2.hidden = false; if (!REDUCE) l2.animate([{ opacity: 0, transform: 'translateX(24px)' }, { opacity: 1, transform: 'none' }], { duration: 320, easing: E.out }); scrollTo({ top: 0, behavior: 'instant' }); }
  }
  function backSplit(pg, instant) { const l1 = $('.lvl1', pg), l2 = $('.lvl2', pg); if (l2.hidden) return; l2.hidden = true; l1.hidden = false; if (!instant && !REDUCE) l1.animate([{ opacity: 0, transform: 'translateX(-24px)' }, { opacity: 1, transform: 'none' }], { duration: 280, easing: E.out }); }
  let openTile = null;
  function closeInline() { $$('.inline-detail').forEach(d => d.remove()); if (openTile) openTile.setAttribute('aria-expanded', 'false'); openTile = null; }
  function inline(key, t) {
    if (openTile === t) { const d = $('.inline-detail'); d.classList.remove('open'); t.setAttribute('aria-expanded', 'false'); openTile = null; setTimeout(() => d.remove(), REDUCE ? 0 : 340); return; }
    closeInline();
    const row = $$('.tile', t.parentElement).filter(x => Math.abs(x.offsetTop - t.offsetTop) < 4 || (x.offsetTop < t.offsetTop + t.offsetHeight && x.offsetTop + x.offsetHeight > t.offsetTop));
    const last = row[row.length - 1] || t;
    const d = document.createElement('div'); d.className = 'inline-detail'; d.innerHTML = `<div>${detailHTML(key)}</div>`;
    last.after(d); t.setAttribute('aria-expanded', 'true'); openTile = t;
    requestAnimationFrame(() => requestAnimationFrame(() => d.classList.add('open')));
  }

  // ---------- Eventos ----------
  tabs.forEach((t, i) => t.addEventListener('click', () => go(i)));
  $('.nav').addEventListener('keydown', e => { const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!d) return; e.preventDefault(); const n = (cur + d + 5) % 5; go(n); tabs[n].focus(); });
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-d]'); if (t && !e.target.closest('.dt')) { openDetail(t.dataset.d, t); return; }
    if (e.target.closest('.back')) { backSplit(pgs[cur]); return; }
    if (e.target.closest('.x')) { dlg.close(); return; }
    if (e.target === dlg) { dlg.close(); }
  });
  wireCommon();
  const toast = $('.toast'); let tt = 0;
  document.addEventListener('keydown', e => {
    const el = e.target instanceof Element ? e.target : null; if ((el && el.closest('input')) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === ']') location.href = `v${String(N % ALL.length + 1).padStart(2, '0')}.html${location.hash}`;
    else if (e.key === '[') location.href = `v${String((N + ALL.length - 2) % ALL.length + 1).padStart(2, '0')}.html${location.hash}`;
    else if (e.key === 'g' || e.key === 'G') location.href = 'index.html';
    else if (e.key === 't' || e.key === 'T') { trn = TRO[(TRO.indexOf(trn) + 1) % TRO.length]; toast.textContent = 'Transición: ' + TRN[trn]; toast.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => toast.classList.remove('on'), 1500); }
  });
  addEventListener('resize', () => placeInd(cur));
  go(Math.max(0, TABS.findIndex(([k]) => '#' + k === location.hash)));
  if (Q.get('open')) openDetail(Q.get('open'), $(`.page.on .tile[data-d="${Q.get('open')}"]`) || $('.page.on .tile'));
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { placeInd(cur); requestAnimationFrame(() => document.body.classList.remove('noanim')); });
  setTimeout(() => placeInd(cur), 400);

  function wireCommon() {
    document.addEventListener('click', e => {
      const ok = e.target.closest('.js-ok');
      if (ok && !ok.dataset.done) { ok.dataset.done = '1'; ok.classList.remove('p'); ok.classList.add('done'); ok.innerHTML = I.check + (ok.textContent.includes('descarte') ? 'Descarte aceptado' : 'Carga aprobada'); return; }
      const f = e.target.closest('.fb[data-f]');
      if (f) { const w = f.closest('.dt'); $$('.fb[data-f]', w).forEach(x => x.setAttribute('aria-pressed', x === f)); $$('tr.rq', w).forEach(tr => tr.classList.toggle('hide', !(f.dataset.f === 'all' || tr.dataset.s.split(' ').includes(f.dataset.f)))); $$('tr.g', w).forEach(g => g.classList.toggle('hide', !$$(`tr.rq[data-g="${g.dataset.g}"]:not(.hide)`, w).length)); }
    });
    // Abrir la matriz ya filtrada cuando el mosaico lo pide (matriz:no, matriz:nd)
    new MutationObserver(() => $$('.dt').forEach(w => { const p = $('.fb[aria-pressed="true"]', w); if (p && !w.dataset.f) { w.dataset.f = '1'; if (p.dataset.f !== 'all') p.click(); } })).observe(document.body, { childList: true, subtree: true });
  }
})();
