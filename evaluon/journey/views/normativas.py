"""Página de Normativas general, sin procedimiento (REQ-094, REQ-096; T-225).

La normativa no está atada a ningún procedimiento: las normas cargadas sirven para todos. Esta
página tiene lo común de la pestaña Normativas (subir una norma, su informe de lectura, validarla y
la lista de normas, con el tema `s5_normas` y `procedure` en `None`) y lleva a la consulta general
de normativa, que pide la fecha de autorización. Lo propio de cada procedimiento (qué normas lo
rigen según su fecha) queda en su pestaña. Encabezado y pestañas como la pantalla de alta: el
desplegable de procedimientos y las cinco pestañas, con Normativas activa. Solo dibuja: las
acciones son las de `s5_normas` (P3).
"""

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections import SECTIONS
from evaluon.journey.sections import s5
from evaluon.journey.temas import s5_normas
from evaluon.journey.views.portada import DROPDOWN_LIMIT, ROLE_LABELS
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.normativas.general"


@require_GET
@memo.scoped
def general(request):
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.SCREEN)
    status = s5_normas.status(request.user, None)
    tabs = [{"label": module.LABEL, "key": module.KEY, "current": module.KEY == s5.KEY,
             "enabled": module.KEY in ("procedimiento", s5.KEY)} for module in SECTIONS]
    context = {
        "procedure": None, "active": s5.KEY, "tabs": tabs,
        "header_label": "Normativas (comunes a todos los procedimientos)",
        "procedures": Procedure.objects.order_by("-created_at", "-pk")[:DROPDOWN_LIMIT],
        "role_label": ROLE_LABELS.get(request.user.commission_role, ""),
        "login_url": reverse("accounts:login"),
        "normativas_url": reverse("expedientes:normativas_general"),
        "summary": s5.summary(request.user, None, ()),
        "t": s5_normas.context(request.user, None, request),
        "partial": s5_normas.PARTIAL,
        "pending_total": status.pending,
        "pending_rows": [(None, item) for item in status.pending_items],
        "missing": status.missing,
        "query_url": reverse("queries:screen"),
    }
    return render(request, "journey/normativas.html", context)
