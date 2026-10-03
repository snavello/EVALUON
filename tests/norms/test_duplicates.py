"""Duplicados al cargar una norma (T-026; plan 001, "Ingesta", punto 2, "Una norma en más
de un archivo" y "Registro de auditoría").

Documentos de prueba, públicos o sintéticos (P4):

- `tests/fixtures/disp-247-2022-anexo-extracto.pdf` (T-012): páginas 1 a 6 del anexo de
  la Disposición AFIP 247/2022.
- Una copia del extracto guardada otra vez con pypdfium2, armada en memoria: otro
  archivo (otra huella) con el mismo texto canónico.
- Las páginas 5 y 6 del extracto, armadas en memoria: otro archivo con otro texto.
- `tests/fixtures/dictamen-sintetico.pdf` (T-024): un dictamen inventado.
"""

import hashlib
import io
from datetime import date
from io import StringIO
from pathlib import Path

import pypdfium2
import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError

from evaluon.accounts import permissions
from evaluon.audit.models import AuditEvent
from evaluon.norms.management.commands import cargar_norma
from evaluon.norms.models import Document, Norm, Reading
from evaluon.norms.services import loading
from tests.conftest import TEST_PASSWORD

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
EXTRACT = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
EXTRACT_BYTES = EXTRACT.read_bytes()
OPINION = FIXTURES / "dictamen-sintetico.pdf"

DATA_247 = {
    "category": "regimen_especifico",
    "norm_type": "Disposición",
    "number": "247",
    "year": 2022,
    "issuer": "AFIP",
    "title": "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas",
    "citation": "Disposición AFIP 247/2022",
    "publication_date": date(2022, 11, 30),
    "effective_from": date(2023, 1, 1),
    "source": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/"
    "375829/disp247.pdf",
}

