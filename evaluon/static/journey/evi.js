/* Evi (feature 020, T-367): abre el panel, pide su contenido al servidor y maneja el recorrido por los siete
   pasos. El texto, los estados y «Qué hacer acá» llegan ya armados desde el servidor (`journey/_evi_contenido.html`);
   acá solo se elige qué paso se ve, se dibujan las uniones y se maneja el teclado. No escribe nada en el servidor:
   un único pedido de lectura (GET) por cada apertura. Sin librerías ni direcciones externas. */
(function () {
  "use strict";
  var boton = document.getElementById("evi-boton");
  var panel = document.getElementById("evi-panel");
  var contenido = document.getElementById("evi-contenido");
  var cerrarBoton = document.getElementById("evi-cerrar");
  if (!boton || !panel || !contenido || !window.fetch) { return; }

  var PAUSA_MS = 4800;
  var S = {abierto: false, pedido: 0, listo: false, sel: null, aqui: [], estados: false,
           jugando: false, pausa: false, rastro: false, visitados: {}, t: null};
  var mapa = null, svg = null, nodos = [], pasos = [], aristas = [];

  function reducido() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function angosto() { return window.matchMedia("(max-width: 760px)").matches; }
  function $(selector) { return contenido.querySelector(selector); }
  function todos(selector) { return Array.prototype.slice.call(contenido.querySelectorAll(selector)); }

  /* ---------- Saludo de la galera: una sola vez al cargar; quieta con menos movimiento ---------- */
  function saludar() {
    if (reducido()) { return; }
    boton.classList.add("saluda");
    setTimeout(function () { boton.classList.remove("saluda"); }, 1100);
  }
  setTimeout(saludar, 700);

  /* ---------- Uniones: curvas con codos redondeados, con la posición real de los nodos ---------- */
  function redondeada(pts, r) {
    var d = "M" + pts[0][0] + " " + pts[0][1];
    for (var i = 1; i < pts.length - 1; i++) {
      var a = pts[i - 1], b = pts[i], c = pts[i + 1];
      var l1 = Math.hypot(b[0] - a[0], b[1] - a[1]), l2 = Math.hypot(c[0] - b[0], c[1] - b[1]);
      var rr = Math.min(r, l1 / 2, l2 / 2);
      d += " L" + (b[0] - (b[0] - a[0]) / l1 * rr) + " " + (b[1] - (b[1] - a[1]) / l1 * rr) +
        " Q" + b[0] + " " + b[1] + " " + (b[0] + (c[0] - b[0]) / l2 * rr) + " " + (b[1] + (c[1] - b[1]) / l2 * rr);
    }
    var u = pts[pts.length - 1];
    return d + " L" + u[0] + " " + u[1];
  }

  function nodo(n) { return mapa.querySelector('.evi-nodo[data-n="' + n + '"]'); }

  function caja(n) {
    var b = nodo(n), l, t, w, h;
    if (angosto()) {
      var c = b.querySelector(".num");
      l = b.offsetLeft + c.offsetLeft; t = b.offsetTop + c.offsetTop; w = c.offsetWidth; h = c.offsetHeight;
      return {l: l, r: l + w, t: t, b: t + h, cx: l + w / 2, cy: t + h / 2};
    }
    l = b.offsetLeft; t = b.offsetTop;
    return {l: l, r: l + b.offsetWidth, t: t, b: t + b.offsetHeight, cx: l + b.offsetWidth / 2, cy: t + 28};
  }

  function trazar() {
    if (!mapa || !svg || !nodo(1) || !nodo(1).offsetWidth) { return; }
    svg.setAttribute("width", mapa.clientWidth);
    svg.setAttribute("height", mapa.clientHeight);
    var desvio = angosto() ? 6 : 10;
    aristas.forEach(function (g) {
      var par = g.dataset.a.split("-"), a = +par[0], b = +par[1];
      var A = caja(a), B = caja(b), pts, dir = [1, 0];
      if (a === 3 && b === 4) {
        var x = (caja(2).r + B.l) / 2;
        pts = [[A.r, A.cy], [x, A.cy], [x, B.cy + desvio], [B.l, B.cy + desvio]];
      } else if (a === 4 && b === 7) {
        var x2 = (A.r + caja(6).l) / 2;
        pts = [[A.r, A.cy + desvio], [x2, A.cy + desvio], [x2, B.cy], [B.l, B.cy]];
      } else if ((a === 4 && b === 5) || (a === 6 && b === 7)) {
        pts = [[A.cx, A.b], [A.cx, B.t]]; dir = [0, 1];
      } else {
        pts = [[A.r, A.cy], [B.l, B.cy]];
      }
      var fin = pts[pts.length - 1], linea = pts.slice();
      linea[linea.length - 1] = [fin[0] - 7 * dir[0], fin[1] - 7 * dir[1]];
      var d = redondeada(linea, 10);
      var bx = fin[0] - 9 * dir[0], by = fin[1] - 9 * dir[1], px = -dir[1] * 5, py = dir[0] * 5;
      var punta = "M" + fin[0] + " " + fin[1] + " L" + (bx + px) + " " + (by + py) + " L" + (bx - px) + " " + (by - py) + "Z";
      g.querySelector(".base").setAttribute("d", d);
      g.querySelector(".luz").setAttribute("d", d);
      g.querySelector(".punta").setAttribute("d", punta);
      g.querySelector(".punta-luz").setAttribute("d", punta);
      g.querySelector(".base").classList.toggle("rayas", S.estados && !nodo(a).classList.contains("s-hecho"));
    });
  }

  function iluminar() {
    var encendidas = {};
    if (S.sel) {
      aristas.forEach(function (g) {
        var par = g.dataset.a.split("-"), a = +par[0], b = +par[1];
        var toca = S.rastro
          ? (S.visitados[a] || S.visitados[b])
          : (a === S.sel || b === S.sel);
        if (toca) { encendidas[g.dataset.a] = a === S.sel; }
      });
    }
    aristas.forEach(function (g) {
      var on = g.dataset.a in encendidas;
      var demora = on && encendidas[g.dataset.a] ? 0.34 : 0;
      var luz = g.querySelector(".luz"), punta = g.querySelector(".punta-luz");
      luz.style.setProperty("--d", demora + "s");
      punta.style.setProperty("--d2", (demora + 0.4) + "s");
      luz.classList.toggle("on", on);
      punta.classList.toggle("on", on);
    });
  }

  /* ---------- Qué se ve ---------- */
  function controles() {
    var sinAqui = S.aqui.length === 0;
    var ant = $('[data-accion="ant"]'), sig = $('[data-accion="sig"]');
    ant.disabled = S.sel === null || (S.sel === 1 && !sinAqui);
    sig.disabled = S.sel === 7;
    $('[data-accion="play"]').hidden = S.jugando;
    $('[data-accion="pausa"]').hidden = !S.jugando;
    $('[data-accion="stop"]').hidden = !S.jugando;
    $('[data-accion="pausa"]').textContent = S.pausa ? "Seguir" : "Pausar";
    $(".evi-cuenta-txt").textContent = S.sel ? "Paso " + S.sel + " de 7" : "Resumen del circuito";
    todos(".evi-puntos i").forEach(function (punto, i) { punto.classList.toggle("on", i + 1 === S.sel); });
  }

  function render() {
    if (!S.listo) { return; }
    nodos.forEach(function (b) {
      var n = +b.dataset.n;
      b.classList.toggle("sel", S.sel === n);
      if (S.sel === n) { b.setAttribute("aria-current", "step"); } else { b.removeAttribute("aria-current"); }
    });
    pasos.forEach(function (seccion) { seccion.hidden = +seccion.dataset.n !== (S.sel || 0); });
    controles();
    trazar();
    iluminar();
  }

  function ir(n, deJuego) {
    if (!deJuego) { S.rastro = false; S.visitados = {}; }
    S.sel = n;
    if (n) { S.visitados[n] = true; }
    render();
  }

  /* ---------- Recorrido ---------- */
  function detener() {
    var estaba = S.jugando;
    clearTimeout(S.t); S.jugando = false; S.pausa = false;
    if (estaba && S.listo) { controles(); }
  }
  function agendar() {
    clearTimeout(S.t);
    S.t = setTimeout(function () {
      if (!S.jugando || S.pausa) { return; }
      if (S.sel >= 7) { detener(); return; }
      ir(S.sel + 1, true); agendar();
    }, PAUSA_MS);
  }
  function jugar() {
    S.jugando = true; S.pausa = false; S.rastro = true; S.visitados = {};
    ir(1, true); agendar();
  }
  function pausar() {
    S.pausa = !S.pausa;
    if (S.pausa) { clearTimeout(S.t); } else { agendar(); }
    controles();
  }
  function siguiente() { detener(); if (S.sel === null) { ir(1); } else if (S.sel < 7) { ir(S.sel + 1); } }
  function anterior() {
    detener();
    if (S.sel === 1 && S.aqui.length === 0) { ir(null); } else if (S.sel > 1) { ir(S.sel - 1); }
  }

  var ACCIONES = {ant: anterior, sig: siguiente, play: jugar, pausa: pausar, stop: detener,
                  volver: function () { detener(); ir(S.aqui[0]); }};

  function alHacerClic(e) {
    var accion = e.target.closest("[data-accion]");
    if (accion && ACCIONES[accion.dataset.accion]) { ACCIONES[accion.dataset.accion](); return; }
    var paso = e.target.closest(".evi-nodo");
    if (paso) { detener(); ir(+paso.dataset.n); }
  }

  function alTeclear(e) {
    if (!mapa || !mapa.contains(document.activeElement)) { return; }
    var k = e.key, n = S.sel || 1;
    if (k === "ArrowRight" || k === "ArrowDown") { n = Math.min(7, n + 1); }
    else if (k === "ArrowLeft" || k === "ArrowUp") { n = Math.max(1, n - 1); }
    else if (k === "Home") { n = 1; }
    else if (k === "End") { n = 7; }
    else { return; }
    e.preventDefault(); detener(); ir(n); nodo(n).focus();
  }

  /* ---------- Contenido ---------- */
  function iniciar() {
    var cuerpo = document.getElementById("evi-cuerpo");
    mapa = document.getElementById("evi-mapa");
    svg = document.getElementById("evi-aristas");
    if (!cuerpo || !mapa || !svg) { S.listo = false; return; }
    nodos = todos(".evi-nodo");
    pasos = todos(".evi-paso");
    aristas = Array.prototype.slice.call(svg.querySelectorAll("g"));
    S.aqui = (cuerpo.dataset.aqui || "").split(",").filter(Boolean).map(Number);
    S.estados = cuerpo.dataset.estados === "1";
    S.sel = S.aqui.length ? S.aqui[0] : null;
    S.visitados = {};
    if (S.sel) { S.visitados[S.sel] = true; }
    S.rastro = false; S.jugando = false; S.pausa = false;
    S.listo = true;
    render();
    if ("ResizeObserver" in window) { new ResizeObserver(function () { trazar(); iluminar(); }).observe(mapa); }
    if (document.fonts && document.fonts.ready) { document.fonts.ready.then(function () { trazar(); iluminar(); }); }
  }

  function pedir() {
    var url = boton.dataset.url + (boton.dataset.pasos ? "?pasos=" + encodeURIComponent(boton.dataset.pasos) : "");
    var numero = ++S.pedido;
    fetch(url, {credentials: "same-origin", headers: {"X-Requested-With": "fetch"}})
      .then(function (r) { if (!r.ok) { throw new Error("estado " + r.status); } return r.text(); })
      .then(function (html) {
        if (numero !== S.pedido) { return; }
        detener();
        contenido.innerHTML = html;
        iniciar();
      })
      .catch(function () {
        if (numero !== S.pedido || S.listo) { return; }
        contenido.innerHTML = '<p class="evi-cargando">No se pudo abrir. Pruebe de nuevo en un momento.</p>';
      });
  }

  /* ---------- Panel ---------- */
  function abrir() {
    S.abierto = true;
    panel.hidden = false;
    boton.setAttribute("aria-expanded", "true");
    pedir();
    document.getElementById("evi-titulo").focus();
  }
  function cerrar(devolverFoco) {
    detener();
    S.abierto = false;
    panel.hidden = true;
    boton.setAttribute("aria-expanded", "false");
    if (devolverFoco) { boton.focus(); }
  }

  boton.addEventListener("click", function () { if (S.abierto) { cerrar(false); } else { abrir(); } });
  cerrarBoton.addEventListener("click", function () { cerrar(true); });
  contenido.addEventListener("click", alHacerClic);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && S.abierto) { e.preventDefault(); cerrar(true); return; }
    if (S.abierto) { alTeclear(e); }
  });
  window.addEventListener("resize", function () { if (S.listo) { trazar(); iluminar(); } });
})();
