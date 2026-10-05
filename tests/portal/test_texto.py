"""Decodificación y normalización del texto del Portal (T-140; REQ-046; ADR-0032).

El texto con acentos rotos que ya viene roto en los bytes no se adivina (P3): se marca.
"""

import unicodedata

from evaluon.portal.parsing import texto


def test_decodes_utf8_declared_page():
    """REQ-046: una página en UTF-8 se decodifica a texto."""
    data = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">Diseño'.encode()
    assert texto.decode(data).endswith("Diseño")


def test_decodes_windows_1252_declared_page():
    """REQ-046: una página declarada en windows-1252 se decodifica con ese códec."""
    data = b'<meta charset="windows-1252">Dise\xf1o'
    assert texto.decode(data).endswith("Diseño")


def test_repairs_double_encoded_text():
    """REQ-046: el UTF-8 leído como latin-1 (Ã³) es recuperable y se recupera."""
    roto = "Disposición".encode("utf-8").decode("latin-1")
    data = ('<meta charset="utf-8">' + roto).encode("utf-8")
    assert texto.decode(data).endswith("Disposición")


def test_normalizes_entities_nbsp_without_semicolon_and_spaces():
    """REQ-046: entidades, `&nbsp` sin punto y coma, espacios y saltos duplicados."""
    assert texto.normalize("EX-1-&nbsp&nbsp&nbsp-ARCA") == "EX-1- -ARCA"
    assert texto.normalize("  uno \n\n  dos\t tres  ") == "uno dos tres"
    assert texto.normalize("Disposici&#243;n") == "Disposición"
    assert texto.normalize("a\x00b\x07c") == "abc"


def test_normalizes_to_nfc():
    """REQ-046: forma Unicode NFC."""
    descompuesto = unicodedata.normalize("NFD", "ÑANDÚ")
    assert texto.normalize(descompuesto) == "ÑANDÚ"
    assert unicodedata.is_normalized("NFC", texto.normalize(descompuesto))


def test_marks_text_broken_in_the_bytes_and_keeps_it_as_is():
    """REQ-046, P3: `¿¿` por letra, `garant¿a`, `�` y `è` se marcan y no se corrigen."""
    for roto in ("LOG¿¿STICA", "garant¿a", "Disposici&#191;&#191;n", "ciudad �", "Gestiòn è"):
        assert texto.clean(roto).damaged, roto
    assert texto.clean("LOG¿¿STICA").value == "LOG¿¿STICA"
    assert texto.clean("Disposici&#191;&#191;n").value == "Disposici¿¿n"


def test_does_not_mark_legitimate_inverted_question_mark():
    """REQ-046: el signo de apertura de una pregunta no es daño."""
    assert not texto.clean("¿Desea continuar?").damaged
    assert not texto.clean("Disposición Nº 247/2022").damaged
