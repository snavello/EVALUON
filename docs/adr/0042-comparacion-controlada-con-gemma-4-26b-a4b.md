# ADR-0042 · Comparación controlada del modelo de generación: Gemma 4 12B contra Gemma 4 26B-A4B

Estado: aceptado · Fecha: 2026-10-06 · Decidió: responsable del proyecto (2026-10-06)

## Contexto

La medición base de la 004 (caso-00, 49 pares) dio 26 coincidencias. De los 23 desaciertos, la revisión del 2026-10-06 atribuyó 4 al modelo (no ve un dato que está en el texto). El ADR-0002 dejó prevista una comparación: "Modelo de contraste: Gemma 4 26B-A4B… se mide con el mismo conjunto solo si M1 no alcanza… pasar a él requiere ajustar el reparto y es una decisión del responsable". El responsable pidió (2026-10-06) hacerla ahora, con la misma evaluación y la misma lista esperada, adoptarlo solo si mejora con razones medidas, y saber cuánto tarda.

Datos actuales (API de Hugging Face, consultada el 2026-10-06; ver "Fuentes" y "Sin verificar"):

| | Gemma 4 12B (hoy) | Gemma 4 26B-A4B | Gemma 4 31B |
|---|---|---|---|
| Repositorio | `google/gemma-4-12B-it-qat-q4_0-gguf` | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | `google/gemma-4-31B-it-qat-q4_0-gguf` |
| Revisión | `29d097773436b69ff9feafd636ab4cf873786537` | `d1c082be9cf3c8a514acf63b8761f4b41935842e` (última modificación 2026-07-17) | no fijada |
| Archivo | `gemma-4-12b-it-qat-q4_0.gguf` | `gemma-4-26B_q4_0-it.gguf` | `gemma-4-31B_q4_0-it.gguf` |
| Bytes | 6.975.879.296 | **14.439.363.584** (13,45 GiB) | 17.651.001.568 (16,44 GiB) |
| SHA-256 | `93567e57…a538b` (el del compose) | **`3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d`** | `179cfb99212709597eae5929112cfca677e1bbf566178b479ae1da0c4772874b` |
| Proyector de imagen | `mmproj-gemma-4-12b-it-qat-q4_0.gguf`, 175.115.616 B, `cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7` | `gemma-4-26B-it-mmproj.gguf`, **1.194.828.160 B**, `a359953a076b877db30c31dbbb4c6d93b4a6e017ee5db5784247e4d4c0dd4f3b` | `gemma-4-31B-it-mmproj.gguf`, 1.200.726.368 B, `6bd60bdb958548b4093196d38744b0f2290c12503a3fddd7486bffa9c5eb07a4` |
| Parámetros | 12.000 M densos | 25.200 M en total, 3.800 M activos (mezcla de expertos) | 31.000 M densos |
| Licencia | Apache 2.0 | Apache 2.0 | Apache 2.0 |

Memoria de video hoy (`specs/004-evaluacion-asistida/entorno.md`, T-148, RTX 5090 Laptop de 24.463 MiB): entorno de uso con el motor de lotes a 32.768: **10.530 MiB**, de los cuales `generation_batch` ocupa 8.075 MiB. El resto (unos 2.455 MiB en esa medición) es lo que no cambia.

Restricción: una sola GPU, una medición a la vez (ADR-0025).

## Alternativas

### A. Gemma 4 26B-A4B, archivo oficial de Google, QAT q4_0 (propuesta)
Misma familia, mismo formato de plantilla y salida estructurada que el 12B; el ADR-0002 ya la nombró como contraste. Solo 3.800 M de parámetros activos: se espera velocidad de generación igual o mayor que la del 12B denso (ADR-0002 cita 248 contra 145 tokens por segundo en una RTX 5090 de escritorio, fuente de tercero), con más capacidad total. Se gana: el candidato más grande que entra en esta GPU junto con embeddings y reranker, con archivo del autor. Se pierde: 14,4 GB más de disco y de descarga; la memoria obliga a apagar un motor; la mezcla de expertos puede ser más lenta en lectura de contexto largo (a medir); el archivo y el proyector hay que fijar y verificar.

