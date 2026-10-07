"""Orientación de la imagen de una página antes de mandarla al modelo con visión (REQ-064;
ADR-0041; T-177).

Un escaneo o una foto puede venir girado 90, 180 o 270 grados; el modelo de visión, ante una
página de costado, inventa texto y repite `[ilegible]` hasta el tope. Se detecta el giro y se
endereza la imagen antes de mandarla:

1. Tesseract OSD (`--psm 0`) sobre una copia reducida: si da una confianza de orientación de
   al menos `ASSESSMENT_VISION_OSD_MIN_CONFIDENCE`, se usa su giro.
2. Si OSD no puede (pocas letras, manuscrito) o duda, se prueban los cuatro giros con el
   reconocimiento de texto en español y se elige el de mayor puntaje (suma de la confianza de
   las palabras con letras que reconoce con seguridad). Si ninguno reconoce palabras, o el
   mejor no supera claramente al giro 0, no se gira.

Todo corre en CPU, en el equipo (P4). El resultado queda en el informe de la lectura (P6):
método, giro aplicado, confianza y puntajes.
"""

import pytesseract
from django.conf import settings

from evaluon.norms.reading import ocr

# Giros posibles, en grados en sentido horario, para dejar el texto derecho.
ROTATIONS = (0, 90, 180, 270)
METHOD_OSD = "osd"
METHOD_TRIAL = "ocr_trial"
METHOD_NONE = "none"

# Palabra "segura" del reconocimiento: confianza mínima y largo mínimo con solo letras.
WORD_MIN_CONFIDENCE = 60
WORD_MIN_LENGTH = 3
# Para girar hace falta que el mejor puntaje supere al del giro 0 en esta proporción: una
# diferencia chica es ruido.
TRIAL_MIN_GAIN = 1.5
TRIAL_MIN_SCORE = 100


def clockwise(image, degrees):
    """`image` girada `degrees` grados en sentido horario (cambia el tamaño si es 90 o 270)."""
    return image.rotate(-degrees, expand=True) if degrees else image


def _small(image):
    copy = image.convert("L")
    side = settings.ASSESSMENT_VISION_ORIENTATION_MAX_SIDE
    if max(copy.size) > side:
        ratio = side / max(copy.size)
        copy = copy.resize((max(1, round(copy.width * ratio)),
                            max(1, round(copy.height * ratio))))
    return copy


def _osd(image):
    """`(giro, confianza)` según Tesseract OSD, o `None` si no puede decidir."""
    try:
        data = pytesseract.image_to_osd(
            image, config="--psm 0", output_type=pytesseract.Output.DICT)
        rotate = int(data["rotate"])
        confidence = float(data["orientation_conf"])
    except Exception:  # noqa: BLE001 - OSD falla con pocas letras: se prueban los giros
        return None
    return (rotate, confidence) if rotate in ROTATIONS else None


def _score(image):
    """Puntaje de legibilidad de `image`: suma de la confianza de las palabras seguras."""
    data = pytesseract.image_to_data(
        image, lang=ocr.LANGUAGE, config="--oem 1 --psm 3",
        output_type=pytesseract.Output.DICT)
    total = 0.0
    for text, conf in zip(data["text"], data["conf"], strict=True):
        text = (text or "").strip()
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            continue
        if conf >= WORD_MIN_CONFIDENCE and len(text) >= WORD_MIN_LENGTH and text.isalpha():
            total += conf
    return total


def detect(image):
    """El giro horario que endereza `image`, con cómo se decidió:
    `{"rotate_clockwise", "method", "confidence", "scores"}`."""
    small = _small(image)
    found = _osd(small)
    if found and found[1] >= settings.ASSESSMENT_VISION_OSD_MIN_CONFIDENCE:
        return {"rotate_clockwise": found[0], "method": METHOD_OSD,
                "confidence": found[1], "scores": None}
    scores = {degrees: round(_score(clockwise(small, degrees)), 1) for degrees in ROTATIONS}
    best = max(ROTATIONS, key=lambda degrees: (scores[degrees], -degrees))
    base = scores[0]
    if best != 0 and scores[best] >= TRIAL_MIN_SCORE and scores[best] >= base * TRIAL_MIN_GAIN:
        return {"rotate_clockwise": best, "method": METHOD_TRIAL,
                "confidence": scores[best], "scores": scores}
    return {"rotate_clockwise": 0, "method": METHOD_NONE,
            "confidence": found[1] if found else None, "scores": scores}


def straighten(image):
    """`(imagen derecha, registro)`: la imagen girada lo que haga falta y el registro del
    giro aplicado."""
    record = detect(image)
    return clockwise(image, record["rotate_clockwise"]), record


