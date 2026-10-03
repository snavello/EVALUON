# ADR-0010 · AFIP y ARCA son el mismo organismo

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

La Administración Federal de Ingresos Públicos (AFIP) pasó a denominarse Agencia de Recaudación y Control Aduanero (ARCA). Es el mismo organismo, con el mismo CUIT. Las normas del corpus fueron dictadas como AFIP y las nuevas, como los pliegos y las consultas de la Comisión, pueden nombrarlo como ARCA.

## Decisión

- AFIP y ARCA se tratan como el mismo organismo en todo el sistema.
- **Las normas no cambian.** Cada norma conserva su nombre de cita oficial, con el organismo que la dictó ("Disposición AFIP 297/03", "Disposición AFIP 247/2022"). No se renombra nada ya cargado.
- Una norma nueva dictada como ARCA se carga con su nombre oficial ("… ARCA …").
- Donde el sistema compara o busca por organismo (identidad de una norma, modificatorias sin cargar, búsqueda por palabras y recuperación), "AFIP" y "ARCA" valen lo mismo.

## Consecuencias

- Una pregunta o una búsqueda que diga "ARCA" tiene que encontrar lo que dice "AFIP", y al revés.
- Una modificatoria anotada con organismo ARCA y una norma cargada como AFIP, o al revés, se reconocen como del mismo organismo.
- La tarea T-057 de la feature 001 hace los cambios en el código.
