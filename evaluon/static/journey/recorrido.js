/* Sondeo del recorrido y de las secciones (REQ-067, REQ-075; ADR-0045). Cada 5 s pide al mismo
   servidor un bloque (las etapas del recorrido, la barra de las cinco secciones o la ventana del
   proceso) y lo reemplaza, sin recargar la página. Se pausa con la pestaña oculta. Conserva el
   foco de quien navega con el teclado y avisa, en la región de estado, cuando algo termina o
   falla (con el motivo en lenguaje llano que trae el bloque). Sin librerías ni direcciones
   externas. */
(function () {
  "use strict";
  var INTERVAL_MS = 5000;
  var status = document.getElementById("journey-status");
  var connection = document.getElementById("journey-connection");
  if (!window.fetch) { return; }

  var FOCUSABLE = "a[href], button, [tabindex]";

  // Lo que se anuncia: los elementos con `data-stage` (etapas) o `data-seccion` (secciones).
  function snapshot(container) {
    var found = {};
    container.querySelectorAll("[data-stage], [data-seccion]").forEach(function (el) {
      var key = el.dataset.stage || el.dataset.seccion;
      found[key] = {state: el.dataset.state, label: el.dataset.label, error: el.dataset.error,
                    kind: el.dataset.stage ? "etapa" : "sección"};
    });
    return found;
  }

  function announce(before, after) {
    if (!status) { return; }
    Object.keys(after).forEach(function (key) {
      var was = before[key], now = after[key];
      if (!was || was.state !== "en_curso" || now.state === "en_curso") { return; }
      var article = now.kind === "etapa" ? "La etapa " : "La sección ";
      status.textContent = now.state === "con_error"
        ? article + now.label + " falló: " + (now.error || "sin motivo registrado") + "."
        : article + now.label + " terminó.";
    });
  }

  function notice(text) {
    if (!connection) { return; }
    connection.hidden = !text;
    connection.textContent = text || "";
  }

  // El foco del teclado sobrevive al reemplazo: se recuerda su posición entre los elementos
  // enfocables del bloque y se devuelve al que quedó en la misma posición.
  function focusIndex(root) {
    var active = document.activeElement;
    if (!active || !root.contains(active)) { return -1; }
    return Array.prototype.indexOf.call(root.querySelectorAll(FOCUSABLE), active);
  }

  function restoreFocus(root, index) {
    if (index < 0) { return; }
    var items = root.querySelectorAll(FOCUSABLE);
    if (items[index]) { items[index].focus(); }
  }

  function watch(root, url) {
    var previous = snapshot(root);

    function poll() {
      if (document.hidden) { return; }
      fetch(url, {credentials: "same-origin", cache: "no-store"})
        .then(function (response) {
          if (response.redirected) { throw new Error("session"); }
          if (!response.ok) { throw new Error("status"); }
          return response.text();
        })
        .then(function (html) {
          var index = focusIndex(root);
          root.innerHTML = html;
          restoreFocus(root, index);
          var current = snapshot(root);
          announce(previous, current);
          previous = current;
          notice("");
        })
        .catch(function (error) {
          if (!connection) { return; }
          if (error.message === "session") {
            notice("La sesión venció. Ingrese de nuevo para seguir viendo el avance.");
            var link = document.createElement("a");
            link.href = root.dataset.loginUrl;
            link.textContent = " Ir al ingreso";
            connection.appendChild(link);
          } else {
            notice("Sin conexión con el servidor; se reintenta.");
          }
        });
    }

    window.setInterval(poll, INTERVAL_MS);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { poll(); }
    });
  }

  var stages = document.getElementById("journey-stages");
  if (stages) { watch(stages, stages.dataset.url); }
  document.querySelectorAll("[data-poll-url]").forEach(function (root) {
    watch(root, root.dataset.pollUrl);
  });
})();
