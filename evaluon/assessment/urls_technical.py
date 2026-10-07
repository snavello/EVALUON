"""Rutas del ok de la Comisión al informe técnico (T-168); `urls.py` las suma a las del espacio
`assessment`."""

from django.urls import path

from evaluon.assessment.views import technical, technical_report

urlpatterns = [
    path("oferta/<int:offer_id>/informe-tecnico/ok/", technical.give, name="technical_give"),
    path("oferta/<int:offer_id>/informe-tecnico/retirar/", technical.withdraw,
         name="technical_withdraw"),
    # El informe técnico del área: subirlo y pedir que el sistema proponga (T-190).
    path("oferta/<int:offer_id>/informe-tecnico/subir/", technical_report.upload_for_offer,
         name="report_upload"),
    path("procedimiento/<int:procedure_id>/informe-tecnico/subir/",
         technical_report.upload_for_procedure, name="report_upload_procedure"),
    path("oferta/<int:offer_id>/informe-tecnico/proponer/", technical_report.propose,
         name="report_propose"),
]
