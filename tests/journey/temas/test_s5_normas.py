"""Tema «subir, leer y validar normas» de la sección Normativas (REQ-094, REQ-097; plan 014, T-214).

Las normas de prueba son páginas de Infoleg sintéticas, con contenido inventado (P4). Los
embeddings se simulan: no se usa la GPU."""

import datetime
import html as htmllib
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse

from evaluon.accounts.models import CommissionRole, Role
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.journey.sections import sections_for
from evaluon.journey.temas import s5_normas
from evaluon.norms.models import (
    Document,
    Norm,
    NormUpload,
    Passage,
    Reading,
    ReadingStatus,
)
from evaluon.norms.reading import read_document
from evaluon.norms.services import loading, upload, validation
from evaluon.norms.splitting.header_fields import propose_fields
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)
from tests.norms.test_upload_proposal import infoleg_page

pytestmark = pytest.mark.django_db

LINES = [
    "AGENCIA DE RECAUDACION Y CONTROL ADUANERO",
    "Resolución General 9999/2024",
    "Procedimiento sintético de prueba para la presentación de formularios.",
    "Ciudad de Buenos Aires, 05/03/2024",
    "VISTO el Expediente N° 1 inventado, y",
    "CONSIDERANDO:",
    "Que se trata de un texto inventado para probar la lectura.",
    "Por ello,",
    "EL DIRECTOR GENERAL DE LA AGENCIA RESUELVE:",
    "ARTÍCULO 1°.- Aprobar el procedimiento sintético.",
    "ARTÍCULO 2°.- Esta resolución entrará en vigencia el 1 de abril de 2024.",
    "ARTÍCULO 3°.- Comuníquese y archívese.",
    "e. 07/03/2024 N° 12345/24 v. 07/03/2024",
]
NORM_FILE = infoleg_page(LINES)
# La misma norma sin decir desde cuándo rige: ese dato queda sin reconocer.
NORM_WITHOUT_DATE = infoleg_page(
    [line for line in LINES if "vigencia" not in line]
    + ["ARTÍCULO 4°.- Rige según se informe."])


def make_user(name, role=Role.READ_WRITE, commission=CommissionRole.EVALUATOR):
    return get_user_model().objects.create_user(
        username=name, password=TEST_PASSWORD, role=role, commission_role=commission)


@pytest.fixture
def evaluator(db):
    """Evaluador de la Comisión con el rol de normativa de lectura y escritura."""
    return make_user("evaluador-normas")


@pytest.fixture
def operator(db):
    """Operador de la Comisión con el rol de normativa de lectura y escritura."""
    return make_user("operador-normas", commission=CommissionRole.OPERATOR)


@pytest.fixture(autouse=True)
def embeddings(fake_embeddings):
    return fake_embeddings


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:normativas", args=[procedure.pk])


def url(name, procedure, *args):
    return reverse(f"expedientes:{name}", args=[procedure.pk, *args])


def page(client, procedure, query=""):
    response = client.get(tab(procedure) + query)
    assert response.status_code == 200
    return response.content.decode()


def notice(client, response):
    """El aviso que muestra la pestaña tras una acción: (ok, texto)."""
    assert response.status_code == 302
    assert response["Location"].startswith(tab_prefix())
    html = client.get(response["Location"]).content.decode()
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)" id="s5-aviso"[^>]*>(.*?)</p>',
                      html, re.S)
    assert found, "la pestaña no muestra el aviso de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


def tab_prefix():
    return "/expedientes/"


def send(client, procedure, data=NORM_FILE, name="rg-9999-2024.htm"):
    return client.post(url("s5_subir", procedure),
                       {"file": SimpleUploadedFile(name, data)})


def correct(client, procedure, upload_id, field, value, reason="Dato escrito por la Comisión"):
    return client.post(url("s5_corregir", procedure, upload_id),
                       {"field": field, "value": value, "reason": reason})


def complete_and_load(client, procedure, user, data=NORM_FILE, name="rg-9999-2024.htm"):
    """Sube la norma, completa lo que no se reconoció y la carga. Devuelve la lectura."""
    log_in(client, user)
    send(client, procedure, data, name)
    staged = NormUpload.objects.get(file_name=name)
    for field, entry in staged.proposal["fields"].items():
        if field in loading.REQUIRED and entry["propuesto"] is None:
            value = {"effective_from": "2024-04-01"}.get(field, "dato escrito")
            correct(client, procedure, staged.pk, field, value)
    response = client.post(url("s5_cargar", procedure, staged.pk), {"kind": "texto"})
    staged.refresh_from_db()
    return staged, response


