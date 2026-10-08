/* Filas de la matriz que se abren con la cita (T-192, REQ-081). Sin librerías ni direcciones
   externas. Sin este script la tabla sigue mostrando todas las filas; solo las citas quedan
   ocultas, y se leen en la matriz completa. */
(function () {
  "use strict";

  function toggle(row) {
    var button = row.querySelector(".abrir");
    var detail = document.getElementById(button.getAttribute("aria-controls"));
    if (!detail) { return; }
    var open = detail.hidden;
    detail.hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.textContent = open ? "▾" : "▸";
  }

  document.addEventListener("click", function (event) {
    var row = event.target.closest("tr.fila-req");
    if (!row) { return; }
    // Los enlaces de la fila (la ubicación en el pliego) siguen su camino.
    if (event.target.closest("a")) { return; }
    toggle(row);
  });
})();
