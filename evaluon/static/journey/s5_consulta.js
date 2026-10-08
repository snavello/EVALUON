/* Espera de la consulta de normativa (T-216, REQ-096). Al enviar la pregunta, desactiva el botón
   para no enviarla dos veces y muestra que el sistema está buscando (la consulta corre con el
   modelo y puede tardar). Sin este script el formulario es un envío común y funciona igual.
   Archivo propio: la política de contenido no admite scripts en línea. */
(function () {
  "use strict";
  var form = document.getElementById("s5-consulta-form");
  var button = document.getElementById("s5-consulta-enviar");
  var waiting = document.getElementById("s5-consulta-espera");
  if (!form || !button || !waiting) { return; }
  form.addEventListener("submit", function () {
    button.disabled = true;
    waiting.hidden = false;
  });
  // Al volver con «Atrás», el navegador puede mostrar la página tal como quedó.
  window.addEventListener("pageshow", function () {
    button.disabled = false;
    waiting.hidden = true;
  });
})();
