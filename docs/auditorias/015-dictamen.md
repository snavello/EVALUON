# Dictamen de auditoría de fallas · Feature 015 (uso y elección del modelo)

- **Alcance:** `specs/015-uso-y-eleccion-del-modelo/`, rango 0a92295a..70e5aa54 (`main`), 191 commits (144 sin merge), 303 archivos. Auditoría de fallas según ADR-0052: lo que no anda, resultados equivocados, conclusiones sin respaldo (P3, constitución 1.4) y datos reales, reservados o secretos (P4). Copia propia `evaluon-wt-015-auditoria` (desacoplada en 70e5aa54) y proyecto docker propio `evaluon-aud015` (base propia, aplicación en 127.0.0.1:8039). No usé la GPU ni el puerto 8000.
- **Resultado:** aprobado con observaciones

## Hallazgos

Sin hallazgos bloqueantes.

1. **Mayor, no bloqueante · P3 (el Portal como fundamento, constitución 1.3 y 1.4, ADR-0053).** Un «cumple» cuyo único fundamento es el dato del Portal se muestra sin el enlace y sin la fecha en que se tomó el dato. P3 exige las dos cosas para ese fundamento.
   - Evidencia:
     - `evaluon/templates/journey/temas/s4_propuesta_par.html:34` (detalle del par en «Evaluación y dictamen») muestra solo `Dato del Portal: {{ c.text }}`.
     - `evaluon/templates/assessment/result.html:52-56` (pantalla de la 004) trae el enlace a la página del Portal, pero no la fecha.
     - La fecha existe (`PortalPage.fetched_at`, `evaluon/portal/models.py:122`) y solo se muestra en las pantallas del Portal (`templates/portal/imported.html:21`, `templates/portal/proposal.html:47`).
   - Cómo se reproduce: con una prueba propia (fuera del repositorio) que usa los ayudantes de `tests/assessment/test_portal_facts.py` (`portal_data`, `run_all`) y pide `expedientes:s4_par`:
     - La regla da `portal_cumple` y el resultado es «cumple».
     - El bloque «Lo que presentó la oferta» dice: «Sin texto de la oferta que respalde una conclusión… Dato del Portal: Garantía: tipo Garantía de mantenimiento de oferta, forma Póliza de caución, monto 21750.00».
     - El HTML no contiene la dirección de la página del Portal ni su fecha de consulta.
     - En `assessment:pair` la sección «Lo que informa el Portal» trae el enlace y no la fecha.
   - Qué corregir: junto a cada cita del Portal en el detalle del par, el enlace a la página o al archivo del Portal y la fecha `fetched_at`. En la pantalla de la 004, la fecha. Un test que lo afirme.

2. **Mayor, no bloqueante · P3 (texto de la oferta leído por visión).** En la pantalla principal, una cita tomada de una página leída por visión se muestra como texto literal de la oferta. No lleva la marca «leída por visión» ni el aviso «Compare con el original antes de confirmar» que muestra la pantalla de la 004. Con la configuración que adopta esta feature (Qwen3.8-27B en `generation_batch`, ADR-0057), la visión por página sigue encendida por omisión, y el repositorio registra que el 27B inventó datos al leer un pagaré manuscrito.
   - Evidencia:
     - `evaluon/templates/journey/temas/s4_propuesta_par.html:32` pone la cita en `<blockquote class="cita">` sin marca. `evaluon/templates/assessment/result.html:78-83` sí muestra la marca, la imagen de la página y el enlace al original.
     - `evaluon/settings.py:522`: `ASSESSMENT_VISION_MAX_PAGES = 40`.
     - `evaluon/settings.py:529-534`: «en el pagaré del caso-00 el 27B inventó el año, el concepto y el proceso, y P3 no admite datos inventados». Por eso se apagó la visión por pasaje, pero no la visión por página.
     - `specs/015-uso-y-eleccion-del-modelo/verificacion/T-259.md:92` (aviso 1): la visión por página sigue encendida. No encontré en el repositorio una decisión posterior sobre ese aviso.
     - `verificacion/T-260.md:216` (O-260-2): el «cumple» de O1 R32 muestra la cita del pagaré leída por visión con otro número de proceso, y una explicación que la cita no sostiene.
     - Cuando el modelo ya había concluido «cumple», su explicación se conserva delante de «Fuente: Portal» (`evaluon/assessment/portal_facts.py:1084-1092`).
   - Cómo se reproduce: con una prueba propia que usa el ayudante `seen_page` de `tests/assessment/test_vision_flow.py` (una página escaneada leída por visión, declaración «cumple»):
     - En `assessment:pair` aparecen la cita, «leída por visión» y «Compare con el original antes de confirmar».
     - En `expedientes:s4_par` aparece la misma cita sin ninguna de las dos marcas, y la palabra «visión» no figura en la página.
   - Qué corregir:
     - Llevar al detalle del par, y a la celda, la marca de la 004 para las citas de páginas leídas por visión, con el enlace al original. El servicio ya entrega `by_vision` (`tests/assessment/test_vision_flow.py:256`).
     - Que el Coordinador decida sobre el aviso 1 de T-259: mantener la visión por página con el 27B o apagarla con `ASSESSMENT_VISION_MAX_PAGES=0` (ADR-0041).

3. **Menor, no bloqueante · P5 (runbook).** `specs/015-uso-y-eleccion-del-modelo/entorno.md:221` dice que la propuesta de datos del oferente «sigue pidiendo a `generation`» y que sin ese motor el nombre queda «no determinado». El código ya la pide al motor de lotes (`evaluon/offers/proposal_fields.py:465`, `generation.generate_batch`, T-248). Corregir la línea.