# Un dictamen inventado, como el documento de prueba.
DATA_OPINION = {
    "category": "dictamen_legal",
    "norm_type": "Dictamen",
    "number": "1",
    "year": 2024,
    "issuer": "Servicio jurídico de prueba",
    "title": "Dictamen sintético de prueba",
    "citation": "Dictamen sintético 1/2024",
    "publication_date": date(2024, 3, 1),
    "effective_from": date(2024, 3, 1),
    "source": "tests/fixtures/dictamen-sintetico.pdf",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def resaved_extract():
    """El extracto guardado otra vez: otros bytes, el mismo texto."""
    source = pypdfium2.PdfDocument(EXTRACT_BYTES)
    target = pypdfium2.PdfDocument.new()
    target.import_pages(source)
    buffer = io.BytesIO()
    target.save(buffer)
    data = buffer.getvalue()
    assert data != EXTRACT_BYTES
    return data


def pages_five_and_six_pdf():
    """Las páginas 5 y 6 del extracto: otro archivo, con otro texto."""
    source = pypdfium2.PdfDocument(EXTRACT_BYTES)
    target = pypdfium2.PdfDocument.new()
    target.import_pages(source, [4, 5])
    buffer = io.BytesIO()
    target.save(buffer)
    return buffer.getvalue()


def load(user, data=EXTRACT_BYTES, file_name="disp-247-2022-anexo-extracto.pdf", **fields):
    values = {**DATA_247, "part": "anexo", "general_regime": True, **fields}
    return loading.load_norm(user, data=data, file_name=file_name, **values)


def put_in_use(document):
    """Deja un documento en uso como versión 1 de su parte, como lo deja la validación."""
    Document.objects.filter(pk=document.pk).update(version_number=1, in_use=True)


# --- Mismo archivo ------------------------------------------------------------------


@pytest.mark.django_db
def test_same_file_twice_warns_and_keeps_one_document(read_write_user):
    """REQ-011: el mismo archivo dos veces da un aviso y un solo documento, aun con una
    confirmación de misma norma: el mismo archivo nunca se incorpora."""
    first = load(read_write_user)

    with pytest.raises(loading.FileAlreadyLoaded, match="ese archivo ya está cargado"):
        load(read_write_user, same_norm_confirmation="other_file")

    assert Document.objects.count() == 1
    event = AuditEvent.objects.get(event_type="load", outcome="rejected")
    assert event.detail["reason"] == "file_already_loaded"
    assert event.detail["duplicate_checks"]["same_file"] == first.document.pk


# --- Misma norma y misma parte en otro archivo ---------------------------------------


@pytest.mark.django_db
def test_same_norm_and_part_in_other_file_is_not_incorporated_without_confirmation(
    read_write_user,
):
    """REQ-011: la misma norma y la misma parte desde otro archivo avisa "misma norma"
    y, sin confirmación expresa, no se incorpora."""
    first = load(read_write_user)

    with pytest.raises(loading.SameNormNotConfirmed) as raised:
        load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf")

    message = str(raised.value)
    assert "misma norma" in message
    assert "parte anexo" in message and "disp-247-2022-anexo-extracto.pdf" in message
    assert Document.objects.count() == 1
    assert [m["document"] for m in raised.value.matches] == [first.document.pk]
    assert raised.value.matches[0]["kind"] == "same_norm_part"


@pytest.mark.django_db
@pytest.mark.parametrize("confirmation", ["other_file", "new_version"])
def test_same_norm_and_part_with_confirmation_is_incorporated_not_in_use(
    read_write_user, confirmation
):
    """REQ-011: con confirmación expresa (otro archivo de lo mismo o versión nueva) se
    incorpora bajo la misma norma, con la confirmación guardada, fuera de uso y sin
    versión; el informe muestra el posible duplicado y lo pone en "Requiere
    atención"."""
    first = load(read_write_user)

    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  same_norm_confirmation=confirmation)

    assert Norm.objects.count() == 1 and second.norm == first.norm
    document = second.document
    assert document.same_norm_confirmation == confirmation
    assert document.in_use is False and document.version_number is None
    assert first.document.same_norm_confirmation == ""
    report = second.reading.report
    assert [d["document"] for d in report["duplicates"]] == [first.document.pk]
    assert report["duplicates"][0]["detail"]
    assert "duplicates" in [item["kind"] for item in report["attention"]]
    assert "Posibles duplicados: 1." in second.reading.report_text
    assert report["duplicates"][0]["detail"] in second.reading.report_text


@pytest.mark.django_db
def test_confirmation_can_be_asked_when_the_warning_appears(read_write_user):
    """REQ-011: la confirmación se puede pedir en el momento del aviso: la función de
    carga recibe el aviso con las coincidencias y la respuesta de la persona."""
    load(read_write_user)
    warnings = []

    def ask(warning):
        warnings.append(warning)
        return "new_version"

    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  confirm_same_norm=ask)

    assert len(warnings) == 1 and "misma norma" in warnings[0].message
    assert second.document.same_norm_confirmation == "new_version"


@pytest.mark.django_db
def test_declined_confirmation_is_not_incorporated(read_write_user):
    """REQ-011: si la persona no confirma, no se incorpora."""
    load(read_write_user)

    with pytest.raises(loading.SameNormNotConfirmed):
        load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
             confirm_same_norm=lambda warning: None)

    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_invalid_confirmation_value_is_rejected(read_write_user):
    """REQ-011: la confirmación es "otro archivo" o "versión nueva"; otro valor se
    rechaza sin incorporar."""
    with pytest.raises(loading.InvalidData, match="confirmación"):
        load(read_write_user, same_norm_confirmation="si")

    assert not Document.objects.exists()


# --- Mismo texto en otro archivo -----------------------------------------------------


