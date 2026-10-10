# Dictamen de auditoría de fallas · Feature 014 (aplicación por secciones)

- **Alcance:** `specs/014-aplicacion-por-secciones/`, rango e0a396d..c13d78c (origin/014-T-227), 262 commits, 322 archivos. Auditoría de fallas según ADR-0052: solo lo que no anda, resultados equivocados, conclusiones sin respaldo (P3) y datos reales o secretos (P4).
- **Resultado:** aprobado con observaciones

## Hallazgos

Sin hallazgos bloqueantes.

1. **Menor, no bloqueante · P7 (suite).** Corrida completa sobre c13d78c (`docker compose run --rm --no-deps app pytest -n 8 --dist worksteal -q`, proyecto `evaluon-aud`): 4462 pasaron, 1 omitida, 2 fallaron en la corrida paralela.
   - `tests/journey/test_moments.py::test_the_25_cells_have_the_state_the_counts_and_the_access`: `OSError: [Errno 12] Cannot allocate memory` (falta de memoria del equipo, que tenía otros proyectos docker en marcha).
   - `tests/portal/test_approval.py::test_approve_one_part_and_reject_the_other_loads_only_what_was_approved`: `KeyError: 'procedimiento'` en `evaluon/portal/services/approval.py:179` (`discover()[item.kind]`).
   - Reproducción: ninguna de las dos se reproduce; las dos pasan al correrlas solas (`2 passed in 16.91s`). Lo más probable es que el segundo fallo sea consecuencia de la misma presión de memoria durante una importación (el registro `discover()` quedó incompleto), pero no lo pude confirmar. Conviene repetir la corrida en un equipo sin carga antes de la auditoría completa; si el KeyError reaparece, es un defecto real del registro de importadores.
   - Se corrió con `--no-deps` porque `docker compose run app` levanta los modelos (GPU) y fallaron por salud en el entorno de auditoría; las pruebas no los necesitaron.

## Controlado y sin hallazgos

- **Permisos por rol (vivo, app en puerto 8037, base propia, usuarios sintéticos):** el usuario de lectura recibe 403 en los 7 POST probados (proponer/confirmar matriz, abrir versión, evaluar, decidir descarte, subir pliego, subir norma) y sus páginas solo tienen el botón de salir. El operador recibe 403 en confirmar matriz, agregar requisito y decidir descarte (coincide con «solo el evaluador»). 47 URL sin parámetros dan 200/302 sin errores 5xx para los tres roles.
- **P4:** no hay `.env`, claves ni volcados versionados (`.env.example` solo); sin secretos literales en el código; los CUIT de tests son sintéticos (30-00000000-0, etc.) y el 33-69345023-9 es el público del organismo; los PDF versionados son los casos chicos sintéticos y el corpus público; `.gitignore` excluye los casos reales. El código no usa clientes de API externos: `evaluon/ai` apunta a servicios locales por configuración y `evaluon/portal` solo lee el Portal público.
- **Tests debilitados:** un solo `skipif` en `tests/portal/test_parsing_pagina.py:158`; sin `xfail` ni `assert True`.
- **Tablero:** `python tools/tablero.py --check` informa que `docs/tablero.md` está al día.

## Para la auditoría completa (no bloquea)

- Verificar la trazabilidad REQ a tarea a test de toda la 014 (36 menciones de «terminada» en `tasks.md`, 31 archivos en `verificacion/`).
- Revisar que cada commit del rango cite tarea, la redacción de registros y el runbook desde cero.
- Se eliminaron 110 líneas de `tests/tenders/test_validation.py` en el rango; revisar que fueran por la reorganización y no pérdida de cobertura.

## Lo que no pude verificar

- Flujos con los modelos de IA y la GPU (no se levantaron para no competir con el sistema real); la evaluación de punta a punta y las evals no se corrieron.
- Datos con contenido real dentro de los PDF versionados: revisé nombres y patrones de texto, no abrí cada PDF.
- Historial completo de git en busca de secretos (revisé solo el árbol del rango).
- La compilación de la imagen local retagueó `evaluon-app:local` en este equipo; los contenedores en marcha no se vieron afectados, pero un reinicio del 8000 sin reconstruir usaría esta imagen (mismo código de c13d78c).
