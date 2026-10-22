/* Motor de las maquetas de exploración visual de EVALUON.
   Arma la aplicación (encabezado + cinco pestañas al mismo nivel) con el caso
   ficticio "Alimento balanceado para perros" y aplica la propuesta elegida
   (tokens, tipografías, disposición, gráficos y transición de página).
   Datos 100 % inventados (P4). */
(() => {
  'use strict';
  const root = document.documentElement;
  const ALL = window.DISENOS;
  const N = +root.dataset.d;
  const cfg = ALL[N - 1];
  const params = new URLSearchParams(location.search);
  const THUMB = params.has('thumb');
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (THUMB) root.classList.add('thumb');

  // ---------- Tema ----------
  if (cfg.fonts) {
    const pre = document.createElement('link');
    pre.rel = 'preconnect'; pre.href = 'https://fonts.gstatic.com'; pre.crossOrigin = '';
    document.head.appendChild(pre);
    const l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?' + cfg.fonts + '&display=swap';
    document.head.appendChild(l);
  }
  const style = document.createElement('style');
  style.textContent = ':root{' + Object.entries(cfg.t).map(([k, v]) => `--${k}:${v}`).join(';') + '}' + (cfg.css || '');
  document.head.appendChild(style);
  document.title = `EVALUON · ${String(N).padStart(2, '0')} ${cfg.name}`;
  if (cfg.dark) root.style.colorScheme = 'dark';

  // ---------- Datos del caso (ficticio) ----------
  const OF = [
    { n: 1, name: 'Nutrición Canina Austral S.A.', short: 'Austral', cuit: '30-00000001-0', total: 16054000, gar: 'Póliza', garM: 802700, docs: 9, falta: [] },
    { n: 2, name: 'Agroalimentos Río Seco S.R.L.', short: 'Río Seco', cuit: '30-00000002-0', total: 13952400, gar: 'Pagaré', garM: 697620, docs: 7, falta: ['Hoja de compliance', 'DJ de intereses'] },
    { n: 3, name: 'Mascotas del Litoral S.A.', short: 'Litoral', cuit: '30-00000003-0', total: 16485000, gar: 'Póliza', garM: 659400, docs: 7, falta: ['Hoja de compliance', 'Fichas técnicas R5 y R6'] },
  ];
  const ESTIMADO = 15800000;
  const REQ = [
    ['F-01', 'Planilla de cotización firmada (Anexo II)', 'F', 'ok ok ok'],
    ['F-02', 'Inscripción vigente en el registro de proveedores', 'F', 'ok ok ok'],
    ['F-03', 'Declaración jurada de intereses', 'F', 'ok pe ok'],
    ['F-04', 'Garantía de mantenimiento del 5 %', 'F', 'ok ok no'],
    ['F-05', 'Mantenimiento de oferta por 60 días', 'F', 'ok ok ok'],
    ['F-06', 'Constancia de CUIT', 'F', 'ok ok ok'],
    ['F-07', 'Poder suficiente del firmante', 'F', 'ok nd ok'],
    ['F-08', 'Domicilio especial constituido', 'F', 'ok ok ok'],
    ['T-01', 'Proteína bruta mínima del 22 % (R1 y R2)', 'T', 'ok nd ok'],
    ['T-02', 'Registro del producto ante SENASA', 'T', 'ok no ok'],
    ['T-03', 'Vencimiento de 12 meses o más desde la entrega', 'T', 'nd ok nd'],
    ['T-04', 'Envase de 20 kg (R1)', 'T', 'ok ok ok'],
    ['T-05', 'Envase de 15 kg (R2 a R4)', 'T', 'ok ok ok'],
    ['T-06', 'Ficha técnica por renglón', 'T', 'ok no nd'],
    ['T-07', 'Dieta gastrointestinal de uso veterinario (R5)', 'T', 'ok ok pe'],
    ['T-08', 'Dieta renal de uso veterinario (R6)', 'T', 'ok no pe'],
    ['T-09', 'Entrega dentro de los 10 días hábiles', 'T', 'no ok ok'],
    ['T-10', 'Muestras a pedido de la Comisión', 'T', 'nd ok ok'],
    ['E-01', 'Habilidad para contratar', 'E', 'ok pe pe'],
    ['E-02', 'Sin deuda previsional', 'E', 'ok pe pe'],
    ['E-03', 'Sin sanciones vigentes como proveedor', 'E', 'ok pe pe'],
    ['E-04', 'Sin juicios pendientes con el organismo', 'E', 'ok pe pe'],
    ['E-05', 'Sin registro de empleadores sancionados', 'E', 'pe pe pe'],
  ].map(([id, txt, g, s]) => ({ id, txt, g, s: s.split(' ') }));
  const ORDER = ['ok', 'no', 'nd', 'pe'];
  const STN = { ok: 'Cumple', no: 'No cumple', nd: 'No determinado', pe: 'Pendiente' };
  OF.forEach((o, k) => {
    o.cnt = { ok: 0, no: 0, nd: 0, pe: 0 };
    REQ.forEach(r => o.cnt[r.s[k]]++);
    o.states = REQ.map(r => r.s[k]);
  });
  const TABS = [
    { k: 'procedimiento', l: 'Procedimiento', badge: 2, pct: 100, meta: '2 novedades del Portal' },
    { k: 'pliego', l: 'Pliego y matriz', badge: 1, pct: 75, meta: 'Falta el Anexo III' },
    { k: 'ofertas', l: 'Ofertas', badge: 4, pct: 70, meta: 'Faltan 4 documentos' },
    { k: 'evaluacion', l: 'Evaluación y dictamen', badge: 0, pct: 55, meta: 'Informe técnico 9 de 16' },
    { k: 'normativas', l: 'Normativas', badge: 1, pct: 80, meta: 'Falta 1 norma' },
  ];
  const STATUS = [
    ['Datos, 6 renglones, cronograma y garantías', 'Nada. Hay 2 novedades del Portal para aprobar'],
    ['Pliego, Anexo I y II; matriz de 23 requisitos', 'Anexo III (modelo de DJ de intereses)'],
    ['3 ofertas, 23 documentos, 2 circulares', 'Compliance de las ofertas 2 y 3; fichas R5 y R6; DJ de la oferta 2'],
    ['Propuesta 3 × 23, orden económico, informe IT-07/2026', 'Dictamen: el Portal publicó uno sin aprobar'],
    ['Disp. AFIP 247/2022 y marco nacional validados', 'Norma de montos 2026 (ficticia) citada por el pliego'],
  ];

  // ---------- Utilidades ----------
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const money = n => '$ ' + n.toLocaleString('es-AR');
  const mill = n => '$ ' + (n / 1e6).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' M';
  const pct = (a, b) => (a / b * 100).toLocaleString('es-AR', { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + ' %';
  const SYM = {
    ok: 'M5 8.4l2.1 2.1L11.2 6',
    no: 'M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8',
    nd: 'M6.3 6.4a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.3M8 11.5v.1',
    pe: 'M8 4.8V8l2 1.3',
  };
  const ico = s => `<span class="st st-${s}" role="img" aria-label="${STN[s]}" data-n="${STN[s]}" tabindex="0"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="8"/><path d="${SYM[s]}"/></svg></span>`;
  const I = {
    portal: '<svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9z"/></svg>',
    up: '<svg viewBox="0 0 24 24"><path d="M12 16V4M7 9l5-5 5 5M5 20h14"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    doc: '<svg viewBox="0 0 24 24"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM14 3v5h5M9 13h6M9 17h4"/></svg>',
    read: '<svg viewBox="0 0 24 24"><path d="M3 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H3zM21 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z"/></svg>',
    out: '<svg viewBox="0 0 24 24"><path d="M12 4v12M7 11l5 5 5-5M5 20h14"/></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
    gavel: '<svg viewBox="0 0 24 24"><path d="M14 5l5 5M11 8l5 5M12.5 6.5l-6 6M4 20h9M8 16l-3 3"/></svg>',
    chev: '<svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>',
  };
  const TI = [
    'M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16.5z',
    'M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM14 3v5h5M9 13h6M9 17h4',
    'M4 8l8-4 8 4-8 4zM4 12l8 4 8-4M4 16l8 4 8-4',
    'M10 6h10M10 12h10M10 18h10M4 6l1.2 1.2L7.5 5M4 12l1.2 1.2 2.3-2.2M4 18l1.2 1.2 2.3-2.2',
    'M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5zM5 19.5A1.5 1.5 0 0 0 6.5 21H19M9 7h6',
  ];
  const tabIcon = i => `<svg class="ti" viewBox="0 0 24 24" aria-hidden="true"><path d="${TI[i]}"/></svg>`;
  const scol = s => `var(--${s})`;
  const ocol = k => `var(--c${k + 1})`;
  let rid = 0;

  // ---------- Gráficos ----------
  const legend = () => `<div class="legend">${ORDER.map(s => `<span><i class="sw" style="--c:${scol(s)}"></i>${STN[s]}</span>`).join('')}</div>`;

  const charts = {
    // Resultado por oferta
    res: {
      stacked: () => OF.map((o, k) => `<div class="crow"><span class="n">Oferta ${o.n} · ${o.short}</span><span class="v">${o.cnt.ok} de 23 cumplen</span>
        <div class="stk">${ORDER.filter(s => o.cnt[s]).map((s, j) => `<i style="flex:${o.cnt[s]};--c:${scol(s)};--i:${k * 4 + j}" title="${STN[s]}: ${o.cnt[s]}"></i>`).join('')}</div></div>`).join('') + legend(),
      donut: () => `<div class="donuts">${OF.map((o, k) => {
        let acc = 0;
        const segs = ORDER.map(s => {
          const v = o.cnt[s] / 23 * 100; const off = 25 - acc; acc += v;
          return v ? `<circle cx="21" cy="21" r="15.915" fill="none" stroke="${scol(s)}" stroke-width="5.2" stroke-dasharray="${Math.max(v - 1.2, 0.1)} ${100 - Math.max(v - 1.2, 0.1)}" stroke-dashoffset="${off}"/>` : '';
        }).join('');
        return `<div><svg class="donut" viewBox="0 0 42 42" style="--i:${k}" role="img" aria-label="Oferta ${o.n}: ${o.cnt.ok} de 23 cumplen">${segs}<text x="21" y="22.5" text-anchor="middle" font-size="10">${o.cnt.ok}</text><text x="21" y="28.5" text-anchor="middle" font-size="3.6" style="font-weight:500;fill:var(--muted)">de 23</text></svg><div class="n">Oferta ${o.n}</div><div class="d">${o.short}</div></div>`;
      }).join('')}</div><div style="margin-top:14px">${legend()}</div>`,
      waffle: () => `<div class="wafs">${OF.map((o, k) => {
        const st = [...o.states].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
        return `<div class="crow" style="margin:0"><span class="n">Oferta ${o.n} · ${o.short}</span><span class="v">${o.cnt.ok}/23</span><div class="waf" style="grid-column:1/-1">${st.map((s, j) => `<i style="--c:${scol(s)};--k:${k * 23 + j}" title="${STN[s]}"></i>`).join('')}</div></div>`;
      }).join('')}</div><div style="margin-top:14px">${legend()}</div>`,
      rings: () => {
        const R = [44, 34, 24];
        const rings = OF.map((o, k) => {
          const C = 2 * Math.PI * R[k]; const v = o.cnt.ok / 23;
          return `<circle cx="55" cy="55" r="${R[k]}" fill="none" stroke="var(--track)" stroke-width="8"/><circle class="v" cx="55" cy="55" r="${R[k]}" fill="none" stroke="${ocol(k)}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-to="${C * (1 - v)}" transform="rotate(-90 55 55)" style="--i:${k}"/>`;
        }).join('');
        return `<div class="ringwrap"><svg class="rings" viewBox="0 0 110 110" width="170" height="170" role="img" aria-label="Porcentaje de requisitos que cumple cada oferta">${rings}</svg>
        <div>${OF.map((o, k) => `<div class="crow" style="margin-bottom:12px"><span class="n"><i class="sw" style="--c:${ocol(k)}"></i>&nbsp; Oferta ${o.n} · ${o.short}</span><span class="v">${Math.round(o.cnt.ok / 23 * 100)} %</span><span style="grid-column:1/-1;font-size:12.5px;color:var(--muted)">${o.cnt.no} no cumple · ${o.cnt.nd} no determinado · ${o.cnt.pe} pendiente</span></div>`).join('')}</div></div>`;
      },
      columns: () => `<div class="cols">${OF.map((o, k) => `<div class="grp">${ORDER.map((s, j) => `<i style="--c:${scol(s)};--h:${o.cnt[s] / 19 * 100}%;--i:${k * 4 + j}" title="${STN[s]}: ${o.cnt[s]}"><span>${o.cnt[s]}</span></i>`).join('')}<b>Oferta ${o.n} · ${o.short}</b></div>`).join('')}</div>${legend()}`,
    },
    // Orden económico
    eco: {
      hbar: () => {
        const s = [...OF].sort((a, b) => a.total - b.total); const max = 17500000;
        return s.map((o, k) => `<div class="hb"><span class="n">${k + 1}.º ${o.short}<small>Oferta ${o.n}</small></span><span class="trk"><i style="--p:${o.total / max * 100}%;--c:${k ? 'color-mix(in srgb,var(--muted) 45%,var(--track))' : 'var(--brand)'};--i:${k}"></i><span class="mk" style="--m:${ESTIMADO / max * 100}%" title="Monto estimado"></span></span><span class="v">${money(o.total)}</span></div>`).join('') +
          `<p class="note">La línea marca el monto estimado (${money(ESTIMADO)}). <b>Río Seco</b> cotiza ${pct(ESTIMADO - s[0].total, ESTIMADO)} por debajo.</p>`;
      },
      lollipop: () => {
        const s = [...OF].sort((a, b) => a.total - b.total);
        const x0 = 12e6, x1 = 17e6, W = 540, L = 96, R = 104, X = v => L + (v - x0) / (x1 - x0) * (W - L - R);
        const ticks = [12e6, 13e6, 14e6, 15e6, 16e6, 17e6].map(v => `<line class="s" x1="${X(v)}" x2="${X(v)}" y1="22" y2="150" stroke-dasharray="2 4"/><text x="${X(v)}" y="168" text-anchor="middle">${v / 1e6} M</text>`).join('');
        const rows = s.map((o, k) => { const y = 48 + k * 42, len = X(o.total) - L; return `<text class="n" x="0" y="${y + 4}">${o.short}</text><line class="v" x1="${L}" x2="${X(o.total)}" y1="${y}" y2="${y}" stroke="${k ? 'var(--muted)' : 'var(--brand)'}" stroke-width="2.5" style="--len:${len};--i:${k}"/><circle cx="${X(o.total)}" cy="${y}" r="6.5" fill="${k ? 'var(--surface)' : 'var(--brand)'}" stroke="${k ? 'var(--muted)' : 'var(--brand)'}" stroke-width="2.5" style="--i:${k}"/><text class="m" x="${X(o.total) + 14}" y="${y + 4}">${mill(o.total)}</text>`; }).join('');
        const est = `<line x1="${X(ESTIMADO)}" x2="${X(ESTIMADO)}" y1="18" y2="150" stroke="var(--accent)" stroke-width="1.5"/><text x="${X(ESTIMADO)}" y="12" text-anchor="middle" style="fill:var(--ink);font-size:11.5px">estimado ${mill(ESTIMADO)}</text>`;
        return `<svg class="lolli" viewBox="0 0 ${W} 176" width="100%" style="max-width:${W}px" role="img" aria-label="Orden económico">${ticks}${est}${rows}</svg><p class="note">Ordenado de menor a mayor. La línea vertical es el monto estimado.</p>`;
      },
      columns: () => {
        const s = [...OF].sort((a, b) => a.total - b.total);
        return `<div class="cols" style="gap:36px">${s.map((o, k) => `<div class="grp"><i style="--c:${k ? 'color-mix(in srgb,var(--muted) 40%,var(--track))' : 'var(--brand)'};--h:${o.total / 17.5e6 * 100}%;--i:${k}"><span style="top:-20px">${mill(o.total)}</span></i><b>${k + 1}.º ${o.short}</b></div>`).join('')}</div><p class="note">Diferencia entre la primera y la segunda: <b>${money(s[1].total - s[0].total)}</b> (${pct(s[1].total - s[0].total, s[0].total)}).</p>`;
      },
      bullet: () => {
        const s = [...OF].sort((a, b) => a.total - b.total); const max = 18e6;
        return s.map((o, k) => `<div class="crow"><span class="n">${k + 1}.º ${o.name}</span><span class="v">${money(o.total)}</span>
          <div class="hb" style="grid-column:1/-1;grid-template-columns:1fr;margin:0"><span class="trk" style="height:16px;background:linear-gradient(90deg,var(--track) 0 ${ESTIMADO / max * 100}%,color-mix(in srgb,var(--track) 60%,var(--line)) ${ESTIMADO / max * 100}% 100%)"><i style="--p:${o.total / max * 100}%;--c:${o.total > ESTIMADO ? 'var(--muted)' : 'var(--brand)'};--i:${k};top:4px;bottom:4px"></i><span class="mk" style="--m:${ESTIMADO / max * 100}%"></span></span></div></div>`).join('') +
          `<p class="note">Fondo claro: hasta el monto estimado (${mill(ESTIMADO)}). Fondo oscuro: por encima.</p>`;
      },
      delta: () => {
        const s = [...OF].sort((a, b) => a.total - b.total);
        return s.map((o, k) => { const d = (o.total - s[0].total) / s[0].total; return `<div class="crow"><span class="n">${k + 1}.º ${o.short} <span style="font-weight:400;color:var(--muted)">· ${money(o.total)}</span></span><span class="v">${k ? '+' + pct(o.total - s[0].total, s[0].total) : 'la más baja'}</span><div class="bar" style="height:10px"><i style="--p:${k ? Math.max(d / 0.2 * 100, 4) : 100}%;--bar-c:${k ? 'var(--accent)' : 'var(--brand)'};--i:${k}"></i></div></div>`; }).join('') +
          `<p class="note">Cuánto más cara es cada oferta que la más baja. Escala: 20 % = barra completa.</p>`;
      },
    },
    // Avance por pestaña
    prog: {
      bars: () => TABS.map((t, i) => `<div class="crow"><span class="n">${t.l}</span><span class="v">${t.pct} %</span><div class="bar"><i style="--p:${t.pct}%;--i:${i};--bar-c:${t.pct === 100 ? 'var(--ok)' : 'var(--brand)'}"></i></div><span style="grid-column:1/-1;font-size:12.5px;color:var(--muted)">Falta: ${STATUS[i][1]} · <button class="link" data-go="${i}">Ir</button></span></div>`).join(''),
      segments: () => TABS.map((t, i) => `<div class="crow"><span class="n">${t.l}</span><span class="v">${t.pct} %</span><div class="seg">${Array.from({ length: 10 }, (_, j) => `<i class="${j < t.pct / 10 ? 'on' : ''}" style="--k:${i * 10 + j}"></i>`).join('')}</div><span style="grid-column:1/-1;font-size:12.5px;color:var(--muted)">Falta: ${STATUS[i][1]} · <button class="link" data-go="${i}">Ir</button></span></div>`).join(''),
      rings: () => `<div class="minirings">${TABS.map((t, i) => { const C = 2 * Math.PI * 26; return `<button data-go="${i}"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" fill="none" stroke="var(--track)" stroke-width="6"/><circle class="v" cx="32" cy="32" r="26" fill="none" stroke="${t.pct === 100 ? 'var(--ok)' : 'var(--brand)'}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-to="${C * (1 - t.pct / 100)}" transform="rotate(-90 32 32)" style="--i:${i}"/><text x="32" y="37" text-anchor="middle" font-size="15">${t.pct}</text></svg><small><b style="color:var(--ink)">${t.l}</b><br>${t.meta}</small></button>`; }).join('')}</div><div class="rows" style="margin-top:14px">${TABS.map((t, i) => t.pct < 100 ? `<div style="grid-template-columns:minmax(0,1fr) auto;padding:9px 0"><span class="d"><b style="color:var(--ink);font-weight:600">${t.l}:</b> falta ${STATUS[i][1].charAt(0).toLowerCase() + STATUS[i][1].slice(1)}</span><button class="link" data-go="${i}">Ir</button></div>` : '').join('')}</div>`,
    },
    // Cronograma
    time: {
      line: () => {
        const ev = [['20/08', 'Publicación', 0], ['10/09', 'Circular N.º 1', 21], ['15/09', 'Fin de consultas', 26], ['22/09', 'Apertura', 33], ['06/10', 'Dictamen en el Portal', 47], ['21/10', 'Hoy', 62], ['', 'Dictamen de la Comisión', 72]];
        const span = 72;
        return `<div class="tl"><div class="ax"><i style="--p:${62 / span * 100}%"></i></div>${ev.map(([d, t, x], k) => `<span class="ev ${t === 'Hoy' ? 'now' : d ? '' : 'fut'}" style="left:${x / span * 100}%"></span><span class="lb ${k % 2 ? 'dn' : 'up'}" style="left:${x / span * 100}%"><b>${d || 'pendiente'}</b>${t}</span>`).join('')}</div>`;
      },
      vertical: () => `<ul class="vt">${[['20/08/2026', 'Publicación en el Portal'], ['08/09/2026', 'Respuesta a la consulta N.º 1'], ['10/09/2026', 'Circular N.º 1 (modificatoria)'], ['15/09/2026', 'Fin de consultas · Circular N.º 2'], ['22/09/2026 11:00', 'Apertura de ofertas'], ['06/10/2026', 'El Portal publica un dictamen'], ['21/10/2026', 'Hoy: informe técnico en lectura', 'now'], ['Pendiente', 'Dictamen de la Comisión', 'fut']].map(([d, t, c]) => `<li class="${c || ''}"><b>${d}</b>${t}</li>`).join('')}</ul>`,
    },
  };
  const C = cfg.charts;

  // ---------- Páginas ----------
  const kpi = (v, l, cls = '', i = 0) => `<div class="kpi rise ${cls}" style="--i:${i}"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  const card = (title, sub, body, extra = '', i = 0, cls = '') => `<section class="card rise ${cls}" style="--i:${i}"><div class="card-h"><div><h3>${title}</h3>${sub ? `<div class="sub">${sub}</div>` : ''}</div>${extra}</div>${body}</section>`;
  const secH = (eye, h, p, actions) => `<div class="sec-h rise" style="--i:0"><div><div class="eyebrow">${eye}</div><h2 class="h2">${h}</h2>${p ? `<p>${p}</p>` : ''}</div><div class="actions">${actions}</div></div>`;

  function pageProc() {
    const ren = [['Alimento balanceado adulto raza grande, bolsa de 20 kg', 120], ['Alimento balanceado adulto raza mediana, bolsa de 15 kg', 80], ['Alimento balanceado cachorro, bolsa de 15 kg', 40], ['Alimento balanceado senior, bolsa de 15 kg', 30], ['Dieta gastrointestinal, bolsa de 10 kg', 20], ['Dieta renal, bolsa de 10 kg', 12]];
    return `
    <div class="hero rise" style="--i:0"><div>
      <div class="eyebrow">Contratación Directa N.º 99/2026</div>
      <h1 class="title">Alimento balanceado para perros</h1>
      <div class="meta"><span>Expediente <b>EX-2026-00000099-DEMO</b></span><span>Autorización <b>14/08/2026</b></span><span>Régimen <b>Disp. AFIP 247/2022</b></span><span>Apertura <b>22/09/2026 11:00</b></span></div></div>
      <div class="actions"><button class="btn">${I.portal}Tomar del Portal</button><button class="btn prim">${I.up}Subir archivo</button></div>
    </div>
    <div class="kpis">${kpi('6', 'Renglones, tomados del Portal', '', 1)}${kpi('3', 'Ofertas del acta de apertura', '', 2)}${kpi('23', 'Requisitos en la matriz (v3)', '', 3)}${kpi('<span data-nov>2</span>', 'Novedades del Portal para aprobar', 'hot', 4)}</div>
    <div class="g2">
      ${card('Qué hay y qué falta, por pestaña', 'Cada pestaña se completa en cualquier orden', charts.prog[C.prog](), '', 5)}
      <div class="stack">
      ${card('Novedades del Portal', 'Última revisión: hoy 08:00. Nada entra sin su aprobación.', `<div class="rows">${[['Respuesta a la consulta N.º 2', 'Aclaratoria · publicada el 06/10/2026', 'Queda en Ofertas'], ['Dictamen de la Comisión Evaluadora', 'Publicado el 06/10/2026', 'Queda en Evaluación y dictamen']].map(([t, d, q]) => `<div style="grid-template-columns:minmax(0,1fr) auto"><div><div class="t">${t}</div><div class="d">${d} · ${q}</div></div><button class="btn sm js-aprobar">${I.check}Aprobar la carga</button></div>`).join('')}</div>`, '<span class="chip nd">2 sin aprobar</span>', 6)}
      ${card('Garantías', 'Del pliego y del Portal', `<table class="tbl"><tbody>${[['Mantenimiento de oferta', '5 % de la oferta', 'Pliego, art. 6.1'], ['Cumplimiento del contrato', '10 % del contrato', 'Pliego, art. 12'], ['Impugnación', '3 % del monto estimado', 'Portal']].map(([a, b, c]) => `<tr><td>${a}<div class="sub" style="margin:0">${c}</div></td><td style="font-weight:600;text-align:right;white-space:nowrap">${b}</td></tr>`).join('')}</tbody></table>`, '', 7)}
      </div>
    </div>
    ${card('Cronograma', 'Fechas del Portal y del pliego', charts.time[C.time](), '<span class="chip">Hoy 21/10/2026</span>', 7)}
    ${card('Renglones', '6 renglones · todos tomados del Portal el 07/10', `<table class="tbl"><thead><tr><th style="width:56px">Rengl.</th><th>Descripción</th><th class="num">Cantidad</th></tr></thead><tbody>${ren.map(([d, q], k) => `<tr><td class="mono">${k + 1}</td><td>${d}</td><td><div class="qty"><span class="bar"><i style="--p:${q / 120 * 100}%;--i:${k}"></i></span><span class="mono" style="min-width:52px;text-align:right">${q} u.</span></div></td></tr>`).join('')}</tbody></table>`, '<span class="chip ok">Del Portal</span>', 8)}`;
  }

  function matrix() {
    const grid = C.matrix === 'grid';
    const head = `<thead><tr><th>Requisito</th>${OF.map(o => `<th>Oferta ${o.n}<small>${o.short}</small></th>`).join('')}</tr></thead>`;
    const groups = [['F', 'Formales', 8], ['T', 'Técnicos', 10], ['E', 'Con información externa (hoja de compliance)', 5]];
    const body = groups.map(([g, name, n]) => `<tr class="grp ${g === 'E' ? 'ext' : ''}" data-g="${g}"><td colspan="4">${name} · ${n}</td></tr>` +
      REQ.filter(r => r.g === g).map(r => `<tr class="r" data-g="${g}" data-s="${r.s.join(' ')}"><td><span class="rid">${r.id}</span>${r.txt}</td>${r.s.map(s => grid ? `<td class="c"><div class="cell ${s}">${ico(s)}</div></td>` : `<td>${ico(s)}</td>`).join('')}</tr>`).join('')).join('');
    const cnt = s => REQ.filter(r => r.s.includes(s)).length;
    const filters = `<div class="filters" role="group" aria-label="Filtrar la matriz"><button class="fchip" aria-pressed="true" data-f="all">Todos <span class="n">23</span></button>${['no', 'nd', 'pe'].map(s => `<button class="fchip" aria-pressed="false" data-f="${s}"><i class="sw" style="--c:${scol(s)}"></i>${STN[s]} <span class="n">${cnt(s)}</span></button>`).join('')}</div>`;
    return `${filters}<table class="mtx ${grid ? 'grid' : ''}">${head}<tbody>${body}</tbody></table>`;
  }

  function pagePliego() {
    const docs = [['Pliego de bases y condiciones particulares', '18 págs. · Portal, 20/08/2026', 'ok', 'Leído'], ['Anexo I · Especificaciones técnicas', '6 págs. · Portal, 20/08/2026', 'ok', 'Leído'], ['Anexo II · Planilla de cotización', '2 págs. · Portal, 20/08/2026', 'ok', 'Leído'], ['Anexo III · Modelo de DJ de intereses', 'El Portal lo lista y no se tomó', 'nd', 'Falta']];
    return `
    ${secH('Pliego y matriz', 'Pliego, anexos y matriz de cumplimiento', 'La matriz la propone el sistema a partir del pliego y sus circulares; cada versión la valida la Comisión.', `<button class="btn">${I.portal}Tomar del Portal</button><button class="btn prim">${I.up}Subir archivo</button>`)}
    <div class="g2">
      ${card('Documentos del pliego', '3 de 4 leídos', `<div class="rows">${docs.map(([t, d, s, c]) => `<div style="grid-template-columns:auto minmax(0,1fr) auto"><span style="color:var(--muted);display:grid">${I.doc.replace('<svg', '<svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7"')}</span><div><div class="t">${t}</div><div class="d">${d}</div></div>${s === 'ok' ? `<span class="chip ok">${c}</span>` : `<button class="btn sm">${I.portal}Tomar del Portal</button>`}</div>`).join('')}</div>`, '', 1)}
      ${card('Versiones de la matriz', 'Cada circular modificatoria abre una versión', `<ul class="vt"><li><b>Versión 1 · 12/09/2026</b>Pliego original · <span class="chip ok">Validada</span></li><li><b>Versión 2 · 16/09/2026</b>Circular N.º 1: cambia el plazo de entrega · <span class="chip ok">Validada</span></li><li class="now"><b>Versión 3 · en revisión</b>Circular N.º 2: agrega T-10 (muestras) · <span class="chip nd">3 cambios por revisar</span></li></ul>`, '', 2)}
    </div>
    ${card('Matriz de cumplimiento', 'Versión 3 · 23 requisitos × 3 ofertas · pase el mouse sobre un ícono para ver el estado', matrix(), legend(), 3)}`;
  }

  function pageOfertas() {
    const low = Math.min(...OF.map(o => o.total));
    const offers = OF.map((o, k) => {
      const gp = o.garM / o.total; const bad = gp < 0.0499;
      return `<article class="card offer rise" style="--i:${k + 1}">
        <div class="ofh"><span class="chip" style="--x:0">Oferta ${o.n}</span>${o.total === low ? '<span class="lowest">La más baja</span>' : ''}</div>
        <h3>${o.name}</h3><div class="cuit">CUIT ${o.cuit}</div>
        <div class="tot">${money(o.total)}</div>
        <dl><dt>Garantía</dt><dd class="${bad ? 'bad' : ''}">${o.gar} · ${money(o.garM)} (${(gp * 100).toLocaleString('es-AR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %)</dd><dt>Documentos</dt><dd>${o.docs} de 9</dd><dt>Compliance</dt><dd>${o.falta.length ? 'Sin cargar' : 'Cargada'}</dd></dl>
        <div class="strip" title="Estado de los 23 requisitos">${o.states.map(s => `<i style="--c:${scol(s)}"></i>`).join('')}</div>
        <div class="falta ${o.falta.length ? '' : 'okk'}"><b>${o.falta.length ? 'Falta' : 'Completa'}</b>${o.falta.length ? o.falta.join(' · ') : 'Todos los documentos y la hoja de compliance'}</div>
        <div class="actions"><button class="btn sm">Ver ficha</button><button class="btn sm ${o.falta.length ? 'prim' : ''}">${I.up}${o.falta.length ? 'Subir lo que falta' : 'Subir documentos'}</button></div>
      </article>`;
    }).join('');
    const circ = [['Circular N.º 1', 'Modificatoria', '10/09/2026', 'Abrió la versión 2 de la matriz', 'ok', 'Cargada'], ['Circular N.º 2', 'Modificatoria', '15/09/2026', 'Abrió la versión 3 de la matriz', 'ok', 'Cargada'], ['Respuesta a la consulta N.º 1', 'Aclaratoria', '08/09/2026', 'Aclara el envase del R5', 'ok', 'Cargada'], ['Respuesta a la consulta N.º 2', 'Aclaratoria', '06/10/2026', 'Novedad del Portal', 'nd', 'Sin aprobar']];
    return `
    ${secH('Ofertas', 'Ofertas, circulares y aclaraciones', 'Las ofertas salen del acta de apertura del Portal; sus documentos los sube la Comisión.', `<button class="btn">${I.portal}Agregar oferta desde el Portal</button><button class="btn prim">${I.up}Subir archivos de una oferta</button>`)}
    <div class="g3">${offers}</div>
    ${card('Circulares y aclaraciones', '4 publicadas en el Portal', `<table class="tbl"><thead><tr><th>Documento</th><th>Tipo</th><th>Fecha</th><th>Efecto</th><th>Estado</th></tr></thead><tbody>${circ.map(([a, b, c, d, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td>${b}</td><td class="mono">${c}</td><td style="color:var(--muted)">${d}</td><td><span class="chip ${s}">${e}</span></td></tr>`).join('')}</tbody></table>`, '', 4)}`;
  }

  function pageEval() {
    return `
    ${secH('Evaluación y dictamen', 'Propuesta del sistema por oferta y requisito', 'El sistema recomienda con su fundamento; la Comisión decide. Lo que no tiene fundamento queda como no determinado.', `<button class="btn">${I.out}Exportar</button><button class="btn prim">${I.portal}Tomar el dictamen del Portal</button>`)}
    <div class="callout rise" style="--i:1"><span class="ic">${I.read}</span><div><div class="t">Informe técnico IT-07/2026 del área requirente</div><div class="d">El sistema lo está leyendo: página 9 de 16.</div><div class="bar"><i style="--p:56%"></i></div></div><button class="btn sm">Ver lo leído</button></div>
    <div class="g2 even">
      ${card('Resultado por oferta', '23 requisitos · versión 3 de la matriz', charts.res[C.res](), '', 2)}
      ${card('Orden económico', 'Total cotizado por oferta, de menor a mayor', charts.eco[C.eco](), '', 3)}
    </div>
    <div class="g2 even">
      ${card('Descartes propuestos', '2 · la Comisión decide cada uno', `
        <div class="q"><div class="qh"><p><b>Oferta 3 · Mascotas del Litoral S.A.</b><br>Garantía de mantenimiento menor al 5 % exigido.</p>${ico('no')}</div>
        <div class="fund"><b>Pliego, art. 6.1:</b> «garantía de mantenimiento del 5 % del monto de la oferta». <b>Oferta:</b> póliza por ${money(659400)}, el 4,0 % de ${money(16485000)}.</div>
        <div class="actions" style="margin-top:10px"><button class="btn sm">Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>
        <div class="q"><div class="qh"><p><b>Oferta 2 · Agroalimentos Río Seco S.R.L.</b><br>Renglón 6 sin registro del producto ante SENASA.</p>${ico('no')}</div>
        <div class="fund"><b>Anexo I, ítem 6:</b> «producto con registro vigente». <b>Oferta:</b> ficha del R6 sin número de registro; se leyeron los 7 documentos y ninguno lo informa.</div>
        <div class="actions" style="margin-top:10px"><button class="btn sm">Aceptar el descarte</button><button class="btn sm">Pedir subsanación</button></div></div>`, '', 4)}
      ${card('Preguntas a la Comisión', '2 sin responder', `
        <div class="q"><div class="qh"><p>Oferta 2: el poder no menciona la facultad de cotizar. ¿Se pide subsanación?</p><span class="chip nd">Sin responder</span></div><div class="actions"><button class="btn sm prim">Responder</button></div></div>
        <div class="q"><div class="qh"><p>Oferta 3: la ficha del R3 informa 10 meses de vencimiento. ¿Se acepta?</p><span class="chip nd">Sin responder</span></div><div class="actions"><button class="btn sm prim">Responder</button></div></div>
        <div class="q"><div class="qh"><p>Oferta 1: ¿la póliza cubre los 60 días de mantenimiento?</p><span class="chip ok">Respondida</span></div><div class="fund"><b>evaluador de muestra, 14/10/2026:</b> «Sí, la vigencia es de 90 días».</div></div>`, '', 5)}
    </div>
    ${card('Dictamen', 'El Portal publicó uno el 06/10/2026 que todavía no se aprobó', `<div class="actions"><button class="btn js-aprobar">${I.check}Aprobar la carga</button><button class="btn">${I.gavel}Preparar el dictamen de la Comisión</button></div>`, '<span class="chip nd">Pendiente</span>', 6)}`;
  }

  function pageNorm() {
    const norms = [['Disposición AFIP 247/2022', 'Régimen de contrataciones vigente', 'v. 2026-03', 'ok', 'Validada'], ['Disposición AFIP 297/03', 'Régimen anterior: no aplica, autorizado en 2026', 'v. 2019-11', 'pe', 'No aplica'], ['Decreto Delegado 1023/2001', 'Marco nacional de contrataciones', 'v. 2024-07', 'ok', 'Validada'], ['Decreto 202/2017', 'Declaración jurada de intereses', 'v. 2017-03', 'ok', 'Validada'], ['Norma complementaria de ejemplo N.º 1', 'Ficticia, cargada para pruebas', 'v. 1', 'nd', 'Sin validar']];
    const cites = [['Disp. 247/2022', 9], ['Dto. 1023/2001', 2], ['Dto. 202/2017', 2], ['Ejemplo N.º 1', 1], ['Montos 2026', 1]];
    return `
    ${secH('Normativas', 'Normas que rigen este procedimiento', 'El régimen sale de la fecha de autorización (14/08/2026): rige la Disposición 247/2022.', `<button class="btn prim">${I.up}Subir archivo</button>`)}
    ${card('Consulta de normativa', 'Las respuestas citan norma, artículo y versión', `<form class="search" onsubmit="return false"><input id="q" placeholder="Escriba una pregunta sobre la normativa" aria-label="Pregunta sobre la normativa"><button class="btn prim js-consultar">Consultar</button></form>
      <div class="examples">${['¿Qué plazo de mantenimiento de oferta fija el régimen?', '¿Cuándo corresponde pedir subsanación?', '¿Qué garantía se exige para impugnar?'].map(e => `<button class="fchip js-ej">${e}</button>`).join('')}</div>
      <div class="answer"><b>Respuesta de muestra.</b> El texto real sale de la normativa cargada y cita artículo y versión. Si no hay fundamento recuperable, el resultado es «no determinado».</div>`, '', 1)}
    <div class="g2">
      ${card('Normas cargadas', '4 validadas · 1 sin validar · 1 falta', `<table class="tbl"><thead><tr><th>Norma</th><th>Qué regula</th><th>Versión</th><th>Estado</th></tr></thead><tbody>${norms.map(([a, b, c, s, e]) => `<tr><td><b style="font-weight:600">${a}</b></td><td style="color:var(--muted)">${b}</td><td class="mono" style="white-space:nowrap">${c}</td><td><span class="chip ${s}">${e}</span></td></tr>`).join('')}<tr><td><b style="font-weight:600">Norma de montos 2026</b></td><td style="color:var(--muted)">Ficticia, citada por el pliego</td><td class="mono">—</td><td><button class="btn sm">${I.up}Subir</button></td></tr></tbody></table>`, '', 2)}
      ${card('Citas del pliego a normas', '15 citas · 14 encontradas', cites.map(([n, v], k) => `<div class="crow"><span class="n">${n}</span><span class="v">${v} ${v === 1 ? 'cita' : 'citas'}</span><div class="bar"><i style="--p:${v / 9 * 100}%;--i:${k};--bar-c:${n === 'Montos 2026' ? 'var(--nd)' : 'var(--brand)'}"></i></div></div>`).join('') + '<p class="note"><b>Montos 2026</b> está citada y no está cargada: sin ella, lo que depende de montos queda como no determinado.</p>', '', 3)}
    </div>`;
  }

  // ---------- Armado ----------
  const MARKS = {
    placa: '<span class="a">EVALU</span><span class="b">ON</span>',
    pill: '<span class="a">EVALU</span><span class="b">ON</span>',
    dot: '<span class="a">evalu</span><i></i><span class="b">on</span>',
    sq: '<span class="iso">E</span><span class="w">EVALUON</span>',
    slash: '<span class="a">EVALU</span><span class="s"></span><span class="b">ON</span>',
  };
  const L = cfg.layout;
  const tabHTML = TABS.map((t, i) => {
    const badge = t.badge ? `<span class="badge" data-badge="${i}">${t.badge}</span>` : '';
    let inner;
    if (L === 'numbered') inner = `<span class="row1"><span class="big">${String(i + 1).padStart(2, '0')}</span>${badge}</span><span>${t.l}</span><span class="tm">${t.meta}</span><span class="bar"><i style="--p:${t.pct}%;--bar-c:${t.pct === 100 ? 'var(--ok)' : 'var(--ind,var(--brand))'}"></i></span>`;
    else if (L === 'rail') inner = `${tabIcon(i)}<span class="tlab"><span>${t.l}</span><span class="tm">${t.meta}</span></span>${badge}`;
    else if (L === 'dock') inner = `<span>${t.l}</span>${badge}`;
    else inner = `${cfg.tabIcons ? tabIcon(i) : ''}<span>${t.l}</span>${badge}`;
    return `<button class="tab" role="tab" id="tab-${t.k}" aria-controls="pg-${t.k}" aria-selected="false" tabindex="-1" data-i="${i}">${inner}</button>`;
  }).join('');
  const nav = `<nav class="tabs" role="tablist" aria-label="Secciones del procedimiento"><span class="ind" aria-hidden="true"></span>${tabHTML}</nav>`;
  const header = `<header class="top"><div class="top-in">
      <a class="mark mark-${cfg.mark}" href="#" aria-label="EVALUON">${MARKS[cfg.mark]}</a>
      ${L === 'dock' ? nav : ''}
      <button class="proc" aria-label="Cambiar de procedimiento"><span class="pt"><small>Procedimiento</small><span class="t">CD 99/2026 · Alimento balanceado para perros</span></span>${I.chev}</button>
      <span class="spacer"></span>
      <span class="user"><b>evaluador de muestra</b><small>Comisión Evaluadora</small></span><span class="avatar" aria-hidden="true">EM</span>
      <button class="btn-salir">Salir</button>
    </div></header>`;
  const pages = [pageProc, pagePliego, pageOfertas, pageEval, pageNorm].map((f, i) => `<section class="page" role="tabpanel" id="pg-${TABS[i].k}" aria-labelledby="tab-${TABS[i].k}">${f()}</section>`).join('');
  const sheetLayouts = ['folder', 'ribbon'];
  const stage = `<main class="stage-wrap"><div class="stage ${sheetLayouts.includes(L) ? 'sheet' : ''}">${pages}</div></main>`;
  let bodyInner;
  if (L === 'dock') bodyInner = stage;
  else if (L === 'rail') bodyInner = `<aside class="tabs-wrap"><div class="rail-h">Secciones</div>${nav}<div class="rail-foot">Avance del procedimiento · 76 %<div class="bar"><i style="--p:76%"></i></div></div></aside>${stage}`;
  else if (L === 'ribbon') bodyInner = `${stage}<aside class="tabs-wrap">${nav}</aside>`;
  else bodyInner = `<div class="tabs-wrap">${nav}</div>${stage}`;
  document.body.innerHTML = `<div class="app l-${L} noanim">${header}<div class="body">${bodyInner}</div></div><div class="toast" role="status" aria-live="polite"></div>`;
  const app = $('.app');

  // ---------- Pestañas e indicador ----------
  const tabs = $$('.tab');
  const pgs = $$('.page');
  const ind = $('.ind');
  const stageEl = $('.stage');
  const vertical = () => (L === 'rail') && innerWidth > 1060;
  function placeInd(i) {
    const t = tabs[i];
    if (!t || !ind) return;
    if (vertical()) {
      ind.style.width = t.offsetWidth + 'px';
      ind.style.height = t.offsetHeight + 'px';
      ind.style.transform = `translate(${t.offsetLeft}px, ${t.offsetTop}px)`;
    } else if (L === 'top' || L === 'numbered') {
      ind.style.width = t.offsetWidth + 'px';
      ind.style.height = '';
      ind.style.transform = `translateX(${t.offsetLeft}px)`;
    } else {
      ind.style.width = t.offsetWidth + 'px';
      ind.style.height = t.offsetHeight + 'px';
      ind.style.transform = `translate(${t.offsetLeft}px, ${t.offsetTop}px)`;
    }
  }
  function setTabs(i) {
    tabs.forEach((t, k) => { t.setAttribute('aria-selected', k === i); t.tabIndex = k === i ? 0 : -1; });
    placeInd(i);
  }
  function fillRings(page) {
    $$('circle.v', page).forEach(c => { c.style.strokeDashoffset = c.dataset.to; });
  }

  // ---------- Transiciones de página ----------
  const E = { out: 'cubic-bezier(.23,1,.32,1)', io: 'cubic-bezier(.77,0,.175,1)', drawer: 'cubic-bezier(.32,.72,0,1)', turn: 'cubic-bezier(.62,.04,.3,1)', in: 'cubic-bezier(.55,.06,.68,.19)' };
  const shade = (el, from, to, dur, bg, delay = 0, ease = E.turn) => {
    const s = document.createElement('div'); s.className = 'shade'; s.style.background = bg; el.appendChild(s);
    return s.animate([{ opacity: from }, { opacity: to }], { duration: dur, delay, easing: ease, fill: 'both' });
  };
  const SH = 'linear-gradient(90deg, rgba(0,0,0,.10), rgba(0,0,0,.42))';
  const SH_UNDER = 'linear-gradient(90deg, rgba(0,0,0,.30), rgba(0,0,0,.06) 70%)';
  const TR = {
    // Hoja que gira sobre el lomo izquierdo, como un libro
    turn(out, inn, dir, o = {}) {
      const d = o.d || 680, ang = o.ang || 90;
      if (dir > 0) {
        out.style.zIndex = 3; inn.style.zIndex = 1; out.style.transformOrigin = '0 50%';
        return { show: d * .55, anims: [
          out.animate([{ transform: 'rotateY(0deg)', boxShadow: '0 0 0 rgba(0,0,0,0)' }, { transform: `rotateY(-${ang * .5}deg)`, boxShadow: '-24px 0 50px rgba(0,0,0,.22)', offset: .5 }, { transform: `rotateY(-${ang}deg)`, boxShadow: '-10px 0 30px rgba(0,0,0,.1)' }], { duration: d, easing: E.turn, fill: 'both' }),
          shade(out, 0, .9, d, SH), shade(inn, 1, 0, d, SH_UNDER)] };
      }
      inn.style.zIndex = 3; out.style.zIndex = 1; inn.style.transformOrigin = '0 50%';
      return { show: d * .5, anims: [
        inn.animate([{ transform: `rotateY(-${ang}deg)` }, { transform: 'rotateY(0deg)' }], { duration: d, easing: E.turn, fill: 'both' }),
        shade(inn, .9, 0, d, SH), shade(out, 0, 1, d, SH_UNDER)] };
    },
    turnsoft(out, inn, dir) { return TR.turn(out, inn, dir, { d: 540, ang: 90 }); },
    // Esquina que se levanta y se dobla
    curl(out, inn, dir) {
      const d = 720, top = dir > 0 ? out : inn, under = dir > 0 ? inn : out;
      top.style.zIndex = 3; under.style.zIndex = 1;
      const h = Math.max(out.offsetHeight, inn.offsetHeight);
      const slope = Math.min(46, 46 * 900 / Math.max(h, 400));
      const fr = t => `polygon(0 0, ${t + slope}% 0, ${t}% 100%, 0 100%)`;
      const flapFr = (t, w) => `polygon(${t + slope}% 0, ${t + slope + w}% 0, ${t + w * .55}% 100%, ${t}% 100%)`;
      const steps = [100, 70, 30, -slope - 2];
      const ws = [0, 14, 12, 0];
      const k = dir > 0 ? steps : [...steps].reverse();
      const kw = dir > 0 ? ws : [...ws].reverse();
      const flap = document.createElement('div');
      flap.className = 'flap'; flap.style.height = h + 'px';
      flap.style.background = 'linear-gradient(100deg, var(--surface-2) 0%, var(--surface) 45%, color-mix(in srgb, var(--surface-2) 70%, #000 12%) 100%)';
      flap.style.filter = 'drop-shadow(-6px 4px 10px rgba(0,0,0,.25))';
      stageEl.appendChild(flap);
      const opt = { duration: d, easing: dir > 0 ? E.io : E.io, fill: 'both' };
      return { show: dir > 0 ? d * .45 : d * .3, extra: [flap], anims: [
        top.animate(k.map(t => ({ clipPath: fr(t) })), opt),
        flap.animate(k.map((t, j) => ({ clipPath: flapFr(t, kw[j]) })), opt),
        shade(under, dir > 0 ? .8 : 0, dir > 0 ? 0 : .8, d, SH_UNDER, 0, E.io)] };
    },
    // Hoja que se desliza sobre la anterior (pila)
    stack(out, inn, dir) {
      const d = 520; stageEl.classList.add('clip');
      if (dir > 0) {
        inn.style.zIndex = 3; out.style.zIndex = 1;
        return { show: d * .35, anims: [
          inn.animate([{ transform: 'translateX(100%)', boxShadow: '-20px 0 40px rgba(0,0,0,.18)' }, { transform: 'translateX(0)', boxShadow: '-20px 0 40px rgba(0,0,0,0)' }], { duration: d, easing: E.drawer, fill: 'both' }),
          out.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-22%)' }], { duration: d, easing: E.drawer, fill: 'both' }),
          shade(out, 0, .5, d, 'rgba(0,0,0,.35)', 0, E.drawer)] };
      }
      out.style.zIndex = 3; inn.style.zIndex = 1;
      return { show: d * .3, anims: [
        out.animate([{ transform: 'translateX(0)', boxShadow: '-20px 0 40px rgba(0,0,0,.18)' }, { transform: 'translateX(100%)', boxShadow: '-20px 0 40px rgba(0,0,0,0)' }], { duration: d, easing: E.drawer, fill: 'both' }),
        inn.animate([{ transform: 'translateX(-22%)' }, { transform: 'translateX(0)' }], { duration: d, easing: E.drawer, fill: 'both' }),
        shade(inn, .5, 0, d, 'rgba(0,0,0,.35)', 0, E.drawer)] };
    },
    // Tarjeta que gira sobre su eje
    flip(out, inn, dir) {
      const a = 200, b = 300;
      out.style.transformOrigin = inn.style.transformOrigin = '50% 30%';
      out.style.zIndex = 2; inn.style.zIndex = 3;
      return { show: a, anims: [
        out.animate([{ transform: 'rotateY(0)', opacity: 1 }, { transform: `rotateY(${-dir * 90}deg)`, opacity: .6 }], { duration: a, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `rotateY(${dir * 90}deg)`, opacity: .6 }, { transform: 'rotateY(0)', opacity: 1 }], { duration: b, delay: a, easing: E.out, fill: 'both' })] };
    },
    // Puerta que se pliega
    fold(out, inn, dir) {
      out.style.transformOrigin = dir > 0 ? '0 50%' : '100% 50%';
      inn.style.transformOrigin = dir > 0 ? '100% 50%' : '0 50%';
      out.style.zIndex = 2; inn.style.zIndex = 3;
      return { show: 120, anims: [
        out.animate([{ transform: 'rotateY(0) translateX(0)', opacity: 1 }, { transform: `rotateY(${dir * 28}deg) translateX(${-dir * 6}%)`, opacity: 0 }], { duration: 300, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `rotateY(${-dir * 22}deg) translateX(${dir * 5}%)`, opacity: 0 }, { transform: 'rotateY(0) translateX(0)', opacity: 1 }], { duration: 460, delay: 90, easing: E.out, fill: 'both' })] };
    },
    // Barrido con cortina
    wipe(out, inn, dir) {
      const d = 560; inn.style.zIndex = 3; out.style.zIndex = 1;
      const from = dir > 0 ? 'inset(0 0 0 100%)' : 'inset(0 100% 0 0)';
      return { show: d * .3, anims: [
        inn.animate([{ clipPath: from, transform: `translateX(${dir * 40}px)` }, { clipPath: 'inset(0 0 0 0)', transform: 'translateX(0)' }], { duration: d, easing: E.io, fill: 'both' }),
        out.animate([{ transform: 'translateX(0)' }, { transform: `translateX(${-dir * 60}px)` }], { duration: d, easing: E.io, fill: 'both' }),
        shade(out, 0, .45, d, 'rgba(0,0,0,.4)', 0, E.io)] };
    },
    // Profundidad: la anterior se aleja, la nueva llega de costado
    depth(out, inn, dir) {
      out.style.zIndex = 1; inn.style.zIndex = 3;
      return { show: 100, anims: [
        out.animate([{ transform: 'scale(1)', opacity: 1, filter: 'blur(0)' }, { transform: 'scale(.95)', opacity: 0, filter: 'blur(2px)' }], { duration: 240, easing: E.in, fill: 'both' }),
        inn.animate([{ transform: `translateX(${dir * 28}px) scale(.99)`, opacity: 0 }, { transform: 'translateX(0) scale(1)', opacity: 1 }], { duration: 420, delay: 80, easing: E.out, fill: 'both' })] };
    },
    shift(out, inn, dir) {
      out.style.zIndex = 1; inn.style.zIndex = 3;
      return { show: 60, anims: [
        out.animate([{ opacity: 1, transform: 'translateX(0)', filter: 'blur(0)' }, { opacity: 0, transform: `translateX(${-dir * 14}px)`, filter: 'blur(3px)' }], { duration: 160, easing: E.in, fill: 'both' }),
        inn.animate([{ opacity: 0, transform: `translateX(${dir * 14}px)`, filter: 'blur(3px)' }, { opacity: 1, transform: 'translateX(0)', filter: 'blur(0)' }], { duration: 300, delay: 60, easing: E.out, fill: 'both' })] };
    },
    fade(out, inn) {
      out.style.zIndex = 1; inn.style.zIndex = 3;
      return { show: 0, anims: [inn.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160, easing: 'ease-out', fill: 'both' })] };
    },
  };
  const TR_NAMES = { turn: 'Hoja que gira sobre el lomo', turnsoft: 'Hoja que gira, más ágil', curl: 'Esquina que se dobla', stack: 'Hoja que se desliza encima', flip: 'Tarjeta que gira', fold: 'Puerta que se pliega', wipe: 'Cortina que barre', depth: 'Profundidad', shift: 'Desplazamiento sutil' };
  const TR_ORDER = Object.keys(TR_NAMES);
  let trName = params.get('tr') && TR[params.get('tr')] ? params.get('tr') : cfg.transition;

  let cur = -1, running = null, showTimer = 0;
  function finishRunning() {
    if (!running) return;
    clearTimeout(showTimer);
    const r = running; running = null;
    r.anims.forEach(a => { try { a.cancel(); } catch (e) { /* nada */ } });
    r.cleanup();
  }
  function go(to, opts = {}) {
    if (to === cur || to < 0 || to >= pgs.length) return;
    finishRunning();
    const from = cur; cur = to;
    setTabs(to);
    const inn = pgs[to];
    if (!opts.hash) history.replaceState(null, '', '#' + TABS[to].k);
    if (from < 0 || opts.instant) {
      pgs.forEach(p => p.classList.remove('active', 'shown', 'rising'));
      inn.classList.add('active', 'shown', 'rising'); fillRings(inn);
      return;
    }
    const out = pgs[from], dir = to > from ? 1 : -1;
    // Si el usuario bajó en la página, sube al comienzo del escenario antes de dar vuelta la hoja
    const sticky = $('.tabs-wrap') && getComputedStyle($('.tabs-wrap')).position === 'sticky' && !vertical() ? $('.tabs-wrap').offsetHeight : 0;
    const top = stageEl.getBoundingClientRect().top + scrollY - sticky - 12;
    if (scrollY > top) scrollTo({ top, behavior: 'instant' });
    out.classList.add('leaving', 'moving'); inn.classList.add('moving');
    inn.classList.remove('shown', 'rising'); inn.classList.add('active');
    $$('circle.v', inn).forEach(c => { c.style.strokeDashoffset = ''; });
    // En las transiciones que destapan la hoja de abajo, esa hoja ya se ve entera;
    // en las demás, su contenido entra escalonado.
    if (!REDUCE && !['turn', 'turnsoft', 'curl', 'stack'].includes(trName)) inn.classList.add('rising');
    const fn = REDUCE ? TR.fade : TR[trName];
    const r = fn(out, inn, dir);
    const extra = r.extra || [];
    running = {
      anims: r.anims,
      cleanup() {
        out.classList.remove('active', 'leaving', 'shown', 'rising');
        [out, inn].forEach(p => { p.classList.remove('moving'); p.style.zIndex = ''; p.style.transformOrigin = ''; $$(':scope > .shade', p).forEach(s => s.remove()); });
        extra.forEach(x => x.remove());
        stageEl.classList.remove('clip');
        inn.classList.add('shown'); fillRings(inn);
      },
    };
    const mine = running;
    showTimer = setTimeout(() => { inn.classList.add('shown'); requestAnimationFrame(() => fillRings(inn)); }, r.show || 0);
    Promise.all(r.anims.map(a => a.finished)).then(() => {
      if (running !== mine) return;
      running = null;
      r.anims.forEach(a => a.cancel());
      mine.cleanup();
    }).catch(() => { /* cancelada por otra transición */ });
  }

  // ---------- Eventos ----------
  tabs.forEach((t, i) => t.addEventListener('click', () => go(i)));
  $('.tabs').addEventListener('keydown', e => {
    const k = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (k === undefined && e.key !== 'Home' && e.key !== 'End') return;
    e.preventDefault();
    const n = e.key === 'Home' ? 0 : e.key === 'End' ? 4 : (cur + k + 5) % 5;
    go(n); tabs[n].focus();
  });
  document.addEventListener('click', e => {
    const g = e.target.closest('[data-go]');
    if (g) { go(+g.dataset.go); return; }
    const ap = e.target.closest('.js-aprobar');
    if (ap && !ap.classList.contains('done')) {
      ap.classList.add('done'); ap.innerHTML = I.check + 'Carga aprobada';
      const b = $('[data-badge="0"]'); const nv = $('[data-nov]');
      if (b) { const v = Math.max(0, +b.textContent - 1); b.textContent = v; b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop'); if (!v) b.style.visibility = 'hidden'; }
      if (nv && ap.closest('#pg-procedimiento')) nv.textContent = Math.max(0, +nv.textContent - 1);
      return;
    }
    const f = e.target.closest('.fchip[data-f]');
    if (f) {
      const wrap = f.closest('.card');
      $$('.fchip[data-f]', wrap).forEach(x => x.setAttribute('aria-pressed', x === f));
      const want = f.dataset.f;
      $$('tr.r', wrap).forEach(tr => {
        const show = want === 'all' || tr.dataset.s.split(' ').includes(want);
        tr.classList.toggle('hide', !show);
        if (show) { tr.classList.remove('flash'); void tr.offsetWidth; tr.classList.add('flash'); }
      });
      $$('tr.grp', wrap).forEach(g => g.classList.toggle('hide', !$$(`tr.r[data-g="${g.dataset.g}"]:not(.hide)`, wrap).length));
      return;
    }
    const ej = e.target.closest('.js-ej');
    if (ej) { $('#q').value = ej.textContent; $('.answer').classList.remove('on'); void $('.answer').offsetWidth; $('.answer').classList.add('on'); return; }
    if (e.target.closest('.js-consultar')) { const a = $('.answer'); a.classList.remove('on'); void a.offsetWidth; a.classList.add('on'); }
  });
  // Atajos ocultos para comparar propuestas: [ y ] cambian de propuesta, T cambia la transición, G vuelve a la galería
  const toast = $('.toast'); let toastT = 0;
  const say = m => { toast.textContent = m; toast.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toast.classList.remove('on'), 1600); };
  document.addEventListener('keydown', e => {
    const el = e.target instanceof Element ? e.target : null;
    if ((el && el.closest('input,textarea')) || e.ctrlKey || e.metaKey || e.altKey) return;
    const hash = location.hash;
    if (e.key === ']') location.href = `d${String(N % ALL.length + 1).padStart(2, '0')}.html${hash}`;
    else if (e.key === '[') location.href = `d${String((N + ALL.length - 2) % ALL.length + 1).padStart(2, '0')}.html${hash}`;
    else if (e.key === 'g' || e.key === 'G') location.href = 'index.html';
    else if (e.key === 't' || e.key === 'T') { trName = TR_ORDER[(TR_ORDER.indexOf(trName) + 1) % TR_ORDER.length]; say('Transición: ' + TR_NAMES[trName]); }
  });
  addEventListener('resize', () => placeInd(cur));
  addEventListener('hashchange', () => { const i = TABS.findIndex(t => '#' + t.k === location.hash); if (i >= 0) go(i, { hash: true }); });

  // ---------- Inicio ----------
  const start = Math.max(0, TABS.findIndex(t => '#' + t.k === location.hash));
  go(start, { instant: true });
  const settle = () => { placeInd(cur); requestAnimationFrame(() => app.classList.remove('noanim')); };
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(settle); else settle();
  setTimeout(() => placeInd(cur), 400);

  // ---------- Control de contraste (consola) ----------
  const hex = h => { const m = /^#([0-9a-f]{6})$/i.exec((h || '').trim()); return m ? [0, 2, 4].map(i => parseInt(m[1].substr(i, 2), 16) / 255) : null; };
  const lum = c => { const [r, g, b] = c.map(v => v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4); return .2126 * r + .7152 * g + .0722 * b; };
  const ratio = (a, b) => { const x = hex(a), y = hex(b); if (!x || !y) return null; const l1 = lum(x), l2 = lum(y); return (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05); };
  const t = cfg.t;
  const pairs = [['ink', 'bg', 4.5], ['ink', 'surface', 4.5], ['muted', 'surface', 4.5], ['muted', 'bg', 4.5], ['brand-ink', 'brand', 4.5], ['accent-ink', 'accent', 4.5], ['header-ink', 'header-bg', 4.5], ['header-muted', 'header-bg', 4.5], ['link', 'surface', 4.5], ['ok', 'surface', 3], ['no', 'surface', 3], ['nd', 'surface', 3], ['pe', 'surface', 3], ['st-sym', 'ok', 3], ['st-sym', 'no', 3], ['st-sym', 'nd', 3], ['st-sym', 'pe', 3]];
  const report = pairs.map(([a, b, min]) => { const r = ratio(t[a], t[b]); return r === null ? null : { par: `${a} / ${b}`, razon: +r.toFixed(2), minimo: min, cumple: r >= min }; }).filter(Boolean);
  window.CONTRASTE = report;
  const bad = report.filter(r => !r.cumple);
  if (bad.length) console.warn('Contraste insuficiente en la propuesta ' + N, bad); else console.info('Contraste OK en la propuesta ' + N);
})();
