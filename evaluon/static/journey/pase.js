/* Dirección del pase de hoja (REQ-139; ADR-0075). En `pagereveal` compara la posición de la
   pestaña de la página anterior con la de la actual y lo deja en <html data-pase>: la hoja avanza o
   vuelve (pase.css). Sin este archivo, o en un navegador sin transiciones entre documentos, la
   navegación es la de siempre. */
(function () {
  "use strict";
  window.addEventListener("pagereveal", function (event) {
    var from = window.navigation && navigation.activation && navigation.activation.from;
    if (!event.viewTransition || !from) { return; }
    var tabs = Array.prototype.slice.call(document.querySelectorAll("nav.tabs a.tab"));
    var before = tabs.findIndex(function (t) { return t.pathname === new URL(from.url).pathname; });
    var now = tabs.findIndex(function (t) { return t.getAttribute("aria-current") === "page"; });
    if (before < 0 || now < 0 || before === now) { return; }
    var root = document.documentElement;
    root.dataset.pase = before < now ? "adelante" : "atras";
    event.viewTransition.finished.finally(function () { delete root.dataset.pase; });
  });
})();
