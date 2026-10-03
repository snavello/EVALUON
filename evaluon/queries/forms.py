"""Formulario de la pregunta de la pantalla de consulta (REQ-013, REQ-020; plan 001,
"Fecha de autorización y régimen aplicado").

La fecha de autorización se valida acá y otra vez en la función de consulta (T-019). Un
campo vacío es válido: la función de consulta usa entonces la fecha del día. Una fecha
posterior al día se rechaza y no se consulta. "Hoy" es la fecha en hora de Buenos Aires
(`TIME_ZONE`), calculada en cada pedido.
"""

from django import forms
from django.utils import timezone

FUTURE_DATE_ERROR = "La fecha de autorización no puede ser posterior a hoy"
INVALID_DATE_ERROR = "Escriba una fecha válida, con día, mes y año"

# El control de fecha del navegador envía año-mes-día; si el navegador no lo tiene, la
# persona escribe día/mes/año, como se muestran las fechas en la pantalla.
DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y"]


def today():
    """Fecha del día en hora de Buenos Aires."""
    return timezone.localdate()


class QueryForm(forms.Form):
    question = forms.CharField(
        label="Pregunta",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    reference_date = forms.DateField(
        label="Fecha de autorización del procedimiento",
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": INVALID_DATE_ERROR},
    )

    def clean_reference_date(self):
        value = self.cleaned_data["reference_date"]
        if value is not None and value > today():
            raise forms.ValidationError(FUTURE_DATE_ERROR)
        return value
