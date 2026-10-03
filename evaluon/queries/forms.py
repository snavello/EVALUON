"""Formularios de la pantalla de consulta: la pregunta y la búsqueda directa (REQ-010,
REQ-013, REQ-020; plan 001, "Fecha de autorización y régimen aplicado" y "Búsqueda
directa (REQ-010)").

La fecha de autorización se valida acá y otra vez en la función de consulta o de
búsqueda (T-019, T-041). Un campo vacío es válido: la función usa entonces la fecha del
día. Una fecha posterior al día se rechaza y no se consulta ni se busca. "Hoy" es la
fecha en hora de Buenos Aires (`TIME_ZONE`), calculada en cada pedido.

El formulario de búsqueda tiene su propio campo de fecha. Se usa con el prefijo
`SEARCH_PREFIX`, para que sus campos no repitan el nombre ni el `id` de los de la
pregunta (`search-reference_date`, `id_search-reference_date`).

La casilla "Incluir textos derogados" (`search-include_repealed`, T-056) viene apagada:
sin marcarla, la búsqueda muestra solo lo vigente a la fecha.
"""

from django import forms
from django.utils import timezone

from evaluon.norms.models import Norm, ReadingStatus

FUTURE_DATE_ERROR = "La fecha de autorización no puede ser posterior a hoy"
INVALID_DATE_ERROR = "Escriba una fecha válida, con día, mes y año"
DATE_LABEL = "Fecha de autorización del procedimiento"

# El control de fecha del navegador envía año-mes-día; si el navegador no lo tiene, la
# persona escribe día/mes/año, como se muestran las fechas en la pantalla.
DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y"]

SEARCH_PREFIX = "search"
SEARCH_EMPTY_ERROR = "Elija una norma y escriba un número de artículo, o escriba palabras para buscar."
SEARCH_NORM_MISSING_ERROR = "Para buscar por número de artículo, elija la norma."
SEARCH_BOTH_ERROR = "Busque por número de artículo o por palabras, no por los dos a la vez."
REPEALED_LABEL = "Incluir textos derogados"


def today():
    """Fecha del día en hora de Buenos Aires."""
    return timezone.localdate()


def reference_date_field():
    """Campo "Fecha de autorización del procedimiento", igual en los dos formularios."""
    return forms.DateField(
        label=DATE_LABEL,
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": INVALID_DATE_ERROR},
    )


def not_after_today(value):
    """La fecha recibida, o un error si es posterior al día."""
    if value is not None and value > today():
        raise forms.ValidationError(FUTURE_DATE_ERROR)
    return value


class QueryForm(forms.Form):
    question = forms.CharField(
        label="Pregunta",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    reference_date = reference_date_field()

    def clean_reference_date(self):
        return not_after_today(self.cleaned_data["reference_date"])


class NormChoiceField(forms.ModelChoiceField):
    """Lista de normas, cada una por su nombre de cita."""

    def label_from_instance(self, obj):
        return obj.citation


def searchable_norms():
    """Normas que tienen al menos un documento en uso con su lectura validada, por
    nombre de cita. Una norma sin validar no se ofrece (REQ-005); si a la fecha elegida
    no rige, la búsqueda lo dice."""
    return Norm.objects.filter(
        documents__in_use=True,
        documents__readings__status=ReadingStatus.VALIDATED,
    ).distinct().order_by("citation", "pk")


class SearchForm(forms.Form):
    """Búsqueda directa: por norma y número de artículo, o por palabras (en todas las
    normas o en la elegida), con su fecha de autorización."""

    norm = NormChoiceField(
        label="Norma",
        queryset=Norm.objects.none(),
        required=False,
        empty_label="Todas las normas",
    )
    article = forms.CharField(label="Número de artículo", required=False, max_length=30)
    words = forms.CharField(
        label="Palabras del texto",
        required=False,
        max_length=500,
        help_text="Para buscar una frase exacta, escríbala entre comillas.",
    )
    reference_date = reference_date_field()
    # Apagada de entrada: la búsqueda muestra solo lo vigente a la fecha (enmienda de
    # REQ-010 del 2026-10-03; T-056).
    include_repealed = forms.BooleanField(label=REPEALED_LABEL, required=False)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", SEARCH_PREFIX)
        super().__init__(*args, **kwargs)
        self.fields["norm"].queryset = searchable_norms()

    def clean_reference_date(self):
        return not_after_today(self.cleaned_data["reference_date"])

    def clean(self):
        cleaned = super().clean()
        article = (cleaned.get("article") or "").strip()
        words = (cleaned.get("words") or "").strip()
        if article and words:
            raise forms.ValidationError(SEARCH_BOTH_ERROR)
        if article and cleaned.get("norm") is None and "norm" not in self.errors:
            self.add_error("norm", SEARCH_NORM_MISSING_ERROR)
        elif not article and not words:
            raise forms.ValidationError(SEARCH_EMPTY_ERROR)
        cleaned["article"] = article
        cleaned["words"] = words
        return cleaned
