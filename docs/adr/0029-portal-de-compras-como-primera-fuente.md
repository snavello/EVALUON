# ADR-0029 · El Portal de Compras como primera fuente, con conexión solo para leerlo

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (con la definición de la Comisión)

## Contexto

La Comisión informó que el Portal de Compras de AFIP/ARCA publica de forma pública y ordenada los datos de cada proceso: número, expediente, encuadre legal, renglones, cronograma, garantías, documentos (pliego, circulares, actos administrativos, acta de apertura, dictamen) y, tras la apertura, las ofertas con su total, su garantía y la cotización por renglón. Hoy EVALUON recibe todo por carga manual, y la cotización por renglón llegó a leerse de fotos de pantalla, con errores.

La exploración del 2026-10-05 con el proceso A0PC000000-0004-LPU25 confirmó:

- la página pública del proceso, el cuadro comparativo y el acta de apertura se leen sin código de verificación;
- la búsqueda de procesos exige un CAPTCHA;
- los documentos de cada oferta (pólizas, declaraciones, hojas técnicas) no son públicos.

EVALUON se diseñó para funcionar sin conexión, todo en el equipo propio (P5; requisitos no funcionales de las features 001, 003 y 008).

## Decisión

1. El Portal de Compras es la **primera fuente** de la información de un proceso. La carga manual queda para lo que no publica (los documentos de las ofertas) o no deja bajar.
2. Se agrega la feature **012 · Importación asistida desde el Portal de Compras**, antes de la 004.
3. **Excepción a la operación sin conexión:** EVALUON puede conectarse a internet **solo para leer el Portal de Compras**. Los pliegos, las ofertas y todo el procesamiento con IA siguen en el equipo (P4 y P5 sin cambios en su fondo). La conexión se limita a ese destino.
4. El sistema **no resuelve ni evita** el CAPTCHA de la búsqueda. El enlace público de cada proceso lo consigue una persona una vez.
5. Nada se carga sin aprobación: el sistema propone, aprueba un evaluador (el operador, solo la carga de documentos), y queda registro P6.
6. Revisión periódica de los procesos en curso: una vez por día hábil, y a demanda.
7. Los términos y condiciones del Portal no son impedimento: el sistema es para la propia AFIP/ARCA.

## Alternativas

- **Importación asistida sin conexión:** el operador baja los archivos y el sistema los reconoce. Se mantiene el diseño sin conexión, pero se pierden los datos estructurados (la cotización por renglón como datos) y el aviso de novedades.
- **Seguir con carga manual:** sin cambios, con el riesgo de olvidar circulares y con la cotización leída de imágenes.

## Consecuencias

- Hace falta un acceso de red acotado al Portal desde el entorno, que el plan de la 012 y el runbook tienen que documentar.
- La lectura del Portal depende de su formato: los tests usan páginas reales guardadas, y si la página cambia, el sistema lo informa y se sigue con la carga manual.
- Las features 003 y 008 reciben la información importada como cualquier carga: el procedimiento, los documentos y las ofertas, con su origen.
