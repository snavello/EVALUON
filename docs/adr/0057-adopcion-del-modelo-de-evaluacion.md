# ADR-0057 · Adopción del modelo de evaluación: Qwen3.8-27B con razonamiento solo en el contraste

Estado: aceptado · Fecha: 2026-10-12 · Decidió: responsable del proyecto (2026-10-12, «Sí; Consulta con el 27B», literal en la spec 015). Reemplaza en parte al ADR-0002 (modelo del motor de lotes y reparto de memoria). Resultado de la comparación que fijó el ADR-0056.

## Contexto

La spec 015 pidió corregir primero el uso del modelo y después comparar modelos con ese uso (REQ-107). El ADR-0056 fijó el protocolo (todo igual salvo el modelo; umbrales escritos antes de medir; 22.000 MiB) y, con su enmienda del 2026-10-11, los topes de tiempo del caso-00 completo: 90 minutos sin razonamiento y 180 con él («Entre rapido y mal y lento y bien elijo lo segundo»). Referencia: el Gemma 4 12B del motor de lotes, medido en T-241 con el código `5671425`. Las variantes se midieron con el caso-00 (LPU25) y, la matriz, con los casos 01, 02 y 06 (los demás no se midieron por el cambio de alcance del Coordinador del 2026-10-12).

Las mediciones, todas en `specs/015-uso-y-eleccion-del-modelo/verificacion/`:

| Registro | Qué mide |
|---|---|
| T-241 | 12B, referencia (código `5671425`) |
| T-244, T-244b, T-244c | Qwen3.8-27B sin razonamiento, con razonamiento en filtro y contraste, y en cuatro pasos (código `5671425`) |
| T-244d | Qwen3.8-27B con razonamiento `low` solo en el contraste, con el código de la ronda extra T-254 (`8e3f2f2`); es la configuración candidata |
| T-245, T-246, T-246b, T-246c | Qwen3.6-35B-A3B: servicio, sin razonamiento, razonamiento en el contraste y en cuatro pasos (código `8e3f2f2`) |

## Alternativas

### A. Qwen3.8-27B con razonamiento `low` solo en el contraste (adoptada)

Cifras del caso-00 (T-244d), contra el 12B de T-241 (la lista presente de las dos se recalculó con el archivo de exclusiones del 2026-10-12, 9 excluidas):

| Medida | Umbral | 12B (T-241) | 27B (T-244d) |
|---|---|---|---|
| Filas que la Comisión conserva | 70 % o más | 29 de 54 = 53,7 % | 28 de 33 = 84,8 % |
| Pedazos sin sujeto | 0 | 2 | 0 |
| Lista esperada presente | 95 % o más | 40 de 43 = 93,0 % | 40 de 43 = 93,0 % |
| Portal: «cumple» con la cita del Portal | 100 % | 12 de 20 = 60,0 % | 16 de 21 = 76,2 % |
| «No determinado» que cuenta | 15 % o menos | 24 de 80 = 30,0 % | 18 de 81 = 22,2 % |
| Contradicciones con el dictamen | 0 | 0 | 0 |
| Citas literales | 100 % | 100 % | 100 % |
| «Cumple» con una cita que no lo sostiene | 0 | 0 | 0 |
| Preguntas conformes | 100 % | 15 de 19 = 78,9 % | 13 de 13 = 100 % |
| Tiempo del caso-00 completo | 90 min (180 con razonamiento) | 31,6 min | 72,9 min (matriz 12,3 + evaluación 60,6) |
| Memoria de video máxima | 22.000 MiB | 18.715 MiB (cuatro motores) | 20.956 MiB (sin `generation`) |

En otros casos (matriz): caso-02, 94 de 98 de la lista (95,9 %); caso-01, 75 de 82 (91,5 %); caso-06, 33 de 37 (89,2 %) contra 34 de 37 (91,9 %) del 12B. Cumple la regla de adopción de REQ-107 contra el 12B en lo medido (T-244d, «Regla de adopción»): mejora cinco medidas con razones par por par y empata la lista presente, sin empeorar contradicciones ni citas. Las otras variantes del 27B no la cumplen: sin razonamiento (T-244) deja la lista presente en 70,8 % contra 85,4 % del 12B con el archivo de entonces y suma un «cumple» sin respaldo (el contraste con razonamiento lo frena); con razonamiento en filtro y contraste (T-244b) la lista queda en 79,2 % y las filas conservadas en 66,7 %; con razonamiento en cuatro pasos (T-244c) aparece 1 contradicción con el dictamen y el tiempo sube a 120,6 min.

