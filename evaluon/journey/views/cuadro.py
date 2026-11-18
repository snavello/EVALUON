"""El cuadro de cumplimiento con el panel lado a lado (feature 018, REQ-152 a REQ-154; T-352).

`expedientes/<id>/cuadro/`: los requisitos del pliego en filas (agrupados por tipo), las ofertas en
columnas y, en cada celda, el estado del par con su nombre escrito. Es una lectura de la misma
matriz que usan el mosaico «Resultado por oferta» y la tabla de la propuesta (`memo.matrix_page`):
el estado de cada celda lo da `s4_propuesta._bucket` y los totales del pie son los de
`s4_propuesta.figures_of`, así que los números coinciden con el mosaico (REQ-152).

Con `?celda=<oferta>-<requisito>` la página dibuja a la derecha el panel del par: el cuerpo de la
página del par (`journey/_par.html`, `desde="cuadro"`), con el texto del pliego, el de la oferta, el
motivo y los mismos formularios. Esos formularios envían a la ruta de siempre (`review.decide`);
esta vista no decide ni escribe nada (P3, P6). El rol de lectura ve el panel sin botones.

El filtro (`?filtro=`, T-355) deja las filas que tienen al menos una celda de ese tipo y se conserva
para el regreso de una decisión. «A decidir» deja las filas con una celda que el sistema no pudo
concluir y las que siguen sin resultado o sin aplicar a la espera de decisión: son las mismas
celdas que cuenta «Decidir N puntos no determinados» del paso 6. Un grupo donde todas las ofertas
cumplen todo (y está confirmado) sale resumido en una línea. «Siguiente a decidir» sigue el orden del
cuadro (tipo, fila, oferta). Sin JavaScript (ADR-0076).
"""

import re
from collections import Counter

from django.http import Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.assessment.models import Doubt
from evaluon.assessment.services import matrix as matrix_service
from evaluon.assessment.services import review
from evaluon.journey import memo, points
from evaluon.journey.proceso import pasos
from evaluon.journey.temas import s4_propuesta
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.temas.s4_descartes import _money
from evaluon.journey.views import portada
from evaluon.portal.models import PortalOfferData
from evaluon.tenders.models import MatrixVersion, RequirementClass

SECTION = "evaluacion"
CELDA = re.compile(r"(\d{1,9})-(\d{1,9})")
RESUMEN_MAX = 110

# El texto de cada celda (decisión del responsable: seis textos) y su clase de color. El color
# solo acompaña: el texto va siempre escrito (REQ-156).
TEXTO_CELDA = {
    "ok": ("Cumple", "ok"), "no": ("No cumple", "no"), "nd": ("A decidir", "nd"),
    "esp": ("Espera informe", "esp"), "pe": ("Sin resultado", "sin"), "na": ("No aplica", "na"),
}
TIPOS = (RequirementClass.FORMAL, RequirementClass.ECONOMICO, RequirementClass.TECNICO)
TIPO_TEXTO = {RequirementClass.FORMAL: "Formales", RequirementClass.ECONOMICO: "Económicos",
              RequirementClass.TECNICO: "Técnicos"}


def estado_de(cell):
    """La clave de `TEXTO_CELDA` de una celda: `_bucket` (la única definición) y, dentro de «pe»,
    el que espera el informe técnico aparte del que no tiene resultado."""
    bucket = s4_propuesta._bucket(cell)
    if (bucket == "pe" and cell.result is not None
            and cell.reason == Doubt.PENDIENTE_INFORME_TECNICO):
        return "esp"
    return bucket


FILTROS = (("todos", "Todos"), ("pendiente", "Con algo pendiente"), ("a-decidir", "A decidir"),
           ("no-cumple", "No cumple"), ("espera-informe", "Esperan informe técnico"))


def _coincide(filtro, celda):
    """Si una celda (`key`, `pendiente`) cuenta para ese filtro. «A decidir» suma lo no determinado
    y lo que sigue sin resultado o sin aplicar a la espera de decisión (como la cuenta del paso 6)."""
    if filtro == "pendiente":
        return celda["pendiente"]
    if filtro == "a-decidir":
        return celda["key"] == "nd" or (celda["key"] in ("pe", "na") and celda["pendiente"])
    if filtro == "no-cumple":
        return celda["key"] == "no"
    if filtro == "espera-informe":
        return celda["key"] == "esp"
    return True


