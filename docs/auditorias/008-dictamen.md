# Dictamen de auditoría · Feature 008 (Ofertas y ficha por oferta)

Fecha: 2026-10-05 · Auditor: agente `auditor` (sin conocer el proceso) · Alcance: `specs/008-ofertas-ficha/`, commits `5b306c2..03e0b34` (incluyen trabajo de la 003 y la 012, no auditado aquí).

Texto devuelto por el auditor y registrado por el Coordinador (el auditor trabaja en solo lectura).

## Resultado

**Aprobado con observaciones.** Sin hallazgos bloqueantes.

## Hallazgos no bloqueantes

1. **Mayor (P7, P3).** REQ-039 no cumple su meta original: 25 de 55 fragmentos (45,5 %) contra 90 % (`verificacion/T-146.md`); los falsos hallazgos subieron de 1 a 10 respecto de T-136. El criterio se enmendó después de medir (ADR-0035, decisión del responsable): el 90 % se informa y pasa a ser meta de la 004. Está documentado y aprobado; conviene que el responsable lo vea explícito en el cierre. Seguir los falsos hallazgos en la 004.
2. **Menor (P2).** Una copia local de `main` desactualizada mostraba T-146 pendiente; en `origin/main` figura terminada y el tablero está al día.
3. **Menor (P4).** Apellidos de dos oferentes de un caso real aparecían en `tasks.md` y `verificacion/T-131.md`. Corregido por el Coordinador al registrar este dictamen ("oferente 1", "oferente 3"); queda la decisión sobre el historial.
4. **Menor (P5).** No hay runbook ni `entorno.md` de la 008; corresponde al despliegue y hace falta antes de aprobarlo.
5. **Menor.** La reescritura del requisito (T-146) no filtra palabras de juicio; no llega a la ficha y queda registrada; el riesgo es solo de sesgo en la recuperación.

## Controlado y correcto

- Trazabilidad: REQ-037 a REQ-044 con tarea y test; los commits de código citan T-NNN (REQ-NNN).
- P3: "no se encontró" y "no se pudo leer"; control de palabras de juicio con reintento y anomalía; texto literal; la ficha no declara cumplimiento.
- P4: sin URLs ni clientes de red en `evaluon/offers`; sin secretos; datos de prueba sintéticos.
- P6 y P8: la ficha guarda versión de la matriz, modelos, parámetros, versiones de instrucciones y lecturas con huella; pasos con candidatos, pedido, salida cruda e interpretado; seis tipos de hecho de auditoría.
- Tablero al día; T-130 a T-136 y T-146 terminadas con su registro de verificación.
- Suite completa sobre `03e0b34` en proyecto aislado y sin GPU: en verde, sin tests omitidos.

## No verificado

Las mediciones del caso-00 (necesitan GPU y corpus local) se tomaron de `T-146.md`; el runbook, que no existe todavía.
