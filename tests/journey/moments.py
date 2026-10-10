"""Arma, paso a paso, los cinco momentos del caso chico inventado (T-217; REQ-075, REQ-097,
REQ-098) con los servicios reales y el modelo simulado: sin GPU, sin red y sin tocar la base
real. Todo el texto es inventado y público (P4).

Un solo procedimiento avanza por los cinco momentos: antes de importar (alta mínima), importado
(pliego leído), matriz propuesta (borrador con requisitos por confirmar), matriz validada y
evaluación terminada con pares propuestos.
"""

import datetime
import types
from unittest import mock

from django.utils import timezone

from evaluon.audit.models import Channel
from evaluon.offers import evaluation
from evaluon.tenders import models as m
from evaluon.tenders.services import procedures as tender_procedures
from evaluon.tenders.services import validation
from tests.assessment.test_matrix import add_run, requirement
from tests.offers.conftest import DATA, make_offer

MOMENTS = ("antes_de_importar", "importado", "matriz_propuesta", "matriz_validada",
           "evaluacion_terminada")
DECLARATION = "Declaro bajo juramento que me encuentro habilitado para contratar"


class _DraftOnly:
    """Hace que `evaluation._create_matrix` deje la versión en borrador, que es como la deja la
    propuesta del modelo: el resto del módulo `tenders.models` queda igual."""

    VersionStatus = types.SimpleNamespace(
        DRAFT=m.VersionStatus.DRAFT, VALIDATED=m.VersionStatus.DRAFT)

    def __getattr__(self, name):
        return getattr(m, name)


class Case:
    """El caso chico en construcción. Cada método lleva el procedimiento al momento siguiente."""

    def __init__(self, operator, evaluator, expected, number="CASO-CHICO-T217"):
        self.operator, self.evaluator, self.expected = operator, evaluator, expected
        self.number = number
        self.procedure = self.document = self.version = None
        self.offers = []
        self.done = []

    def antes_de_importar(self):
        registration = tender_procedures.register_procedure(
            self.operator, number=self.number, procedure_type="Contratación directa sintética",
            subject="Adquisición de insumos de oficina sintéticos (caso inventado)",
            authorization_date=datetime.date(2026, 1, 15), channel=Channel.COMMAND)
        self.procedure = registration.procedure

    def importado(self):
        self.document = evaluation._read_pliego(
            self.operator, self.procedure, DATA, self.expected.matrix["pliego"])

    def matriz_propuesta(self):
        with mock.patch.object(evaluation, "m", _DraftOnly()):
            self.version = evaluation._create_matrix(
                self.operator, self.procedure, self.document, self.expected.matrix["requisitos"])
        m.MatrixVersion.objects.filter(pk=self.version.pk).update(
            validated_at=None, validated_by=None)
        # Los cuatro primeros quedan propuestos: esperan que la Comisión los confirme.
        m.Requirement.objects.filter(version=self.version, number__lte=4).update(
            state=m.RequirementState.PROPUESTO)

    def matriz_validada(self):
        for row in self.version.requirements.all():
            m.Consequence.objects.create(
                requirement=row, consequence_type="desestimacion", grounds=[], origin="persona",
                chosen=True, chosen_by=self.operator, chosen_at=timezone.now(),
                chosen_note="Consecuencia elegida para el caso inventado.")
        validation.validate(self.evaluator, self.version.pk)

    def evaluacion_terminada(self):
        first = make_offer(self.procedure, self.operator, "Oferente A", {
            "oferta.pdf": [f"{DECLARATION}. Oferente A. Texto de la oferta."]})
        second = make_offer(self.procedure, self.operator, "Oferente B", {
            "oferta.pdf": ["Texto de la oferta del oferente B."]})
        self.offers = [first, second]
        declaration = requirement(self.procedure, "declaración jurada")
        registry = requirement(self.procedure, "constancia de inscripción")
        add_run(self.operator, self.procedure, first,
                {declaration: "cumple", registry: "cumple"})
        add_run(self.operator, self.procedure, second,
                {declaration: "no_cumple", registry: ("no_determinado", "duda")})

    def go_to(self, moment):
        """Lleva el caso hasta `moment`, pasando por los anteriores que falten."""
        for step in MOMENTS[len(self.done):MOMENTS.index(moment) + 1]:
            getattr(self, step)()
            self.done.append(step)