def _resumen(text):
    text = " ".join((text or "").split())
    return text if len(text) <= RESUMEN_MAX else text[:RESUMEN_MAX].rstrip() + "…"


def _celda_pedida(request, procedure, page):
    """`(oferta, requisito)` de `?celda=`, o `None` si no viene. 404 si no son dos números o si la
    oferta o el requisito no son de este procedimiento. Un requisito de una versión anterior de la
    matriz (hubo una evaluación nueva) es del procedimiento pero ya no está en el cuadro: se
    devuelve igual y la página se dibuja sin panel."""
    raw = request.GET.get("celda", "")
    if not raw:
        return None
    found = CELDA.fullmatch(raw)  # `$` aceptaría un salto de línea al final
    if found is None:
        raise Http404("La celda no es válida.")
    offer_id, requirement_id = int(found.group(1)), int(found.group(2))
    if not any(o.pk == offer_id for o in page.offers):
        raise Http404("Esa oferta no es de este procedimiento.")
    if not any(r.pk == requirement_id for r in page.requirements) and not (
            MatrixVersion.objects.filter(procedure=procedure,
                                         requirements__pk=requirement_id).exists()):
        raise Http404("Ese requisito no es de este procedimiento.")
    return offer_id, requirement_id


def _columnas(page, figures):
    """Las ofertas en columnas: número, oferente, total del acta y lo cumplido hasta ahora (las
    cifras de `figures_of`, las del mosaico)."""
    data = {d.offer_id: d for d in PortalOfferData.objects.filter(offer__in=page.offers)}
    by_number = {o.number: o for o in figures.offers} if figures else {}
    columns = []
    for offer in page.offers:
        info = data.get(offer.pk)
        mine = by_number.get(offer.number)
        # Lo que no cumple, falta decidir o espera, contado de las mismas celdas que se dibujan;
        # «Espera informe» y «Sin resultado» suman el `pe` de `figures_of`.
        seen = Counter(estado_de(page.cells[(offer.pk, r.pk)]) for r in page.requirements)
        columns.append({
            "number": offer.number, "bidder": offer.bidder, "figures": mine,
            "total": _money(info.total, info.currency) if info and info.total is not None else "",
            "count": (mine.ok + mine.no + mine.nd + mine.pe) if mine else 0,
            "waiting": seen["esp"], "without": seen["pe"]})
    return columns


def _grupos(page, base_url, selected, filtro):
    """Las filas por tipo de requisito, cada celda con su texto, su clase y su enlace."""
    texts = points.texts_of_page(page)
    groups = []
    for kind in TIPOS:
        rows = []
        for requirement in page.requirements:
            if requirement.category != kind:
                continue
            quotes = texts[requirement.pk].quotes if requirement.pk in texts else []
            title = _resumen(quotes[0].text if quotes else "Sin cita")
            if kind == RequirementClass.TECNICO and not quotes:
                # La cita del pliego ya dice «1. RENGLÓN N° 1 - …»: solo sin cita se escribe el renglón.
                items = ", ".join(str(i) for i in requirement.items)
                title = f"Renglón {items or '—'} · {title}"
            cells = []
            for offer in page.offers:
                cell = page.cells[(offer.pk, requirement.pk)]
                key = estado_de(cell)
                text, css = TEXTO_CELDA[key]
                anchor = f"c-{offer.pk}-{requirement.pk}"
                query = f"celda={offer.pk}-{requirement.pk}" + (f"&filtro={filtro}" if filtro else "")
                cells.append({
                    "key": key, "text": text, "css": css, "id": anchor,
                    "unconfirmed": key in ("ok", "no") and cell.state == review.PROPOSED,
                    "label": f"Oferta {offer.number}, requisito {requirement.number}",
                    "url": f"{base_url}?{query}#{anchor}" if cell.result is not None else "",
                    "selected": selected == (offer.pk, requirement.pk),
                    "pendiente": cell.state == matrix_service.PENDING})
            rows.append({"number": requirement.number, "title": title, "cells": cells})
        if rows:
            groups.append({"kind": kind, "label": TIPO_TEXTO[kind], "rows": rows})
    return groups


