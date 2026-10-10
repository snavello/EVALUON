"""Página "Procedimientos" (REQ-022; plan 003, "Pantalla" y "Roles"; ADR-0005; T-069).

Una página armada en el servidor con la lista de procedimientos (número, objeto, fecha
de autorización, régimen y estado de la matriz) y el formulario para registrar uno. La
lista la da `services.procedures.list_procedures` y el alta,
`services.procedures.register_procedure`: las dos comprueban el rol de la Comisión, de
modo que un usuario sin ese rol recibe "acceso denegado" (403) y el rechazo queda
registrado.

Un alta correcta redirige a la lista con `?registrado=<id>`, para que recargar no vuelva
a registrar, y la página muestra arriba la línea de fecha y régimen con el texto fijo de
la 001 (`queries/_regime_line.html`), con el régimen calculado a la fecha del
procedimiento. Un formulario rechazado (dato vacío, fecha posterior al día, número
repetido) vuelve marcado y no registra nada.

La vista no guarda nada en la sesión, como las de la 001.
"""

from django import forms
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from evaluon.audit.models import Channel
from evaluon.queries.forms import DATE_INPUT_FORMATS, INVALID_DATE_ERROR
from evaluon.tenders.models import Procedure
from evaluon.tenders.services import procedures as services
from evaluon.journey.legacy import section_url, to_section

TEMPLATE = "tenders/procedures.html"

# Parámetro con que la redirección después del alta nombra al procedimiento registrado.
REGISTERED_PARAM = "registrado"


def _max_length(field):
    return Procedure._meta.get_field(field).max_length


class ProcedureForm(forms.Form):
    number = forms.CharField(label="Número del procedimiento",
                             max_length=_max_length("number"))
    procedure_type = forms.CharField(label="Tipo", max_length=_max_length("procedure_type"))
    subject = forms.CharField(label="Objeto", widget=forms.Textarea(attrs={"rows": 3}))
    authorization_date = forms.DateField(
        label="Fecha de autorización",
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": INVALID_DATE_ERROR},
    )

    def clean_authorization_date(self):
        value = self.cleaned_data["authorization_date"]
        if value > services.today():
            raise forms.ValidationError(services.FUTURE_DATE_MESSAGE)
        return value


def _registered_id(request):
    try:
        return int(request.GET.get(REGISTERED_PARAM, ""))
    except ValueError:
        return None


@to_section(lambda request: reverse("inicio"))
@require_http_methods(["GET", "POST"])
def procedures(request):
    """Lista y formulario. Al enviar, se valida el formulario y se llama a la función de
    alta; un rechazo vuelve al formulario marcado."""
    if request.method == "POST":
        form = ProcedureForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                registration = services.register_procedure(
                    request.user,
                    number=data["number"],
                    procedure_type=data["procedure_type"],
                    subject=data["subject"],
                    authorization_date=data["authorization_date"],
                    channel=Channel.SCREEN,
                )
            except services.ProcedureRefused as error:
                form.add_error(error.field, str(error))
            else:
                return redirect(
                    reverse("tenders:procedures")
                    + f"?{REGISTERED_PARAM}={registration.procedure.pk}"
                )
    else:
        form = ProcedureForm()

    rows = services.list_procedures(request.user, channel=Channel.SCREEN)
    registered_id = _registered_id(request) if request.method == "GET" else None
    registered = next(
        (row for row in rows if row.procedure.pk == registered_id), None
    )
    return render(request, TEMPLATE, {
        "form": form,
        "rows": rows,
        "registered": registered,
    })
