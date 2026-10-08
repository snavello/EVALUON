/* Subida de varios archivos de la pestaña «Pliego y matriz» (T-198, REQ-080). Al elegir los
   archivos, arma una fila por archivo con su tipo, su título y su fecha opcional. Sin este
   script el formulario sube todos los archivos con el tipo único de arriba. Sin librerías ni
   direcciones externas. */
(function () {
  "use strict";
  var input = document.getElementById("s2-archivos");
  var holder = document.getElementById("s2-por-archivo");
  var common = document.getElementById("s2-tipo");
  if (!input || !holder || !common) { return; }
  var tipos = JSON.parse(holder.getAttribute("data-tipos") || "[]");

  function text(tag, content) {
    var node = document.createElement(tag);
    node.textContent = content;
    return node;
  }

  function stem(name) {
    return name.replace(/\.[^.]+$/, "").replace(/_/g, " ");
  }

  function render() {
    holder.textContent = "";
    var files = input.files;
    if (!files || !files.length) { return; }
    var table = document.createElement("table");
    table.className = "matriz lectura";
    var head = document.createElement("tr");
    ["Archivo", "Tipo", "Título", "Fecha (opcional)"].forEach(function (label) {
      var th = text("th", label); th.scope = "col"; head.appendChild(th);
    });
    var thead = document.createElement("thead"); thead.appendChild(head); table.appendChild(thead);
    var body = document.createElement("tbody");
    Array.prototype.forEach.call(files, function (file, index) {
      var row = document.createElement("tr");
      var name = text("th", file.name); name.scope = "row"; row.appendChild(name);
      var kindCell = document.createElement("td");
      var select = document.createElement("select");
      select.name = "kind_" + index;
      select.setAttribute("aria-label", "Tipo de " + file.name);
      tipos.forEach(function (pair) {
        var option = text("option", pair[1]); option.value = pair[0];
        if (pair[0] === common.value) { option.selected = true; }
        select.appendChild(option);
      });
      kindCell.appendChild(select); row.appendChild(kindCell);
      var titleCell = document.createElement("td");
      var title = document.createElement("input");
      title.type = "text"; title.name = "title_" + index; title.value = stem(file.name);
      title.setAttribute("aria-label", "Título de " + file.name);
      titleCell.appendChild(title); row.appendChild(titleCell);
      var dateCell = document.createElement("td");
      var date = document.createElement("input");
      date.type = "date"; date.name = "issued_on_" + index;
      date.setAttribute("aria-label", "Fecha de " + file.name);
      dateCell.appendChild(date); row.appendChild(dateCell);
      body.appendChild(row);
    });
    table.appendChild(body);
    holder.appendChild(table);
  }

  input.addEventListener("change", render);
})();
