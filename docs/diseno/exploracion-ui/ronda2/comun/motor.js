/* Motor de la ronda 2 de la exploración visual de EVALUON.
   Misma aplicación y mismo caso ficticio en todas las versiones; cambia el mundo
   (letra, paleta, densidad y un gesto propio) y la transición entre pestañas. */
(() => {
  'use strict';
  const root = document.documentElement;
  const ALL = window.MUNDOS;
  const N = +root.dataset.v;
  const W = ALL[N - 1];
  const Q = new URLSearchParams(location.search);
  const THUMB = Q.has('thumb');
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (THUMB) root.classList.add('thumb');

  // ---------- Tema ----------
  if (W.fonts) {
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = 'https://fonts.googleapis.com/css2?' + W.fonts + '&display=swap';
    document.head.appendChild(l);
  }
  const style = document.createElement('style');
  style.textContent = ':root{' + Object.entries(W.t).map(([k, v]) => `--${k}:${v}`).join(';') + '}' + (W.css || '');
  document.head.appendChild(style);
  document.title = `EVALUON · ${W.name}`;

  // ---------- Datos del caso (ficticio, P4) ----------
  const OF = [
    { n: 1, name: 'Nutrición Canina Austral S.A.', short: 'Austral', cuit: '30-00000001-0', total: 16054000, gar: 'Póliza', garM: 802700, docs: 9, falta: [] },
    { n: 2, name: 'Agroalimentos Río Seco S.R.L.', short: 'Río Seco', cuit: '30-00000002-0', total: 13952400, gar: 'Pagaré', garM: 697620, docs: 7, falta: ['Hoja de compliance', 'DJ de intereses'] },
    { n: 3, name: 'Mascotas del Litoral S.A.', short: 'Litoral', cuit: '30-00000003-0', total: 16485000, gar: 'Póliza', garM: 659400, docs: 7, falta: ['Hoja de compliance', 'Fichas técnicas R5 y R6'] },
  ];
  const EST = 15800000;
  const REQ = [
    ['F-01', 'Planilla de cotización firmada (Anexo II)', 'F', 'ok ok ok'], ['F-02', 'Inscripción vigente en el registro de proveedores', 'F', 'ok ok ok'],
    ['F-03', 'Declaración jurada de intereses', 'F', 'ok pe ok'], ['F-04', 'Garantía de mantenimiento del 5 %', 'F', 'ok ok no'],
    ['F-05', 'Mantenimiento de oferta por 60 días', 'F', 'ok ok ok'], ['F-06', 'Constancia de CUIT', 'F', 'ok ok ok'],
    ['F-07', 'Poder suficiente del firmante', 'F', 'ok nd ok'], ['F-08', 'Domicilio especial constituido', 'F', 'ok ok ok'],
    ['T-01', 'Proteína bruta mínima del 22 % (R1 y R2)', 'T', 'ok nd ok'], ['T-02', 'Registro del producto ante SENASA', 'T', 'ok no ok'],
    ['T-03', 'Vencimiento de 12 meses o más desde la entrega', 'T', 'nd ok nd'], ['T-04', 'Envase de 20 kg (R1)', 'T', 'ok ok ok'],
    ['T-05', 'Envase de 15 kg (R2 a R4)', 'T', 'ok ok ok'], ['T-06', 'Ficha técnica por renglón', 'T', 'ok no nd'],
    ['T-07', 'Dieta gastrointestinal de uso veterinario (R5)', 'T', 'ok ok pe'], ['T-08', 'Dieta renal de uso veterinario (R6)', 'T', 'ok no pe'],
    ['T-09', 'Entrega dentro de los 10 días hábiles', 'T', 'no ok ok'], ['T-10', 'Muestras a pedido de la Comisión', 'T', 'nd ok ok'],
    ['E-01', 'Habilidad para contratar', 'E', 'ok pe pe'], ['E-02', 'Sin deuda previsional', 'E', 'ok pe pe'],
    ['E-03', 'Sin sanciones vigentes como proveedor', 'E', 'ok pe pe'], ['E-04', 'Sin juicios pendientes con el organismo', 'E', 'ok pe pe'],
    ['E-05', 'Sin registro de empleadores sancionados', 'E', 'pe pe pe'],
  ].map(([id, txt, g, s]) => ({ id, txt, g, s: s.split(' ') }));
  const ORD = ['ok', 'no', 'nd', 'pe'];
  const STN = { ok: 'Cumple', no: 'No cumple', nd: 'No determinado', pe: 'Pendiente' };
  OF.forEach((o, k) => { o.cnt = { ok: 0, no: 0, nd: 0, pe: 0 }; REQ.forEach(r => o.cnt[r.s[k]]++); o.states = REQ.map(r => r.s[k]); });
  const TABS = [
    { k: 'procedimiento', l: 'Procedimiento', count: 2, fol: '1–6' },
    { k: 'pliego', l: 'Pliego y matriz', count: 1, fol: '7–33' },
    { k: 'ofertas', l: 'Ofertas', count: 4, fol: '34–96' },
    { k: 'evaluacion', l: 'Evaluación y dictamen', count: 1, fol: '97–112' },
    { k: 'normativas', l: 'Normativas', count: 1, fol: '—' },
  ];
  const SIG = W.sig;

  // ---------- Utilidades ----------
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const money = n => '$ ' + n.toLocaleString('es-AR');
  const mill = n => '$ ' + (n / 1e6).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' M';
  const pc = (a, b) => (a / b * 100).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' %';
  const SYM = { ok: 'M5 8.4l2.1 2.1L11.2 6', no: 'M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8', nd: 'M6.3 6.4a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.3M8 11.5v.1', pe: 'M8 4.8V8l2 1.3' };
  const ico = s => `<span class="st st-${s}" role="img" aria-label="${STN[s]}" data-n="${STN[s]}" tabindex="0"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="8"/><path d="${SYM[s]}"/></svg></span>`;
  const svg = d => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
  const I = {
    portal: svg('M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9z'),
    up: svg('M12 16V4M7 9l5-5 5 5M5 20h14'), check: svg('M5 12.5l4.5 4.5L19 7.5'), down: svg('M12 4v12M7 11l5 5 5-5M5 20h14'),
    chev: svg('M6 9l6 6 6-6'), ext: svg('M4 7h16M4 12h10M4 17h7M17 14l3 3-3 3'), plus: svg('M12 5v14M5 12h14'),
  };
  const scol = s => `var(--${s})`;
  const legend = () => `<div class="legend">${ORD.map(s => `<span><i class="sw" style="--c:${scol(s)}"></i>${STN[s]}</span>`).join('')}</div>`;
  const tag = (cls, t) => SIG === 'stamp' && cls === 'ok' ? `<span class="stamp" style="--stamp:var(--ok)">${t}</span>` : `<span class="tag ${cls}">${t}</span>`;
  const folio = i => SIG === 'folio' && TABS[i].fol !== '—' ? `<span class="folio" aria-label="Folios ${TABS[i].fol}">fs. ${TABS[i].fol}</span>` : '';
  const fs = t => SIG === 'folio' ? ` · fs. ${t}` : '';
  const rider = (c, t) => SIG === 'riders' ? `<span class="rider" style="--c:${c}" title="${t}"></span>` : '';

  // ---------- Gráficos ----------
  const CH = {
    res: {
      stacked: () => OF.map(o => `<div class="crow"><span class="n">Oferta ${o.n} · ${o.short}</span><span class="v">${o.cnt.ok} de 23 cumplen</span><div class="stk">${ORD.filter(s => o.cnt[s]).map(s => `<i style="flex:${o.cnt[s]};--c:${scol(s)}" title="${STN[s]}: ${o.cnt[s]}"></i>`).join('')}</div></div>`).join('') + legend(),
      waffle: () => OF.map(o => `<div class="crow"><span class="n">Oferta ${o.n} · ${o.short}</span><span class="v">${o.cnt.ok} de 23</span><div class="waf">${o.states.map((s, j) => `<i style="--c:${scol(s)}" title="${REQ[j].id}: ${STN[s]}"></i>`).join('')}</div></div>`).join('') + `<p class="cap">Cada casilla es un requisito, en el orden de la matriz.</p>` + legend(),
      table: () => `<table class="tbl"><thead><tr><th>Oferta</th>${ORD.map(s => `<th class="r">${ico(s)}</th>`).join('')}</tr></thead><tbody>${OF.map(o => `<tr><td><b style="font-weight:600">${o.n} · ${o.short}</b></td>${ORD.map(s => `<td class="r data">${o.cnt[s]}</td>`).join('')}</tr>`).join('')}</tbody></table><div style="margin-top:.75rem">${legend()}</div>`,
    },
    eco: {
      hbar: () => { const s = [...OF].sort((a, b) => a.total - b.total), mx = 17.5e6; return s.map((o, k) => `<div class="hb"><span class="n">${k + 1}.º ${o.short}<small>Oferta ${o.n}</small></span><span class="trk"><i style="--p:${o.total / mx * 100}%;--c:${k ? 'color-mix(in srgb,var(--ink-2) 35%,var(--sunken))' : 'var(--brand)'}"></i><span class="mk" style="--m:${EST / mx * 100}%" title="Monto estimado"></span></span><span class="v">${money(o.total)}</span></div>`).join('') + `<p class="cap">La marca vertical es el monto estimado, ${money(EST)}. <b>Río Seco</b> cotiza ${pc(EST - s[0].total, EST)} por debajo.</p>`; },
      lollipop: () => {
        const s = [...OF].sort((a, b) => a.total - b.total), x0 = 13e6, x1 = 17e6, Wd = 560, L = 88, R = 100, X = v => L + (v - x0) / (x1 - x0) * (Wd - L - R);
        const ticks = [13e6, 14e6, 15e6, 16e6, 17e6].map(v => `<line x1="${X(v)}" x2="${X(v)}" y1="26" y2="146" stroke="var(--line)" stroke-dasharray="2 4"/><text x="${X(v)}" y="164" text-anchor="middle">${v / 1e6} M</text>`).join('');
        const rows = s.map((o, k) => { const y = 50 + k * 40; return `<text class="n" x="0" y="${y + 4}">${o.short}</text><line x1="${L}" x2="${X(o.total)}" y1="${y}" y2="${y}" stroke="${k ? 'var(--ink-2)' : 'var(--brand)'}" stroke-width="2"/><circle cx="${X(o.total)}" cy="${y}" r="6" fill="${k ? 'var(--surface)' : 'var(--brand)'}" stroke="${k ? 'var(--ink-2)' : 'var(--brand)'}" stroke-width="2"/><text class="m" x="${X(o.total) + 13}" y="${y + 4}">${mill(o.total)}</text>`; }).join('');
        return `<svg class="lolli" viewBox="0 0 ${Wd} 172" width="100%" style="max-width:${Wd}px" role="img" aria-label="Orden económico">${ticks}<line x1="${X(EST)}" x2="${X(EST)}" y1="20" y2="146" stroke="var(--accent)" stroke-width="1.5"/><text x="${X(EST)}" y="13" text-anchor="middle" style="fill:var(--ink)">estimado ${mill(EST)}</text>${rows}</svg><p class="cap">De menor a mayor; la línea vertical es el monto estimado.</p>`;
      },
      bullet: () => { const s = [...OF].sort((a, b) => a.total - b.total), mx = 18e6; return s.map((o, k) => `<div class="crow"><span class="n">${k + 1}.º ${o.name}</span><span class="v">${money(o.total)}</span><div class="hb" style="grid-column:1/-1;grid-template-columns:1fr;margin:0"><span class="trk" style="background:linear-gradient(90deg,var(--sunken) 0 ${EST / mx * 100}%,color-mix(in srgb,var(--sunken) 55%,var(--line)) ${EST / mx * 100}% 100%)"><i style="--p:${o.total / mx * 100}%;--c:${o.total > EST ? 'var(--ink-2)' : 'var(--brand)'};top:5px;bottom:5px"></i><span class="mk" style="--m:${EST / mx * 100}%"></span></span></div></div>`).join('') + `<p class="cap">Fondo claro: hasta el monto estimado (${mill(EST)}). Fondo más oscuro: por encima.</p>`; },
      delta: () => { const s = [...OF].sort((a, b) => a.total - b.total); return `<table class="tbl"><thead><tr><th>Orden</th><th>Oferta</th><th class="r">Total</th><th class="r">Sobre la más baja</th></tr></thead><tbody>${s.map((o, k) => `<tr><td class="data">${k + 1}.º</td><td><b style="font-weight:600">${o.short}</b> <span class="muted sm">· oferta ${o.n}</span></td><td class="r data">${money(o.total)}</td><td class="r data">${k ? '+ ' + money(o.total - s[0].total) + ' (' + pc(o.total - s[0].total, s[0].total) + ')' : '—'}</td></tr>`).join('')}</tbody></table><p class="cap">Monto estimado: <b class="data">${money(EST)}</b>. La más baja cotiza ${pc(EST - s[0].total, EST)} por debajo.</p>`; },
    },
    time: {
      line: () => {
        const ev = [['20/08', 'Publicación', 0], ['10/09', 'Circular N.º 1', 21], ['15/09', 'Fin de consultas', 26], ['22/09', 'Apertura', 33], ['06/10', 'Dictamen en el Portal', 47], ['21/10', 'Hoy', 62], ['', 'Dictamen de la Comisión', 72]];
        return `<div class="tl"><div class="ax"><i style="--p:${62 / 72 * 100}%"></i></div>${ev.map(([d, t, x], k) => `<span class="ev ${t === 'Hoy' ? 'now' : d ? '' : 'fut'}" style="left:${x / 72 * 100}%"></span><span class="lb ${k % 2 ? 'dn' : 'up'}" style="left:${x / 72 * 100}%"><b>${d || 'pendiente'}</b>${t}</span>`).join('')}</div>`;
      },
      stations: () => {
        const ev = [['20/08', 'Publicación'], ['10/09', 'Circular N.º 1'], ['15/09', 'Fin de consultas'], ['22/09', 'Apertura'], ['06/10', 'Dictamen en el Portal'], ['21/10', 'Usted está aquí'], ['', 'Dictamen de la Comisión']];
        return `<ol class="metro">${ev.map(([d, t], k) => `<li class="${k === 5 ? 'now' : k === 6 ? 'fut' : 'done'}"><span class="dot"></span><b class="data">${d || 'próxima'}</b><span>${t}</span></li>`).join('')}</ol>`;
      },
    },
  };
  const C = W.charts;

  // ---------- Páginas ----------
  const blk = (title, note, body, cls = '') => `<section class="blk ${cls}"><div class="blk-h"><h3>${title}</h3>${note ? `<span class="note">${note}</span>` : ''}</div>${body}</section>`;
  const ph = (i, title, sub, acts, facts = '') => `<header class="ph"><div><h1${i ? ' class="h2like"' : ''}>${title}</h1>${sub ? `<p class="sub">${sub}</p>` : ''}${facts}</div><div class="acts">${acts}</div>${folio(i)}</header>`;

  function pProc() {
    const todo = [
      [0, 'Respuesta a la consulta N.º 2', 'Novedad del Portal del 06/10. Queda en Ofertas.', `<button class="btn sm js-ok">${I.check}Aprobar la carga</button>`, 'nd'],
      [3, 'Dictamen publicado en el Portal', 'Novedad del Portal del 06/10. Queda en Evaluación y dictamen.', `<button class="btn sm js-ok">${I.check}Aprobar la carga</button>`, 'nd'],
      [1, 'Anexo III · Modelo de DJ de intereses', 'El Portal lo lista y no se tomó.', `<button class="btn sm">${I.portal}Tomar del Portal</button>`, 'pe'],
      [2, 'Hoja de compliance de las ofertas 2 y 3', 'La carga una persona identificada.', `<button class="btn sm">${I.up}Subir</button>`, 'pe'],
      [2, 'Fichas técnicas R5 y R6 de la oferta 3', 'Sin ellas, T-07 y T-08 quedan pendientes.', `<button class="btn sm">${I.up}Subir</button>`, 'pe'],
      [2, 'DJ de intereses de la oferta 2', 'Requisito F-03.', `<button class="btn sm">${I.up}Subir</button>`, 'pe'],
      [4, 'Norma de montos 2026 (ficticia)', 'El pliego la cita y no está cargada.', `<button class="btn sm">${I.up}Subir</button>`, 'pe'],
    ];
    const ren = [['Alimento balanceado adulto raza grande, bolsa de 20 kg', 120], ['Alimento balanceado adulto raza mediana, bolsa de 15 kg', 80], ['Alimento balanceado cachorro, bolsa de 15 kg', 40], ['Alimento balanceado senior, bolsa de 15 kg', 30], ['Dieta gastrointestinal, bolsa de 10 kg', 20], ['Dieta renal, bolsa de 10 kg', 12]];
    return `${ph(0, 'Alimento balanceado para perros', '', `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`,
      `<div class="facts"><span>Contratación Directa <b class="data">N.º 99/2026</b></span><span>Expediente <b class="data">EX-2026-00000099-DEMO</b></span><span>Autorización <b>14/08/2026</b></span><span>Rige la <b>Disp. AFIP 247/2022</b></span><span>Apertura <b>22/09/2026 11:00</b></span></div>`)}
    <div class="cols2">
      ${blk('Para hacer', '<span data-todo>7</span> pendientes en las cinco pestañas', `<table class="tbl todo"><tbody>${todo.map(([s, t, d, a, k]) => `<tr><td style="width:1.5rem">${rider(scol(k), STN[k]) || ico(k)}</td><td><div class="task">${t}</div><div class="muted sm">${d}</div></td><td class="sec"><button class="lnk" data-go="${s}">${TABS[s].l}</button></td><td class="r">${a}</td></tr>`).join('')}</tbody></table>`)}
      <div class="stack">
        ${blk('Datos', 'Del Portal, 07/10 08:00', `<dl class="fields">${[['Número', '<span class="data">CD 99/2026</span>'], ['Tipo', 'Contratación Directa'], ['Expediente', '<span class="data">EX-2026-00000099-DEMO</span>'], ['Organismo', 'Departamento de Compras (muestra)'], ['Autorización', '14/08/2026<small>Rige la Disp. 247/2022; la 297/03 no aplica</small>'], ['Objeto', 'Alimento balanceado para perros']].map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join('')}</dl>`)}
        ${blk('Garantías', 'Pliego y Portal', `<dl class="fields">${[['Mantenimiento de oferta', `5 % de la oferta<small>Pliego, art. 6.1${fs('7')}</small>`], ['Cumplimiento del contrato', `10 % del contrato<small>Pliego, art. 12${fs('11')}</small>`], ['Impugnación', '3 % del monto estimado<small>Portal; el pliego no la menciona</small>']].map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join('')}</dl>`)}
      </div>
    </div>
    ${blk('Cronograma', 'Hoy, 21/10/2026', CH.time[C.time]())}
    ${blk('Renglones', '6, tomados del Portal', `<table class="tbl"><thead><tr><th style="width:4rem">Renglón</th><th>Descripción</th><th class="r">Cantidad</th></tr></thead><tbody>${ren.map(([d, q], k) => `<tr><td class="data">${k + 1}</td><td>${d}</td><td class="r data">${q} u.</td></tr>`).join('')}</tbody></table>`)}`;
  }

  function matrix() {
    const head = `<thead><tr><th>Requisito</th>${OF.map(o => `<th>Oferta ${o.n}<span>${o.short}</span></th>`).join('')}</tr></thead>`;
    const groups = [['F', 'Formales', 8], ['T', 'Técnicos', 10], ['E', 'Con información externa: se cumplen con la hoja de compliance', 5]];
    let band = 0;
    const body = groups.map(([g, name, n]) => { band = 0; return `<tr class="g ${g === 'E' ? 'ext' : ''}" data-g="${g}"><td colspan="4">${g === 'E' ? I.ext : ''}${name} · ${n}</td></tr>` + REQ.filter(r => r.g === g).map(r => `<tr class="r ${Math.floor(band++ / 2) % 2 === 0 ? 'band' : ''}" data-g="${g}" data-s="${r.s.join(' ')}"><td><span class="rid">${r.id}</span>${r.txt}</td>${r.s.map(s => `<td>${ico(s)}</td>`).join('')}</tr>`).join(''); }).join('');
    const cnt = s => REQ.filter(r => r.s.includes(s)).length;
    return `<div class="filters" role="group" aria-label="Filtrar la matriz"><button class="fb" aria-pressed="true" data-f="all">Todos <span class="n">23</span></button>${['no', 'nd', 'pe'].map(s => `<button class="fb" aria-pressed="false" data-f="${s}"><i class="sw" style="--c:${scol(s)}"></i>${STN[s]} <span class="n">${cnt(s)}</span></button>`).join('')}</div><table class="mtx">${head}<tbody>${body}</tbody></table>`;
  }

  function pPliego() {
    const docs = [['Pliego de bases y condiciones particulares', '18 págs. · Portal, 20/08/2026', 'ok', '7–24'], ['Anexo I · Especificaciones técnicas', '6 págs. · Portal, 20/08/2026', 'ok', '25–30'], ['Anexo II · Planilla de cotización', '2 págs. · Portal, 20/08/2026', 'ok', '31–32'], ['Anexo III · Modelo de DJ de intereses', 'El Portal lo lista y no se tomó', 'pe', '']];
    return `${ph(1, 'Pliego y matriz', 'La matriz la propone el sistema a partir del pliego y sus circulares; cada versión la valida la Comisión.', `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn p">${I.up}Subir archivo</button>`)}
    <div class="cols2">
      ${blk('Documentos', '3 de 4 leídos', `<table class="tbl"><tbody>${docs.map(([t, d, s, f]) => `<tr><td><div class="task">${rider(s === 'ok' ? 'var(--ok)' : 'var(--nd)', '')}${t}</div><div class="muted sm">${d}${f ? fs(f) : ''}</div></td><td class="r">${s === 'ok' ? tag('ok', 'Leído') : `<button class="btn sm">${I.portal}Tomar del Portal</button>`}</td></tr>`).join('')}</tbody></table>`)}
      ${blk('Versiones de la matriz', 'Cada circular modificatoria abre una', `<table class="tbl"><tbody>${[['1', '12/09/2026', 'Pliego original', 'ok', 'Validada'], ['2', '16/09/2026', 'Circular N.º 1: cambia el plazo de entrega', 'ok', 'Validada'], ['3', 'en revisión', 'Circular N.º 2: agrega T-10 (muestras)', 'nd', '3 cambios por revisar']].map(([v, d, t, s, e]) => `<tr><td class="data" style="width:3rem">v${v}</td><td><div>${t}</div><div class="muted sm">${d}</div></td><td class="r">${tag(s, e)}</td></tr>`).join('')}</tbody></table>`)}
    </div>
    ${blk('Matriz de cumplimiento', 'Versión 3 · 23 requisitos × 3 ofertas', matrix() + `<div style="margin-top:.875rem">${legend()}</div>`)}`;
  }

  function pOfertas() {
    const low = Math.min(...OF.map(o => o.total));
    const row = (lab, f) => `<tr><th scope="row">${lab}</th>${OF.map(f).join('')}</tr>`;
    const cmp = `<table class="cmp"><thead><tr><th></th>${OF.map(o => `<th>${rider(o.falta.length ? 'var(--nd)' : 'var(--ok)', o.falta.length ? 'Falta documentación' : 'Completa')}<span class="lab">Oferta ${o.n}</span><b>${o.name}</b><small>CUIT ${o.cuit}</small></th>`).join('')}</tr></thead><tbody>
      ${row('Total cotizado', o => `<td><span class="big">${money(o.total)}</span>${o.total === low ? '<span class="low">la más baja</span>' : ''}</td>`)}
      ${row('Garantía', o => { const p = o.garM / o.total, bad = p < .0499; return `<td class="${bad ? 'bad' : ''}">${o.gar} · <span class="data">${money(o.garM)}</span><div class="sm ${bad ? '' : 'muted'}">${(p * 100).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} % ${bad ? '— el pliego exige 5 %' : 'de la oferta'}</div></td>`; })}
      ${row('Documentos', o => `<td>${o.docs} de 9</td>`)}
      ${row('Hoja de compliance', o => `<td>${o.falta.length ? tag('nd', 'Sin cargar') : tag('ok', 'Cargada')}</td>`)}
      ${row('23 requisitos', o => `<td><div class="strip" title="${o.cnt.ok} cumplen, ${o.cnt.no} no cumplen, ${o.cnt.nd} no determinados, ${o.cnt.pe} pendientes">${o.states.map(s => `<i style="--c:${scol(s)}"></i>`).join('')}</div><div class="sm muted" style="margin-top:.375rem">${o.cnt.ok} cumplen · ${o.cnt.no} no · ${o.cnt.nd} sin determinar · ${o.cnt.pe} pend.</div></td>`)}
      ${row('Falta', o => `<td>${o.falta.length ? o.falta.join('<br>') : '<span class="muted">Nada</span>'}</td>`)}
      ${row('', o => `<td><div class="acts"><button class="btn sm">Ver ficha</button>${o.falta.length ? `<button class="btn sm p">${I.up}Subir lo que falta</button>` : ''}</div></td>`)}
    </tbody></table>`;
    const circ = [['Circular N.º 1', 'Modificatoria', '10/09/2026', 'Abrió la versión 2 de la matriz', 'ok', 'Cargada'], ['Circular N.º 2', 'Modificatoria', '15/09/2026', 'Abrió la versión 3 de la matriz', 'ok', 'Cargada'], ['Respuesta a la consulta N.º 1', 'Aclaratoria', '08/09/2026', 'Aclara el envase del R5', 'ok', 'Cargada'], ['Respuesta a la consulta N.º 2', 'Aclaratoria', '06/10/2026', 'Novedad del Portal', 'nd', 'Sin aprobar']];
    return `${ph(2, 'Ofertas', 'Las ofertas salen del acta de apertura del Portal; sus documentos los sube la Comisión.', `<button class="btn">${I.portal}Agregar oferta desde el Portal</button><button class="btn p">${I.up}Subir archivos de una oferta</button>`)}
    ${blk('Las tres ofertas del acta', 'Apertura del 22/09/2026 11:00', `<div style="overflow-x:auto">${cmp}</div>`)}
    ${blk('Circulares y aclaraciones', '4 publicadas en el Portal', `<table class="tbl"><thead><tr><th>Documento</th><th>Tipo</th><th>Fecha</th><th>Efecto</th><th class="r">Estado</th></tr></thead><tbody>${circ.map(([a, b, c, d, s, e]) => `<tr><td class="task">${a}</td><td>${b}</td><td class="data">${c}</td><td class="muted">${d}</td><td class="r">${tag(s, e)}</td></tr>`).join('')}</tbody></table>`)}`;
  }

  function pEval() {
    return `${ph(3, 'Evaluación y dictamen', 'El sistema propone con su fundamento; la Comisión decide. Lo que no tiene fundamento queda como no determinado.', `<button class="btn">${I.down}Exportar</button><button class="btn p">${I.portal}Tomar el dictamen del Portal</button>`)}
    <section class="blk reading"><div><b>Informe técnico IT-07/2026 del área requirente</b><div class="muted sm">El sistema lo está leyendo: página 9 de 16.</div></div><div class="bar"><i style="--p:56%"></i></div><button class="btn sm">Ver lo leído</button></section>
    <div class="cols2 even">
      ${blk('Resultado por oferta', 'Versión 3 de la matriz', CH.res[C.res]())}
      ${blk('Orden económico', 'Total cotizado', CH.eco[C.eco]())}
    </div>
    <div class="cols2 even">
      ${blk('Descartes propuestos', '2 · decide la Comisión', `
        <div class="item"><div class="ih"><p><b>Oferta 3 · Mascotas del Litoral S.A.</b><br>Garantía de mantenimiento menor al 5 % exigido.</p>${ico('no')}</div>
        <p class="fund"><b>Pliego, art. 6.1${fs('7')}:</b> «garantía de mantenimiento del 5 % del monto de la oferta». <b>Oferta:</b> póliza por ${money(659400)}, el 4,0 % de ${money(16485000)}.</p>
        <div class="acts"><button class="btn sm js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>
        <div class="item"><div class="ih"><p><b>Oferta 2 · Agroalimentos Río Seco S.R.L.</b><br>Renglón 6 sin registro del producto ante SENASA.</p>${ico('no')}</div>
        <p class="fund"><b>Anexo I, ítem 6${fs('30')}:</b> «producto con registro vigente». <b>Oferta:</b> la ficha del R6 no informa número de registro; se leyeron sus 7 documentos y ninguno lo informa.</p>
        <div class="acts"><button class="btn sm js-ok">${I.check}Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>`)}
      ${blk('Preguntas a la Comisión', '2 sin responder', `
        <div class="item"><div class="ih"><p>Oferta 2: el poder no menciona la facultad de cotizar. ¿Se pide subsanación?</p>${tag('nd', 'Sin responder')}</div><div class="acts"><button class="btn sm p">Responder</button></div></div>
        <div class="item"><div class="ih"><p>Oferta 3: la ficha del R3 informa 10 meses de vencimiento. ¿Se acepta?</p>${tag('nd', 'Sin responder')}</div><div class="acts"><button class="btn sm p">Responder</button></div></div>
        <div class="item"><div class="ih"><p>Oferta 1: ¿la póliza cubre los 60 días de mantenimiento?</p>${tag('ok', 'Respondida')}</div><p class="fund"><b>evaluador de muestra, 14/10/2026:</b> «Sí, la vigencia es de 90 días».</p></div>`)}
    </div>
    ${blk('Dictamen', 'El Portal publicó uno el 06/10/2026; no se aprobó todavía', `<div class="acts"><button class="btn js-ok">${I.check}Aprobar la carga</button><button class="btn">Preparar el dictamen de la Comisión</button></div>`)}`;
  }

  function pNorm() {
    const norms = [['Disposición AFIP 247/2022', 'Régimen de contrataciones vigente', '2026-03', 'ok', 'Validada'], ['Disposición AFIP 297/03', 'Régimen anterior: no aplica (autorizado en 2026)', '2019-11', '', 'No aplica'], ['Decreto Delegado 1023/2001', 'Marco nacional de contrataciones', '2024-07', 'ok', 'Validada'], ['Decreto 202/2017', 'Declaración jurada de intereses', '2017-03', 'ok', 'Validada'], ['Norma complementaria de ejemplo N.º 1', 'Ficticia, cargada para pruebas', '1', 'nd', 'Sin validar']];
    const cites = [['Disp. 247/2022', 9], ['Dto. 1023/2001', 2], ['Dto. 202/2017', 2], ['Ejemplo N.º 1', 1], ['Montos 2026', 1]];
    return `${ph(4, 'Normativas', 'El régimen sale de la fecha de autorización (14/08/2026): rige la Disposición 247/2022.', `<button class="btn p">${I.up}Subir archivo</button>`)}
    ${blk('Consulta de normativa', 'Cada respuesta cita norma, artículo y versión', `<form class="search" onsubmit="return false"><input id="q" placeholder="Escriba una pregunta sobre la normativa" aria-label="Pregunta sobre la normativa"><button class="btn p js-q">Consultar</button></form>
      <div class="ex">${['¿Qué plazo de mantenimiento de oferta fija el régimen?', '¿Cuándo corresponde pedir subsanación?', '¿Qué garantía se exige para impugnar?'].map(e => `<button class="fb js-ex">${e}</button>`).join('')}</div>
      <div class="answer"><b>Respuesta de muestra.</b> La respuesta real sale de la normativa cargada, con artículo y versión. Sin fundamento recuperable, el resultado es «no determinado».</div>`)}
    <div class="cols2">
      ${blk('Normas cargadas', '4 validadas · 1 sin validar · 1 falta', `<table class="tbl"><thead><tr><th>Norma</th><th>Qué regula</th><th>Versión</th><th class="r">Estado</th></tr></thead><tbody>${norms.map(([a, b, c, s, e]) => `<tr><td class="task">${a}</td><td class="muted">${b}</td><td class="data" style="white-space:nowrap">${c}</td><td class="r">${tag(s, e)}</td></tr>`).join('')}<tr><td class="task">Norma de montos 2026</td><td class="muted">Ficticia; la cita el pliego</td><td class="data">—</td><td class="r"><button class="btn sm">${I.up}Subir</button></td></tr></tbody></table>`)}
      ${blk('Citas del pliego', '15 · 14 encontradas', cites.map(([n, v]) => `<div class="crow"><span class="n">${n}</span><span class="v">${v}</span><div class="bar"><i style="--p:${v / 9 * 100}%;--bar:${n === 'Montos 2026' ? 'var(--nd)' : 'var(--brand)'}"></i></div></div>`).join('') + '<p class="cap"><b>Montos 2026</b> está citada y no está cargada: lo que depende de montos queda como no determinado.</p>')}
    </div>`;
  }

  // ---------- Armado ----------
  const tabHTML = TABS.map((t, i) => `<button class="tab" role="tab" id="tab-${t.k}" aria-controls="pg-${t.k}" aria-selected="false" tabindex="-1" data-i="${i}"><span class="tlab">${t.l}</span>${t.count ? `<span class="count" data-count="${i}">${t.count}</span>` : ''}</button>`).join('');
  const nav = `<nav class="nav" aria-label="Secciones del procedimiento">${W.layout === 'rail' ? '<div class="rail-h">Secciones</div>' : ''}<div class="tabs" role="tablist"><span class="ind" aria-hidden="true"></span>${tabHTML}</div></nav>`;
  const shell = `<header class="shell"><div class="shell-in">
    <a class="mark" href="#" aria-label="EVALUON">${W.mark}</a>
    <button class="proc" aria-label="Cambiar de procedimiento"><span class="pt"><small>Procedimiento</small><span class="t">CD 99/2026 · Alimento balanceado para perros</span></span>${I.chev}</button>
    <span class="grow"></span>
    <span class="who"><span><b>evaluador de muestra</b><small>Comisión Evaluadora</small></span><span class="av" aria-hidden="true">EM</span></span>
    <button class="out">Salir</button></div></header>`;
  const pages = [pProc, pPliego, pOfertas, pEval, pNorm].map((f, i) => `<section class="page" role="tabpanel" id="pg-${TABS[i].k}" aria-labelledby="tab-${TABS[i].k}">${f()}</section>`).join('');
  const stage = `<main class="main"><div class="stage-wrap"><div class="stage">${pages}</div></div></main>`;
  document.body.className = `w-${W.id} l-${W.layout} noanim`;
  document.body.innerHTML = `${shell}<div class="frame">${nav}${stage}</div><div class="toast" role="status" aria-live="polite"></div>`;
  if (W.after) W.after(document.body);

  // ---------- Pestañas ----------
  const tabs = $$('.tab'), pgs = $$('.page'), ind = $('.ind'), stageEl = $('.stage');
  function placeInd(i) { const t = tabs[i]; if (!t || !ind) return; ind.style.width = t.offsetWidth + 'px'; ind.style.transform = `translateX(${t.offsetLeft}px)`; }
  function setTabs(i) { tabs.forEach((t, k) => { t.setAttribute('aria-selected', k === i); t.tabIndex = k === i ? 0 : -1; t.classList.toggle('past', k < i); }); placeInd(i); }

  // ---------- Transiciones: 300–480 ms, salida más corta que la entrada ----------
  const E = { out: 'cubic-bezier(.16,1,.3,1)', io: 'cubic-bezier(.65,0,.35,1)', in: 'cubic-bezier(.5,0,.75,0)', turn: 'cubic-bezier(.6,.05,.3,1)' };
  const shade = (el, a, b, d, bg, ease = E.io) => { const s = document.createElement('div'); s.className = 'shade'; s.style.background = bg; el.appendChild(s); return s.animate([{ opacity: a }, { opacity: b }], { duration: d, easing: ease, fill: 'both' }); };
  const SH = 'linear-gradient(90deg,rgba(0,0,0,.06),rgba(0,0,0,.32))', SHU = 'linear-gradient(90deg,rgba(0,0,0,.22),rgba(0,0,0,.04) 70%)';
  const TR = {
    // Hoja de expediente que gira sobre el lomo izquierdo
    turn(out, inn, dir, d = 460) {
      if (dir > 0) { out.style.zIndex = 3; inn.style.zIndex = 1; out.style.transformOrigin = '0 50%';
        return [out.animate([{ transform: 'rotateY(0)' }, { transform: 'rotateY(-90deg)' }], { duration: d, easing: E.turn, fill: 'both' }), shade(out, 0, .8, d, SH), shade(inn, .9, 0, d, SHU)]; }
      inn.style.zIndex = 3; out.style.zIndex = 1; inn.style.transformOrigin = '0 50%';
      return [inn.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0)' }], { duration: d, easing: E.turn, fill: 'both' }), shade(inn, .8, 0, d, SH), shade(out, 0, .9, d, SHU)];
    },
    turnsoft(out, inn, dir) { return TR.turn(out, inn, dir, 380); },
    // Hoja de formulario que se levanta sobre su borde superior, como un block
    flipup(out, inn, dir) {
      const d = 400;
      if (dir > 0) { out.style.zIndex = 3; inn.style.zIndex = 1; out.style.transformOrigin = '50% 0';
        return [out.animate([{ transform: 'rotateX(0)', opacity: 1 }, { transform: 'rotateX(78deg)', opacity: 0 }], { duration: d, easing: E.io, fill: 'both' }), shade(inn, .5, 0, d, 'linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,0) 40%)')]; }
      inn.style.zIndex = 3; out.style.zIndex = 1; inn.style.transformOrigin = '50% 0';
      return [inn.animate([{ transform: 'rotateX(78deg)', opacity: 0 }, { transform: 'rotateX(0)', opacity: 1 }], { duration: d, easing: E.out, fill: 'both' }), shade(out, 0, .4, d, 'rgba(0,0,0,.25)')];
    },
    // Papel continuo: la hoja nueva sube desde abajo como en la impresora
    feed(out, inn, dir) {
      const d = 380; stageEl.classList.add('clip');
      inn.style.zIndex = 2; out.style.zIndex = 1;
      const h = Math.min(out.offsetHeight, innerHeight);
      return [out.animate([{ transform: 'translateY(0)' }, { transform: `translateY(${-dir * h * .35}px)`, opacity: 0 }], { duration: d * .8, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `translateY(${dir * h * .5}px)`, opacity: 0 }, { transform: 'translateY(0)', opacity: 1 }], { duration: d, easing: E.out, fill: 'both' })];
    },
    // Esquina que se despega, como una hoja de un taco de sellos
    curl(out, inn, dir) {
      const d = 480, top = dir > 0 ? out : inn, under = dir > 0 ? inn : out;
      top.style.zIndex = 3; under.style.zIndex = 1;
      const fr = t => `polygon(0 0, ${t + 40}% 0, ${t}% 100%, 0 100%)`;
      const k = dir > 0 ? [100, 55, -42] : [-42, 55, 100];
      return [top.animate(k.map(t => ({ clipPath: fr(t) })), { duration: d, easing: E.io, fill: 'both' }), shade(under, dir > 0 ? .6 : 0, dir > 0 ? 0 : .6, d, SHU)];
    },
    // Tren: la pantalla nueva entra por el costado sobre la vía
    slide(out, inn, dir) {
      const d = 340; stageEl.classList.add('clip'); inn.style.zIndex = 2; out.style.zIndex = 1;
      return [out.animate([{ transform: 'translateX(0)', opacity: 1 }, { transform: `translateX(${-dir * 8}%)`, opacity: 0 }], { duration: d * .75, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `translateX(${dir * 12}%)`, opacity: 0 }, { transform: 'translateX(0)', opacity: 1 }], { duration: d, delay: 40, easing: E.out, fill: 'both' })];
    },
    // Fichero: la ficha sale hacia atrás y la siguiente sube desde el cajón
    drawer(out, inn, dir) {
      const d = 420; out.style.transformOrigin = '50% 100%'; inn.style.transformOrigin = '50% 100%';
      out.style.zIndex = dir > 0 ? 1 : 3; inn.style.zIndex = dir > 0 ? 3 : 1;
      return [out.animate([{ transform: 'rotateX(0) translateY(0)', opacity: 1 }, { transform: `rotateX(${dir > 0 ? -16 : 16}deg) translateY(${dir > 0 ? -16 : 24}px)`, opacity: 0 }], { duration: d * .7, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `rotateX(${dir > 0 ? 14 : -10}deg) translateY(${dir > 0 ? 40 : -20}px)`, opacity: 0 }, { transform: 'rotateX(0) translateY(0)', opacity: 1 }], { duration: d, delay: 60, easing: E.out, fill: 'both' })];
    },
    shift(out, inn, dir) {
      inn.style.zIndex = 2;
      return [out.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 120, easing: 'ease-in', fill: 'both' }),
        inn.animate([{ opacity: 0, transform: `translateX(${dir * 10}px)` }, { opacity: 1, transform: 'none' }], { duration: 220, delay: 60, easing: E.out, fill: 'both' })];
    },
    fade(out, inn) { inn.style.zIndex = 2; return [inn.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 140, easing: 'ease-out', fill: 'both' })]; },
  };
  const TRN = { turn: 'Hoja de expediente que gira', turnsoft: 'Hoja que gira, más corta', flipup: 'Hoja de block que se levanta', feed: 'Papel que avanza', curl: 'Esquina que se despega', slide: 'Pantalla que entra por la vía', drawer: 'Ficha que sale del cajón', shift: 'Desplazamiento corto' };
  const TRO = Object.keys(TRN);
  let trn = Q.get('tr') && TR[Q.get('tr')] ? Q.get('tr') : W.transition;

  let cur = -1, run = null;
  function settle() { if (!run) return; const r = run; run = null; r.anims.forEach(a => { try { a.cancel(); } catch (e) { /* nada */ } }); r.done(); }
  function go(to, opt = {}) {
    if (to === cur || to < 0 || to > 4) return;
    settle();
    const from = cur; cur = to; setTabs(to);
    if (!opt.hash) history.replaceState(null, '', '#' + TABS[to].k);
    const inn = pgs[to];
    if (from < 0) { pgs.forEach(p => p.classList.remove('on')); inn.classList.add('on'); return; }
    const out = pgs[from], dir = to > from ? 1 : -1;
    const navH = W.layout === 'rail' && innerWidth > 1060 ? 0 : $('.nav').offsetHeight;
    const top = stageEl.getBoundingClientRect().top + scrollY - navH - 16;
    if (scrollY > top) scrollTo({ top, behavior: 'instant' });
    out.classList.add('leaving', 'moving'); inn.classList.add('on', 'moving');
    const anims = (REDUCE ? TR.fade : TR[trn])(out, inn, dir);
    const me = run = { anims, done() { out.classList.remove('on', 'leaving', 'moving'); inn.classList.remove('moving'); [out, inn].forEach(p => { p.style.zIndex = ''; p.style.transformOrigin = ''; $$(':scope > .shade', p).forEach(s => s.remove()); }); stageEl.classList.remove('clip'); } };
    Promise.all(anims.map(a => a.finished)).then(() => { if (run !== me) return; run = null; anims.forEach(a => a.cancel()); me.done(); }).catch(() => {});
  }

  tabs.forEach((t, i) => t.addEventListener('click', () => go(i)));
  $('.tabs').addEventListener('keydown', e => {
    const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (d === undefined && e.key !== 'Home' && e.key !== 'End') return;
    e.preventDefault(); const n = e.key === 'Home' ? 0 : e.key === 'End' ? 4 : (cur + d + 5) % 5; go(n); tabs[n].focus();
  });
  const today = '21 OCT 2026';
  function decCount(i) { const b = $(`[data-count="${i}"]`); if (!b) return; const v = Math.max(0, +b.textContent - 1); b.textContent = v; b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop'); if (!v) b.hidden = true; }
  document.addEventListener('click', e => {
    const g = e.target.closest('[data-go]'); if (g) { go(+g.dataset.go); return; }
    const ok = e.target.closest('.js-ok');
    if (ok && !ok.dataset.done) {
      ok.dataset.done = '1';
      const label = ok.textContent.includes('descarte') ? 'Descarte aceptado' : 'Carga aprobada';
      if (SIG === 'stamp') { const s = document.createElement('span'); s.className = 'stamp press'; s.innerHTML = `${label}<small>${today} · E.M.</small>`; ok.replaceWith(s); }
      else { ok.classList.add('done'); ok.innerHTML = I.check + label; }
      const tr = e.target.closest('tr'); if (tr && tr.closest('.todo')) { decCount(0); const t = $('[data-todo]'); t.textContent = Math.max(0, +t.textContent - 1); }
      return;
    }
    const f = e.target.closest('.fb[data-f]');
    if (f) {
      const wrap = f.closest('.blk'); $$('.fb[data-f]', wrap).forEach(x => x.setAttribute('aria-pressed', x === f));
      $$('tr.r', wrap).forEach(tr => { const show = f.dataset.f === 'all' || tr.dataset.s.split(' ').includes(f.dataset.f); tr.classList.toggle('hide', !show); if (show && !REDUCE) { tr.classList.remove('hit'); void tr.offsetWidth; tr.classList.add('hit'); } });
      $$('tr.g', wrap).forEach(gr => gr.classList.toggle('hide', !$$(`tr.r[data-g="${gr.dataset.g}"]:not(.hide)`, wrap).length));
      return;
    }
    const ex = e.target.closest('.js-ex'); if (ex) { $('#q').value = ex.textContent; }
    if (ex || e.target.closest('.js-q')) { const a = $('.answer'); a.classList.remove('on'); void a.offsetWidth; a.classList.add('on'); }
  });
  const toast = $('.toast'); let tt = 0;
  document.addEventListener('keydown', e => {
    const el = e.target instanceof Element ? e.target : null;
    if ((el && el.closest('input,textarea')) || e.ctrlKey || e.metaKey || e.altKey) return;
    const h = location.hash;
    if (e.key === ']') location.href = `v${String(N % ALL.length + 1).padStart(2, '0')}.html${h}`;
    else if (e.key === '[') location.href = `v${String((N + ALL.length - 2) % ALL.length + 1).padStart(2, '0')}.html${h}`;
    else if (e.key === 'g' || e.key === 'G') location.href = 'index.html';
    else if (e.key === 't' || e.key === 'T') { trn = TRO[(TRO.indexOf(trn) + 1) % TRO.length]; toast.textContent = 'Transición: ' + TRN[trn]; toast.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => toast.classList.remove('on'), 1500); }
  });
  addEventListener('resize', () => placeInd(cur));
  addEventListener('hashchange', () => { const i = TABS.findIndex(t => '#' + t.k === location.hash); if (i >= 0) go(i, { hash: true }); });
  go(Math.max(0, TABS.findIndex(t => '#' + t.k === location.hash)));
  const ready = () => { placeInd(cur); requestAnimationFrame(() => document.body.classList.remove('noanim')); };
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(ready);
  setTimeout(() => placeInd(cur), 400);
})();
