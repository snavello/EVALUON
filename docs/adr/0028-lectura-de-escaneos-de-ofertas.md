# ADR-0028 · Lectura de escaneos y fotos de ofertas con el OCR existente, con preparación de imagen solo si hace falta

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (al aprobar el plan 008; fotos sueltas JPG y PNG aceptadas)

## Contexto

REQ-038 pide leer documentos con texto y escaneados o fotografiados, e informar las páginas que no se pudieron leer o se leyeron con baja confianza. El caso-00 tiene ofertas "escaneadas con celular". El camino debe correr sin conexión (P4, P5).

Ya existe `evaluon/norms/reading/ocr.py` (ADR-0004, alternativa D): Tesseract con el modelo `spa` de `tessdata_best`, página dibujada a 300 ppp en escala de grises, estado por confianza promedio de la página (legible desde 80, dudosa desde 50, ilegible por debajo) y clasificación de página (con texto, escaneada, texto inservible, en blanco). Esos umbrales son "valores de partida, sin medición" y se calibraron solo con escaneos de normas. No acepta imágenes sueltas (JPG, PNG), solo PDF.

## Alternativas

### A. Usar el OCR existente tal como está

- Se gana: cero código nuevo en lectura; mismo comportamiento ya verificado; informa páginas ilegibles y dudosas.
- Se pierde: una foto de celular (torcida, con sombras, de baja resolución) puede dar muchas páginas dudosas; no acepta fotos sueltas.

### B. OCR existente más una preparación de imagen condicional, y aceptar fotos sueltas (elegida)

- Las fotos JPG y PNG se aceptan al cargar: el original se guarda tal cual y para leerlo se convierte a un PDF de una página, en el equipo. Una página con confianza por debajo de `DOUBTFUL_FROM` se vuelve a leer una vez con enderezado y umbral adaptativo; se conserva la lectura de mayor confianza y el informe dice cuál se usó.
- Se gana: lo que A ya hace, más cobertura de fotos y una segunda oportunidad a las páginas malas, sin cambiar lo que ya funciona (las páginas buenas no se tocan).
- Se pierde: un paso de CPU más en páginas dudosas (segundos por página); una dependencia de procesamiento de imagen si no está ya en la imagen (se verifica antes de agregarla); más código para calibrar con escaneos reales.

### C. Modelo de visión local

- Descartado en el ADR-0027, alternativa D: sin modelo verificado, la GPU está casi llena y el texto no sería literal recuperable.

## Decisión

Se adopta B en dos pasos para respetar el ritmo del ADR-0025: el corte vertical (T-130) usa A tal cual con un documento escaneado sintético; la preparación de imagen y las fotos sueltas llegan con T-131, y los umbrales se ajustan con las ofertas reales del caso-00 solo dentro de las dos rondas de la medición. Una página que sigue ilegible queda en la lista de "páginas no leídas" de la oferta, visible para la Comisión (REQ-038, escenario 3); nunca se completa a mano ni por el modelo.

## Consecuencias

- Más fácil: la Comisión sabe qué páginas revisar, sin que el sistema suponga.
- Más difícil: la calidad de una foto de celular puede seguir siendo insuficiente; en ese caso se registra como límite en la lista de revisión con el primer producto, con el número de páginas afectadas.
- Revertir: quitar el segundo intento y la conversión de fotos deja el comportamiento de A.
