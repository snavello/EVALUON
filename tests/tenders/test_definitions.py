"""Bloque común de definiciones del responsable y registro de la versión y la huella de cada
instrucción de la matriz (T-236; REQ-102, REQ-106; ADR-0054, regla 4; ADR-0055, regla 8).

El bloque `matriz-definiciones-v1.md` copia las decisiones del responsable del 2026-10-10
(spec 015) y el código lo incluye en las instrucciones que llevan su marca. Los textos son
inventados o propios de las instrucciones (P4).
"""

import hashlib
from pathlib import Path

import pytest

from evaluon.tenders.proposal import extraction

PROMPTS = Path(extraction.PROMPTS_DIR)
BLOCK = (PROMPTS / "matriz-definiciones-v1.md").read_text(encoding="utf-8")


def test_the_common_block_is_a_published_version_of_the_settings(settings):
    """REQ-102: el bloque común tiene su versión en `MATRIX_PROMPT_VERSIONS` y su archivo."""
    assert settings.MATRIX_PROMPT_VERSIONS["definiciones"] == "matriz-definiciones-v1"
    assert (PROMPTS / "matriz-definiciones-v1.md").is_file()


@pytest.mark.parametrize("literal", [
    # Lo que no entra (decisión del 2026-10-10: «no entran ninguno de los 3»).
    "El pago, la moneda de pago y la factura",
    "La forma de presentar la oferta por el Portal",
    "la confirmación por el Administrador Legitimado",
    "cargar, consignar o subir datos o documentos en el Portal",
    "Los compromisos que se cumplen al presentarse",
    "la mera presentación implicará el conocimiento y aceptación del pliego",
    "Las consecuencias",
    "Las obligaciones del organismo",
    # Lo que sí entra: la salvedad.
    "la moneda en que se cotiza la oferta",
    # Opciones y formas elegidas («Requisito de la forma elegida»).
    "que puede no usar",
    "entra solo como condición de esa opción",
    "que el oferente tiene que elegir",
    "el límite del pagaré o la póliza según la norma de la Superintendencia",
    "se evalúan solo en la oferta que eligió esa forma",
    # Una fila por unidad de sentido, con el ejemplo del perro.
    "Una fila es una unidad de sentido",
    "la oración completa",
    "Las condiciones de una misma oración no se separan en filas distintas",
    "cuatro patas",
    "dos ojos",
    "marrón",
])
def test_the_common_block_copies_each_decision_of_the_spec(literal):
    """REQ-102, REQ-101: el bloque común lleva cada decisión literal de la spec 015."""
    assert literal in BLOCK


@pytest.mark.parametrize("forbidden", [
    "dividí", "fragmento más corto", "ante la duda", "mantené",
])
def test_the_common_block_has_none_of_the_rules_that_push_to_the_error(forbidden):
    """REQ-102 (ADR-0054, regla 6 y 7): el bloque no trae «dividí», «fragmento más corto» ni
    una regla de «ante la duda»."""
    assert forbidden not in BLOCK.lower()


@pytest.fixture
def prompt_dir(tmp_path, monkeypatch, settings):
    """Una carpeta de instrucciones de prueba con una instrucción que lleva la marca del bloque."""
    (tmp_path / "bloque-v1.md").write_text("DEFINICIONES DE PRUEBA\n", encoding="utf-8")
    (tmp_path / "con-marca-v1.md").write_text(
        f"Antes.\n\n{extraction.DEFINITIONS_MARK}\n\nDespués.\n", encoding="utf-8")
    (tmp_path / "sin-marca-v1.md").write_text("Sin bloque.\n", encoding="utf-8")
    monkeypatch.setattr(extraction, "PROMPTS_DIR", tmp_path)
    settings.MATRIX_PROMPT_VERSIONS = {
        "definiciones": "bloque-v1", "con": "con-marca-v1", "sin": "sin-marca-v1"}
    return tmp_path


def test_the_instruction_includes_the_common_block_where_it_has_the_mark(prompt_dir):
    """REQ-102: el código reemplaza la marca por el bloque común; el texto del pedido lo trae."""
    instruction = extraction.load_instruction("con")

    assert extraction.DEFINITIONS_MARK not in instruction.text
    assert instruction.text == "Antes.\n\nDEFINICIONES DE PRUEBA\n\nDespués.\n"
    assert extraction.load_prompt("con") == instruction.text


def test_the_instruction_records_its_version_and_the_sha256_of_its_file_and_block(prompt_dir):
    """REQ-106, P6: la instrucción registra su versión, la huella de su archivo y la versión y la
    huella del bloque común; con eso se reconstruye el texto exacto."""
    instruction = extraction.load_instruction("con")

    file_hash = hashlib.sha256((prompt_dir / "con-marca-v1.md").read_bytes()).hexdigest()
    block_hash = hashlib.sha256((prompt_dir / "bloque-v1.md").read_bytes()).hexdigest()
    assert instruction.record == {
        "nombre": "con", "version": "con-marca-v1", "sha256": file_hash,
        "definiciones": {"version": "bloque-v1", "sha256": block_hash}}


def test_an_instruction_without_the_mark_has_no_block_in_its_record(prompt_dir):
    """REQ-106: una instrucción que no usa el bloque registra solo su versión y su huella."""
    instruction = extraction.load_instruction("sin")

    assert instruction.text == "Sin bloque.\n"
    assert set(instruction.record) == {"nombre", "version", "sha256"}


def test_the_sha256_is_the_same_with_unix_or_windows_line_endings():
    """REQ-106: la huella de un texto no depende del fin de línea del equipo."""
    assert extraction.text_sha256("a\r\nb\r\n") == extraction.text_sha256("a\nb\n")


def test_the_registry_has_every_version_the_block_and_the_hash_of_each_file(prompt_dir):
    """REQ-106, P6: lo que se guarda en `prompt_versions` de la propuesta: la versión de cada
    instrucción, la del bloque común y, en `huellas`, la huella de cada archivo."""
    registry = extraction.instruction_registry(["con", "sin"])

    assert registry["con"] == "con-marca-v1" and registry["sin"] == "sin-marca-v1"
    assert registry["definiciones"] == "bloque-v1"
    assert set(registry["huellas"]) == {"con", "sin", "definiciones"}
    assert registry["huellas"]["con"] == extraction.load_instruction("con").sha256


def test_a_request_without_parsed_output_still_carries_its_instruction(prompt_dir):
    """REQ-106, P6: una salida cortada o una falla del servicio (sin lo interpretado) también
    deja la versión y la huella de la instrucción en el pedido."""
    instruction = extraction.load_instruction("con")

    assert extraction.with_instruction(None, instruction) == {"instruccion": instruction.record}
    assert extraction.with_instruction({"tramos": {}}, instruction) == {
        "tramos": {}, "instruccion": instruction.record}
