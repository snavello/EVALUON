"""Subir el archivo de una norma y proponer sus datos (T-213; REQ-094, ADR-0051).

Documentos de prueba, públicos o sintéticos (P4):

- Reales y públicos: `corpus/normativa/` (Disposición AFIP 247/2022 y 297/2003 en página
  web de Infoleg, anexo de la 247 en PDF).
- Sintéticos, con la forma de los reales y contenido inventado: una resolución general, un
  decreto, armados en memoria en la forma de una página de Infoleg, y
  `tests/fixtures/dictamen-sintetico.pdf`.

Umbral del plan 014 (ADR-0051): al menos 8 de cada 10 datos correctos en cinco normas.
Se mide sobre las cinco juntas (40 de 50) y se informa cada una.
"""

import difflib
import unicodedata
from datetime import date
from pathlib import Path

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, Channel
from evaluon.norms.models import Document, Norm, NormUpload, ProposalState, Reading
from evaluon.norms.reading import read_document
from evaluon.norms.services import loading, upload
from evaluon.norms.splitting.header_fields import propose_fields

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus" / "normativa"
FIXTURES = REPO / "tests" / "fixtures"

FIELD_NAMES = tuple(loading.FIELDS)

# Lo que dicen los documentos, escrito a mano (el manifiesto del corpus, ADR-0006). La
# fecha de vigencia de la 247 y de la 297 la informó el responsable: los archivos no la
# dicen con fecha, así que el sistema no la propone.
TRUTH_247 = {
    "category": "regimen_especifico", "norm_type": "Disposición", "number": "247",
    "year": 2022, "issuer": "AFIP",
    # Lo que dice el artículo 1 entre comillas; la 247 no tiene otra línea de título.
    "title": "RÉGIMEN GENERAL PARA CONTRATACIONES DE BIENES, SERVICIOS Y OBRAS PÚBLICAS DE "
    "LA ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS",
    "citation": "Disposición AFIP 247/2022", "publication_date": date(2022, 11, 30),
    "effective_from": date(2023, 1, 1), "source": "disp-afip-247-2022-original.htm",
}
TRUTH_297 = {
    "category": "regimen_especifico", "norm_type": "Disposición", "number": "297",
    "year": 2003, "issuer": "AFIP",
    "title": "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas de "
    "la AFIP",
    "citation": "Disposición AFIP 297/2003", "publication_date": date(2003, 6, 13),
    "effective_from": date(2003, 6, 14), "source": "disp-afip-297-2003-original.htm",
}


def infoleg_page(lines):
    """Una página de Infoleg sintética: encabezado del sitio, un párrafo por línea."""
    body = "\n".join(f"<P>{line}</P>" for line in lines)
    html = (
        "<HTML><HEAD><META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; "
        "charset=windows-1252\"><TITLE>InfoLEG sintético</TITLE></HEAD><BODY>\n"
        f"{body}\n</BODY></HTML>"
    )
    return html.encode("cp1252")


RESOLUTION = infoleg_page([
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
])
DECREE = infoleg_page([
    "PODER EJECUTIVO NACIONAL",
    "Decreto 9.998/2023",
    "DECTO-2023-9998-APN-PTE",
    "Ciudad de Buenos Aires, 10/12/2023",
    "VISTO el expediente inventado, y",
    "CONSIDERANDO:",
    "Que es un decreto inventado.",
    "EL PRESIDENTE DE LA NACION ARGENTINA DECRETA:",
    "ARTÍCULO 1°.- Apruébase el “REGLAMENTO SINTÉTICO DE PRUEBA DE LAS COMPRAS”.",
    "ARTÍCULO 2°.- El presente decreto entrará en vigencia el 02/01/2024.",
    "ARTÍCULO 3°.- Comuníquese, publíquese y archívese.",
    "e. 11/12 N° 99999/23 v. 11/12/2023",
])
TRUTH_RESOLUTION = {
    "category": "otra_normativa", "norm_type": "Resolución General", "number": "9999",
    "year": 2024, "issuer": "ARCA",
    "title": "Procedimiento sintético de prueba para la presentación de formularios.",
    "citation": "Resolución General ARCA 9999/2024",
    "publication_date": date(2024, 3, 7), "effective_from": date(2024, 4, 1),
    "source": "rg-9999-2024.htm",
}
TRUTH_DECREE = {
    "category": "marco_nacional", "norm_type": "Decreto", "number": "9998",
    "year": 2023, "issuer": "Poder Ejecutivo Nacional",
    "title": "REGLAMENTO SINTÉTICO DE PRUEBA DE LAS COMPRAS",
    "citation": "Decreto 9998/2023", "publication_date": date(2023, 12, 11),
    "effective_from": date(2024, 1, 2), "source": "decreto-9998-2023.htm",
}
TRUTH_OPINION = {
    "category": "dictamen_legal", "norm_type": "Dictamen", "number": "99", "year": 2026,
    "issuer": None,
    "title": "consulta de prueba sobre la garantía de mantenimiento de oferta.",
    "citation": None, "publication_date": None,
    "effective_from": None, "source": "dictamen-sintetico.pdf",
}


