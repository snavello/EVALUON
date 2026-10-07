/* Sondeo del recorrido (REQ-067; ADR-0045). Cada 5 s pide al mismo servidor el bloque de las
   etapas y lo reemplaza, sin recargar la página. Sin librerías ni direcciones externas. */
(function () {
  "use strict";
  var INTERVAL_MS = 5000;
  var root = document.getElementById("journey-stages");
  var status = document.getElementById("journey-status");
  var connection = document.getElementById("journey-connection");
  if (!root || !window.fetch) { return; }

  function snapshot(container) {
    var found = {};
    container.querySelectorAll("[data-stage]").forEach(function (el) {
      found[el.dataset.stage] = {state: el.dataset.state, label: el.dataset.label,
                                 error: el.dataset.error};
    });
    return found;
  }

  function announce(before, after) {
    Object.keys(after).forEach(function (key) {
      var was = before[key], now = after[key];
      if (!was || was.state !== "en_curso" || now.state === "en_curso") { return; }
      status.textContent = now.state === "con_error"
        ? "La etapa " + now.label + " falló: " + (now.error || "sin motivo registrado") + "."
        : "La etapa " + now.label + " terminó.";
    });
  }

  function notice(text) {
    connection.hidden = !text;
    connection.textContent = text || "";
  }

  var previous = snapshot(root);

  function poll() {
    if (document.hidden) { return; }
    fetch(root.dataset.url, {credentials: "same-origin", cache: "no-store"})
      .then(function (response) {
        if (response.redirected) { throw new Error("session"); }
        if (!response.ok) { throw new Error("status"); }
        return response.text();
      })
      .then(function (html) {
        root.innerHTML = html;
        var current = snapshot(root);
        announce(previous, current);
        previous = current;
        notice("");
      })
      .catch(function (error) {
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
})();