# --- Subir el archivo y ver lo que propone el sistema (REQ-094) ------------------------------


def test_the_tab_offers_upload_and_lists_nothing_at_first(client, procedure, evaluator):
    """REQ-094, REQ-097: «Subir una norma» siempre a la vista, y la lista vacía lo dice."""
    log_in(client, evaluator)
    html = page(client, procedure)
    assert "Subir una norma" in html and 'type="file"' in html
    assert "Todavía no hay normas cargadas" in html
    section = sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas")
    assert section.upload_url.endswith("#s5-subir")
    assert 'href="' + section.upload_url + '"' in html


def test_uploading_the_file_shows_the_proposed_data_with_their_evidence(
        client, procedure, evaluator):
    """REQ-094, «Solo subir el archivo»: se sube el archivo, no se tipea nada, y cada dato
    propuesto muestra de dónde sale; lo que no se reconoce queda marcado."""
    log_in(client, evaluator)
    ok, text = notice(client, send(client, procedure))
    assert ok and "rg-9999-2024.htm" in text
    staged = NormUpload.objects.get()
    assert staged.state == "propuesto" and staged.uploaded_by == evaluator
    html = page(client, procedure)
    assert f'id="s5-subida-{staged.pk}"' in html
    assert "Para confirmar: «rg-9999-2024.htm»" in html
    assert "9999" in html and "Resolución General" in html
    assert re.search(r'class="evidencia">[^<]*«[^<]*9999', html)  # la evidencia
    assert "Cargar la norma" in html


def test_what_the_system_does_not_recognize_is_marked_and_blocks_the_load(
        client, procedure, evaluator):
    """REQ-094: un dato obligatorio sin reconocer queda marcado y la carga espera."""
    log_in(client, evaluator)
    send(client, procedure, NORM_WITHOUT_DATE, "sin-vigencia.htm")
    staged = NormUpload.objects.get()
    assert staged.proposal["fields"]["effective_from"]["propuesto"] is None
    html = page(client, procedure)
    assert "No se reconoció: complételo" in html
    assert re.search(r'<button class="btn primario" type="submit" disabled>Cargar la norma', html)
    refused = client.post(url("s5_cargar", procedure, staged.pk), {"kind": "texto"})
    ok, text = notice(client, refused)
    assert not ok and "fecha de vigencia" in text
    assert not Norm.objects.exists()


def test_an_unreadable_file_and_a_repeated_file_are_refused_with_a_notice(
        client, procedure, evaluator):
    """REQ-094: el archivo ilegible o repetido se rechaza con su motivo y no cambia nada."""
    log_in(client, evaluator)
    ok, text = notice(client, send(client, procedure, b"esto no es una norma", "x.pdf"))
    assert not ok and "No se subió nada" in text
    assert not NormUpload.objects.exists()
    send(client, procedure)
    ok, text = notice(client, send(client, procedure))
    assert not ok and "espera confirmación" in text
    assert NormUpload.objects.count() == 1
    ok, text = notice(client, client.post(url("s5_subir", procedure), {}))
    assert not ok and "Elija el archivo" in text


# --- Escribir el valor y el motivo -----------------------------------------------------------


def test_a_correction_needs_the_value_and_the_reason_and_keeps_what_was_proposed(
        client, procedure, evaluator):
    """REQ-094, «Escribe el valor y motivo»: sin motivo no se guarda; con motivo queda el valor
    propuesto, el nuevo, quién y cuándo."""
    log_in(client, evaluator)
    send(client, procedure)
    staged = NormUpload.objects.get()
    proposed = staged.proposal["fields"]["title"]["propuesto"]
    ok, text = notice(client, correct(client, procedure, staged.pk, "title", "Otro título", " "))
    assert not ok and "motivo" in text
    staged.refresh_from_db()
    assert staged.proposal["fields"]["title"]["corregido"] is None

    ok, _ = notice(client, correct(client, procedure, staged.pk, "title", "Otro título",
                                   "El título figura así en el sitio"))
    assert ok
    staged.refresh_from_db()
    entry = staged.proposal["fields"]["title"]
    assert entry["propuesto"] == proposed and entry["corregido"] == "Otro título"
    assert entry["quien"] == evaluator.username and entry["cuando"]
    html = page(client, procedure)
    assert "Otro título" in html and "El título figura así en el sitio" in html
    assert htmllib.escape(proposed, quote=False) in html or proposed in html
    assert AuditEvent.objects.filter(event_type=EventType.NORM_UPLOAD, channel=Channel.SCREEN,
                                     outcome=Outcome.OK, detail__action="correct").exists()