def _plain(text):
    decomposed = unicodedata.normalize("NFKD", str(text).lower())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def _same(field, proposed, truth):
    if field == "title":
        return difflib.SequenceMatcher(None, _plain(proposed), _plain(truth)).ratio() >= 0.9
    return proposed == truth


def _proposal(data, name):
    found = propose_fields(read_document(data), name)
    return {n: (found[n].value if found[n] else None) for n in FIELD_NAMES}, found


def _score(data, name, truth):
    values, _ = _proposal(data, name)
    return {n: values[n] is not None and _same(n, values[n], truth[n]) for n in FIELD_NAMES}


# Norma, nombre del archivo, datos esperados.
SAMPLES = [
    ((CORPUS / "disp-afip-247-2022-original.htm").read_bytes(),
     "disp-afip-247-2022-original.htm", TRUTH_247),
    ((CORPUS / "disp-afip-297-2003-original.htm").read_bytes(),
     "disp-afip-297-2003-original.htm", TRUTH_297),
    (RESOLUTION, "rg-9999-2024.htm", TRUTH_RESOLUTION),
    (DECREE, "decreto-9998-2023.htm", TRUTH_DECREE),
    ((FIXTURES / "dictamen-sintetico.pdf").read_bytes(), "dictamen-sintetico.pdf",
     TRUTH_OPINION),
]


# --- Umbral y datos no reconocidos -----------------------------------------------------


def test_at_least_eight_of_ten_data_are_correct_in_five_public_norms():
    """REQ-094 (umbral del plan 014): 40 de 50 datos correctos en cinco normas. Los datos
    que las reglas no pueden saber (la vigencia en plazos, el organismo del dictamen, las
    fechas de un dictamen) no cuentan como aciertos."""
    report = {}
    for data, name, truth in SAMPLES:
        report[name] = _score(data, name, truth)
    correct = sum(sum(flags.values()) for flags in report.values())
    assert correct >= 40, {name: [n for n, ok in flags.items() if not ok]
                           for name, flags in report.items()}


def test_the_proposal_is_never_a_wrong_value_where_the_file_says_otherwise():
    """REQ-094: ningún dato propuesto contradice lo que dice el documento. Lo que no se
    reconoce queda sin valor, no con uno equivocado."""
    for data, name, truth in SAMPLES:
        values, _ = _proposal(data, name)
        wrong = [n for n in FIELD_NAMES
                 if values[n] is not None and not _same(n, values[n], truth[n])
                 and n != "source"]
        assert wrong == [], (name, wrong)


def test_a_date_in_working_days_is_not_calculated_so_the_effective_date_is_not_proposed():
    """REQ-094 (plan 001: el sistema no calcula la vigencia): la 247/2022 dice «a partir
    de los veinte días hábiles desde su publicación» y la 297/03 «a partir del día
    siguiente»; en ninguna se propone fecha de vigencia."""
    for data, name, _ in SAMPLES[:2]:
        values, _ = _proposal(data, name)
        assert values["effective_from"] is None, name


def test_the_annex_does_not_take_the_number_of_the_norm_it_replaces():
    """REQ-094: el anexo de la 247/2022 dice en su referencia «Disposición N° 297/03», la
    norma que sustituye. No es su número: tipo, número y año quedan sin reconocer."""
    data = (CORPUS / "disp-afip-247-2022-anexo.pdf").read_bytes()
    values, found = _proposal(data, "disp-afip-247-2022-anexo.pdf")
    assert values["norm_type"] is None and values["number"] is None
    assert values["year"] is None and values["citation"] is None
    assert values["issuer"] == "AFIP"
    assert values["title"].startswith("RÉGIMEN GENERAL PARA CONTRATACIONES")


def test_each_proposed_data_names_its_page_and_text():
    """REQ-094: cada dato propuesto trae su evidencia: la página (vacía en una página
    web) y el texto de donde salió."""
    values, found = _proposal(
        (FIXTURES / "dictamen-sintetico.pdf").read_bytes(), "dictamen-sintetico.pdf"
    )
    number = found["number"]
    assert number.page == 1 and "99/2026" in number.text
    web = propose_fields(read_document(RESOLUTION), "rg.htm")
    assert web["publication_date"].page is None
    assert web["publication_date"].text.startswith("e. 07/03/2024")


