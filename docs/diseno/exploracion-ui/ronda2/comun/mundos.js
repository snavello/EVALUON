/* Ronda 2: ocho mundos tomados de lo que la Comisión Evaluadora conoce de memoria.
   Cada mundo aporta solo letra, paleta, densidad y un gesto propio; la navegación,
   los controles y la organización de la pantalla son los de una aplicación de trabajo.
   Escena de uso: oficina con luz de día, jornadas largas, dictámenes que se imprimen;
   por eso todos son claros. */
const MARK = (on = 'ON') => `<span class="iso">E</span><span>EVALU<span class="on">${on}</span></span>`;

// Guilloche: líneas de interferencia como en el papel de seguridad (dibujado, sin imágenes).
function guilloche(color) {
  const w = 1200, h = 64; let paths = '';
  for (let k = 0; k < 14; k++) {
    let d = '';
    for (let x = 0; x <= w; x += 6) {
      const y = h / 2 + Math.sin(x / 38 + k * .45) * (12 + k * .9) * Math.cos(x / 210 - k * .2) + Math.sin(x / 9 + k) * 1.2;
      d += (x ? 'L' : 'M') + x + ' ' + y.toFixed(1);
    }
    paths += `<path d="${d}" fill="none" stroke="${color}" stroke-width=".6" stroke-opacity="${(.22 + (k % 3) * .06).toFixed(2)}"/>`;
  }
  return `url("data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>${paths}</svg>`)}")`;
}

