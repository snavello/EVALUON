# ADR-0050 · Formato de las exportaciones de la evaluación

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto (formato «Excel y PDF»; plan y dependencia con «ok avanza», 21:20)

## Contexto

REQ-093 pide exportar en la sección 4 la planilla por oferta y el cuadro comparativo. Decisión del responsable (2026-10-07): «Excel y PDF». Hoy solo la matriz de cumplimiento se imprime y baja en PDF con `weasyprint`, que ya está fijado en las dependencias. No hay ninguna librería de hojas de cálculo. El entorno es local y reproducible (P5): una dependencia nueva se fija con versión exacta, funciona sin internet una vez instalada y no manda datos a ningún servicio (P4).

Datos verificados el 2026-10-07 en fuentes públicas: XlsxWriter 3.2.9 (publicada el 16-09-2025), licencia BSD-2-Clause, requiere Python 3.8 o posterior ([CERN simple-repository](https://simple-repository.app.cern.ch/project/xlsxwriter), [PyPI](https://pypi.python.org/pypi/XlsxWriter)); openpyxl 3.1.5 (publicada el 28-06-2024), licencia MIT ([CERN simple-repository](https://simple-repository.app.cern.ch/project/openpyxl)). La versión exacta y su compatibilidad con la versión de Python de la imagen se confirman al fijarla (T-212).

## Alternativas

### A. XlsxWriter para el Excel y `weasyprint` para el PDF
XlsxWriter solo escribe archivos `.xlsx` (no los lee), con formato, anchos de columna, filtros, paneles fijos y varias hojas. Se gana: es lo que hace falta (generar, no leer), licencia permisiva, publicación reciente, todo local; una hoja por oferta más una de cuadro comparativo. El PDF reutiliza el mecanismo existente. Se pierde: una dependencia nueva a fijar y a incluir en la imagen.

### B. openpyxl para el Excel y `weasyprint` para el PDF
Lee y escribe `.xlsx`. Se gana: licencia permisiva y muy conocida. Se pierde: lee y modifica archivos, que esta feature no necesita (P10); última publicación más antigua.

### C. CSV y PDF (sin dependencia nueva)
Se gana: ninguna dependencia. Se pierde: no es lo que decidió el responsable («Excel y PDF») y el CSV no tiene formato ni varias hojas.

## Decisión

A, propuesta: **Excel con XlsxWriter y PDF con `weasyprint`**, generados en el servidor local. La planilla por oferta es un libro con una hoja por oferta (requisito, resultado, fundamento, decisión de la Comisión, descarte y su decisión) más una hoja del cuadro comparativo; el cuadro también sale en PDF. El responsable acepta o rechaza la dependencia nueva junto con el plan.

## Consecuencias

- Más fácil: archivos con formato que se abren directo en Excel; el PDF hereda la hoja de estilos de impresión.
- Más difícil: mantener la dependencia nueva con su versión fijada; rehacer la imagen (`docker compose build app`).
- Revertir: cambiar el generador; las rutas y el hecho de auditoría `eval_export` no cambian.