# --- Cargar, informe de lectura y validar (REQ-094) ------------------------------------------


def test_loading_the_norm_opens_its_reading_report_inside_the_tab(client, procedure, evaluator):
    """REQ-094: al cargar se ve el informe de lectura dentro de la pestaña, con «Validar la norma»
    al pie para el evaluador."""
    staged, response = complete_and_load(client, procedure, evaluator)
    assert staged.state == "aprobado" and staged.document_id
    ok, text = notice(client, response)
    assert ok and "falta que lo valide un evaluador" in text
    assert "lectura=" in response["Location"]
    html = client.get(response["Location"]).content.decode()
    assert "Informe de lectura · Resolución General" in html
    reading = staged.document.readings.get()
    assert htmllib.escape(reading.report_text.splitlines()[0], quote=False) in html
    assert "Validar la norma" in html
    assert "Cargada, sin validar" in html


def test_the_evaluator_validates_the_norm_from_the_screen(client, procedure, evaluator):
    """REQ-094: el evaluador valida sin comandos; la norma queda en uso y con su versión."""
    staged, response = complete_and_load(client, procedure, evaluator)
    reading = staged.document.readings.get()
    done = client.post(url("s5_validar", procedure, reading.pk))
    ok, text = notice(client, done)
    assert ok and "Se validó la lectura" in text and "versión" in text
    reading.refresh_from_db()
    assert reading.status == ReadingStatus.VALIDATED and reading.validated_by == evaluator
    staged.document.refresh_from_db()
    assert staged.document.in_use and staged.document.version_number == 1
    assert Passage.objects.filter(unit__reading=reading).exists()
    event = AuditEvent.objects.get(event_type=EventType.VALIDATION, outcome=Outcome.OK)
    assert event.channel == Channel.SCREEN and event.user == evaluator
    html = page(client, procedure)
    assert "Validada el " in html


def test_the_operator_uploads_and_loads_but_does_not_see_validate(client, procedure, operator):
    """REQ-091, REQ-094: el operador sube y carga, pero «Validar la norma» no se dibuja."""
    staged, response = complete_and_load(client, procedure, operator)
    assert staged.state == "aprobado"
    html = client.get(response["Location"]).content.decode()
    assert "Validar la norma" not in html
    assert "La validación la hace un evaluador de la Comisión" in html
    assert "el rol de evaluador de la Comisión" in html


def test_an_operator_posting_validate_gets_403_and_the_rejection_is_recorded(
        client, procedure, evaluator, operator):
    """P6, REQ-094: validar sin ser evaluador da 403, no cambia nada y deja el hecho."""
    staged, _ = complete_and_load(client, procedure, evaluator)
    reading = staged.document.readings.get()
    log_in(client, operator)
    before = AuditEvent.objects.filter(outcome=Outcome.REJECTED).count()
    response = client.post(url("s5_validar", procedure, reading.pk))
    assert response.status_code == 403
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() == before + 1
    reading.refresh_from_db()
    assert reading.status == ReadingStatus.PENDING
    assert not AuditEvent.objects.filter(event_type=EventType.VALIDATION).exists()


def test_a_user_without_a_commission_role_cannot_use_the_actions(client, procedure):
    """P6: sin rol de la Comisión, subir también da 403 y deja el rechazo."""
    outsider = make_user("sin-comision", commission=CommissionRole.NONE)
    log_in(client, outsider)
    before = AuditEvent.objects.filter(outcome=Outcome.REJECTED).count()
    response = send(client, procedure)
    assert response.status_code == 403
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() == before + 1
    assert not NormUpload.objects.exists()


def test_without_the_normativa_write_role_the_screen_says_which_role_is_missing(
        client, procedure):
    """REQ-094, plan 014: el evaluador sin el rol de normativa ve cuál le falta; y si lo fuerza,
    el servicio lo rechaza con 403 y deja el hecho."""
    only_commission = make_user("solo-comision", role=Role.READ)
    log_in(client, only_commission)
    html = page(client, procedure)
    assert "le falta el rol de normativa de lectura y escritura" in html
    assert 'type="file"' not in html
    before = AuditEvent.objects.filter(outcome=Outcome.REJECTED).count()
    assert send(client, procedure).status_code == 403
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() > before


def test_the_post_actions_return_to_the_tab_and_refuse_get(client, procedure, evaluator):
    """Las acciones son POST y vuelven a la pestaña de Normativas."""
    log_in(client, evaluator)
    assert client.get(url("s5_subir", procedure)).status_code == 405
    response = send(client, procedure)
    assert response["Location"].startswith(tab(procedure) + "?aviso=")