@pytest.mark.django_db
def test_same_text_in_other_file_and_other_part_still_warns_same_norm(read_write_user):
    """REQ-011: el mismo texto canónico cargado desde otro archivo y con otra parte
    sigue avisando "misma norma": la comprobación de texto no mira la parte."""
    first = load(read_write_user)

    with pytest.raises(loading.SameNormNotConfirmed) as raised:
        load(read_write_user, data=resaved_extract(), file_name="copia.pdf",
             part="anexo-i")

    assert raised.value.matches[0]["kind"] == "same_text"
    assert raised.value.matches[0]["document"] == first.document.pk
    assert "mismo texto" in str(raised.value)
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_same_text_in_other_norm_warns_same_norm(read_write_user):
    """REQ-011: el mismo texto con los datos de otra norma también avisa "misma
    norma", porque el texto se compara contra todos los documentos."""
    load(read_write_user)

    with pytest.raises(loading.SameNormNotConfirmed):
        load(read_write_user, data=resaved_extract(), file_name="copia.pdf",
             number="999", citation="Disposición AFIP 999/2022")

    assert Norm.objects.count() == 1


# --- Otra parte de la misma norma ----------------------------------------------------


@pytest.mark.django_db
def test_annex_of_a_norm_with_its_body_is_added_without_confirmation(read_write_user):
    """REQ-011: el anexo de una norma que ya tiene cargado el cuerpo no es un duplicado:
    se incorpora sin confirmación, con el mensaje informativo, y queda una sola norma
    con dos documentos."""
    load(read_write_user, data=pages_five_and_six_pdf(), file_name="cuerpo.pdf",
         part="cuerpo")

    annex = load(read_write_user, citation=None)

    assert Norm.objects.count() == 1 and Document.objects.count() == 2
    assert annex.document.same_norm_confirmation == ""
    assert annex.notices == (
        "Se suma como parte anexo de la Disposición AFIP 247/2022, que ya tiene cargado "
        "el cuerpo.",
    )
    assert annex.reading.report["duplicates"] == []
    assert "Posibles duplicados: ninguno." in annex.reading.report_text


@pytest.mark.django_db
def test_different_effective_date_between_parts_is_warned(read_write_user):
    """REQ-011: si la fecha de vigencia indicada difiere de la de otra parte en uso de
    la misma norma, se avisa; el documento se incorpora igual, con la fecha escrita."""
    body = load(read_write_user, data=pages_five_and_six_pdf(), file_name="cuerpo.pdf",
                part="cuerpo")
    put_in_use(body.document)

    annex = load(read_write_user, effective_from=date(2023, 1, 2))

    assert annex.document.effective_from == date(2023, 1, 2)
    warning = [n for n in annex.notices if "fecha de vigencia" in n]
    assert warning == [
        "Atención: la fecha de vigencia indicada (2023-01-02) difiere de la de la parte "
        "cuerpo en uso (2023-01-01). Revísela antes de validar: las fechas de carga no "
        "se pueden corregir por comando."
    ]


@pytest.mark.django_db
def test_same_effective_date_between_parts_is_not_warned(read_write_user):
    """REQ-011: con la misma fecha de vigencia que la otra parte en uso no hay aviso."""
    body = load(read_write_user, data=pages_five_and_six_pdf(), file_name="cuerpo.pdf",
                part="cuerpo")
    put_in_use(body.document)

    annex = load(read_write_user)

    assert not [n for n in annex.notices if "fecha de vigencia" in n]


# --- Registro ------------------------------------------------------------------------


@pytest.mark.django_db
def test_refused_same_norm_is_recorded_with_the_checks(read_write_user):
    """REQ-012: una carga rechazada por "misma norma" sin confirmar queda registrada,
    con el resultado de las comprobaciones de duplicado."""
    first = load(read_write_user)
    copy = resaved_extract()

    with pytest.raises(loading.SameNormNotConfirmed):
        load(read_write_user, data=copy, file_name="copia.pdf")

    event = AuditEvent.objects.get(event_type="load", outcome="rejected")
    assert event.user == read_write_user
    assert event.detail["reason"] == "same_norm_not_confirmed"
    checks = event.detail["duplicate_checks"]
    assert checks["same_file"] is None
    assert checks["same_text"] == [first.document.pk]
    assert checks["same_norm_part"] == [first.document.pk]
    assert event.detail["same_norm_confirmation"] is None
    assert event.detail["file"]["sha256"] == sha256(copy)