### B. Gemma 4 31B denso, QAT q4_0
Se gana: el más capaz de la familia. Se pierde: pesos de 16.833 MiB más caché de contexto y buffers (estimación 3 a 4 GB a 32.768) más lo que no cambia: unos 22.500 a 23.500 MiB de 24.463, sin margen para Windows ni para la lectura por visión; ADR-0002 lo descartó de entrada por lo mismo; velocidad de generación menor (denso). No se mide salvo que el responsable lo pida después.

### C. Gemma 4 12B en 8 bits (la escalera del ADR-0002)
Se gana: misma familia, 12,7 GB (cifra de ADR-0002 [32]), entra sin tocar el reparto. Se pierde: es el mismo modelo con menos pérdida de compresión; no ataca "el modelo no ve un dato". Queda como segunda opción si el 26B no se puede adoptar.

### D. No comparar y corregir solo diseño, datos y medida
Se gana: ninguna descarga ni hora de GPU. Se pierde: no se sabe si los 4 desaciertos del modelo se arreglan con más modelo, y el 80 % queda más apretado (T-155 estima 71 % con las correcciones de diseño). El responsable pidió comparar.

## Decisión

Se propone A, con este diseño.

### Cómo se prueba

1. **Mismo todo menos el modelo.** Mismo código (el que deje T-158), mismas instrucciones, mismas ofertas leídas (con la lectura por visión del ADR-0041 ya aplicada en las dos corridas), misma matriz validada, misma lista esperada (`dictamen-esperado.yaml`, con huella y visto bueno), mismos parámetros del motor (contexto 32.768, `--parallel 1`, temperatura 0, semilla fija, sin pensamiento). Nada se ajusta al 26B: si lo necesita, ese es un hallazgo, no un ajuste.
2. **Dos corridas y de a una.** T-161: 12B con visión (la referencia). T-162: 26B con visión. Nunca juntas, y no con otra medición.
3. **Cómo se pone el modelo.** Reemplaza **temporalmente** a `generation_batch` (el motor de las evaluaciones); `generation` (consulta de normativa), `embeddings` y `reranker` siguen. Un archivo `docker-compose.modelo-grande.yml` (nuevo) sobrescribe solo `generation_batch` con variables propias del lote (`GENERATION_BATCH_MODEL_FILE`, `GENERATION_BATCH_MODEL_ALIAS`, `GENERATION_BATCH_MODEL_SHA256`, `GENERATION_BATCH_MMPROJ_FILE`); el compose base sigue con el 12B. Volver es no usar el archivo y recrear el servicio.
4. **Registro (P6).** Cada evaluación registra el alias, la huella del archivo del modelo del lote y la del proyector, no las de `generation`: por eso `assessment/services/evaluate.py` y los registros de la 003 y la 008 pasan a leer la huella del lote (`GENERATION_BATCH_MODEL_SHA256`, por omisión la misma que el modelo de `generation`).

### Memoria de video con contexto 32.768 (estimación; T-159 la mide)

| Concepto | MiB |
|---|---|
| Lo que no cambia (embeddings, reranker, base de CUDA y `generation`), por diferencia con T-148 (10.530 − 8.075) | 2.455 |
| Pesos del 26B-A4B (14.439.363.584 B) | 13.770 |
| Caché de contexto y buffers a 32.768 (ADR-0002 [25]: el 26B-A4B de 15,64 GiB midió 17.702 MiB a 32.000, es decir unos 1.700 MiB sobre los pesos; el 12B de este equipo crece 228 MiB al duplicar el contexto) | 1.700 a 2.500 |
| Proyector de imagen (1.194.828.160 B) más buffers de imagen | 1.139 + 300 a 600 |
| **Total con el 26B reemplazando a `generation_batch`, con visión** | **19.400 a 20.500 de 24.463** |
| Total sin visión | 17.900 a 18.800 |
| Los dos juntos (12B de lotes y 26B) | 27.000 o más: no entra |