Se gana: la mejor matriz medida (menos filas que quitar: no propone 19 de las 54 del 12B), el mejor Portal, menos «no determinado», preguntas conformes y ninguna contradicción. Se pierde: 2,3 veces el tiempo del 12B; la memoria roza el tope (margen de 1.044 MiB) y **solo entra con `generation` apagado**.

### B. Qwen3.6-35B-A3B (descartado)

Entra en servicio (T-245: 21.286 MiB, reuso de la caché de prefijo de 97,7 % a 98,5 %, 0 tokens de pensamiento). Es el más rápido: 14,7 min sin razonamiento (2,2 veces más rápido que el 12B) y 40,3 min con razonamiento en cuatro pasos. Pero ninguna de sus variantes llega al 12B sin un defecto:

| Variante | Qué falla contra el 12B |
|---|---|
| Sin razonamiento (T-246) y con razonamiento en el contraste (T-246b, con los mismos resultados) | lista presente 39 de 43 = 90,7 % (12B: 93,0 %); «no determinado» 25 de 80 = 31,2 % (12B: 30,0 %); preguntas conformes 15 de 20 = 75,0 % (12B: 78,9 %); 1 «cumple» con respaldo parcial (12B: 0). Mejoran filas conservadas (69,0 %), pedazos y Portal (65,0 %) |
| Con razonamiento en cuatro pasos (T-246c) | 1 «cumple» sostenido por una cita que no dice lo que se afirma (P3) y coincidencia con el dictamen de 45 de 49 (12B: 46); la extracción descarta la oferta sin condicionamientos como consecuencia en 3 de los 4 casos medidos (H-246c-3) |

Contra el 27B del mismo código (T-244d): filas conservadas 75,7 % contra 84,8 % en la mejor variante; en los casos, la lista presente baja de 33 a 29 de 37 en el caso-06 (78,4 % contra 89,2 %), de 94 a 92 de 98 en el caso-02 y de 75 a 69 de 82 en el caso-01 (84,1 % contra 91,5 %). Es también el que más memoria usa (21.292 MiB; margen de 708 MiB) y solo entra con `generation` apagado, igual que el 27B. Su plantilla no admite el nivel de razonamiento (`reasoning_effort`): el nivel `low` no le llega y todos los pasos que piensan llegan al tope de 1.024 tokens (T-246b, T-246c). Razón del descarte: no cumple la regla de adopción y el 27B la cumple; la velocidad no compensa quedar con más requisitos afuera (decisión del 2026-10-11: calidad antes que velocidad).

### C. Gemma 4 26B-A4B (descartado desde el ADR-0042)

Medido en T-162 con el mismo uso: 15 de 49 coincidencias contra 24 del 12B, 0 contradicciones, 0 de 2 «no cumple» reales contra 1 de 2, la mitad del tiempo y 17.965 MiB con `generation` apagado (ADR-0042, «Resultado»). No cumplió los puntos 3, 4 y 5 de su tabla de adopción y se quedó el 12B. No se volvió a medir con el uso corregido: el Qwen3.8-27B, denso y de 27.000 M de parámetros activos contra los 3.800 M del 26B, lo supera con el uso corregido, y el ADR-0056 ya lo había reemplazado como modelo de contraste.

### D. Seguir con el Gemma 4 12B

Es la referencia y cumple todos los topes con holgura (31,6 min; 18.715 MiB con los cuatro motores encendidos, la Consulta incluida). Queda como camino de vuelta, no como opción: con el uso corregido pide quitar casi la mitad de las filas (53,7 % conservadas) y deja 4 de cada 10 celdas del Portal sin «cumple» (T-241).

### E. Resto de las alternativas del ADR-0056

Qwen3.6-27B denso (control): no se midió; quedaba de respaldo «si A da problemas de servicio» y el 27B sirvió sin problemas (T-243, T-244 a T-244d). Muse Glimmer-30B, Ministral 3 14B, gpt-oss-20b, Gemma 4 31B, Mistral Small 4 y GLM-5.3-Flash: descartados por el ADR-0056 (alucinación, sin visión, sin margen de memoria o sin caber) y no hizo falta volver a ellos. No comparar: superada por la decisión del responsable de medir.

## Decisión

Decisión literal del responsable (2026-10-12): «Sí; Consulta con el 27B».

