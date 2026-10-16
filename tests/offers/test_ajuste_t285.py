"""Ajuste único del paso 2 en la visión (T-285; REQ-119; spec 016; ADR-0041, decisión 3; ADR-0070).

La medición T-283 (D-283-9) mostró que con la `vision-v5` la copia de un documento de identidad omitía
un dato visible (una fecha). La `vision-v6` dice, como definición general y sin ejemplo, que en un
documento de identidad, una credencial o una constancia cada dato visible es texto, también los chicos
o de un costado (D-51: transcribir literalmente el texto visible). Lo que hace el modelo lo mide T-286.
"""

from django.conf import settings

from evaluon.offers import vision

RULE = ("En un documento de identidad, una credencial o una constancia, cada dato visible es texto: "
        "también las fechas, los números y los rótulos chicos o de un costado.")


def test_d283_9_the_vision_instruction_says_every_visible_datum_of_an_identity_document_is_text():
    """REQ-119 (D-51; ADR-0041, decisión 3): la instrucción vigente de la visión (`vision-v6`) dice que
    cada dato visible de un documento de identidad, una credencial o una constancia es texto, con las
    fechas y los números chicos; la v5 no lo decía. Las reglas de no adivinar siguen (D-54)."""
    text = vision.load_prompt()

    assert settings.ASSESSMENT_VISION_PROMPT_VERSION == "vision-v6"
    assert RULE in text
    assert RULE not in vision.PROMPTS_DIR.joinpath("vision-v5.md").read_text(encoding="utf-8")
    assert "no adivines una palabra ni un número" in text and "[ilegible]" in text
