/* Espera de la consulta (T-016) y enlaces entre citas (T-037); plan 001, "Pantalla,
   acceso y comandos".
   Al enviar la pregunta, desactiva el botón para no enviarla dos veces y muestra el
   aviso de espera. Sin este script el formulario es un envío común y funciona igual.
   Archivo propio: la política de contenido no admite scripts en línea. */

(function () {
  "use strict";

  // Texto de una cita mostrado una sola vez (T-037): las demás citas de la misma unidad
  // llevan a él con un enlace "más arriba". Al seguirlo se despliega la cita que lo
  // contiene, y también la cita de afuera si el texto es el de una unidad que modifica
  // a otra. Sin script, el enlace lleva igual al lugar y la cita se abre a mano.
  function openTarget() {
    var id = window.location.hash.slice(1);
    var target = id ? document.getElementById(id) : null;
    if (!target) {
      return;
    }
    var inner = target.querySelector("details");
    if (inner) {
      inner.open = true;
    }
    for (var node = target; node; node = node.parentElement) {
      if (node.tagName === "DETAILS") {
        node.open = true;
      }
    }
    target.scrollIntoView();
  }

  window.addEventListener("hashchange", openTarget);
  openTarget();

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