@pytest.mark.django_db
def test_confirmed_load_records_checks_and_confirmation(read_write_user):
    """REQ-012: la carga confirmada deja en su hecho `load` las comprobaciones y la
    confirmación expresa."""
    first = load(read_write_user)

    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  same_norm_confirmation="other_file")

    detail = second.event.detail
    assert detail["same_norm_confirmation"] == "other_file"
    assert detail["duplicate_checks"]["same_norm_part"] == [first.document.pk]
    assert detail["duplicate_checks"]["same_text"] == []
    assert detail["duplicate_checks"]["new_part_of_norm"] is None


@pytest.mark.django_db
def test_added_part_records_checks_and_notices(read_write_user):
    """REQ-012: la carga de otra parte deja en su hecho `load` que se sumó a la norma y
    los avisos que se mostraron."""
    body = load(read_write_user, data=pages_five_and_six_pdf(), file_name="cuerpo.pdf",
                part="cuerpo")
    put_in_use(body.document)

    annex = load(read_write_user, effective_from=date(2023, 1, 2))

    detail = annex.event.detail
    assert detail["duplicate_checks"]["new_part_of_norm"] == body.norm.pk
    assert detail["duplicate_checks"]["existing_parts"] == ["cuerpo"]
    assert detail["notices"] == list(annex.notices)
    assert detail["same_norm_confirmation"] is None


@pytest.mark.django_db
def test_concurrent_load_gives_a_plain_message(read_write_user, monkeypatch):
    """REQ-011, REQ-012: si otra carga guarda el mismo archivo o la misma norma al mismo
    tiempo, la base lo impide y la persona recibe un mensaje llano; el intento queda
    registrado."""

    def collide(**fields):
        raise IntegrityError("duplicate key value violates unique constraint")

    monkeypatch.setattr(Document.objects, "create", collide)

    with pytest.raises(loading.ConcurrentLoad, match="al mismo tiempo"):
        load(read_write_user)

    assert not Norm.objects.exists()
    event = AuditEvent.objects.get(event_type="load")
    assert (event.outcome, event.detail["reason"]) == ("rejected", "concurrent_load")


# --- Informe: documento y categoría (avisos de T-024 y T-025) -------------------------


@pytest.mark.django_db
def test_report_document_part_has_file_name_hash_and_read_date(read_write_user):
    """REQ-004, REQ-012: la parte "Documento" del informe guardado trae el nombre del
    archivo, su huella y la fecha de lectura, en los datos y en el texto."""
    result = load(read_write_user)

    document = result.reading.report["document"]
    assert document["file_name"] == "disp-247-2022-anexo-extracto.pdf"
    assert document["file_sha256"] == sha256(EXTRACT_BYTES)
    assert document["read_at"]
    assert date.fromisoformat(document["read_at"][:10]) == result.reading.created_at.date()
    text = result.reading.report_text
    assert "Archivo: disp-247-2022-anexo-extracto.pdf." in text
    assert f"Huella del archivo: {sha256(EXTRACT_BYTES)}." in text
    assert f"Fecha de lectura: {document['read_at']}." in text


@pytest.mark.django_db
def test_loaded_opinion_is_split_into_points(read_write_user):
    """REQ-003, REQ-017: un dictamen cargado se parte con su regla, en puntos."""
    result = loading.load_norm(read_write_user, data=OPINION.read_bytes(),
                               file_name="dictamen-sintetico.pdf", **DATA_OPINION)

    keys = list(result.reading.units.order_by("order").values_list("key", flat=True))
    assert keys[:3] == ["punto-i", "punto-i/punto-1", "punto-i/punto-2"]
    assert set(result.reading.units.values_list("unit_type", flat=True)) == {"punto"}
    assert result.reading.report["rule"] == "dictamenes"


