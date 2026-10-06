"""Unir los grupos y el contraste en un resultado (REQ-052, REQ-053, REQ-055, REQ-060; plan 004,
"Unir grupos y contrastar"; ADR-0038; T-150). Sin base ni modelo: la lógica pura."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import combine
from evaluon.assessment.citations import Located

DOC = SimpleNamespace(pk=1, title="oferta.pdf")


def cite(start=0, text="texto citado"):
    return Located(document=DOC, reading=None, page=1, char_start=start,
                   char_end=start + len(text), text=text)


def group(index, result, *, exigence="condicion", cites=(), doubt="", question="",
          external=False, explanation=""):
    return combine.GroupResult(index, result, doubt=doubt, exigence=exigence,
                               citations=list(cites), question=question, external=external,
                               explanation=explanation)


def run(*groups, unread=(), without_reading=(), unread_groups=0):
    return combine.combine(list(groups), unread=list(unread),
                           without_reading=list(without_reading), unread_groups=unread_groups)


UNREAD = [{"document": 1, "title": "doc.pdf", "page": 2}]


def test_a_conclusion_with_a_cited_text_stands_and_goes_to_the_contrast():
    """REQ-052, REQ-053: "cumple" con cita ubicada es la propuesta, pendiente de contraste."""
    combined = run(group(0, "cumple", cites=[cite()], explanation="Lo dice el texto."))
    assert combined.outcome == "cumple" and combined.doubt == ""
    assert combined.needs_contrast
    assert [c.text for c in combined.citations] == ["texto citado"]


def test_a_conclusion_and_no_consta_in_the_other_groups_keeps_the_conclusion():
    """ADR-0038: una conclusión con cita y "no consta" en los demás grupos queda."""
    combined = run(group(0, "no_consta", exigence="documento"),
                   group(1, "no_cumple", cites=[cite(10)]),
                   group(2, "no_consta", exigence="documento"))
    assert combined.outcome == "no_cumple"


def test_cumple_and_no_cumple_in_different_groups_is_a_contradiction():
    """ADR-0038: "cumple" y "no cumple" en grupos distintos: no determinado por
    contradicción, con las citas de ambos."""
    combined = run(group(0, "cumple", cites=[cite(0, "uno")]),
                   group(1, "no_cumple", cites=[cite(50, "dos")]))
    assert combined.outcome == "no_determinado" and combined.doubt == "contradiccion"
    assert [c.text for c in combined.citations] == ["uno", "dos"]
    assert not combined.needs_contrast


def test_a_group_in_doubt_stops_a_conclusion_from_the_other():
    """ADR-0038 (conservador): si otro grupo duda, no se concluye; se conservan las citas."""
    combined = run(group(0, "cumple", cites=[cite()]),
                   group(1, "no_determinado", doubt="duda"))
    assert combined.outcome == "no_determinado" and combined.doubt == "duda"
    assert len(combined.citations) == 1


def test_all_groups_no_consta_for_a_document_is_not_found_when_everything_was_read():
    """REQ-060: "no se encontró el documento" si la exigencia es un documento en todos los
    grupos, no hay páginas sin leer y se leyeron todos los grupos. Sin pregunta."""
    combined = run(group(0, "no_consta", exigence="documento"),
                   group(1, "no_consta", exigence="documento"))
    assert combined.outcome == "sin_documento" and combined.doubt == ""
    assert combined.exigence == "documento"
    assert combined.question == ""
    assert not combined.unread_warning


def test_no_consta_with_unread_pages_is_not_a_missing_document():
    """ADR-0038: con páginas sin leer, no se supone que el documento no estaba: no
    determinado por lectura incompleta, con una pregunta."""
    combined = run(group(0, "no_consta", exigence="documento"), unread=UNREAD)
    assert combined.outcome == "no_determinado" and combined.doubt == "lectura_incompleta"
    assert combined.unread_warning
    assert "doc.pdf, página 2" in combined.question


def test_no_consta_with_a_group_that_was_not_read_is_incomplete():
    """ADR-0038: con grupos que pasaron del tope, queda lectura incompleta."""
    combined = run(group(0, "no_consta", exigence="documento"), unread_groups=1)
    assert combined.outcome == "no_determinado" and combined.doubt == "lectura_incompleta"


def test_no_consta_with_a_document_without_reading_is_incomplete():
    combined = run(group(0, "no_consta", exigence="documento"), without_reading=[7])
    assert combined.doubt == "lectura_incompleta"


def test_no_consta_for_a_condition_is_a_missing_data_with_a_question():
    """REQ-055: si la exigencia es una condición y todo se leyó, falta un dato: no
    determinado con una pregunta (la del modelo, o la fija)."""
    asked = run(group(0, "no_consta", exigence="condicion",
                      question="¿Qué plazo de entrega se aceptó?"))
    assert asked.outcome == "no_determinado" and asked.doubt == "sin_dato"
    assert asked.question == "¿Qué plazo de entrega se aceptó?"
    fixed = run(group(0, "no_consta", exigence="condicion"))
    assert fixed.doubt == "sin_dato" and fixed.question


def test_an_external_requirement_is_undetermined_with_a_question_and_never_inferred():
    """P9, REQ-055: lo que se verifica fuera de la oferta es "no determinado" (falta la hoja de
    compliance), aunque otro grupo diga "cumple", y con una pregunta."""
    combined = run(group(0, "cumple", cites=[cite()]),
                   group(1, "no_determinado", doubt="duda", external=True))
    assert combined.outcome == "no_determinado" and combined.doubt == "externo"
    assert "hoja de compliance" in combined.question
    assert not combined.needs_contrast


def test_a_conclusion_whose_citation_was_not_located_is_undetermined_without_citation():
    """REQ-053: una conclusión sin cita ubicada queda "no determinado" `sin_cita`."""
    combined = run(group(0, "no_determinado", doubt="sin_cita", explanation="Dice cumple."))
    assert combined.outcome == "no_determinado" and combined.doubt == "sin_cita"


def test_a_doubt_without_a_failed_citation_is_a_plain_doubt():
    combined = run(group(0, "no_determinado", doubt="duda"),
                   group(1, "no_determinado", doubt="sin_cita"))
    assert combined.doubt == "duda"


def test_no_groups_is_an_incomplete_reading():
    combined = run()
    assert combined.outcome == "no_determinado" and combined.doubt == "lectura_incompleta"


def test_the_contrast_that_does_not_say_yes_downgrades_and_keeps_the_citations():
    """ADR-0038: si el contraste no contesta `si`, "no determinado" `sin_corroborar` con las
    mismas citas; con `si` nada cambia; un resultado que no es conclusión no se contrasta."""
    combined = run(group(0, "cumple", cites=[cite()], explanation="Lo dice."))
    assert combine.apply_contrast(combined, "si") is combined
    for answer in ("no", "parcial"):
        downgraded = combine.apply_contrast(combined, answer, "solo lo anuncia")
        assert downgraded.outcome == "no_determinado"
        assert downgraded.doubt == "sin_corroborar"
        assert downgraded.citations == combined.citations
        assert "solo lo anuncia" in downgraded.explanation
    undetermined = run(group(0, "no_determinado", doubt="duda"))
    assert combine.apply_contrast(undetermined, "no") is undetermined


@pytest.mark.parametrize("doubt", ["externo", "sin_dato", "lectura_incompleta"])
def test_these_doubts_always_carry_a_question(doubt):
    """REQ-055: externo, sin dato y lectura incompleta siempre llevan una pregunta."""
    assert combine.fixed_question(doubt, UNREAD, "algo")
    assert not combine.fixed_question("duda")


def test_a_doubt_with_unread_pages_is_an_incomplete_reading_with_a_question():
    """ADR-0038: con partes de la oferta sin leer, una duda puede venir de ahí: queda
    `lectura_incompleta` y se le pregunta a la Comisión."""
    combined = run(group(0, "no_determinado", doubt="duda", cites=[cite()],
                         explanation="Anuncia el documento, pero su página es ilegible."),
                   unread=UNREAD)
    assert combined.outcome == "no_determinado" and combined.doubt == "lectura_incompleta"
    assert combined.unread_warning and "doc.pdf, página 2" in combined.question
    assert len(combined.citations) == 1


def test_only_an_undetermined_result_carries_the_models_question():
    """REQ-055: una conclusión no lleva pregunta, aunque el modelo la haya formulado."""
    combined = run(group(0, "cumple", cites=[cite()], question="¿Y esto?"))
    assert combined.outcome == "cumple" and combined.question == ""
    undetermined = run(group(0, "no_determinado", doubt="duda", question="¿Y esto?"))
    assert undetermined.question == "¿Y esto?"


def test_a_downgraded_conclusion_carries_the_question_for_the_commission():
    """REQ-055, REQ-056 (T-153): un "cumple" que el contraste baja a `sin_corroborar` lleva la
    pregunta, para que el evaluador lo confirme, lo corrija o lo rechace."""
    combined = run(group(0, "cumple", cites=[cite()], explanation="Lo dice."))
    assert combined.question == ""
    downgraded = combine.apply_contrast(combined, "parcial", "solo lo anuncia")
    assert downgraded.doubt == "sin_corroborar" and downgraded.question


def test_external_wins_over_a_doubt_and_over_a_missing_document():
    """REQ-055, T-156: lo que se verifica fuera de la oferta es "externo" aunque otro grupo
    dude o diga "no consta" un documento que se leyó completo (no es "no se encontró")."""
    over_doubt = run(group(0, "no_determinado", doubt="duda"),
                     group(1, "no_determinado", doubt="duda", external=True))
    assert over_doubt.doubt == "externo" and over_doubt.question
    over_missing = run(group(0, "no_consta", exigence="documento"),
                       group(1, "no_determinado", doubt="duda", exigence="documento",
                             external=True))
    assert over_missing.outcome == "no_determinado" and over_missing.doubt == "externo"
    single = run(group(0, "no_determinado", doubt="duda", exigence="documento", external=True))
    assert single.outcome == "no_determinado" and single.doubt == "externo"


def test_a_technical_no_cumple_needs_a_clause_that_is_in_the_requirement():
    """REQ-052, T-156: la cláusula citada tiene que estar letra por letra en el requisito."""
    requirement = "Renglón 5 del pliego: «5.1 Bolsas de 20 kilos.  5.2 Proteína mínima 24 %.»"
    assert combine.clause_supported("5.1 Bolsas de 20 kilos.", requirement)
    assert combine.clause_supported("Bolsas de 20  kilos.", requirement)
    assert not combine.clause_supported("Bolsas de 10 kilos.", requirement)
    assert not combine.clause_supported("", requirement)


def test_a_trivial_stretch_of_the_requirement_is_not_a_clause():
    """REQ-052, T-157: un tramo literal pero sin contenido ("de", "3.1", "Renglón 5") no es una
    cláusula: no alcanza para sostener un "no cumple"."""
    requirement = "Renglón 5 del pliego: «5.1 Bolsas de 20 kilos.  5.2 Proteína mínima 24 %.»"
    for trivial in ("de", "5.1", "Renglón 5", "20 kilos", "Bolsas de"):
        assert not combine.clause_supported(trivial, requirement)
    assert combine.clause_supported("5.2 Proteína mínima 24 %.", requirement)


def test_a_group_without_data_for_a_technical_no_cumple_is_undetermined_without_data():
    """REQ-052, T-156: el grupo que bajó un "no cumple" sin cláusula llega como `sin_dato` y
    lleva siempre una pregunta; no se vuelve "duda"."""
    combined = run(group(0, "no_determinado", doubt="sin_dato", cites=[cite()]))
    assert combined.outcome == "no_determinado" and combined.doubt == "sin_dato"
    assert combined.question and not combined.needs_contrast


# --- Contraste por cláusula (T-158) ------------------------------------------------------------

PUPPY_ROW = ("Renglón 5 del pliego: 5.1 Alimento balanceado para cachorros. "
             "5.2 Presentación en bolsa de 15 kilos.")
PUPPY = "5.1 Alimento balanceado para cachorros."
BAG = "5.2 Presentación en bolsa de 15 kilos."


def a_cumple():
    return run(group(0, "cumple", cites=[cite()], explanation="Es el mismo producto."))


ADULTS = cite(100, "perros adultos")


def test_a_contradicted_clause_makes_the_cumple_a_no_cumple_citing_the_clause():
    """REQ-052, REQ-053: la oferta ofrece alimento para adultos y el pliego pide cachorros: no
    cumple, con la cláusula y la cita de la oferta que la contradice (T-164)."""
    rows = [(PUPPY, "contradice", "La oferta es para adultos.", ADULTS), (BAG, "coincide", "")]
    combined = combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW)
    assert combined.outcome == "no_cumple" and combined.doubt == ""
    assert PUPPY in combined.explanation and "adultos" in combined.explanation
    assert [c.text for c in combined.citations] == ["perros adultos", "texto citado"]


def test_a_contradiction_without_a_quote_of_the_offer_stays_undetermined():
    """REQ-052, REQ-053, T-164 (F-1): "contradice" sin cita de la oferta ubicada no alcanza para
    "no cumple": no determinado, con pregunta."""
    for rows in ([(PUPPY, "contradice", "La oferta es para adultos.")],
                 [(PUPPY, "contradice", "La oferta es para adultos.", None)]):
        combined = combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW)
        assert combined.outcome == "no_determinado" and combined.doubt == "sin_dato"
        assert combined.question and PUPPY in combined.explanation


def test_a_contradiction_that_is_about_the_quality_of_the_reading_is_not_a_no_cumple():
    """REQ-052, T-164 (F-1): un motivo de escaneo u OCR, aunque traiga cita, deja "no
    determinado" con pregunta; un estado "no_legible" también."""
    for why in ("Errores de transcripción y omite dos minerales.",
                "El escaneo tiene un OCR deficiente.", "Texto ilegible."):
        rows = [(PUPPY, "contradice", why, ADULTS)]
        combined = combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW)
        assert combined.outcome == "no_determinado" and combined.question, why
    combined = combine.apply_clauses(a_cumple(), [(PUPPY, "no_legible", "")], "", PUPPY_ROW)
    assert combined.outcome == "no_determinado" and combined.doubt == "sin_dato"