1. **Se adopta el Qwen3.8-27B** (`Qwen3.8-27B-UD-Q4_K_M.gguf`, huella `322e194f…9123482`, con su proyector de imagen; ADR-0056, `entorno.md`) **para el motor de lotes** (`generation_batch`: matriz, evaluación, fichas, lectura con visión), **con el razonamiento propio del modelo en nivel `low` solo en el contraste** de la evaluación (`GENERATION_BATCH_REASONING_CONTRAST=low`, tope de 1.024 tokens de razonamiento por pedido). Los demás pasos (extracción, completitud, filtro, evaluación) no piensan: T-244b y T-244c mostraron que con razonamiento empeoran la matriz o la evaluación del 27B.
2. **Se descartan** el Qwen3.6-35B-A3B y el Gemma 4 26B-A4B, con las cifras de arriba.
3. **Un solo motor.** El 27B atiende evaluaciones y Consulta; el motor de la Consulta (`generation`, 12B) desaparece cuando se cumpla T-255. Antes de pasar la Consulta al 27B se miden las evals de la 001 (P7: 85 % de aciertos, 90 % de abstención, 100 % de cita literal, ADR-0002) y ninguna medida puede empeorar frente al 12B. Mientras tanto la Consulta queda apagada (consecuencias).
4. **Configuración de uso por omisión** (lo más simple y reversible):
   - `.env.example` trae `COMPOSE_FILE=docker-compose.yml:docker-compose.qwen38-27b.yml:docker-compose.razonamiento.yml:docker-compose.sin-consulta.yml`, `COMPOSE_PATH_SEPARATOR=:` y `GENERATION_BATCH_REASONING_CONTRAST=low`. Un `.env` copiado de ese ejemplo hace que `docker compose up -d` levante el 27B en `generation_batch` con razonamiento en el contraste y sin `generation`. Los comandos de mediciones y runbooks anteriores usan `-f archivo` explícito y no leen `COMPOSE_FILE`: siguen valiendo.
   - Un archivo nuevo, `docker-compose.sin-consulta.yml`, pone `generation` en el perfil `consulta-12b` (no arranca) y hace que `app` no lo espere (`required: false`). Es lo único nuevo: el compose base y el de razonamiento no cambian de contenido (el base monta dos archivos más en `app` para los tests de coherencia, `docker-compose.sin-consulta.yml` y `.env.example`) y el del 27B suma solo la espera de la carga, un `start_period` de 900 s en el chequeo de salud de `generation_batch`.
   - **Por qué esta y no otra.** (a) Pasar el 27B al compose base y dejar el 12B como archivo adicional: cambia el `command`, los valores por omisión en el compose, en `settings.py` y en `.env`, y los tests de coherencia que comparan `generation_batch` con `generation` y con los candidatos; los comandos de todos los runbooks y mediciones (`-f docker-compose.yml`) dejarían de significar «el 12B». Más superficie para el mismo efecto. (b) `docker-compose.override.yml`: Compose lo lee solo, incluso en `docker compose run ... pytest`, en el cierre de tareas y en cualquier comando sin `-f`; cambiaría el entorno de las pruebas sin que se note. (c) Perfiles en el base: el base dejaría de levantar la Consulta, que sigue siendo la instalación de la 001 a la 014.
   - **Reversibilidad.** Volver al 12B con la Consulta es borrar o comentar las tres líneas de `.env` y recrear los servicios (`entorno.md`, «Cómo se vuelve al 12B»). No hay migración ni dato que cambie; los archivos del 12B siguen en `models/`. Un `.env` existente no cambia hasta que se le agreguen esas líneas: desplegarlo es una decisión de P11.
   - **Riesgo conocido.** `COMPOSE_FILE` en `.env` alcanza a todo `docker compose` sin `-f` que se corra en esa carpeta, incluso las pruebas (`docker compose run --rm app pytest`): la aplicación recibe entonces las variables del 27B. Los tests de coherencia (`tests/test_compose_env.py`) leen los archivos de compose y no dependen de ello.
5. **La propuesta de datos del procedimiento** (`procedure_fields`, el alta desde el pliego) pasa de `generation` al motor de lotes (`generate_batch`), para que funcione con el 27B; su traza de auditoría nombra el motor y el modelo (`models.generation_batch`), como la matriz y la evaluación (P6). **La Consulta**, cuando el motor `generation` no responde, muestra «La consulta de normativa no está disponible por ahora…» en su pantalla y en la pestaña de Normativas, con el botón desactivado, y no ejecuta la pregunta ni guarda una consulta fallida. Antes del aviso, con `generation` caído, la pregunta recorría la recuperación y terminaba en «No se pudo completar la consulta. Hubo una falla técnica…», con una consulta fallida guardada.

## Consecuencias

