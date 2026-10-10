/* Propuesta de una oferta subida (T-202, REQ-083): mientras el sistema lee los archivos, la
   pestaña se vuelve a pedir cada tantos segundos (`data-recargar`) para mostrar el avance y, al
   terminar, el nombre y el CUIT propuestos. Sin este script se ve el mismo estado al recargar. */
(function () {
  "use strict";
  var block = document.querySelector("[data-recargar]");
  if (!block) { return; }
  var seconds = parseInt(block.getAttribute("data-recargar"), 10) || 5;
  window.setTimeout(function () {
    if (document.visibilityState === "hidden") {
      document.addEventListener("visibilitychange", function () { window.location.reload(); },
                                { once: true });
      return;
    }
    window.location.reload();
  }, seconds * 1000);
})();
