// Botón "Imprimir" de la vista de impresión de la matriz (T-086). La política de contenido
// no admite scripts en la página: el botón se engancha desde este archivo.
document.addEventListener("DOMContentLoaded", function () {
  var button = document.getElementById("print-button");
  if (button) {
    button.addEventListener("click", function () { window.print(); });
  }
});