@pytest.mark.django_db
def test_opinion_as_annex_is_rejected_in_plain_words(read_write_user):
    """REQ-017: un dictamen se carga como documento único; con una parte de anexo se
    rechaza con un mensaje llano, sin incorporar."""
    with pytest.raises(loading.InvalidData, match="dictamen"):
        loading.load_norm(read_write_user, data=OPINION.read_bytes(),
                          file_name="dictamen-sintetico.pdf", part="anexo",
                          **DATA_OPINION)

    assert not Document.objects.exists()


@pytest.mark.django_db
def test_reading_has_no_pending_duplicates_section(read_write_user):
    """REQ-011, REQ-004: el informe guardado dice que los duplicados se comprobaron, y
    "Requiere atención" y el texto se volvieron a armar después de completarlos.

    El texto se compara con el que arma el informe tal como se guardó desde la carga
    (`result.reading.report`): el que se lee de la base es `jsonb`, que reordena las
    claves de las versiones de las herramientas."""
    from evaluon.norms.splitting.report import attention_items, report_text

    result = load(read_write_user)

    reading = Reading.objects.get()
    assert result.reading == reading
    assert reading.report == result.reading.report
    assert reading.report["duplicates"] == []
    assert "se comprueban al cargar" not in reading.report_text
    assert "Posibles duplicados: ninguno." in reading.report_text
    assert reading.report["attention"] == attention_items(reading.report)
    assert reading.report_text == report_text(result.reading.report)


# --- Comando cargar_norma ------------------------------------------------------------


COMMAND_ARGS = [
    "--categoria", "regimen_especifico",
    "--tipo", "Disposición",
    "--numero", "247",
    "--anio", "2022",
    "--organismo", "AFIP",
    "--titulo", DATA_247["title"],
    "--nombre", "Disposición AFIP 247/2022",
    "--fecha-publicacion", "2022-11-30",
    "--fecha-vigencia", "2023-01-01",
    "--fuente", DATA_247["source"],
]


@pytest.fixture
def keyboard(monkeypatch):
    """Simula lo que la persona escribe: la clave y, si se la piden, la respuesta a la
    confirmación de misma norma. Devuelve las preguntas que se le hicieron."""
    prompts = []

    def type_(answer=None):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)

        def fake_answer(prompt):
            prompts.append(prompt)
            if answer is None:
                raise AssertionError("no se esperaba una pregunta por teclado")
            return answer

        monkeypatch.setattr(cargar_norma, "ask_confirmation", fake_answer)
        return prompts

    return type_


def run(path, *args, user):
    out = StringIO()
    call_command("cargar_norma", str(path), *COMMAND_ARGS, *args, stdout=out,
                 stderr=StringIO(), usuario=user.username)
    return out.getvalue()


def write_file(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.django_db
def test_command_same_file_twice_warns(read_write_user, keyboard):
    """REQ-011: `cargar_norma` con el mismo archivo dos veces avisa y no lo duplica."""
    keyboard()
    run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)

    with pytest.raises(CommandError, match="ese archivo ya está cargado"):
        run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)

    assert Document.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("answer", "stored"),
    [("otro-archivo", "other_file"), ("version-nueva", "new_version"),
     ("versión nueva", "new_version")],
)
def test_command_asks_same_norm_confirmation_by_keyboard(
    read_write_user, keyboard, tmp_path, answer, stored
):
    """REQ-011: ante "misma norma", `cargar_norma` muestra el aviso, pregunta por
    teclado si es otro archivo de lo mismo o una versión nueva y, con la respuesta,
    incorpora el documento fuera de uso."""
    keyboard()
    run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)
    prompts = keyboard(answer)
    other = write_file(tmp_path, "otro.pdf", pages_five_and_six_pdf())

    out = run(other, "--parte", "anexo", "--regimen-general", user=read_write_user)

    assert len(prompts) == 1 and "otro-archivo" in prompts[0]
    assert "misma norma" in out
    assert "registrar_version" in out
    document = Document.objects.get(file_name="otro.pdf")
    assert document.same_norm_confirmation == stored and not document.in_use