# --- stage ---------------------------------------------------------------------------


def stage_resolution(user, name="rg-9999-2024.htm", data=RESOLUTION):
    return upload.stage(user, data, name)


@pytest.mark.django_db
def test_stage_keeps_the_file_and_proposes_each_data_with_its_evidence(read_write_user):
    """REQ-094: subir el archivo lo guarda en `norms_upload` y propone los diez datos; lo
    no reconocido queda marcado."""
    staged = stage_resolution(read_write_user)

    staged.refresh_from_db()
    assert staged.state == ProposalState.PROPUESTO
    assert staged.file_format == "html" and bytes(staged.content) == RESOLUTION
    assert staged.uploaded_by == read_write_user
    fields = staged.proposal["fields"]
    assert set(fields) == set(FIELD_NAMES)
    assert fields["number"]["propuesto"] == "9999"
    assert fields["number"]["reconocido"] is True
    assert fields["number"]["evidencia"]["texto"] == "Resolución General 9999/2024"
    assert fields["publication_date"]["propuesto"] == "2024-03-07"
    assert fields["effective_from"]["propuesto"] == "2024-04-01"
    assert fields["number"]["corregido"] is None


@pytest.mark.django_db
def test_what_is_not_recognized_is_marked(read_write_user):
    """REQ-094: «lo no reconocido queda marcado»: sin valor, sin evidencia, a completar."""
    data = infoleg_page(["Un texto cualquiera sin encabezado de norma.", "Otra línea."])
    staged = upload.stage(read_write_user, data, "sin-encabezado.htm")

    fields = staged.proposal["fields"]
    for name in FIELD_NAMES:
        if name == "source":
            continue
        assert fields[name]["reconocido"] is False, name
        assert fields[name]["propuesto"] is None and fields[name]["evidencia"] is None
    assert fields["source"]["propuesto"] == "sin-encabezado.htm"


@pytest.mark.django_db
def test_stage_records_the_event(read_write_user):
    """REQ-094 (P6): subir deja un hecho `norm_upload` con el archivo, qué se reconoció y
    qué no."""
    staged = stage_resolution(read_write_user)

    event = AuditEvent.objects.get(event_type="norm_upload")
    assert event.outcome == "ok" and event.channel == Channel.SCREEN
    assert event.user == read_write_user
    assert event.detail["action"] == "stage" and event.detail["upload"] == staged.pk
    assert event.detail["file"]["sha256"] == staged.file_sha256
    assert "number" in event.detail["recognized"]


@pytest.mark.django_db
def test_stage_needs_the_read_write_role(read_user):
    """REQ-094: sin el rol de lectura y escritura no se sube nada."""
    with pytest.raises(RoleRejected):
        upload.stage(read_user, RESOLUTION, "rg.htm")
    assert NormUpload.objects.count() == 0


@pytest.mark.django_db
def test_a_file_already_loaded_is_rejected_as_the_load_does(read_write_user):
    """REQ-094: un archivo repetido se rechaza como hoy, con la misma excepción y mensaje
    que la carga; no queda ninguna subida."""
    values = {n: v for n, v in TRUTH_RESOLUTION.items()}
    loading.load_norm(read_write_user, data=RESOLUTION, file_name="rg.htm", **values)

    with pytest.raises(loading.FileAlreadyLoaded, match="ya está cargado"):
        upload.stage(read_write_user, RESOLUTION, "otra-copia.htm")

    assert NormUpload.objects.count() == 0
    rejected = AuditEvent.objects.get(event_type="norm_upload")
    assert rejected.outcome == "rejected" and rejected.detail["action"] == "stage"


@pytest.mark.django_db
def test_a_file_already_waiting_is_rejected(read_write_user):
    """REQ-094: el mismo archivo no se sube dos veces mientras espera confirmación."""
    first = stage_resolution(read_write_user)

    with pytest.raises(upload.AlreadyStaged):
        stage_resolution(read_write_user, name="otra-copia.htm")

    assert NormUpload.objects.get().pk == first.pk


@pytest.mark.django_db
def test_a_file_that_is_not_a_pdf_nor_a_web_page_is_rejected(read_write_user):
    """REQ-094: un archivo que no se puede leer no se sube."""
    with pytest.raises(loading.UnreadableFile):
        upload.stage(read_write_user, b"no es ni pdf ni web", "raro.bin")
    assert NormUpload.objects.count() == 0