# --- El mismo resultado que con los comandos (REQ-094) ---------------------------------------


def snapshot():
    """Lo que dejan cargar y validar una norma, sin identificadores ni momentos."""
    norm = Norm.objects.get()
    document = Document.objects.get()
    reading = Reading.objects.get()
    return {
        "norm": (norm.category, norm.norm_type, norm.number, norm.year, norm.issuer, norm.title,
                 norm.citation, norm.general_regime),
        "document": (document.part, document.publication_date, document.effective_from,
                     document.effective_to, document.source, document.file_name,
                     document.file_format, document.file_sha256, document.in_use,
                     document.version_number),
        "reading": (reading.status, reading.sequence, reading.canonical_sha256,
                    reading.report_text, reading.units.count()),
        "passages": Passage.objects.count(),
        "load": AuditEvent.objects.filter(event_type=EventType.LOAD).count(),
        "validation": AuditEvent.objects.filter(event_type=EventType.VALIDATION,
                                                outcome=Outcome.OK).count(),
    }


def via_commands(user, name):
    """Lo que hacen `cargar_norma` y `validar_informe`: `load_norm` y `validate_reading` con los
    datos que lee el sistema del mismo archivo. Se deshace al terminar."""
    proposed = propose_fields(read_document(NORM_FILE), name)
    fields = {n: (proposed[n].value if proposed[n] else None) for n in loading.FIELDS}
    assert all(fields[n] is not None for n in loading.REQUIRED)
    with transaction.atomic():
        result = loading.load_norm(user, data=NORM_FILE, file_name=name, part=None,
                                   general_regime=False, channel=Channel.COMMAND, **fields)
        validation.validate_reading(user, result.reading.pk, channel=Channel.COMMAND)
        found = snapshot()
        transaction.set_rollback(True)
    return found


def test_uploading_and_validating_from_the_screen_gives_the_same_result_as_the_commands(
        client, procedure, evaluator, monkeypatch):
    """REQ-094: el resultado de subir y validar desde la pantalla es el mismo que con los
    comandos, que llaman a `load_norm` y `validate_reading` con estos mismos datos.

    El informe de lectura lleva la fecha de lectura al segundo (`read_at`): si las dos
    cargas caen en segundos distintos, `report_text` difiere sin que difiera la carga. Las
    dos leen aquí la hora de un mismo reloj detenido (T-224); `localtime` con un valor
    sigue igual."""
    real_localtime = loading.timezone.localtime
    frozen = real_localtime()
    monkeypatch.setattr(
        loading.timezone, "localtime",
        lambda value=None, timezone=None: real_localtime(
            frozen if value is None else value, timezone))
    name = "rg-9999-2024.htm"
    from_commands = via_commands(evaluator, name)
    assert not Norm.objects.exists()
    staged, _ = complete_and_load(client, procedure, evaluator, NORM_FILE, name)
    assert not [f for f, e in staged.proposal["fields"].items() if e["corregido"]]
    client.post(url("s5_validar", procedure, staged.document.readings.get().pk))
    from_screen = snapshot()
    assert from_screen == from_commands
    assert from_screen["reading"][0] == ReadingStatus.VALIDATED
    assert from_screen["load"] == 1 and from_screen["validation"] == 1


# --- La lista, los pendientes y los faltantes ------------------------------------------------


def test_the_list_shows_state_origin_and_local_times(client, procedure, evaluator):
    """REQ-097: cada norma con su estado, versión y de dónde vino; las fechas en hora local."""
    log_in(client, evaluator)
    staged, _ = complete_and_load(client, procedure, evaluator)
    # 01:30 UTC del 8/10 es el 7/10 22:30 en Buenos Aires.
    moment = datetime.datetime(2026, 10, 8, 1, 30, tzinfo=datetime.UTC)
    NormUpload.objects.filter(pk=staged.pk).update(uploaded_at=moment)
    send(client, procedure, NORM_WITHOUT_DATE, "otra.htm")
    NormUpload.objects.filter(file_name="otra.htm").update(uploaded_at=moment)
    html = page(client, procedure)
    assert "Resolución General ARCA 9999/2024" in html or "9999/2024" in html
    assert "sin versión" in html and "Cargada, sin validar" in html
    assert f"Archivo subido por {evaluator.username} el 07/10/2026" in html
    assert "subida por evaluador-normas el 07/10/2026 22:30" in html
    assert "08/10/2026 01:30" not in html


