# ADR-0050 · Formato de las exportaciones de la evaluación

Estado: propuesto · Fecha: 2026-10-07 · Decidió: —

## Contexto

REQ-093 pide exportar en la sección 4 la planilla por oferta y el cuadro comparativo. Hoy solo la matriz de cumplimiento se imprime y baja en PDF (con `weasyprint`, que ya está en las dependencias fijadas). No hay ninguna librería de hojas de cálculo. El entorno es local y reproducible (P5); agregar una dependencia obliga a fijar su versión, a rehacer la imagen y a verificar su licencia y su mantenimiento: esos datos se verifican al implementar, no se dan por conocidos aquí.

## Alternativas

### A. CSV para la planilla y PDF para el cuadro comparativo
La planilla (una fila por oferta y requisito) es un CSV en UTF-8 con marca de orden de bytes, para que una hoja de cálculo lo abra bien; el cuadro, que es para leer e imprimir, es una página impresa con `weasyprint`, igual que la matriz. Se gana: ninguna dependencia nueva, mismo mecanismo que ya existe, fácil de probar. Se pierde: el CSV no tiene formato ni varias hojas; el cuadro no se edita.

### B. Hoja de cálculo nativa (`.xlsx`) para los dos
Una librería de hojas de cálculo escribiría un archivo con una hoja por oferta y el cuadro con formato. Se gana: es lo que probablemente espera quien dice «planilla». Se pierde: una dependencia nueva a fijar y verificar (versión, licencia, mantenimiento), más superficie de prueba y de rehacer la imagen.

### C. Solo PDF para los dos
Se gana: un solo mecanismo. Se pierde: la planilla no se puede ordenar ni filtrar.

## Decisión

A, propuesta, por simplicidad (P10) y porque no suma dependencias. Si el responsable prefiere `.xlsx`, se elige B y la tarea T-212 verifica antes la librería (versión actual, licencia, mantenimiento) en su documentación oficial y la fija.

## Consecuencias

- Más fácil: sin dependencia nueva; el cuadro hereda la hoja de estilos de impresión.
- Más difícil: si se quiere formato de hoja de cálculo, hay que sumar la dependencia después.
- Revertir: cambiar el generador de la planilla; las rutas y el hecho de auditoría `eval_export` no cambian.