Se acepta si el máximo observado queda en 22.000 MiB o menos (margen de unos 2,4 GB para Windows y la pantalla, ADR-0002). Si no llega, se baja el contexto a 24.576 con presupuesto de grupo de 14.000 (ADR-0037) para las dos corridas y se registra, porque el contexto es una variable de la comparación y tiene que ser igual en las dos.

### Umbral para adoptarlo (escrito antes de medir, ADR-0025)

Referencia: T-161 (12B con visión), mismo código y misma lista. El 26B se adopta solo si cumple **todo**:

| # | Medida | Para adoptar | Bloquea |
|---|---|---|---|
| 1 | Contradicciones con el dictamen | 0 | sí |
| 2 | "Cumple" o "no cumple" sin cita literal de la oferta; citas literales | 0; 100 % | sí |
| 3 | Coincidencia | pares que pasan a coincidir menos pares que dejan de coincidir ≥ 4 sobre la referencia (hoy ≥ 8 puntos de 49), y al menos 2 de los 4 desaciertos "del modelo" recuperados | sí |
| 4 | Incumplimientos reales (pares donde el dictamen dice "no cumple") detectados como "no cumple" | no menos que la referencia, y ninguno de ellos que antes se detectaba | sí |
| 5 | Razón de la mejora | cada par que cambia se revisa y se clasifica; la mejora debe venir de pares donde el 12B "no veía un dato que está" o contrastaba mal, no de un cambio de lo que se cuenta | sí |
| 6 | Tiempo por oferta | hasta 30 min por oferta (decisión del responsable, 2026-10-06; el caso-00 completo, hasta 90 min) | sí |
| 7 | Memoria de video máxima | hasta 22.000 MiB, y 0 pedidos fallidos por memoria o espera agotada | sí |
| 8 | Fragmentos de la ficha, orden económico, descarte | no peor que la referencia | no, se informa |

Si los puntos 1 a 2 y 6 a 7 se cumplen pero la mejora de 3 y 4 queda entre 2 y 3 pares, se hace la segunda ronda; si queda por debajo de 2, no. Rondas: ronda 1 es T-162; ronda 2 (T-163, condicional) permite un solo cambio, y el mismo para los dos modelos (presupuesto de grupo o la instrucción del contraste, y entonces se repite también la referencia: sube el tiempo). Después no hay más rondas: queda el 12B y el impacto pasa a la lista de revisión (ADR-0024). Sin mejora con razones medidas, queda el 12B; el 26B no se mantiene instalado.

### Cuánto tarda (estimación honesta; la medición real corrige estos números)

Referencia medida: el caso chico con el 12B tarda de 37 a 41 s por oferta (54 pedidos, 24 de ellos contrastes, `verificacion/T-151.md`). El caso-00 pesa más: 3 ofertas, 49 pares con dictamen, ofertas de 9, 16 y 45 páginas (la oferta 2 queda a 471 tokens del presupuesto de grupo; la 1 pasa a dos grupos), unos 150 a 250 pedidos entre lectura y contraste, con el prefijo de documentos reutilizado dentro del grupo. No hay medida de tiempo del caso-00 completo en el repositorio.

| Paso | Estimación | Quién espera |
|---|---|---|
| Descarga de 15,6 GB (26B 14,44 GB + proyector 1,19 GB; y el proyector del 12B, 0,18 GB), con verificación de huella | 15 a 45 min según la conexión (a 10 a 15 MB/s unos 20 a 25 min) más 3 min de huellas | desatendida |
| Puesta en marcha del servicio, prueba de humo con texto y con imagen, medición de memoria | 1 h de trabajo (la carga del modelo, 1 a 3 min) | T-159 |
| Corrida de referencia, 12B con visión, caso-00 | 10 a 25 min de GPU | T-161 |
| Corrida del 26B con visión, caso-00 | 15 a 45 min de GPU (de 0,7 a 2 veces la del 12B; la mezcla de expertos genera rápido y lee contexto largo a velocidad parecida) | T-162 |
| Informe y revisión par por par | 1 a 2 h de trabajo | T-162 |
| **Total, una ronda** | **3 a 5 horas de reloj; unas 1 a 1,5 h de GPU** | |
| Segunda ronda, si se hace | 1,5 a 2 h de reloj más las dos corridas de nuevo | T-163 |

