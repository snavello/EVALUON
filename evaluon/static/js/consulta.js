/* Espera de la consulta (T-016; plan 001, "Pantalla, acceso y comandos").
   Al enviar la pregunta, desactiva el botón para no enviarla dos veces y muestra el
   aviso de espera. Sin este script el formulario es un envío común y funciona igual.
   Archivo propio: la política de contenido no admite scripts en línea. */

(function () {
  "use strict";

  var form = document.getElementById("query-form");
  var button = document.getElementById("query-submit");
  var waiting = document.getElementById("query-waiting");
  if (!form || !button || !waiting) {
    return;
  }

  form.addEventListener("submit", function () {
    button.disabled = true;
    waiting.hidden = false;
  });

  // Al volver con "Atrás", el navegador puede mostrar la página tal como quedó:
  // se deja el botón otra vez disponible y el aviso oculto.
  window.addEventListener("pageshow", function () {
    button.disabled = false;
    waiting.hidden = true;
  });
})();