# --- correct -------------------------------------------------------------------------


@pytest.mark.django_db
def test_correct_keeps_the_proposed_the_corrected_the_reason_who_and_when(read_write_user):
    """REQ-094 («Escribe el valor y motivo»): queda el valor propuesto, el corregido, el
    motivo, quién y cuándo."""
    staged = stage_resolution(read_write_user)

    upload.correct(read_write_user, staged.pk, "title", "Título corregido a mano",
                   "El título del archivo está incompleto")

    entry = NormUpload.objects.get(pk=staged.pk).proposal["fields"]["title"]
    assert entry["propuesto"].startswith("Procedimiento sintético")
    assert entry["corregido"] == "Título corregido a mano"
    assert entry["motivo"] == "El título del archivo está incompleto"
    assert entry["quien"] == read_write_user.get_username()
    assert entry["cuando"]
    event = AuditEvent.objects.filter(event_type="norm_upload").latest("pk")
    assert event.detail["action"] == "correct" and event.detail["field"] == "title"
    assert event.detail["corregido"] == "Título corregido a mano"
    assert event.detail["motivo"] == "El título del archivo está incompleto"


@pytest.mark.django_db
def test_a_second_correction_does_not_lose_the_first(read_write_user):
    """REQ-094: corregir de nuevo conserva el propuesto original y la lista de
    correcciones."""
    staged = stage_resolution(read_write_user)
    upload.correct(read_write_user, staged.pk, "number", "9998", "primer intento")
    upload.correct(read_write_user, staged.pk, "number", "9997", "segundo intento")

    entry = NormUpload.objects.get(pk=staged.pk).proposal["fields"]["number"]
    assert entry["propuesto"] == "9999" and entry["corregido"] == "9997"
    assert [c["valor"] for c in entry["correcciones"]] == ["9998", "9997"]


@pytest.mark.django_db
def test_a_data_not_recognized_is_completed_with_value_and_reason(read_write_user):
    """REQ-094 (ADR-0051): lo que el sistema no reconoció se completa del mismo modo, con
    el motivo «no reconocido»; la fecha se guarda como AAAA-MM-DD."""
    data = infoleg_page(["Un texto cualquiera sin encabezado de norma."])
    staged = upload.stage(read_write_user, data, "sin-encabezado.htm")

    upload.correct(read_write_user, staged.pk, "publication_date", "2024-03-07",
                   "no reconocido")

    entry = NormUpload.objects.get(pk=staged.pk).proposal["fields"]["publication_date"]
    assert entry["propuesto"] is None and entry["reconocido"] is False
    assert entry["corregido"] == "2024-03-07"