4. **Menor, no bloqueante · P7 (suite en el entorno documentado).** El servicio `app` de `docker-compose.yml` no monta `specs/`: el ancla `x-app` sí lo hace (línea 89), pero `app` repite su lista de volúmenes sin esa línea.
   - Con el comando documentado (`docker compose run --rm app pytest`), el test de cobertura de REQ-106 se saltea (`tests/test_instrucciones_revisadas.py:85-89`).
   - Los tests de generalidad dependen de `corpus/casos/`, que está fuera de git.
   - En esta auditoría pasaron porque monté `specs/` y `corpus/` en solo lectura.
   - Qué corregir: sumar `./specs:/app/specs:ro` a la lista de `app`, o documentar el montaje.

## Para la auditoría completa (no bloquea)

- **Feature sin cerrar.** En `tasks.md`, T-263 (medición de cierre) está en curso y T-249 y T-255, pendientes. La última medición registrada (T-260) da «No pasa». El ADR-0059 sigue «propuesto», y T-260 y T-263 lo usan como criterio.
- **Criterio del IVA.** Se muestra como «Criterio de la Comisión (2026-10-12)» (`evaluon/assessment/criteria.py:40`, `evaluon/journey/temas/s4_propuesta.py:91`). Es una decisión del responsable, no una respuesta de la Comisión con quién respondió y cuándo. Es un tema de redacción de P3; la spec lo pide así.
- **Presentación física atada al Portal.** Según el docstring de `evaluon/assessment/presentation.py`, cuando el pliego ata la presentación física a la marca «Requiere presentar» del Portal, el código da «no determinado» y no «no cumple», como dice la decisión literal del 2026-10-12. Es un desvío aceptado por el Coordinador que no está escrito en la spec (P1).

## Lo que se controló y está bien

- **Suite (P7):**
  - Corrida sobre 70e5aa54 con `pytest -n 6`, en contenedor y base propios, con `corpus/` y `specs/` en solo lectura: **5866 pasaron, 1 salteada, 0 fallaron** (828 s).
  - La salteada es anterior al rango: `tests/portal/test_parsing_pagina.py:158`, «páginas reales: solo local (P4)».
- **Esquema:**
  - Las migraciones corren desde cero sin errores, incluidas `tenders 0010` y `0011`.
  - `migrate tenders 0009` y la vuelta hacia adelante corren sin errores.
  - `makemigrations --check --dry-run` responde «No changes detected».
- **Entorno (parcial):**
  - `db`, `migrate` y `app` se levantan desde cero con el compose base: `app` sana en 127.0.0.1:8039, `/static/css/evaluon.css` da 200 y `/` redirige al ingreso.
  - Con el motor de la Consulta apagado, `/consulta/` da 200 con «La consulta de normativa no está disponible por ahora…» y el botón desactivado.
- **Motores (por inspección del código):**
  - Todos los pedidos de lotes van a `GENERATION_BATCH_URL`: informe técnico, reescritura, ficha, visión y propuesta de datos del procedimiento y del oferente.
  - La matriz cuenta tokens con el motor de lotes y no con el de la Consulta (`consequences.py:447`, `norm_support.py:264`).
- **P3 en las reglas nuevas:**
  - La regla de ausencia exige lectura completa, documentos nombrados y que nada la contradiga (`absence.py`, `criteria.py`).
  - «No aplica» se guarda como «cumple» con `aplica=false`, pero nunca se muestra como «cumple» (`evaluon/assessment/models.py:255-261`).
  - Una oferta sin documentos leídos no se evalúa (`evaluate.py:201` y `1244`).
  - Existe «no determinado» y las reglas lo usan cuando hay duda.
- **P4:**
  - En lo que agrega el rango solo hay CUIT inventados (30-00000000-0, 30-11111111-1, 20-22222222-2); no hay DNI, correos ni razones sociales.
  - No entró ningún archivo de `corpus/casos/`, respaldo ni PDF, ni ningún secreto (solo el `TEST_PASSWORD` de las pruebas).
  - Las únicas URL nuevas son las descargas de modelos de Hugging Face con revisión fijada (`scripts/fetch_models.sh`), fuera del camino de pliegos y ofertas. La red `egress` sigue solo en `portal_worker`.
- **Tests:**
  - No hay `skip` ni `xfail` nuevos, salvo los que dependen de montar `corpus/casos/` o `specs/`.
  - Las aserciones quitadas corresponden al cambio de regla (ADR-0043 → ADR-0053) y a las «divisiones» que la spec saca.
  - El único test sin `assert` es el de `makemigrations --check`, que falla por excepción.
- **Tablero:** `python tools/tablero.py --check` responde «docs/tablero.md está al día».
- **Commits y requisitos:** los 144 commits sin merge llevan `T-NNN` o `gestión:`. Cada requisito de REQ-101 a REQ-107 aparece en tests (de 11 a 26 archivos cada uno).

## Lo que no pude verificar

- **Evals y criterios de aceptación numéricos (REQ-101 a REQ-107):** la GPU está ocupada por la medición de cierre (T-263) y el encargo prohíbe usarla. No corrí evals ni comparé métricas con la corrida anterior. Tampoco comprobé con el modelo real que D-260-1 esté resuelto; solo que el código parte el pedido y que sus tests pasan.
- **El entorno completo desde cero con los servicios de IA** (27B en `generation_batch`, `embeddings`, `reranker`): por el mismo motivo.
- **Secretos en todo el historial:** revisé solo el diff del rango.
- **El contenido de `corpus/casos/`** (fuera de git): no lo abrí; solo lo monté en solo lectura para los tests. No miré el caso reservado.
