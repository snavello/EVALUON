# ADR-0056 · Modelos candidatos para el motor de lotes: Qwen3.8-27B y Qwen3.6-35B-A3B, y protocolo de la comparación

Estado: aceptado · Fecha: 2026-10-10 · Decidió: — (el responsable pidió el 2026-10-10 «evaluar probar otros modelos locales de IA como qwen 3.6 30B o el que sugieras» y aprobó bajar Qwen3.8-27B y Qwen3.6-35B-A3B; qué se elige es del Planificador y se somete a su aprobación)

## Contexto

La comparación del ADR-0042 (2026-10-06) midió Gemma 4 26B-A4B contra el 12B con el mismo uso: 15 de 49 coincidencias contra 24, 0 contradicciones, 17.965 MiB con `generation` apagado. **Se quedó el 12B.** Un modelo de 3.800 M de parámetros activos perdió contra uno denso de 12.000 M.

El diagnóstico del 2026-10-10 atribuye el 85 % de los errores de T-229 al uso y el 15 % al modelo; la spec 015 pide corregir el uso y **después** comparar modelos con ese uso (REQ-107), porque sin corregirlo comparar no sirve (el 26B ya perdió con el mismo uso).

La investigación de candidatos (2026-10-10, fuera del repositorio; las fichas y las listas de archivos se leyeron por un proxy de texto porque `huggingface.co` no respondió desde este equipo) encontró:

- **«Qwen 3.6 30B» no existe.** Qwen3.6 abierto tiene dos modelos: **Qwen3.6-35B-A3B** (mezcla de expertos, 35.000 M totales y 3.000 M activos, 2026-04-16) y **Qwen3.6-27B** (denso, 2026-04-22). Después salió **Qwen3.8-27B** (denso, 2026-08-14). Los tres tienen licencia Apache 2.0 y visión.
- Archivos (API de Hugging Face, consultada el 2026-10-10 con una herramienta que resume; la huella real se comprueba al bajar): `unsloth/Qwen3.8-27B-GGUF`, `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16.464.440.224 bytes (SHA-256 informado `322e194f…23482`), proyector `mmproj-F16.gguf` 927.607.488 bytes (`cbb841a9…e43e`); `unsloth/Qwen3.6-35B-A3B-GGUF`, `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf`, 17.730.509.792 bytes (`649d7508…ebbb3`), proyector `mmproj-F16.gguf` 899.283.680 bytes (`8971ee4f…887f`).
- Memoria estimada (sin medir) con lo fijo de 2.455 MiB del ADR-0042: Qwen3.8-27B unos 21.600 MiB, Qwen3.6-35B-A3B unos 21.400, contra el tope de 22.000.
- Riesgos conocidos: la caché de prefijo de llama.cpp con modelos de atención híbrida (Qwen3.5/3.6/3.8) puede reprocesar todo el prompt (incidencias 21831 y 23030 de llama.cpp, cerradas «not planned»), lo que anularía el ahorro del prefijo de grupo de la evaluación; los benchmarks de los fabricantes son con pensamiento y EVALUON corre sin pensamiento y a temperatura 0; CUDA 13.2 da salida corrupta con Qwen3.6 según Unsloth (la etiqueta `server-cuda` de la compilación fijada b11347 es CUDA 12 por defecto: se comprueba); el `presence_penalty` 1,5 que recomienda Qwen rompe las citas literales y no se usa.
- Los archivos son de un tercero (Unsloth), no del autor del modelo como el 12B de Google (ADR-0002). La huella y la revisión fijada compensan el origen.

Restricciones: una sola GPU y una medición a la vez (ADR-0025); 22.000 MiB como máximo (ADR-0042); P4 (el motor corre con `--offline`; la descarga es el único paso con internet, una vez por equipo); P5 (reproducible); el protocolo es el del ADR-0042: **todo igual salvo el modelo**.

## Alternativas

### A. Qwen3.8-27B denso, UD-Q4_K_M (propuesta, primero)
Se gana: 27.000 M de parámetros activos (el 26B-A4B tenía 3.800 M); el mejor IFBench de la lista (79,5 contra 69,1 del Qwen3.6-27B, ficha oficial, con pensamiento); buena lectura de documentos (OmniDocBench 91,1); misma arquitectura `qwen35` que llama.cpp soporta desde febrero de 2026. Se pierde: más lento (denso; unos 35 a 45 tokens por segundo estimados contra unos 73 del 12B, extrapolado de un tercero, sin medir): el caso-00 completo podría pasar los 60 minutos; memoria al borde del tope; sin IFEval multilingüe publicado.

### B. Qwen3.6-35B-A3B mezcla de expertos, UD-IQ4_XS (propuesta, segundo)
Se gana: es lo que el responsable nombró; rápido (unos 100 tokens por segundo en una RTX 3090, de un tercero); MMLU-Pro 85,2. Se pierde: 3.000 M activos, el mismo riesgo del 26B-A4B que perdió; cuantización IQ4_XS más agresiva para entrar. Se mide para cerrar la pregunta, no como favorito.

### C. Qwen3.6-27B denso (control)
Se gana: la misma familia y el tamaño de A con una generación menos. Se pierde: una medición más sin que haya motivo todavía; queda de respaldo si A da problemas de servicio.

### D. Los otros que la investigación descartó
Muse Glimmer-30B (Meta): alucinación del 82 % contra 49 % de Qwen3.6-27B en AA-Omniscience, un riesgo para citas literales; solo si fallan los dos. Ministral 3 14B: sin benchmarks verificados. gpt-oss-20b: sin visión. Gemma 4 31B: sin margen de memoria (ADR-0042). Mistral Small 4 y GLM-5.3-Flash: no caben.

### E. No comparar
Se gana: ninguna hora de GPU. Se pierde: el responsable no sabría si el 15 % atribuido al modelo se arregla con más modelo; lo pidió expresamente.

## Decisión

Se propone **medir A y después B, de a uno**, con este protocolo (T-242 a T-247):

1. **Mismo todo menos el modelo:** mismo commit del código, mismas instrucciones, mismo caso (caso-00 y casos 01 a 06), misma lista esperada con su huella, mismos parámetros del motor (contexto 32.768, `--parallel 1`, temperatura 0, semilla fija, sin pensamiento nativo: `enable_thinking: false`). Nada se ajusta al candidato; si lo necesita, es un hallazgo. La única variable de servicio que se puede mover para que entre en memoria es el tipo de caché de claves y valores (`q8_0`), y se registra.
2. **Servicio:** un archivo adicional de Docker Compose por candidato, como el ADR-0042 (`docker-compose.modelo-grande.yml` queda para el 26B); cada uno reemplaza solo `generation_batch`. El compose base no cambia. Volver es no usar el archivo.
3. **Registro (P6):** alias, huella del archivo y del proyector, compilación de llama.cpp, contexto, tipo de caché y banderas de la caché de prefijo, en la corrida y en cada pedido, por las variables `GENERATION_BATCH_*` que la aplicación ya lee. Antes de la primera medición se corrige (T-251) que el cuerpo del pedido de lotes diga el modelo de `generation` y que los tokens de los lotes se cuenten con el tokenizador de `generation`, que es el de Gemma: con otro modelo el presupuesto de los lotes y de los grupos de documentos saldría mal contado. La referencia del 12B se mide con ese mismo código.
4. **Antes de medir un candidato:** prueba de humo con texto y con imagen, memoria máxima medida, control de la caché de prefijo (un segundo pedido con el mismo prefijo reutiliza al menos el 90 % de sus tokens) y control del razonamiento apagado (cero tokens de pensamiento en la salida).
5. **Compuerta de salida temprana:** se corre primero el caso-00 completo (matriz y evaluación de las tres ofertas); si el candidato no entra en 22.000 MiB, tarda más de 60 minutos o da una contradicción con el dictamen, se descarta sin correr los casos 01 a 06, con esa evidencia.
6. **Umbral de adopción (REQ-107, escrito antes de medir):** cumple REQ-101 a REQ-105 al menos tan bien como el 12B con el uso corregido; mejora al menos una de esas medidas, con razones por par (cada par que cambia se revisa y se clasifica); no empeora contradicciones (0), citas literales (100 %), tiempo ni memoria; entra en 22.000 MiB; el caso-00 completo tarda como máximo 60 minutos.
7. **Rondas:** una sola; sin ronda de ajuste por candidato (ADR-0024 y ADR-0025). Lo que falte pasa a la lista de revisión con su impacto.
8. **Resultado:** un ADR nuevo (reservado ADR-0057) que adopta o descarta, con las dos corridas como evidencia. Adoptar cambia el reparto del ADR-0002 y exige aprobación del responsable y el despliegue (P11); `generation` (consulta de normativa) queda en 12B salvo otra decisión, porque hay que medir la 001 antes de cambiarlo (P7).

## Consecuencias

Más fácil: la decisión de modelo queda con evidencia por par y con el uso corregido; volver al 12B es no usar el archivo adicional.

Más difícil: unos 36 GB más en `models/` (fuera del repositorio) y cuatro huellas más en `scripts/models.sha256`; dos archivos de compose más (se suman al del 26B) con sus tests de coherencia (`tests/test_compose_env.py`, `tests/tenders/test_generation_batch.py`); entre 6 y 12 horas de GPU en total (la medición del 12B con el uso corregido, las dos pruebas de humo de una hora y las dos comparaciones de 1,5 a 3,5 horas cada una), sin otra carga mientras tanto (estimación a medir); origen de los archivos en un tercero.

Para revertir: recrear `generation_batch` solo con el compose base y borrar los archivos de `models/`.

## Fuentes

Consultadas el 2026-10-10 (las de Hugging Face, por una herramienta que resume y por el proxy de texto del informe local; la comprobación real es la huella al descargar):

- Árbol de archivos de `unsloth/Qwen3.8-27B-GGUF`: https://huggingface.co/api/models/unsloth/Qwen3.8-27B-GGUF/tree/main
- Árbol de archivos de `unsloth/Qwen3.6-35B-A3B-GGUF`: https://huggingface.co/api/models/unsloth/Qwen3.6-35B-A3B-GGUF/tree/main
- Fichas oficiales: https://huggingface.co/Qwen/Qwen3.8-27B, https://huggingface.co/Qwen/Qwen3.6-27B, https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Repositorios de Qwen (listas de modelos): https://github.com/QwenLM/Qwen3.6 y https://github.com/QwenLM/Qwen3.8
- Soporte de la arquitectura `qwen35` en llama.cpp: https://github.com/ggml-org/llama.cpp/pull/19468; caché de prefijo en modelos híbridos: https://github.com/ggml-org/llama.cpp/issues/21831 y https://github.com/ggml-org/llama.cpp/issues/23030
- Apagar el pensamiento y CUDA 13.2: https://unsloth.ai/docs/models/qwen3.6 y https://unsloth.ai/docs/models/qwen3.8
- Alucinación de Muse Glimmer-30B: https://artificialanalysis.ai/articles/muse-glimmer
- Velocidad de un tercero para el 35B-A3B: https://insiderllm.com/guides/qwen-3-6-local-ai-guide/
- ADR-0002, ADR-0037, ADR-0042 y `specs/004-evaluacion-asistida/entorno.md`.

## Sin verificar

- **Memoria, velocidad y caché de prefijo de los dos candidatos con esta compilación y esta notebook:** son estimaciones o datos de otra GPU; las miden T-243 (Qwen3.8-27B) y T-245 (Qwen3.6-35B-A3B) antes de cada comparación.
- **Que la compilación `server-cuda-b11347` cargue las dos arquitecturas** (`qwen35` y `qwen35moe`) y los proyectores: lo comprueban T-243 y T-245.
- **Muestreo de Qwen:** sus fichas recomiendan parámetros distintos de la temperatura 0 y desaconsejan la decodificación codiciosa **con pensamiento**; sin pensamiento y a temperatura 0, que es el protocolo, no se verificó. No se usan los valores de las fichas (no se consultaron en esta revisión).
- **Las huellas y los tamaños** se leyeron por una herramienta que resume y por el proxy del informe local: el descargador falla si la huella no coincide con `scripts/models.sha256`; esa es la comprobación real.
- **Las revisiones exactas** de los repositorios (por ejemplo `4ca72078…` para Qwen3.8-27B) se fijan completas al fijar las URL en T-242.
- **La velocidad de los modelos densos de 27.000 M** en esta GPU: por eso el límite de 60 minutos puede dejar fuera a A.
