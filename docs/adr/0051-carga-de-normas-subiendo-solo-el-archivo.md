# ADR-0051 · Carga de normas subiendo solo el archivo

Estado: propuesto · Fecha: 2026-10-07 · Decidió: —

## Contexto

El responsable decidió que una norma se carga «solo subiendo el archivo»: el sistema la lee, muestra el informe de lectura y la Comisión la valida, todo desde la pantalla (REQ-094). Hoy `load_norm` exige diez datos de la norma (categoría, tipo, número, año, emisor, título, cita, fecha de publicación, vigencia y fuente) que el comando recibe como argumentos, y la validación exige el rol de normativa de lectura y escritura. Cada norma es versionada (P8) y la validación es una decisión de una persona (P3). La normativa es pública y puede procesarse sin restricciones de P4.

## Alternativas

### A. Datos propuestos por reglas sobre el encabezado, confirmación y recién entonces la carga
El archivo espera en una tabla de subidas (`norms_upload`); el sistema lo lee y propone cada dato con su evidencia (página y texto) por reglas sobre el encabezado y el pie; los datos que no reconoce quedan marcados y la persona los confirma o completa; al confirmar se llama a `load_norm` sin cambios. Se gana: se cumple «subir el archivo» en lo que se puede inferir, sin tocar la carga validada ni el versionado; sin IA; la persona decide. Se pierde: una tabla nueva y reglas de encabezado que habrá que mantener; algunos datos (por ejemplo la categoría) pueden no inferirse y se piden.

### B. Datos propuestos con el modelo local
Igual que A, pero el modelo lee el encabezado. Se gana: más tolerancia a formatos distintos. Se pierde: instrucciones nuevas al modelo, evals (P7) y un recurso (GPU) para algo que las reglas pueden resolver en normas con encabezado estándar.

### C. Formulario con los diez datos, como el comando, y archivo
Se gana: es lo más simple y reutiliza la carga tal cual. Se pierde: contradice la decisión «solo subir el archivo».

## Decisión

A, propuesta. B queda como alternativa si las reglas no alcanzan el umbral del plan (8 de 10 datos correctos en 5 normas públicas del corpus) tras dos rondas. La pantalla exige el rol de evaluador de la Comisión para validar; el servicio mantiene su rol de normativa, así que el usuario que valida debe tener ambos (duda abierta del plan).

Corrección: un dato propuesto de la norma se corrige escribiendo el valor y un motivo obligatorio; queda el valor propuesto, el corregido, el motivo, quién y cuándo (decisión del responsable, 2026-10-07). Un dato que el sistema no reconoció se completa del mismo modo, con el motivo «no reconocido».

## Consecuencias

- Más fácil: cargar una norma sin comandos; ver el informe de lectura y validar desde la pantalla.
- Más difícil: mantener reglas de encabezado; dos roles para validar.
- Revertir: quitar la tabla de subidas y la pantalla; los comandos de `norms/management/commands/` siguen funcionando y no se tocan.