def _filtrar(groups, filtro):
    """`(grupos, cantidades)`: las filas que dejan los filtros y cuántas deja cada uno. Con filtro,
    los grupos sin filas desaparecen; sin filtro, el que cumple todo se marca `resumido`."""
    counts = {clave: sum(1 for g in groups for r in g["rows"]
                         if any(_coincide(clave, c) for c in r["cells"])) for clave, _ in FILTROS}
    shown = []
    for group in groups:
        rows = group["rows"]
        if filtro not in ("", "todos"):
            rows = [r for r in rows if any(_coincide(filtro, c) for c in r["cells"])]
        if not rows:
            continue
        cells = [c for r in rows for c in r["cells"]]
        resumido = (filtro in ("", "todos") and all(c["key"] == "ok" and not c["unconfirmed"]
                                                    and not c["selected"] for c in cells))
        shown.append({**group, "rows": rows, "resumido": resumido})
    return shown, counts


def _siguiente(groups, filtro, selected, base_url):
    """El enlace a la próxima celda a decidir después de la abierta, en el orden del cuadro y con el
    mismo filtro; si ya no queda ninguna de ese filtro, la próxima con algo pendiente. `""` si no
    hay panel abierto o no queda ninguna con resultado para abrir."""
    if selected is None:
        return ""
    orden = [c for g in groups for r in g["rows"] for c in r["cells"]]
    posicion = next((i for i, c in enumerate(orden) if c["selected"]), -1)
    for clave in ((filtro,) if filtro in ("pendiente", "no-cumple", "espera-informe")
                  else ("a-decidir",)) + ("pendiente",):
        for c in orden[posicion + 1:]:
            if c["url"] and _coincide(clave, c):
                return c["url"]
    return ""


def _panel(request, procedure, selected, filtro):
    """El HTML del panel de la celda elegida, o `""` si no hay celda o su par ya no existe (por
    ejemplo tras una evaluación nueva): entonces se muestra el cuadro sin panel."""
    if selected is None:
        return ""
    try:
        context = s4_propuesta.par_context(request, procedure, *selected, desde="cuadro",
                                           filtro=filtro or None)
    except Http404:
        return ""
    # Quien no tiene rol de la Comisión no puede abrir el archivo original (403): la plantilla no le
    # ofrece el enlace y dibuja solo el nombre. El HTML sale entero de la plantilla (nada se reemplaza
    # a mano sobre el texto ya dibujado); `_par.html` no cambia sin `sin_original`.
    context["sin_original"] = not request.user.commission_role
    return render_to_string("journey/_par.html", context, request=request)


@require_GET
@memo.scoped
@portada.reading
def cuadro(request, procedure_id):
    overview = portada.overview_of(request, procedure_id)
    procedure = overview.procedure
    page = memo.matrix_page(request.user, procedure.pk)
    selected = _celda_pedida(request, procedure, page)
    filtro = request.GET.get("filtro", "")
    filtro = filtro if filtro in acciones.FILTROS_CUADRO else ""
    figures = s4_propuesta.figures_of(page)
    groups = _grupos(page, reverse("expedientes:cuadro", args=[procedure.pk]), selected, filtro)
    panel = _panel(request, procedure, selected, filtro)
    base = reverse("expedientes:cuadro", args=[procedure.pk])
    siguiente = _siguiente(groups, filtro, selected, base)
    groups, counts = _filtrar(groups, filtro)
    context = portada.shell(request, overview, active=SECTION)
    context.update({
        "section": overview.get(SECTION), "columns": _columnas(page, figures), "groups": groups,
        "total_rows": len(page.requirements), "evaluated": figures is not None,
        "filtro": filtro, "panel": panel, "siguiente": siguiente,
        "filtros": [{"clave": c, "texto": t, "n": counts[c], "url": f"{base}?filtro={c}"}
                    for c, t in FILTROS], "pasos": pasos.PASOS, "pasos_aqui": (4, 6),
        "tab_url": acciones.tab_url(procedure),
    })
    return render(request, "journey/cuadro.html", context)