window.MUNDOS = [
  {
    id: 'continuo', name: 'Papel continuo',
    world: 'Los listados de computadora en papel continuo pautado en verde, con sus bordes perforados: así salían los listados de compras de la administración.',
    move: 'Las filas de todas las tablas van en franjas verdes de a dos, como el papel pautado, y el escenario tiene los márgenes perforados. Al cambiar de pestaña, la hoja nueva sube como en la impresora.',
    risk: 'Las franjas y los márgenes perforados pueden leerse como nostalgia si se exageran; acá quedan en el fondo de las filas y en el margen.',
    fontNames: 'Public Sans · Martian Mono (solo cifras)', layout: 'top', sig: 'bands', transition: 'feed',
    charts: { res: 'stacked', eco: 'hbar', time: 'line' }, mark: MARK(),
    fonts: 'family=Public+Sans:wght@400;500;600;700&family=Martian+Mono:wght@400;500;600',
    t: { ground: '#EEF2EC', surface: '#FFFFFF', sunken: '#E7EFE4', line: '#CCD8CA', 'line-soft': '#E1E9DE', ink: '#142318', 'ink-2': '#4A5B4E', brand: '#1F4D33', 'brand-hover': '#27603F', 'on-brand': '#FFFFFF', accent: '#A8321F', link: '#1F5E3B',
      shell: '#1F4D33', 'on-shell': '#F1F6EF', 'on-shell-2': '#B9CDBE', 'shell-line': 'rgba(255,255,255,.18)', 'shell-chip': 'rgba(255,255,255,.06)', band: '#E6F1E2', ind: '#1F4D33', 'av-bg': '#E4F0E0', 'av-ink': '#1F4D33',
      'mark-bg': '#F1F6EF', 'mark-ink': '#1F4D33', 'mark-on': '#A9DCB3', 'f-ui': "'Public Sans', sans-serif", 'f-data': "'Martian Mono', monospace", sel: 'rgba(31,77,51,.18)' },
    css: `.tbl tbody tr:nth-child(4n+1) td,.tbl tbody tr:nth-child(4n+2) td,.mtx tr.r.band td{background:var(--band)}
      .data,.big{font-size:.9em;letter-spacing:-.02em}
      .stage-wrap{position:relative}
      .stage-wrap::before,.stage-wrap::after{content:"";position:absolute;top:1.75rem;bottom:2.5rem;width:16px;background:radial-gradient(circle,var(--ground) 0 3.4px,transparent 4px) center 6px/16px 21px repeat-y,var(--surface);border:1px dashed var(--line)}
      .stage-wrap::before{left:2px;border-width:0 1px 0 0}.stage-wrap::after{right:2px;border-width:0 0 0 1px}
      @media (max-width:700px){.stage-wrap::before,.stage-wrap::after{display:none}}`,
  },
  {
    id: 'expediente', name: 'Expediente foliado',
    world: 'La carátula de cartulina manila del expediente y su foliado: cada hoja numerada a mano con el sello de la mesa de entradas, y las citas «a fs. 7».',
    move: 'Cada pestaña lleva su folio («fs. 7–33») y los fundamentos citan la foja donde está el texto, como se cita en un expediente. Al cambiar de pestaña, la hoja gira sobre el lomo.',
    risk: 'Los folios son de muestra: en el sistema real tendrían que salir de la foliatura del expediente electrónico, o no mostrarse.',
    fontNames: 'Libre Franklin · Courier Prime (folios y números)', layout: 'rail', sig: 'folio', transition: 'turn',
    charts: { res: 'waffle', eco: 'delta', time: 'line' }, mark: MARK(),
    fonts: 'family=Libre+Franklin:wght@400;500;600;700&family=Courier+Prime:wght@400;700',
    t: { ground: '#F3F4F6', surface: '#FFFFFF', sunken: '#EEF0F3', line: '#D9DCE2', 'line-soft': '#E7E9ED', ink: '#1A1E26', 'ink-2': '#525967', brand: '#22365F', 'brand-hover': '#2B4475', 'on-brand': '#FFFFFF', accent: '#A3242C', link: '#22508F',
      shell: '#FFFFFF', 'rail-bg': '#E6D3A3', 'rail-line': '#CDB57E', 'rail-ink': '#4A3818', 'rail-on': '#2A1D08', 'rail-sel': '#F4E8C8', 'rail-muted': '#5E4A22',
      'mark-bg': '#E6D3A3', 'mark-ink': '#2A1D08', 'mark-on': '#A3242C', 'f-ui': "'Libre Franklin', sans-serif", 'f-data': "'Courier Prime', monospace", 'count-bg': '#A3242C', 'count-ink': '#FFFFFF', sel: 'rgba(230,211,163,.6)' },
    css: `.ph{padding-top:2.25rem}.data,.big{font-weight:700;letter-spacing:-.01em}
      .mark .iso{border-radius:2px 8px 2px 2px;box-shadow:inset -3px 0 0 #CDB57E}`,
  },
  {
    id: 'sello', name: 'Sello y tampón',
    world: 'El sello de goma, el tampón de tinta violeta y el fechador rojo con los que una oficina deja constancia de que algo se recibió, se aprobó o se descartó.',
    move: 'Cuando la Comisión aprueba una carga o acepta un descarte, el botón se vuelve una impresión de sello con la fecha y las iniciales. «Validada» y «Leído» también aparecen sellados. Al cambiar de pestaña, la hoja se despega por la esquina.',
    risk: 'El sello solo marca decisiones de una persona; si se usara para estados del sistema perdería sentido (P3: decide la Comisión).',
    fontNames: 'Geist · Geist Mono (solo cifras)', layout: 'top', sig: 'stamp', transition: 'curl',
    charts: { res: 'stacked', eco: 'lollipop', time: 'line' }, mark: MARK(),
    fonts: 'family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600',
    t: { ground: '#F5F4F8', surface: '#FFFFFF', sunken: '#EFEDF4', line: '#DEDAE8', 'line-soft': '#EAE7F0', ink: '#1B1924', 'ink-2': '#565266', brand: '#4A3790', 'brand-hover': '#57439F', 'on-brand': '#FFFFFF', accent: '#C0263A', link: '#4A3790',
      shell: '#4A3790', 'on-shell': '#F4F1FB', 'on-shell-2': '#D2CAEE', 'shell-line': 'rgba(255,255,255,.2)', 'shell-chip': 'rgba(255,255,255,.07)', ind: '#4A3790', 'av-bg': '#F4F1FB', 'av-ink': '#4A3790',
      'mark-on': '#FFC9D0', 'f-ui': "'Geist', sans-serif", 'f-data': "'Geist Mono', monospace", sel: 'rgba(74,55,144,.18)' },
    css: `.mark .iso{background:transparent;color:var(--on-shell);border:2px solid currentColor;outline:1px solid currentColor;outline-offset:2px;border-radius:50%;width:1.5rem;height:1.5rem;font-size:.8125rem;margin-right:.25rem}
      .stamp{font-family:'Geist',sans-serif}`,
  },
  {
    id: 'subte', name: 'Línea de subte',
    world: 'La señalética del subte porteño: carteles azul noche con letra blanca, el amarillo de «usted está aquí» y el plano de la línea con sus estaciones.',
    move: 'Las cinco pestañas son estaciones de una misma línea y el cronograma se dibuja como el plano de la línea, con la estación de hoy en amarillo. Al cambiar de pestaña, la pantalla entra por la vía.',
    risk: 'Las pestañas no tienen orden obligatorio (decisión del 07/10); la línea muestra dónde está uno, no un recorrido forzado.',
    fontNames: 'Host Grotesk (con cifras tabulares)', layout: 'top', sig: 'line', transition: 'slide',
    charts: { res: 'table', eco: 'lollipop', time: 'stations' }, mark: '<span class="iso">E</span><span>EVALUON</span>',
    fonts: 'family=Host+Grotesk:wght@400;500;600;700',
    t: { ground: '#F2F3F5', surface: '#FFFFFF', sunken: '#ECEEF1', line: '#D8DCE2', 'line-soft': '#E6E9ED', ink: '#111722', 'ink-2': '#4A5363', brand: '#14213D', 'brand-hover': '#1E3158', 'on-brand': '#FFFFFF', accent: '#FFCD00', link: '#0E58A8',
      shell: '#14213D', 'on-shell': '#FFFFFF', 'on-shell-2': '#B8C2D6', 'shell-line': 'rgba(255,255,255,.16)', 'shell-chip': 'rgba(255,255,255,.06)', 'nav-bg': '#14213D', 'tab-ink': '#B8C2D6', 'tab-on': '#FFFFFF',
      now: '#FFCD00', tl: '#14213D', 'count-bg': '#FFCD00', 'count-ink': '#111722', 'mark-bg': '#FFCD00', 'mark-ink': '#14213D', 'av-bg': '#FFCD00', 'av-ink': '#14213D',
      'f-ui': "'Host Grotesk', sans-serif", 'f-data': "'Host Grotesk', sans-serif", sel: 'rgba(255,205,0,.4)' },
    css: `.mark .iso{border-radius:50%}
      .nav{border-bottom:0}
      .tabs{gap:0;padding-top:.375rem}
      .tabs::before{content:"";position:absolute;left:calc(1.25rem + .75rem + .4375rem);right:2rem;top:1.125rem;height:4px;background:rgba(255,255,255,.22);border-radius:2px}
      .tab{flex:1;flex-direction:column;align-items:flex-start;gap:.375rem;padding:.4375rem 1.5rem .75rem .75rem}
      .tab:last-child{flex:0 0 auto}
      .tab::before{content:"";width:.875rem;height:.875rem;border-radius:50%;background:#14213D;border:3px solid rgba(255,255,255,.55);position:relative;z-index:1;transition:background-color .2s,border-color .2s,transform .2s var(--e-out)}
      .tab.past::before{border-color:#fff}
      .tab[aria-selected="true"]::before{background:#FFCD00;border-color:#FFCD00;transform:scale(1.3)}
      .tab .count{position:absolute;left:2rem;top:.3125rem}
      .ind{display:none}
      .metro li.now .dot{border-color:#14213D}`,
  },
  {
    id: 'formulario', name: 'Formulario preimpreso',
    world: 'Los formularios preimpresos de la AFIP y del Estado: casilleros con su leyenda chica en la esquina, rubros numerados y el fondo de color de cada copia.',
    move: 'Los datos del procedimiento, las garantías y la comparación de ofertas van en casilleros con su leyenda, como un formulario. Al cambiar de pestaña, la hoja se levanta como en un block.',
    risk: 'Los casilleros ordenan los datos, pero no se puede escribir en ellos: los datos salen del Portal o de un archivo (decisión del 07/10). Tienen que leerse como datos, nunca como un campo vacío.',
    fontNames: 'Source Sans 3 · Source Code Pro (solo cifras)', layout: 'top', sig: 'form', transition: 'flipup',
    charts: { res: 'waffle', eco: 'bullet', time: 'line' }, mark: MARK(),
    fonts: 'family=Source+Sans+3:wght@400;500;600;700&family=Source+Code+Pro:wght@400;500;600',
    t: { ground: '#EEF3F4', surface: '#FFFFFF', sunken: '#E8F1F2', line: '#C9DADD', 'line-soft': '#DCE8EA', ink: '#0F1E22', 'ink-2': '#48595E', brand: '#1D5F6A', 'brand-hover': '#237180', 'on-brand': '#FFFFFF', accent: '#B4232F', link: '#1D5F6A',
      shell: '#DCEBEE', 'on-shell': '#0F1E22', 'on-shell-2': '#3D585E', 'shell-line': '#B6CED3', 'shell-chip': '#EAF3F5', ind: '#1D5F6A', 'th-bg': '#F0F6F7', 'av-bg': '#1D5F6A', 'av-ink': '#FFFFFF',
      'mark-bg': '#1D5F6A', 'mark-on': '#B4232F', 'f-ui': "'Source Sans 3', sans-serif", 'f-data': "'Source Code Pro', monospace", 'fs-body': '1rem', sel: 'rgba(29,95,106,.18)' },
    css: `.fields{gap:0;border:1px solid #9FC0C6;border-radius:3px;overflow:hidden;background:#F6FAFB}
      .fields div{border:0;border-right:1px solid #B6CED3;border-bottom:1px solid #B6CED3;padding:.375rem .625rem .5rem!important}
      .fields div:nth-child(2n){border-right:0}
      .fields div:nth-last-child(-n+2){border-bottom:0}
      .fields dt{font-size:.6875rem;text-transform:uppercase;letter-spacing:.06em;color:#2F6B75}
      .fields dd{font-weight:600}
      .cmp td,.cmp th{border:1px solid #DCE8EA}
      .cmp tbody th{background:#F0F6F7;text-transform:uppercase;font-size:.6875rem;letter-spacing:.05em;color:#2F6B75}`,
  },
  {
    id: 'fichero', name: 'Fichero de oficina',
    world: 'El fichero metálico con sus fichas de cartulina, la línea roja del encabezado de cada ficha y las señales de color que se enganchan arriba para marcar lo pendiente.',
    move: 'Cada pendiente y cada oferta llevan su señal de color enganchada: ámbar si falta algo, verde si está completa. Al cambiar de pestaña, la ficha sale hacia atrás y la siguiente sube del cajón.',
    risk: 'Las señales repiten información que ya dan los íconos; en la matriz no se usan para no duplicar el estado.',
    fontNames: 'Atkinson Hyperlegible Next · Atkinson Hyperlegible Mono', layout: 'top', sig: 'riders', transition: 'drawer',
    charts: { res: 'waffle', eco: 'hbar', time: 'line' }, mark: MARK(),
    fonts: 'family=Atkinson+Hyperlegible+Next:wght@400;500;600;700&family=Atkinson+Hyperlegible+Mono:wght@400;500;600',
    t: { ground: '#DFE5E2', surface: '#FFFFFF', sunken: '#EEF2F0', line: '#C8D2CD', 'line-soft': '#E2E8E5', ink: '#172220', 'ink-2': '#4A5753', brand: '#2E4A42', 'brand-hover': '#375A50', 'on-brand': '#FFFFFF', accent: '#C8333B', link: '#2B5E8C',
      shell: '#2E4A42', 'on-shell': '#EEF3F1', 'on-shell-2': '#B7C8C1', 'shell-line': 'rgba(255,255,255,.16)', 'shell-chip': 'rgba(255,255,255,.06)', 'nav-bg': '#DFE5E2', ind: '#2E4A42', 'av-bg': '#E8B23A', 'av-ink': '#172220',
      'mark-bg': '#EEF3F1', 'mark-ink': '#2E4A42', 'mark-on': '#F2C24E', 'f-ui': "'Atkinson Hyperlegible Next', sans-serif", 'f-data': "'Atkinson Hyperlegible Mono', monospace", sel: 'rgba(232,178,58,.35)' },
    css: `.nav{border-bottom:0;padding-top:.625rem}
      .tabs{gap:.25rem;align-items:flex-end}
      .tab{background:#EEF2F0;border:1px solid #C8D2CD;border-bottom:0;border-radius:8px 8px 0 0;padding:.625rem .875rem .5625rem}
      .tab[aria-selected="true"]{background:#FFFFFF;color:var(--ink)}
      .ind{display:none}
      .blk-h{border-bottom:1.5px solid #D9646A;padding-bottom:.5rem}
      .cmp thead th{position:relative;padding-top:1.25rem}
      .cmp thead .rider{position:absolute;top:0;left:.75rem;width:1.75rem;height:.625rem;border-radius:0 0 2px 2px}
      .tbl .task .rider{margin-right:.5rem}`,
  },
  {
    id: 'seguridad', name: 'Papel de seguridad',
    world: 'El papel de seguridad de los documentos oficiales: fondos de guilloche en tinta verde, filetes finos y la seriedad de lo que no se puede falsificar.',
    move: 'Una banda de guilloche dibujada recorre el encabezado y es lo único ornamental de la pantalla; todo lo demás es sobrio. Al cambiar de pestaña, la hoja gira, más corto.',
    risk: 'El guilloche es decorativo; se justifica solo como firma de marca en el encabezado y nunca dentro del área de trabajo.',
    fontNames: 'Golos Text · Spectral (solo el título del procedimiento)', layout: 'top', sig: 'guilloche', transition: 'turnsoft',
    charts: { res: 'table', eco: 'bullet', time: 'line' }, mark: MARK(),
    fonts: 'family=Golos+Text:wght@400;500;600;700&family=Spectral:wght@600',
    t: { ground: '#F1F5F4', surface: '#FFFFFF', sunken: '#EAF1EF', line: '#D2DEDB', 'line-soft': '#E3EBE9', ink: '#10201F', 'ink-2': '#4A5C5A', brand: '#1D4B48', 'brand-hover': '#24605C', 'on-brand': '#FFFFFF', accent: '#8A2E5C', link: '#1D5C58',
      shell: '#E4EFEC', 'on-shell': '#10201F', 'on-shell-2': '#405653', 'shell-line': '#C3D5D1', 'shell-chip': 'rgba(255,255,255,.6)', ind: '#1D4B48', 'av-bg': '#1D4B48', 'av-ink': '#FFFFFF',
      'mark-bg': '#1D4B48', 'mark-on': '#8A2E5C', 'f-ui': "'Golos Text', sans-serif", 'f-data': "'Golos Text', sans-serif", sel: 'rgba(29,75,72,.16)' },
    css: `#pg-procedimiento h1{font-family:'Spectral',serif;font-weight:600;font-size:2.125rem;letter-spacing:-.01em}`,
    after(body) { const s = body.querySelector('.shell'); s.style.backgroundImage = guilloche('#1D4B48'); s.style.backgroundSize = 'auto 100%'; s.style.backgroundRepeat = 'repeat-x'; s.style.backgroundPosition = 'center'; },
  },
  {
    id: 'canon', name: 'Estándar del Estado',
    world: 'El estándar de la categoría, sin vueltas: el sistema de diseño de los sitios del Estado nacional (barra azul noche, azul de enlace y Encode Sans), como lo usa hoy ARCA.',
    move: 'Ninguno a propósito. Es la puerta de salida: lo conocido, hecho con la terminación de los mejores productos del rubro. Cambia de pestaña con un desplazamiento corto.',
    risk: 'Es la opción más segura y la menos propia: EVALUON se parecería a cualquier trámite del Estado.',
    fontNames: 'Encode Sans (con cifras tabulares)', layout: 'top', sig: 'canon', transition: 'shift',
    charts: { res: 'stacked', eco: 'hbar', time: 'line' }, mark: MARK(),
    fonts: 'family=Encode+Sans:wght@400;500;600;700',
    t: { ground: '#F5F6F7', surface: '#FFFFFF', sunken: '#F0F2F4', line: '#DDE1E5', 'line-soft': '#ECEEF1', ink: '#2B2F33', 'ink-2': '#5A6066', brand: '#0072BB', 'brand-hover': '#0062A3', 'on-brand': '#FFFFFF', accent: '#C2410C', link: '#0068AB',
      shell: '#242C4F', 'on-shell': '#FFFFFF', 'on-shell-2': '#C3C8DA', 'shell-line': 'rgba(255,255,255,.16)', 'shell-chip': 'rgba(255,255,255,.06)', ind: '#0072BB', 'av-bg': '#FFFFFF', 'av-ink': '#242C4F',
      'mark-bg': '#FFFFFF', 'mark-ink': '#242C4F', 'mark-on': '#7CC4F2', 'f-ui': "'Encode Sans', sans-serif", 'f-data': "'Encode Sans', sans-serif" },
  },
];
