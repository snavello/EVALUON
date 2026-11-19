# Dictamen de auditoría de fallas · Feature 020 (Evi, la guía del procedimiento)

- **Alcance:** `specs/020-evi-guia-del-procedimiento/`, rango 72164121^..d36fc076 (`origin/main`), 12 commits, 44 archivos (código: `evaluon/journey/evi/`, `views/evi.py`, `context.py`, `urls.py`, `settings.py`, `static/journey/evi.{js,css}`, plantillas `_evi_*.html`, `base.html`). Auditoría de fallas según ADR-0036 y ADR-0052, con el carril liviano de ADR-0081 y ADR-0082. Copia propia `.claude/worktrees/aud020` y proyecto docker propio `evaluon-aud020` (dado de baja con `down -v`).
- **Resultado:** aprobado

## Hallazgos

Sin hallazgos bloqueantes. Nada impide funcionar ni expone datos.

## Para la auditoría de cumplimiento (no bloquea)

- No revisé trazabilidad completa commit a tarea ni la redacción de las verificaciones (`verificacion/T-367.md`, `T-368.md`, `lote.md`). T-367 y T-368 figuran terminadas y tienen archivo de verificación. `Despliegue: pendiente` en `tasks.md`, como corresponde.

## Lo que se controló y está bien

- **Pruebas (P7):** `tests/journey/test_evi.py` y `tests/journey/test_evi_preguntas.py` sobre origin/main, contenedor y base propios: **90 pasaron, 0 fallaron**, 68 s. Sin `skip` ni `xfail` en ambos archivos. No corrí la suite completa ni las diez preguntas reales contra la IA (el encargo lo excluye).
- **Solo lectura (REQ-169):** `panel.py` y `views/evi.py` (`general`, `procedimiento`) solo renderizan; la única escritura es el hecho de auditoría de cada pregunta (`_responder`). Los endpoints de panel son `require_GET` y los de pregunta `require_POST` (con CSRF: `evi.js` l. 246 y l. 263 envía el token).
- **Permisos:** `procedimiento` y `preguntar_procedimiento` usan `@reading` y `overview_of`, igual que la portada (404 si no existe, 403 sin rol). El panel no dibuja enlaces. La aplicación exige sesión (`LoginRequiredMiddleware`, `settings.py` l. 85) y el botón y los estilos solo se cargan con `user.is_authenticated` (`base.html`).
- **P3 (Evi no decide):** la instrucción `prompts/evi-v1.txt` prohíbe decidir y recomendar y remite a la Comisión; `preguntas.limpio` quita del estado que va al modelo cuál oferta es la más baja o la más alta y los nombres de oferentes. La salida se valida (JSON con esquema, corte por longitud, tope de 1500 caracteres). Es experimental y rotulado (ADR-0082).
- **Escape de la respuesta:** `_evi_respuesta.html` escapa siempre `{{ p }}`; no hay `|safe`, `mark_safe` ni `autoescape off` en las plantillas ni en los módulos de Evi. El único `innerHTML` de `evi.js` (l. 226 y l. 268) inserta HTML ya renderizado por el servidor; los avisos de cliente usan `textContent`.
- **P4:** el pedido va solo por `generation.generate` al motor local (`GENERATION_URL`); el módulo no importa `evaluon.ai.external` ni contiene URLs, claves ni clientes de API. El contexto es solo la guía y el estado del procedimiento, sin pliegos, ofertas ni normativa. Sin material reservado en el rango (pruebas con procedimientos inventados; el YAML de preguntas es público).
- **REQ-173:** el ajuste `EVI_QUESTIONS_ENABLED` apaga el bloque y la ruta responde 404; `EVI_TIMEOUT_SECONDS=50` (< 60 s); si el motor está ocupado, `consulta_notice` evita el pedido y se avisa; `preguntar` no lanza y cada falla vuelve como resultado fallido. El ajuste está en `docker-compose.yml` l. 71-72 y `.env.example` l. 177-179. P6: cada pregunta deja hecho de auditoría con usuario, pregunta, respuesta, modelo, versión de la instrucción y resultado.
- **Aislamiento de la evaluación:** el diff no toca instrucciones, recuperación ni modelo de la evaluación; la instrucción de Evi está en su propia carpeta y versionada.
- **Tablero:** `python tools/tablero.py --check` responde que `docs/tablero.md` está al día.

## Lo que no pude verificar

- Suite completa y evals (el encargo lo excluye); las diez preguntas de prueba contra la IA local real (las corre el Coordinador, `manage.py evi_preguntas`).
- Anchos de 360, 1280 y 1440 px, contraste y animaciones: requieren navegador, no los medí (están en `verificacion/lote.md`, sin contrastar por mí).
- Historial completo de git en busca de secretos: revisé solo el diff del rango.