@pytest.mark.django_db
@pytest.mark.parametrize("answer", ["no", "", "si"])
def test_command_without_confirmation_does_not_incorporate(
    read_write_user, keyboard, tmp_path, answer
):
    """REQ-011: si la persona no indica otro archivo ni versión nueva, no se
    incorpora."""
    keyboard()
    run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)
    keyboard(answer)
    other = write_file(tmp_path, "otro.pdf", pages_five_and_six_pdf())

    with pytest.raises(CommandError, match="no se confirmó"):
        run(other, "--parte", "anexo", "--regimen-general", user=read_write_user)

    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_command_without_keyboard_does_not_incorporate(
    read_write_user, keyboard, tmp_path, monkeypatch
):
    """REQ-011: sin teclado (fin de la entrada) y sin la opción, no se incorpora."""
    keyboard()
    run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)

    def no_keyboard(prompt):
        raise EOFError

    monkeypatch.setattr(cargar_norma, "ask_confirmation", no_keyboard)
    other = write_file(tmp_path, "otro.pdf", pages_five_and_six_pdf())

    with pytest.raises(CommandError, match="no se confirmó"):
        run(other, "--parte", "anexo", "--regimen-general", user=read_write_user)

    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_command_confirmation_option_runs_without_keyboard(
    read_write_user, keyboard, tmp_path
):
    """REQ-011: `--confirmar-misma-norma version-nueva` da la confirmación expresa sin
    preguntar por teclado (para los tests y la carga del corpus)."""
    keyboard()
    run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)
    prompts = keyboard()
    other = write_file(tmp_path, "otro.pdf", pages_five_and_six_pdf())

    out = run(other, "--parte", "anexo", "--regimen-general",
              "--confirmar-misma-norma", "version-nueva", user=read_write_user)

    assert prompts == []
    assert "misma norma" in out
    assert Document.objects.get(file_name="otro.pdf").same_norm_confirmation == "new_version"


@pytest.mark.django_db
def test_command_confirmation_option_only_accepts_two_values(read_write_user, keyboard):
    """REQ-011: la opción solo acepta otro-archivo o version-nueva."""
    keyboard()

    with pytest.raises(CommandError):
        run(EXTRACT, "--confirmar-misma-norma", "si", user=read_write_user)

    assert not Document.objects.exists()


@pytest.mark.django_db
def test_command_informs_added_part_and_different_date(read_write_user, keyboard, tmp_path):
    """REQ-011: al sumar el anexo a una norma que ya tiene el cuerpo, el comando lo
    informa sin preguntar y avisa la fecha de vigencia distinta de la parte en uso."""
    keyboard()
    body = write_file(tmp_path, "cuerpo.pdf", pages_five_and_six_pdf())
    run(body, "--parte", "cuerpo", "--regimen-general", user=read_write_user)
    put_in_use(Document.objects.get())
    args = [a for a in COMMAND_ARGS]
    args[args.index("--fecha-vigencia") + 1] = "2023-01-02"

    out = StringIO()
    call_command("cargar_norma", str(EXTRACT), *args, "--parte", "anexo",
                 "--regimen-general", stdout=out, stderr=StringIO(),
                 usuario=read_write_user.username)
    out = out.getvalue()

    assert (
        "Se suma como parte anexo de la Disposición AFIP 247/2022, que ya tiene cargado "
        "el cuerpo." in out
    )
    assert "la fecha de vigencia indicada (2023-01-02) difiere" in out
    assert Norm.objects.count() == 1 and Document.objects.count() == 2


@pytest.mark.django_db
def test_command_message_uses_the_report_page_wording(read_write_user, keyboard):
    """REQ-004: el mensaje de carga nombra las páginas como el informe (ilegibles, sin
    texto, etc.) y no dice "páginas no leídas"."""
    keyboard()

    out = run(EXTRACT, "--parte", "anexo", "--regimen-general", user=read_write_user)

    assert "no leídas" not in out
    assert "Ilegibles: ninguna." in out
    assert "Sin texto:" in out and "En blanco:" in out