**Reparto de memoria (reemplaza en parte al ADR-0002 y al ADR-0037).** El 27B en `generation_batch`, con `embeddings` y `reranker` y sin `generation`, ocupa 20.956 MiB de 24.463 (tope 22.000). El reparto del ADR-0002 (generación hasta 18 GB) queda superado: el motor de lotes pasa a usar unos 18 GB; `generation` (12B, unos 7.800 MiB) ya no entra. Contexto 32.768, caché f16, `--ctx-checkpoints 32`, `--checkpoint-min-step 1024` (ADR-0056, T-243).

**Lo que sigue del ADR-0002:** el motor (`llama-server`, compilación fijada, `--offline`), la salida con esquema JSON, la cita literal y la abstención. El modelo inicial de la Consulta sigue siendo el 12B hasta T-255.

**Tiempo y carga.** El caso-00 completo tarda 72,9 minutos contra 31,6 del 12B. La carga del modelo hasta `/health` tarda de 3 a 10 minutos (3 min 4 s en T-244d). Con los 120 s de `start_period` del compose base, el motor de lotes pasaba a `unhealthy` durante la carga y `docker compose up -d` (el `worker` espera su salud) terminaba con error; el archivo del 27B sube ese `start_period` a 900 s, y `docker compose up` desde cero tarda ese tiempo más en estar listo para evaluar. El requisito no funcional de la spec de 60 minutos queda reemplazado por los topes del 2026-10-11 (90 y 180 minutos).

**La Consulta queda apagada** mientras el 27B esté en el motor de lotes, hasta T-255 (que mide las evals de la 001 con el 27B, P7, y quita `generation` y `docker-compose.sin-consulta.yml`). Los usuarios ven el aviso, no una falla. La búsqueda directa de normativa no usa el modelo y sigue disponible.

**Lo que usa hoy `generation` y queda sin motor.** Con el 27B sin `generation`, la Consulta (esperado) y la propuesta de datos del **oferente** (`evaluon/offers/proposal_fields.py`, el nombre del oferente: pide a `generation.generate`). Esta última degrada sin fallar (el dato queda «no determinado»; `except AIServiceError`), y no se cambió aquí porque la toca T-248 (instrucciones del nombre del oferente): conviene pasarla al motor de lotes en esa tarea. Fichas, lectura con visión, informe técnico, matriz, respaldo normativo y evaluación ya piden al motor de lotes.

## Salvedades

1. **La referencia del 12B es de antes de T-254.** El 12B se midió con el código `5671425` y el 27B de T-244d con `8e3f2f2` (el responsable pidió no repetir el 12B). Parte de la ventaja en filas conservadas (84,8 % contra 53,7 %) puede ser del código: las 10 filas del formulario de la declaración jurada pueden deberse a T-254, y los 6 requisitos que el 27B recupera contra T-244 los traía el 12B con el código anterior, así que contra el 12B no son mejora. Las 9 filas restantes que el 27B no propone ya no las proponía con el código anterior (T-244): vienen del modelo.
2. **El caso-06 tiene un requisito menos que el 12B:** 33 de 37 contra 34 de 37, la prórroga automática del mantenimiento, que en el caso-00 falta en todas las variantes. El caso-02 llega al 95,9 %.
3. **Las metas absolutas de la spec no se cumplen**, como tampoco las cumplía el 12B: lista presente 93,0 % (meta 95 %), Portal 76,2 % (meta 100 %), «no determinado» 22,2 % (meta 15 %). Lo que falta pasa a la lista de revisión con el primer producto, con su impacto (ADR-0024 y ADR-0025): en el caso-00, 5 de 21 celdas del Portal no llegan a «cumple» y 18 de 81 celdas quedan «no determinado» sin esperar un documento ausente. No se perdió ningún requisito ni se violó un principio, así que no hay otra ronda.
4. **Una sola medición por variante** y la evaluación de la configuración elegida es idéntica a la de T-244b (T-244d). Los casos 01 y 02 no tienen referencia del 12B con el código de T-241 (H-244-6 impidió medirlos).
5. **El 27B solo entra con `generation` apagado.** No hay margen para encender el motor de la Consulta junto con él (T-243, T-244).

## Para revertir

Borrar o comentar en `.env` las líneas `COMPOSE_FILE`, `COMPOSE_PATH_SEPARATOR` y `GENERATION_BATCH_REASONING_CONTRAST`, y recrear `generation_batch`, `worker`, `app` y `generation` solo con el compose base: vuelve el 12B con la Consulta. La reversa de los cambios de código (`procedure_fields` al motor de lotes, aviso de la Consulta) no hace falta: con el 12B en los dos motores se comportan igual que antes. Borrar los 17,4 GB del 27B de `models/` requiere la confirmación del responsable.
