"""Rutas de la normativa: entrega del documento original (REQ-002, T-036). La ruta
lleva nombre para que las citas (T-037) y la búsqueda (T-041) la enlacen:
`{% url "norms:original" document_id %}`."""

from django.urls import path

from evaluon.norms import views

app_name = "norms"

urlpatterns = [
    path(
        "documentos/<int:document_id>/original/",
        views.original,
        name="original",
    ),
]