## Consecuencias

- Más fácil: la decisión de modelo queda con evidencia por par y no por impresión; el compose base no cambia de modelo; volver es no usar el archivo adicional.
- Más difícil: 15,6 GB más en `models/` (fuera del repositorio) y en `scripts/models.sha256`; durante la prueba no corren evaluaciones con el 12B del lote; el contexto y la memoria quedan atados a la comparación; si se adopta, hay que reabrir el reparto del ADR-0002 (generación hasta 18 GB, embeddings y reranker hasta 3 GB, margen 3 GB) con la medición real y actualizar el ADR-0037 y `entorno.md`.
- Si se adopta: ADR nuevo que reemplaza el modelo del motor de lotes (el ADR-0002 dice que se registre el cambio), con las dos corridas como evidencia. `generation` (consulta de normativa) queda en 12B salvo otra decisión: hay que medir la 001 antes de cambiarlo (P7).
- Para revertir: recrear `generation_batch` con el compose base.

## Fuentes

Consultadas el 2026-10-06 mediante una herramienta que resume las páginas (ver "Sin verificar").

- API de árbol de archivos de `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` (tamaños y SHA-256): https://huggingface.co/api/models/google/gemma-4-26B-A4B-it-qat-q4_0-gguf/tree/main
- Revisión de `google/gemma-4-26B-A4B-it-qat-q4_0-gguf`: https://huggingface.co/api/models/google/gemma-4-26B-A4B-it-qat-q4_0-gguf/revision/main
- Ficha: https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf
- API de árbol de `google/gemma-4-31B-it-qat-q4_0-gguf`: https://huggingface.co/api/models/google/gemma-4-31B-it-qat-q4_0-gguf/tree/main
- API de árbol de `google/gemma-4-12B-it-qat-q4_0-gguf` en la revisión fijada: https://huggingface.co/api/models/google/gemma-4-12B-it-qat-q4_0-gguf/tree/29d097773436b69ff9feafd636ab4cf873786537
- ADR-0002 (fuente [25]: mediciones de memoria y velocidad de un tercero en RTX 5090 de escritorio), ADR-0037, `specs/004-evaluacion-asistida/entorno.md`.

## Sin verificar

- **Las huellas y los tamaños se leyeron por una herramienta que resume.** El descargador verifica la huella contra `scripts/models.sha256` y falla si no coincide; esa es la comprobación real. La revisión del 26B (`d1c082be…`) debe confirmarse al fijar la URL.
- Que la compilación `server-cuda-b11347` cargue el 26B-A4B (mezcla de expertos) y su proyector: T-159, antes de cualquier medición.
- La memoria del 26B con contexto 32.768 es una estimación a partir de datos de otra GPU y de otro archivo; la memoria real y la velocidad en esta notebook no están medidas.
- Las velocidades citadas son de un tercero y de otra GPU; los tiempos de la tabla son estimaciones.
- La espera por pedido del motor de lotes (`GENERATION_BATCH_TIMEOUT_SECONDS`, 180 s) puede quedar corta con el 26B en un grupo de 20.000 tokens: se mide en T-159 y, si hace falta, se sube para las dos corridas.

## Resultado (2026-10-06)

Medido en T-162 (`specs/004-evaluacion-asistida/verificacion/T-162.md`): el 26B-A4B dio 15 de 49 coincidencias contra 24 del 12B (referencia T-161), 0 contradicciones, 0 de 2 no cumple reales contra 1 de 2, la mitad del tiempo y 17.965 MiB con `generation` apagado. No cumple los puntos 3, 4 y 5 de la tabla de adopción: **se queda el 12B**. No corresponde la ronda 2 (T-163).
