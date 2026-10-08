"""Alta de un procedimiento antes de que exista (REQ-076; plan 014, T-195).

Es la pantalla `expedientes/nuevo/`, dentro de la estructura de cinco pestañas: Procedimiento es la
única con contenido y la de Normativas está disponible; Pliego y matriz, Ofertas y Evaluación
quedan en gris hasta que se cree el procedimiento. Tiene dos entradas:

- «Explorar el Portal»: se pega el enlace del proceso (`links.register_link`) y se pasa a
  `nuevo/<enlace>/`, donde el sistema muestra lo que encontró, agrupado, con su aprobación (el mismo
  tema `s1_portal`). Nada se tipea más que el enlace. Cuando el evaluador aprueba los datos se crea
  el procedimiento y la pantalla pasa a su pestaña Procedimiento.
- «Subir el pliego»: es del tema `s1_pliego` (T-197). Mientras ese tema no ofrezca su entrada
  (`context(...)` con la clave `upload`), se muestra a la vista, deshabilitada.

No hay alta en blanco: sin propuesta no hay nada que escribir. Las acciones llaman a los mismos
servicios de la 012 que las pantallas viejas, por lo que dejan el mismo cambio y el mismo hecho de
auditoría (P6). Solo traducen: el rol lo comprueba cada servicio.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey.sections import SECTIONS
from evaluon.journey.temas import s1_pliego, s1_portal
from evaluon.journey.views.portada import DROPDOWN_LIMIT, ROLE_LABELS
from evaluon.portal.models import PortalLink
from evaluon.portal.services import links as link_service
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.nuevo.nuevo"
TEMPLATE = "journey/nuevo.html"
REFRESH_SECONDS = 5


def _shell(request):
    """Lo que necesita el encabezado y las pestañas cuando todavía no hay procedimiento."""
    latest = Procedure.objects.order_by("-created_at", "-pk")
    newest = latest.first()
    tabs = [{"label": module.LABEL, "key": module.KEY, "current": module.KEY == "procedimiento",
             "enabled": module.KEY in ("procedimiento", "normativas")} for module in SECTIONS]
    return {
        "procedure": None, "active": "procedimiento", "tabs": tabs,
        "procedures": latest[:DROPDOWN_LIMIT],
        "role_label": ROLE_LABELS.get(request.user.commission_role, ""),
        "login_url": reverse("accounts:login"),
        "normativas_url": (reverse("expedientes:normativas", args=[newest.pk]) if newest
                           else reverse("queries:screen")),
    }


def _link(link_id):
    try:
        return PortalLink.objects.select_related("procedure").get(pk=link_id)
    except PortalLink.DoesNotExist:
        raise Http404("No hay un proceso del Portal con ese número.")


def _back(link, entries):
    """Vuelve a la propuesta del enlace; si ya tiene procedimiento, a su pestaña Procedimiento."""
    if link.procedure_id:
        return s1_portal.back(link.procedure, entries)
    return redirect(f"{reverse('expedientes:nuevo_enlace', args=[link.pk])}"
                    f"?portal={s1_portal.pack(entries)}")


@require_http_methods(["GET", "POST"])
def nuevo(request):
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.SCREEN)
    error, existing, pasted = "", None, ""
    if request.method == "POST":
        pasted = request.POST.get("url", "")
        try:
            link = link_service.register_link(request.user, pasted, channel=Channel.SCREEN)
        except link_service.LinkRefused as refused:
            error = str(refused)
            existing = PortalLink.objects.filter(url=pasted.strip()).first()
        else:
            return redirect(reverse("expedientes:nuevo_enlace", args=[link.pk]))
    pliego = s1_pliego.context(request.user, None, request)
    context = _shell(request)
    context.update({"link": None, "error": error, "pasted": pasted, "existing": existing,
                    "pliego": pliego, "pliego_partial": s1_pliego.PARTIAL})
    return render(request, TEMPLATE, context)


@require_GET
def enlace(request, link_id):
    """Lo que encontró el sistema en el proceso, agrupado, con su aprobación."""
    link = _link(link_id)
    if link.procedure_id:
        return redirect(reverse("expedientes:procedimiento", args=[link.procedure_id]))
    view = s1_portal.link_view(request.user, link)
    context = _shell(request)
    context.update({
        "link": view, "messages": s1_portal.messages_for(request.GET.get("portal"), None),
        "confirm_kinds": s1_portal.CIRCULAR_CHOICES, "refresh": view["job"]["open"] and
        REFRESH_SECONDS, "new_url": reverse("expedientes:nuevo"),
    })
    return render(request, TEMPLATE, context)


@require_POST
def decidir(request, link_id):
    link = _link(link_id)
    had_procedure = bool(link.procedure_id)
    entries = s1_portal.decide_from_post(request.user, link, request.POST)
    link.refresh_from_db()
    if link.procedure_id and not had_procedure:
        entries.insert(0, s1_portal.entry(
            f"El procedimiento {link.procedure.number} quedó listo: ya están disponibles todas "
            "sus pestañas."))
    return _back(link, entries)


@require_POST
def revisar(request, link_id):
    link = _link(link_id)
    return _back(link, s1_portal.review_entries(request.user, link))


@require_POST
def dejar(request, link_id):
    link = _link(link_id)
    return _back(link, s1_portal.stop_entries(request.user, link))
