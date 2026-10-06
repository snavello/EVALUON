# Dictamen de auditoría de funcionamiento · Feature 012 (Importación desde el Portal de Compras)

Fecha: 2026-10-06 · Auditor: agente `auditor` (funcionamiento, ADR-0036) · Rango: `e067520..afb5ab9`. Texto del auditor, registrado por el Coordinador.

## Resultado

**Aprobado con observaciones.** Sin bloqueantes.

- P4: sin secretos en el código; el host del Portal sale de `PORTAL_ALLOWED_HOSTS`; solo `portal_worker` está en la red con salida, con test; sin archivos de casos ni `.env` en el rango.
- T-138 a T-145 terminadas, cada una con su registro de verificación; tests de REQ-045 a REQ-051; un solo `skipif` legítimo.

## No bloqueantes

1. Falta un test de que `medir_portal` exige rol de evaluador.
2. Las listas esperadas tienen visto bueno del Coordinador (2026-10-06); la del caso-05 se corrigió leyendo el cuadro guardado a mano, en una verificación independiente de T-145.
3. Para la auditoría de cumplimiento: alinear `entorno.md` con el resultado de la pasada en vivo (100 %).

## No verificado

La suite (cifras de los informes, 3201 en verde al cerrar T-145), la medición en vivo (la hizo el Coordinador), el runbook desde cero.