def test_unvalidated_norms_and_waiting_uploads_are_pending_and_amendments_are_missing(
        client, procedure, evaluator, make_norm, make_document, make_pending_amendment):
    """REQ-097: lo pendiente de validar y lo que espera confirmación se cuenta; la modificatoria
    registrada y sin cargar es un faltante con «Subir norma»."""
    base = sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas")
    assert base.pending == 0 and not base.tema_missing
    complete_and_load(client, procedure, evaluator)
    send(client, procedure, NORM_WITHOUT_DATE, "esperando.htm")
    target = make_norm()
    make_document(target)
    make_pending_amendment(target, norm_type="decreto", number="77", year=2020,
                           issuer="Poder Ejecutivo Nacional")
    section = sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas")
    assert section.pending == 2
    texts = " ".join(item.text for item in section.pending_items)
    assert "espera la validación" in texts and "esperando.htm" in texts
    missing = [m for m in section.tema_missing if "Modificatoria sin cargar" in m.text]
    assert len(missing) == 1 and "decreto 77/2020" in missing[0].text
    assert missing[0].action == "Subir norma" and missing[0].url.endswith("#s5-subir")
    assert any("sin validar" in detail for _, detail in section.summary)
    html = page(client, procedure)
    assert "Modificatorias sin cargar: decreto 77/2020" in html


def test_validating_removes_the_pending_item(client, procedure, evaluator):
    """REQ-097: validada la norma, deja de figurar entre los pendientes."""
    staged, _ = complete_and_load(client, procedure, evaluator)
    assert sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas").pending == 1
    client.post(url("s5_validar", procedure, staged.document.readings.get().pk))
    assert sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas").pending == 0


def test_the_norm_library_does_not_depend_on_the_procedure(evaluator, procedure):
    """La biblioteca de normas es común: el contexto se arma también sin procedimiento (la
    pantalla de alta lleva a la consulta general) y lista las mismas normas."""
    class Request:
        GET = {}

    with_procedure = s5_normas.context(evaluator, procedure, Request())
    without = s5_normas.context(evaluator, None, Request())
    assert without["pid"] is None and without["rows"] == with_procedure["rows"]


def test_the_tab_has_no_mockup_texts_nor_links_to_the_old_screens(client, procedure, evaluator):
    """Sin textos de la maqueta (ficticia, de ejemplo) ni enlaces a la pantalla vieja de
    normas o a las rutas de comandos."""
    complete_and_load(client, procedure, evaluator)
    html = page(client, procedure)
    block = html[html.index('class="s5-norm"'):]
    for text in ("(ficticia)", "de ejemplo", "[texto de ejemplo]", "Disp. AFIP 247/2022 (", "InfoLEG",
                 "listar_normas", "cargar_norma", "validar_informe", "manage.py"):
        assert text not in block, text
    assert "/recorrido/" not in block


def test_the_texts_are_plain_and_agree_in_number(client, procedure, evaluator):
    """Lenguaje de la Comisión: plurales bien, etiquetas con mayúscula, parte elegida sin claves
    internas y la marca de régimen general redactada sin ambigüedad."""
    log_in(client, evaluator)
    ok, text = notice(client, send(client, procedure, NORM_WITHOUT_DATE, "norma-anexo-ii.htm"))
    assert "(s)" not in text and re.search(r"leyó \(\d+ página", text)
    html = page(client, procedure)
    assert "(s)" not in html
    assert "Página web, 1 página ·" in html
    assert "Falta 1 dato obligatorio: escríbalo" in html
    assert "Categoría" in html and "Fecha de vigencia" in html and "categoría<" not in html
    assert "<small class=\"suave\"> · obligatorio</small>" in html
    assert "Texto de la norma" in html and "Anexo</option>" in html
    assert 'value="II"' in html
    assert "Esta norma es un régimen general de contrataciones (como la Disp. AFIP 247/2022" in html
    assert "clave del anexo" not in html and ">cuerpo<" not in html and 'value="cuerpo"' not in html
    section = sections_for(evaluator, procedure, channel=Channel.SCREEN).get("normativas")
    assert any("1 subida espera confirmar sus datos" in d for _, d in section.summary)


def test_choosing_annex_loads_the_norm_as_an_annex_part(client, procedure, evaluator):
    """«Anexo» con su nombre carga la parte `anexo-ii`; «Texto de la norma», el cuerpo."""
    log_in(client, evaluator)
    send(client, procedure)
    staged = NormUpload.objects.get()
    client.post(url("s5_cargar", procedure, staged.pk), {"kind": "anexo", "annex_name": "II"})
    staged.refresh_from_db()
    assert staged.state == "aprobado" and staged.document.part == "anexo-ii"
