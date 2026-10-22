/* Tablero de las secciones (REQ-127; ADR-0076). Sin este script cada mosaico es un ancla a la zona
   de detalles, que queda visible. Con él: el detalle del mosaico tocado se mueve debajo de la fila
   de ese mosaico y se despliega (la animación es una transición de CSS); hay uno solo abierto; el
   mismo mosaico lo pliega. Abre además el detalle que nombra el # de la dirección (o que contiene
   el elemento con ese id) y, si no hay #, el que declara el servidor en data-abre. */
(function () {
  "use strict";
  var root = document.querySelector(".tablero");
  var board = root && root.querySelector(".board");
  var zone = root && root.querySelector(".detalles");
  if (!board || !zone) { return; }
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var tiles = [].slice.call(board.querySelectorAll(".tile"));
  var panels = {};
  [].forEach.call(zone.querySelectorAll(".inline-detail"), function (p) { panels[p.id] = p; });
  var current = null;
  root.classList.add("con-js");

  tiles.forEach(function (tile) {
    var id = tile.dataset.detail;
    if (!id || !panels[id]) { return; }
    tile.setAttribute("role", "button");
    tile.setAttribute("aria-controls", id);
    tile.setAttribute("aria-expanded", "false");
  });

  function mark() {
    tiles.forEach(function (tile) {
      if (tile.getAttribute("role") === "button") {
        tile.setAttribute("aria-expanded", String(!!current && tile.dataset.detail === current.id));
      }
    });
  }

  // Los mosaicos de la misma fila comparten offsetTop: el detalle va después del último.
  function endOfRow(tile) {
    var last = tile;
    tiles.forEach(function (other) { if (other.offsetTop === tile.offsetTop) { last = other; } });
    return last;
  }

  function fold(panel) {
    panel.classList.remove("open");
    var back = function () { if (!panel.classList.contains("open")) { zone.appendChild(panel); } };
    if (reduce) { back(); } else { setTimeout(back, parseFloat(getComputedStyle(panel).transitionDuration) * 1000 || 350); }
  }

  function show(id, instant) {
    var panel = panels[id];
    if (!panel || panel === current) { return; }
    var previous = current;
    current = panel;
    if (previous) { fold(previous); }
    var opener = tiles.filter(function (t) { return t.dataset.detail === id; })[0] || tiles[tiles.length - 1];
    endOfRow(opener).after(panel);
    root.classList.toggle("quieto", !!instant);
    void panel.offsetHeight; // sin esto el navegador no anima desde el alto cero
    panel.classList.add("open");
    mark();
  }

  function hide() {
    if (current) { fold(current); }
    current = null;
    mark();
  }

  board.addEventListener("click", function (event) {
    var tile = event.target.closest(".tile");
    var id = tile && tile.getAttribute("role") === "button" && tile.dataset.detail;
    if (!id) { return; }
    event.preventDefault();
    if (current && current.id === id) { hide(); } else { show(id, false); }
  });
  board.addEventListener("keydown", function (event) {
    var tile = event.target.closest(".tile");
    if (tile && event.key === " ") { event.preventDefault(); tile.click(); }
  });

  function fromHash() {
    var element = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    var panel = element && (panels[element.id] ? element : element.closest(".inline-detail"));
    if (!panel || panels[panel.id] !== panel) { return false; }
    show(panel.id, true);
    if (element !== panel) { element.scrollIntoView(); }
    return true;
  }
  window.addEventListener("hashchange", fromHash);
  if (!fromHash() && root.dataset.abre) { show(root.dataset.abre, true); }
})();