def test_a_clause_that_does_not_appear_makes_it_undetermined_with_a_question():
    """REQ-052, REQ-055: una cláusula que la oferta no menciona: no determinado, con pregunta."""
    rows = [(PUPPY, "coincide", "para cachorros"), (BAG, "no_aparece", "")]
    combined = combine.apply_clauses(a_cumple(), rows, "¿Qué bolsa ofrece?", PUPPY_ROW)
    assert combined.outcome == "no_determinado" and combined.doubt == "sin_dato"
    assert combined.question == "¿Qué bolsa ofrece?" and BAG in combined.explanation
    # sin pregunta del modelo, el sistema pone la suya
    assert combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW).question


def test_a_contradiction_without_a_real_clause_does_not_become_a_no_cumple():
    """REQ-052: "contradice" con una cláusula inventada no alcanza para "no cumple"."""
    rows = [("5.9 Una cláusula que no existe.", "contradice", "otro valor", ADULTS)]
    combined = combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW)
    assert combined.outcome == "no_determinado" and combined.question


def test_only_when_every_clause_matches_the_cumple_stands():
    """REQ-052: todas coinciden: queda el "cumple", que sigue al contraste común."""
    rows = [(PUPPY, "coincide", "cachorros"), (BAG, "coincide", "15 kg")]
    combined = combine.apply_clauses(a_cumple(), rows, "", PUPPY_ROW)
    assert combined.outcome == "cumple" and combined.needs_contrast