@pytest.mark.django_db
@pytest.mark.parametrize("reason", ["", "   ", None])
def test_a_correction_without_reason_is_refused(read_write_user, reason):
    """REQ-094: el motivo es obligatorio; sin él no se corrige nada."""
    staged = stage_resolution(read_write_user)

    with pytest.raises(upload.InvalidCorrection, match="motivo"):
        upload.correct(read_write_user, staged.pk, "number", "1", reason)

    entry = NormUpload.objects.get(pk=staged.pk).proposal["fields"]["number"]
    assert entry["corregido"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("field,value", [
    ("category", "inventada"), ("year", "veintidós"), ("publication_date", "31/12/2024"),
    ("title", "  "), ("no_existe", "x"),
])
def test_an_invalid_value_is_refused(read_write_user, field, value):
    """REQ-094: el valor se valida como lo hace la carga (categoría, año, fecha)."""
    staged = stage_resolution(read_write_user)

    with pytest.raises(upload.InvalidCorrection):
        upload.correct(read_write_user, staged.pk, field, value, "motivo")


@pytest.mark.django_db
def test_correct_needs_role_and_a_pending_upload(read_write_user, read_user):
    """REQ-094: corregir pide el rol de lectura y escritura y una subida que espere."""
    staged = stage_resolution(read_write_user)
    with pytest.raises(RoleRejected):
        upload.correct(read_user, staged.pk, "number", "1", "motivo")
    with pytest.raises(upload.UploadNotFound):
        upload.correct(read_write_user, staged.pk + 100, "number", "1", "motivo")
    NormUpload.objects.filter(pk=staged.pk).update(state=ProposalState.FALLIDO)
    with pytest.raises(upload.UploadNotPending):
        upload.correct(read_write_user, staged.pk, "number", "1", "motivo")


# --- confirm -------------------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_loads_the_norm_as_the_command_does(read_write_user):
    """REQ-094: confirmar llama a `load_norm` con los datos confirmados y crea la norma, el
    documento, el original y la lectura pendiente, igual que el comando; la subida queda
    aprobada con su documento."""
    staged = stage_resolution(read_write_user)
    upload.correct(read_write_user, staged.pk, "title", "Procedimiento sintético",
                   "título más corto")

    result = upload.confirm(read_write_user, staged.pk)

    norm = Norm.objects.get()
    assert (norm.norm_type, norm.number, norm.year, norm.issuer) == (
        "resolucion general", "9999", 2024, "afip")  # ARCA y AFIP, el mismo organismo (ADR-0010)
    assert norm.citation == "Resolución General ARCA 9999/2024"
    assert norm.title == "Procedimiento sintético" and norm.category == "otra_normativa"
    document = Document.objects.get()
    assert document == result.document
    assert document.publication_date == date(2024, 3, 7)
    assert document.effective_from == date(2024, 4, 1)
    assert document.source == "rg-9999-2024.htm" and document.in_use is False
    assert document.file_sha256 == staged.file_sha256
    assert Reading.objects.get().status == "pending"
    staged.refresh_from_db()
    assert staged.state == ProposalState.APROBADO and staged.document == document
    load = AuditEvent.objects.get(event_type="load")
    assert load.outcome == "ok" and load.channel == Channel.SCREEN
    confirm = AuditEvent.objects.filter(event_type="norm_upload").latest("pk")
    assert confirm.detail["action"] == "confirm"
    assert confirm.detail["document"] == document.pk
    assert confirm.detail["fields"]["title"]["motivo"] == "título más corto"


@pytest.mark.django_db
def test_confirm_without_a_required_data_does_not_load_anything(read_write_user):
    """REQ-094: si falta un dato (aquí la vigencia de la 247), no se carga y se dice cuál."""
    data, name, _ = SAMPLES[0]
    staged = upload.stage(read_write_user, data, name)

    with pytest.raises(upload.MissingConfirmedData, match="fecha de vigencia") as error:
        upload.confirm(read_write_user, staged.pk)

    assert error.value.missing == ["effective_from"]
    assert Norm.objects.count() == 0 and Document.objects.count() == 0
    staged.refresh_from_db()
    assert staged.state == ProposalState.PROPUESTO

    upload.correct(read_write_user, staged.pk, "effective_from", "2023-01-01",
                   "no reconocido")
    result = upload.confirm(read_write_user, staged.pk)
    assert result.norm.citation == "Disposición AFIP 247/2022"
    assert result.document.effective_from == date(2023, 1, 1)


@pytest.mark.django_db
def test_a_refused_load_leaves_the_upload_waiting_and_keeps_the_refusal(read_write_user):
    """REQ-094 (aviso de T-193: aprobar y crear el objeto en una transacción): si la carga
    rechaza (la norma existe con otro título), no queda aprobada la subida ni nada
    cargado, y el rechazo de la carga queda registrado."""
    first = stage_resolution(read_write_user)
    upload.confirm(read_write_user, first.pk)
    other = infoleg_page(["Distinto", "Resolución General 9999/2024"])
    second = upload.stage(read_write_user, other, "otra.htm")
    for name, value in (("title", "Un título distinto"), ("category", "otra_normativa"),
                        ("publication_date", "2024-03-07"),
                        ("effective_from", "2024-04-01"), ("issuer", "ARCA"),
                        ("citation", "Resolución General ARCA 9999/2024")):
        upload.correct(read_write_user, second.pk, name, value, "completo")

    with pytest.raises(loading.NormDataMismatch):
        upload.confirm(read_write_user, second.pk)

    second.refresh_from_db()
    assert second.state == ProposalState.PROPUESTO and second.document is None
    assert Document.objects.count() == 1
    refusal = AuditEvent.objects.filter(event_type="load", outcome="rejected").get()
    assert refusal.detail["reason"] == "norm_data_mismatch"
    last = AuditEvent.objects.filter(event_type="norm_upload").latest("pk")
    assert last.outcome == "rejected" and last.detail["action"] == "confirm"


@pytest.mark.django_db
def test_confirm_twice_or_without_role_is_refused(read_write_user, read_user):
    """REQ-094: una subida ya aprobada no se confirma de nuevo; sin rol, tampoco."""
    staged = stage_resolution(read_write_user)
    with pytest.raises(RoleRejected):
        upload.confirm(read_user, staged.pk)
    upload.confirm(read_write_user, staged.pk)

    with pytest.raises(upload.UploadNotPending):
        upload.confirm(read_write_user, staged.pk)
    assert Document.objects.count() == 1
