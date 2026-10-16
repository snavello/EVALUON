# Glosario de códigos

> Se genera con `python tools/glosario.py` a partir de `specs/`, `docs/adr/` y `evals/`. No editar a mano.

Qué significa cada prefijo:

| Prefijo | Qué es |
|---|---|
| **T-NNN** | Tarea de una feature (código y tests); vive en specs/NNN/tasks.md |
| **REQ-NNN** | Requisito funcional de una spec; único en el proyecto |
| **ADR-NNNN** | Decisión de arquitectura registrada en docs/adr/ |
| **D-NNN-N** | Hallazgo de una verificación que impide o condiciona (defecto); NNN es la tarea verificada |
| **H-NNN-N** | Hallazgo de una verificación (misma idea que D-, nombre usado desde la 016) |
| **O-NNN-N** | Observación de una verificación: no impide integrar |
| **D-NN** | Decisión literal del responsable o definición derivada usada en las instrucciones al modelo (specs/NNN/revision-instrucciones.md) |
| **M-NNN** | Entrada de la lista esperada de un caso (un requisito que la matriz debe traer); fuera de git |
| **EV-NNN** | Caso del conjunto dorado de evals (pregunta pública con respuesta esperada) |
| **P1 a P11** | Principio de la constitución |
| **NNN** | Feature de la hoja de ruta (001, 003, …, 016) |
| **caso-0N** | Caso público del corpus (pliego, circulares y, en el 00, ofertas y dictamen) |

## Principios de la constitución (11)

| Código | Feature | Qué es | · |
|---|---|---|---|
| **P1** |  | La especificación es la fuente de verdad |  |
| **P2** |  | Trazabilidad de punta a punta |  |
| **P3** |  | El sistema recomienda, la Comisión decide |  |
| **P4** |  | Clasificación de datos |  |
| **P5** |  | Local primero y reproducible |  |
| **P6** |  | Registro de auditoría completo |  |
| **P7** |  | Evals además de tests |  |
| **P8** |  | Normativa versionada |  |
| **P9** |  | Validaciones externas como hojas de compliance |  |
| **P10** |  | Simplicidad |  |
| **P11** |  | Compuertas humanas |  |

## Features (16)

| Código | Feature | Qué es | · |
|---|---|---|---|
| **001** | 001 | Normativa consultable con cita: Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que… |  |
| **003** | 003 | Procedimiento, pliego final y matriz de cumplimiento: El procedimiento con su fecha de autorización; la carga del pliego final publicado; la matriz de cumplimiento… |  |
| **008** | 008 | Ofertas y ficha por oferta: La carga de cada oferta en varios documentos (PDF con texto o escaneado) y una ficha por oferta: síntesis de… |  |
| **012** | 012 | Importación asistida desde el Portal de Compras: El sistema explora la página pública del proceso en el Portal de Compras (datos, renglones, documentos… |  |
| **013** | 013 | Recorrido del procedimiento (aplicación mínima): Una entrada con los procedimientos y, por procedimiento, sus etapas en orden con su estado, el avance en vivo… |  |
| **014** | 014 | Aplicación por secciones: La aplicación organizada en cinco secciones sin orden obligatorio (procedimiento, pliego y matriz, ofertas… |  |
| **015** | 015 | Uso y elección del modelo: Corregir cómo se usa el modelo (instrucciones, citas de oración completa, encabezados, dato del Portal… |  |
| **016** | 016 | Calidad medible y modelos por clase de dato: Verdad celda por celda para más casos públicos, instrucciones y reglas simplificadas, y uso medido de un… |  |
| **004** | 004 | Evaluación asistida de ofertas: Por cada oferta y cada requisito de la matriz, una propuesta de cumple, no cumple o no determinado con su… |  |
| **005** | 005 | Hojas de compliance: La carga, por la Comisión, del documento de compliance de cada oferta: lo verificado en sistemas no… |  |
| **009** | 009 | Validación continua con la Comisión: Un circuito único para que la Comisión responda y valide preguntas y respuestas del sistema, y registre sus… |  |
| **002** | 002 | Análisis del pliego borrador: Opcional: un informe de cumplimiento de un pliego borrador contra la normativa, con preguntas a la Comisión… |  |
| **006** | 006 | Salidas de la evaluación: Planilla por oferta y cuadro comparativo; el borrador de acta queda diferido |  |
| **007** | 007 | Acceso por red: Uso de la pantalla desde otras computadoras, con conexión cifrada y bloqueo tras intentos fallidos de clave |  |
| **010** | 010 | Asistente técnico: Un asistente que compara la parte técnica de cada oferta con las especificaciones del pliego, renglón por… |  |
| **011** | 011 | Pautas para documentos legibles por IA: Una sección que, con el sistema maduro, genera recomendaciones para redactar pliegos, circulares y… |  |

## Tareas (314)

| Código | Feature | Qué es | Estado |
|---|---|---|---|
| **T-001** | 001 | Comprobar la GPU dentro de un contenedor | terminada |
| **T-002** | 001 | Levantar el motor de generación y medir su velocidad | terminada |
| **T-003** | 001 | Levantar embeddings y reranker y medir la memoria de video | terminada |
| **T-004** | 001 | Fijar Postgres con sus extensiones y búsqueda en español | terminada |
| **T-005** | 001 | Armar el esqueleto de Django con sus librerías | terminada |
| **T-006** | 001 | Crear usuarios con rol, ingreso y salida | terminada |
| **T-007** | 001 | Crear el registro de auditoría y el alta de usuarios | terminada |
| **T-008** | 001 | Crear las tablas de normas, lecturas, unidades y pasajes | terminada |
| **T-009** | 001 | Crear las funciones de unidades consultables a una fecha | terminada |
| **T-010** | 001 | Crear la tabla del registro detallado de consultas | terminada |
| **T-011** | 001 | Crear los clientes de IA, sus dobles y los parámetros | terminada |
| **T-012** | 001 | Leer un PDF con texto | terminada |
| **T-013** | 001 | Partir en artículos y armar el informe mínimo | terminada |
| **T-014** | 001 | Cargar una norma, listarla y ver su informe | terminada |
| **T-015** | 001 | Validar una lectura y calcular pasajes y vectores | terminada |
| **T-016** | 001 | Armar la pantalla de consulta con sus tres bloques | terminada |
| **T-017** | 001 | Recuperar por significado y reordenar con el reranker | terminada |
| **T-018** | 001 | Generar la respuesta con esquema e insertar las citas | terminada |
| **T-019** | 001 | Unir la consulta de punta a punta con su registro | terminada |
| **T-020** | 001 | Probar el hilo mínimo con los servicios reales | terminada |
| **T-021** | 001 | Leer un PDF escaneado con reconocimiento de texto | terminada |
| **T-022** | 001 | Leer una página web guardada | terminada |
| **T-023** | 001 | Partir normas completas con incisos, anexos y considerandos | terminada |
| **T-024** | 001 | Partir dictámenes y recomendaciones en puntos y párrafos | terminada |
| **T-025** | 001 | Completar el informe de lectura | terminada |
| **T-026** | 001 | Avisar duplicados al cargar una norma | terminada |
| **T-027** | 001 | Releer un documento y reemplazar la lectura anterior | terminada |
| **T-028** | 001 | Integrar los tres formatos en la carga | terminada |
| **T-029** | 001 | Registrar relaciones entre normas y mostrar los vínculos | terminada |
| **T-030** | 001 | Registrar versiones de una norma | terminada |
| **T-031** | 001 | Partir en pasajes las unidades largas | terminada |
| **T-032** | 001 | Recuperar por tres caminos y unir los candidatos | terminada |
| **T-033** | 001 | Seleccionar por categoría, sumar cambios y ordenar | terminada |
| **T-034** | 001 | Completar instrucciones, marca de regímenes y orden | terminada |
| **T-035** | 001 | Buscar unidades por artículo y por palabras | terminada |
| **T-036** | 001 | Entregar el documento original con sesión | terminada |
| **T-037** | 001 | Mostrar las citas con categoría, papel y cambios | terminada |
| **T-038** | 001 | Registrar ingresos, ingresos fallidos y rechazos por rol | terminada |
| **T-039** | 001 | Correr el conjunto de preguntas y medir las exigencias | terminada |
| **T-040** | 001 | Unir recuperación y generación completas con su registro | terminada |
| **T-041** | 001 | Mostrar y registrar la búsqueda en la pantalla | terminada |
| **T-042** | 001 | Agregar calibración del umbral y comparación de corridas | terminada |
| **T-043** | 001 | Cargar y validar el corpus real y ajustar las reglas | terminada |
| **T-044** | 001 | Registrar relaciones, versiones y modificatorias del corpus | terminada |
| **T-045** | 001 | Calibrar el umbral con el conjunto de preguntas | terminada |
| **T-046** | 001 | Correr las evals y medir tiempo y memoria | terminada |
| **T-047** | 001 | Probar una consulta con la red desconectada | terminada |
| **T-048** | 001 | Probar el respaldo y la restauración de la base | terminada |
| **T-049** | 001 | Levantar todo desde cero y dejar datos para el runbook | terminada |
| **T-050** | 001 | Partir la 297/03 y el cuerpo de la 247/2022 desde la web | terminada |
| **T-051** | 001 | Registrar las modificatorias sin cargar de una norma | terminada |
| **T-052** | 001 | Avisar modificatorias sin cargar en respuesta y búsqueda | terminada |
| **T-053** | 001 | Conservar la eñe en la búsqueda por palabras | terminada |
| **T-054** | 001 | Pasar a la aplicación las variables de los servicios de IA | terminada |
| **T-055** | 001 | Agregar el nombre de cita de la norma | terminada |
| **T-056** | 001 | Mostrar en la búsqueda solo lo vigente, con casilla para los derogados | terminada |
| **T-057** | 001 | Tratar AFIP y ARCA como el mismo organismo | terminada |
| **T-058** | 001 | Corrector tolerante de datos clave | terminada |
| **T-059** | 001 | Reescribir los datos clave del conjunto dorado | terminada |
| **T-060** | 001 | Calibración por hueco, lote de aceptación y margen de error en las evals | terminada |
| **T-061** | 001 | Redactar el lote de aceptación | terminada |
| **T-062** | 001 | Fijar el umbral con la regla nueva | terminada |
| **T-063** | 001 | Instrucciones para responder la remisión a una norma no cargada | terminada |
| **T-064** | 001 | Reescribir EV-027, EV-028 y EV-029 como preguntas con respuesta | terminada |
| **T-065** | 001 | Corregir la espera intermitente de test_wait y el borde de la calibración | terminada |
| **T-066** | 001 | Casos y corrida corta de REQ-019 | bloqueada |
| **T-067** | 003 | Crear las tablas, los tipos de hecho y los parámetros de la 003 | terminada |
| **T-068** | 003 | Sumar el rol de la Comisión a los usuarios | terminada |
| **T-069** | 003 | Registrar un procedimiento y mostrar su régimen | terminada |
| **T-070** | 003 | Partir un pliego en tramos con renglones, clase por sección y control de cobertura | terminada |
| **T-071** | 003 | Ejecutar pedidos en segundo plano con su propio motor | terminada |
| **T-072** | 003 | Cargar los documentos del pliego y leerlos en segundo plano | terminada |
| **T-073** | 003 | Proponer la matriz en nivel media, con filas técnicas por renglón | terminada |
| **T-074** | 003 | Mostrar la matriz propuesta con la leyenda de borrador, la cobertura y el aviso de fin | terminada |
| **T-075** | 003 | Probar el hilo mínimo con el caso-00 y los servicios reales | terminada |
| **T-076** | 003 | Preparar la lista esperada del caso-00 | terminada |
| **T-077** | 003 | Medir una propuesta contra una lista esperada | terminada |
| **T-078** | 003 | Completar los niveles alta y exigente | terminada |
| **T-079** | 003 | Revisar la matriz: confirmar, corregir, quitar y agregar | terminada |
| **T-080** | 003 | Sugerir consecuencias con fundamento | terminada |
| **T-081** | 003 | Elegir la consecuencia en la pantalla, con su motivo | terminada |
| **T-082** | 003 | Validar la matriz y abrir versiones nuevas | terminada |
| **T-083** | 003 | Incorporar circulares y respuestas a consultas | terminada |
| **T-084** | 003 | Correr la medición del caso-00 | terminada |
| **T-085** | 003 | Ofrecer solo los niveles que mejoran | terminada |
| **T-086** | 003 | Imprimir y exportar la matriz a PDF con la leyenda de borrador | terminada |
| **T-087** | 003 | Comparar en la misma zona horaria la fecha de lectura del informe | terminada |
| **T-088** | 003 | Cambiar el rol de la Comisión de un usuario existente, con registro | terminada |
| **T-089** | 003 | Contar bien las páginas en la extrapolación de tiempos | terminada |
| **T-090** | 003 | Investigar y corregir los reinicios de los servidores de generación | terminada |
| **T-091** | 003 | Comparar niveles medidos en corridas separadas | terminada |
| **T-092** | 003 | Aceptar las divisiones de la completitud aunque el original no coincida letra por letra | terminada |
| **T-093** | 003 | Ajustar las instrucciones con el caso-00 (enumeraciones, tablas, condiciones como efecto) | terminada |
| **T-094** | 003 | Medir la aceptación con los casos 01 y 02 | terminada |
| **T-095** | 003 | Contar como "a revisión obligatoria" los requisitos en tramos pendientes | terminada |
| **T-096** | 003 | Corregir la cobertura de tramos de medir_matriz cuando hay circulares | terminada |
| **T-097** | 003 | Corregir la cita literal de las filas técnicas con varios documentos en medir_matriz | terminada |
| **T-098** | 003 | Corregir la pasada de circulares (fuentes, tramos descartados y no ubicados) | terminada |
| **T-099** | 003 | Crear la tabla de filas descartadas, el estado de sugerencia, el respaldo normativo, las citas repetidas y los… | terminada |
| **T-100** | 003 | Quitar el nivel "media" y dejar un solo proceso registrado | terminada |
| **T-101** | 003 | Unificar las filas que repiten la misma condición | terminada |
| **T-102** | 003 | Filtrar con dos preguntas y repartir cada fila en firme, sugerencia o descartada | terminada |
| **T-103** | 003 | Medir los sobrantes sobre las filas firmes, con tope e informe de descartadas | terminada |
| **T-104** | 003 | Listar y devolver las filas descartadas, y revisar por grupos | terminada |
| **T-105** | 003 | Mostrar las descartadas, las citas repetidas y la revisión por grupos | terminada |
| **T-106** | 003 | Medir el filtro, las sugerencias y el respaldo normativo con el caso-00 y ajustarlos | pendiente |
| **T-107** | 003 | Decidir con el responsable el tope, la lista y las sugerencias con lo medido en el caso-00 | terminada |
| **T-108** | 003 | Medir la aceptación del proceso con filtro y sugerencias con los casos 01 y 02, y REQ-031 con los casos 03 y 04 | terminada |
| **T-109** | 003 | Buscar el respaldo normativo de cada sugerencia, sin que nunca la descarte | terminada |
| **T-110** | 003 | Decidir las sugerencias: pasar a requisito o quitar, una por una o por grupo, y bloquear la validación | terminada |
| **T-111** | 003 | Medir las sugerencias y el respaldo normativo: a revisión obligatoria e informe | terminada |
| **T-112** | 003 | Mostrar la sección de sugerencias con su respaldo en la pantalla y en la impresión | terminada |
| **T-113** | 003 | Pasada de circulares, entrega 1: unidades de cambio aplicadas por clave, sin modelo | terminada |
| **T-114** | 003 | Crear el campo de original en un anexo, el pedido de extracción de cambios y los parámetros de circulares | terminada |
| **T-115** | 003 | Pasada de circulares, entrega 2: el modelo extrae la lista de cambios donde no hay clave | terminada |
| **T-116** | 003 | Mostrar y imprimir el original en el anexo, el cambio agrupado y el requisito agregado por una circular | terminada |
| **T-117** | 003 | Medir REQ-031 por fila en medir_matriz: documento, fecha, texto original y vigente | terminada |
| **T-118** | 003 | Cargar los casos 05 y 06 y preparar sus listas esperadas de circulares | terminada |
| **T-119** | 003 | Actualizar la lista esperada del caso-01 con las filas que las circulares afectan | terminada |
| **T-120** | 003 | Medir y ajustar la pasada de circulares con los casos 01, 05 y 06, con estabilidad | terminada |
| **T-121** | 003 | Corregir el consumo de memoria de la medición (citas que cargaban cada una su lectura) | terminada |
| **T-122** | 003 | Mostrar los cambios vigentes de la norma al proponer consecuencias, o no fundar en unidades modificadas | pendiente |
| **T-123** | 003 | Corregir la medición: citas de otra lectura y filas suprimidas por una circular | terminada |
| **T-124** | 003 | Pasada de circulares: original en el anexo por título y requisitos que agrega un "Debe decir" | terminada |
| **T-125** | 003 | Corregir el criterio del filtro que descartó requisitos reales | terminada |
| **T-126** | 003 | Mostrar la cadena completa de circulares que modifican una misma condición | terminada |
| **T-127** | 003 | Impedir que una aclaración termine como supresión y registrar la versión de circulares_cambios | terminada |
| **T-128** | 003 | Aplicar una aclaración de cláusula a todas sus citas | terminada |
| **T-129** | 003 | Reconocer supresiones dichas con sustantivo y aplicar la aclaración de un renglón a sus citas | terminada |
| **T-137** | 003 | Pasada de circulares: revisión obligatoria visible ante un cambio sin resolver y las tres causas de la aceptación a… | terminada |
| **T-147** | 003 | Circulares: aviso en la fila que cambia (#183) y medición del criterio de ADR-0034 | terminada |
| **T-178** | 003 | Pliegos nuevos: cláusulas de primer nivel sin punto, recuadros de una columna, obligaciones de ejecución, garantía de… | terminada |
| **T-148** | 004 | Esquema, configuración compartida y tamaños: módulo assessment con todas sus tablas y triggers, tipo de pedido y de… | terminada |
| **T-149** | 004 | Preparar los casos para medir (Coordinador): caso chico calcado de ofertas reales y lista esperada del dictamen del… | terminada |
| **T-150** | 004 | Corte vertical: evaluar una oferta de punta a punta (lectura completa por grupos, cita ubicada, contraste, cuatro… | terminada |
| **T-151** | 004 | Medir el caso chico: lista esperada, comparación y comando medir_evaluacion | terminada |
| **T-152** | 004 | Matriz de evaluación de todas las ofertas: descarte propuesto, orden económico con el Portal, estado por oferta y aviso… | terminada |
| **T-153** | 004 | Revisión: confirmar, corregir y rechazar cada propuesta, con historial y fundamentos a la vista | terminada |
| **T-154** | 004 | Preguntas a la Comisión, respuestas como fundamento y subsanación con su recorrido | terminada |
| **T-155** | 004 | Medir el caso-00 contra el dictamen (medición base) | terminada |
| **T-156** | 004 | Corregir los hallazgos de T-155 y medir de nuevo (ronda 1) | terminada |
| **T-157** | 004 | Solo si T-156 no llegó al umbral: corregir y medir de nuevo (ronda 2, la última) | terminada |
| **T-158** | 004 | Contraste por cláusula de un cumple técnico: cero contradicciones con el dictamen (tercera ronda por la contradicción… | terminada |
| **T-164** | 004 | Corregir los hallazgos de T-158: el no cumple técnico exige una cita de la oferta que contradiga la cláusula (F-1) y el… | terminada |
| **T-159** | 004 | Descarga y verificación de archivos y servicio: proyector del 12B, 26B-A4B con su proyector, variables propias del… | terminada |
| **T-160** | 004 | Lectura con visión de las páginas dudosas: criterio, imagen, transcripción, lectura nueva con origen vision, registro y… | terminada |
| **T-161** | 004 | Medir el caso-00 con el 12B y visión (referencia, y medición de la visión y de T-164) | terminada |
| **T-162** | 004 | Medir el caso-00 con el 26B-A4B y visión, comparar con T-161 y decidir según el umbral (ronda 1) | terminada |
| **T-163** | 004 | Solo si T-162 quedó entre 2 y 3 pares de adoptarlo: un cambio igual para los dos modelos y las dos corridas de nuevo… | terminada |
| **T-165** | 004 | Esquema y resultados nuevos (enmienda de decisiones literales): motivos nuevos de "no determinado", opinión y hechos en… | terminada |
| **T-166** | 004 | Externos e ilegible como regla: "falta la hoja de compliance" (catálogo y marca del modelo) y "no se pudo leer" con… | terminada |
| **T-167** | 004 | Filas técnicas por renglón: documento técnico y renglones con oferta como hechos, resultado "pendiente del informe… | terminada |
| **T-168** | 004 | Ok de la Comisión del informe técnico y presentación en la matriz de los resultados nuevos | terminada |
| **T-169** | 004 | El Portal como fuente: dato o documento en el Portal, falta de coincidencia y cita del Portal | terminada |
| **T-170** | 004 | Medición con la regla nueva: conteo por tipo de par, --verificar-decisiones y actualización de la lista esperada del… | terminada |
| **T-171** | 004 | Medir el caso-00 con las decisiones aplicadas (medición final, una sola) | terminada |
| **T-172** | 004 | Corregir los hallazgos de T-171: documento técnico afirmado por una línea de precio (H-3), ilegible del pagaré en todos… | terminada |
| **T-173** | 004 | Medir el caso-00 con los datos del Portal cargados (ronda 2, la última, ADR-0025) | terminada |
| **T-174** | 004 | Emparejar las ofertas del Portal con las cargadas a mano (CUIT o nombre normalizado, como propuesta del evaluador)… | terminada |
| **T-175** | 004 | Completar REQ-062 y corregir el medidor tras T-173: cita del Portal de la cotización y de la garantía cuando la oferta… | terminada |
| **T-177** | 004 | Lectura con visión: enderezar la página, texto plano con marcador de fin, penalizar la repetición y franjas a mayor… | terminada |
| **T-176** | 004 | Medir el caso-00 después de T-175 y T-177 (medición final) | terminada |
| **T-269** | 007 | Corte vertical: Caddy en Windows con certificado, lista y firewall, los pasos del responsable en entorno.md, y Django… | en verificación |
| **T-270** | 007 | Bloqueo de 5 intentos y 15 minutos con mensaje genérico también en comandos, registro con la computadora de origen y la… | pendiente |
| **T-271** | 007 | Cambio de clave (mínimo 8, comunes, distinta de la actual), clave inicial obligatoria y clave_inicial; cierre de sesión… | pendiente |
| **T-272** | 007 | Prueba en la red con el caso chico, con el responsable: 5 de 5 secciones desde una computadora de la lista y los… | pendiente |
| **T-130** | 008 | Corte vertical con el caso chico: esquema, carga, lectura (texto y escaneo), ficha, pantalla mínima y medición | terminada |
| **T-131** | 008 | Completar la carga y la lectura de ofertas: pantalla, fotos sueltas, segundo intento de lectura y lista de páginas no… | terminada |
| **T-132** | 008 | Corregir la ficha: confirmar, corregir, quitar y agregar fragmentos, historial y aviso de versión de la matriz | terminada |
| **T-133** | 008 | Preparar el caso-00 para medir: lista esperada de fichas de las tres ofertas y matriz validada (Coordinador) | terminada |
| **T-134** | 008 | Medir la ficha con las tres ofertas del caso-00 (medición base) | terminada |
| **T-135** | 008 | Corregir los hallazgos de T-134 y medir de nuevo (ronda 1) | terminada |
| **T-136** | 008 | Solo si T-135 no llegó al umbral: corregir y medir de nuevo (ronda 2, la última) | terminada |
| **T-146** | 008 | Búsqueda de la ficha con el requisito reescrito como lo diría una oferta | terminada |
| **T-138** | 012 | Preparar el esquema, la conexión acotada y la cola del Portal: tablas de portal, cambios de tenders_job y de auditoría… | terminada |
| **T-139** | 012 | Preparar los casos para probar: páginas reales del caso-00 y de un proceso con circulares (fuera del repositorio)… | terminada |
| **T-140** | 012 | Leer la página pública del proceso: datos básicos, renglones, cronograma, garantías y lista de documentos, con el texto… | terminada |
| **T-141** | 012 | Corte vertical: registrar el enlace, explorar, proponer, aprobar ítem por ítem y cargar el procedimiento y los… | terminada |
| **T-142** | 012 | Importar los documentos: bajar el pliego, circulares y demás con su huella y cargarlos por load_document | terminada |
| **T-143** | 012 | Importar las ofertas: acta de apertura y cuadro comparativo, ofertas con garantía y cotización por renglón | terminada |
| **T-144** | 012 | Revisión periódica: una vez por día hábil y a demanda, con novedades y sin repetir lo decidido | terminada |
| **T-145** | 012 | Medir con el caso-00 y el proceso con circulares, corregir una ronda y dejar la medición | terminada |
| **T-179** | 013 | Corte vertical: módulo journey, página de recorrido del caso chico con la etapa Evaluación en vivo (sondeo cada 5 s)… | terminada |
| **T-180** | 013 | Etapas Portal, Pliego y circulares, y Matriz: estado, pendientes y enlaces | terminada |
| **T-181** | 013 | Etapa Ofertas: documentos, fichas, estado, pendientes y enlaces | terminada |
| **T-182** | 013 | Etapa Matriz de evaluación: pares por decidir, preguntas abiertas, ok del informe técnico y enlaces | terminada |
| **T-183** | 013 | Entrada completa: procedimientos con etapa actual y pendientes; alta explorando primero el Portal y la carga a mano… | terminada |
| **T-184** | 013 | Avance fino de los pedidos: columna progress en la cola y aviso desde la evaluación y la ficha (aprobada por el… | terminada |
| **T-187** | 013 | Ventana del proceso: panel en vivo con los pasos del pedido en curso, en lenguaje llano (REQ-070) | terminada |
| **T-188** | 013 | Aplicar la guía visual aprobada (docs/diseno/guia-visual.md, tokens.css): encabezado, recorrido, tablas y estados con… | pendiente |
| **T-189** | 013 | Hoja de compliance por oferta: subirla una vez, rige para todos los requisitos externos de la oferta (reevaluación… | terminada |
| **T-190** | 013 | Informe técnico del área: subirlo (por procedimiento u oferta), el sistema propone apto/no apto por oferta y renglón… | terminada |
| **T-191** | 013 | Recorrido: cuentas y accesos de hojas de compliance e informes técnicos que faltan en la etapa de evaluación (REQ-073… | pendiente |
| **T-185** | 013 | Los cinco momentos y los roles con el caso chico: 30 de 30 celdas y enlaces de las seis etapas | pendiente |
| **T-186** | 013 | Comprobación con el caso-00 desde cero (Coordinador y testeador): cinco momentos, avance en vivo y carga en menos de 2 s | pendiente |
| **T-192** | 014 | Corte vertical: esqueleto de las cinco secciones (barra, portada con pendientes y sugerencias separados, jerarquía… | terminada |
| **T-193** | 014 | Esquema de la feature (una sola tarea): cambios de historial de documentos, tipos nuevos, borrador de procedimiento y… | terminada |
| **T-194** | 014 | Sección 1: datos del procedimiento con origen de cada dato, régimen por fecha de autorización, renglones, apertura… | terminada |
| **T-195** | 014 | Sección 1: explorador y cargador del Portal (pegar enlace, propuesta agrupada, aprobar ítem por ítem o todo) y… | terminada |
| **T-196** | 014 | Propuesta de datos y renglones desde el pliego subido: servicio, pedido en segundo plano, citas y aprobación que crea… | terminada |
| **T-197** | 014 | Sección 1: alta subiendo el pliego (propuesta con citas; el evaluador aprueba, descarta o corrige escribiendo valor y… | terminada |
| **T-198** | 014 | Sección 2: documentos del pliego, anexos y especificaciones (lista por tipo con origen, subida de varios a la vez… | terminada |
| **T-199** | 014 | Servicio de historial de documentos del pliego y de las ofertas: reemplazar, retirar, restituir, con auditoría y estado… | terminada |
| **T-200** | 014 | Sección 2: reemplazar, retirar y restituir documentos del pliego, historial de versiones y «retirados» | terminada |
| **T-201** | 014 | Sección 2: acciones de la Comisión en la tabla de la matriz (confirmar, corregir, quitar, agregar, validar), versión… | terminada |
| **T-202** | 014 | Sección 3: lista de ofertas con alta a la vista (desde el Portal o subiendo archivos, con nombre y CUIT propuestos para… | terminada |
| **T-203** | 014 | Sección 3: ficha de cada oferta (qué presentó frente a cada requisito, con el fragmento o «no se encontró en la oferta») | terminada |
| **T-204** | 014 | Sección 3: anexos técnicos dentro de la oferta y hoja de compliance por oferta con el faltante a la vista (absorbe la… | terminada |
| **T-205** | 014 | Sección 3: circulares y aclaraciones (Portal o subidas); una circular modificatoria abre una versión nueva de la matriz… | terminada |
| **T-206** | 014 | Sección 3: reemplazar, retirar y restituir documentos de la oferta, con historial y «retirados» | terminada |
| **T-207** | 014 | Sección 4: propuesta de evaluación por oferta y requisito (cumple, no cumple, no determinado, con fundamento) y… | terminada |
| **T-208** | 014 | Sección 4: preguntas a la Comisión y pedidos de subsanación con su respuesta registrada | terminada |
| **T-209** | 014 | Sección 4: informe técnico del área (por procedimiento o por oferta) y ok de la Comisión (absorbe la parte de informe… | terminada |
| **T-210** | 014 | Sección 4: descartes propuestos y orden económico; el evaluador confirma o rechaza cada descarte con quién y cuándo | terminada |
| **T-211** | 014 | Sección 4: dictamen del Portal o subido (sin borrador) | terminada |
| **T-212** | 014 | Sección 4: exportar la planilla por oferta (Excel) y el cuadro comparativo (Excel y PDF); suma la dependencia… | terminada |
| **T-213** | 014 | Propuesta de los datos de una norma desde su archivo y staging de la subida (sin pantalla) | terminada |
| **T-214** | 014 | Sección 5: subir una norma, ver el informe de lectura y validarla desde la pantalla | terminada |
| **T-215** | 014 | Sección 5: normas que rigen al procedimiento según su fecha de autorización y cuáles faltan cargar | terminada |
| **T-216** | 014 | Sección 5: consulta de normativa con citas literales | terminada |
| **T-217** | 014 | Los cinco momentos y los roles con el caso chico: estados y cuentas de las cinco secciones, 25 de 25 celdas (reemplaza… | terminada |
| **T-218** | 014 | Comprobación final con el caso chico y el caso-00 (Coordinador y testeador): 26 de 26 requisitos en pantalla, 0 datos… | terminada |
| **T-219** | 014 | Las pantallas anteriores redirigen a su sección y el menú queda con la entrada nueva | terminada |
| **T-220** | 014 | Propuesta de nombre y CUIT del oferente desde los archivos de una oferta: borrador, pedido en segundo plano, citas… | terminada |
| **T-221** | 014 | Rendimiento de las pestañas con datos reales: Pliego y matriz, Ofertas y Evaluación cargan en menos de 2 s con el… | terminada |
| **T-222** | 014 | Pendientes y sugerencias agrupados cuando son muchos: con el procedimiento real la pestaña Evaluación lista 258… | terminada |
| **T-223** | 014 | Menos consultas en los servicios de la evaluación y de la matriz (N+1 en matrix_page, external_results, question_list y… | terminada |
| **T-224** | 014 | Suite en paralelo con pytest-xdist (8 procesos, de 35 a 8 min) y tests inestables corregidos | terminada |
| **T-225** | 014 | Huecos funcionales: no pedir subsanación, descartar una subida de norma, Normativas general sin procedimiento… | terminada |
| **T-226** | 014 | Encabezado y pestañas legibles en pantallas angostas (reglas de la maqueta para 900 y 1100 px) | terminada |
| **T-227** | 014 | Decisiones del 2026-10-10 y brechas de la comprobación final: lo que la circular no tocó viene confirmado en la versión… | terminada |
| **T-228** | 014 | Evaluación legible: en cada celda, pendiente y pregunta se ve el punto completo del pliego con el fragmento del… | terminada |
| **T-229** | 014 | Rehacer el caso LPU25 en el sistema principal como lo haría la Comisión: respaldo, retiro de los datos de la carga de… | terminada |
| **T-230** | 014 | Revisión de errores gruesos del caso rehecho, pestaña por pestaña, como lo vería la Comisión (inconsistencias, textos… | terminada |
| **T-231** | 014 | Errores gruesos de la revisión C en Evaluación: «Evaluar de nuevo» en la pestaña tras responder una pregunta y aviso… | terminada |
| **T-232** | 014 | Errores gruesos de la revisión C en Pliego y matriz, Normativas y encabezados: consecuencia «El pliego no indica»… | terminada |
| **T-267** | 014 | Identidad visual (enmienda del 2026-10-13): logotipo para fondo oscuro en el encabezado de todas las páginas, isotipo… | terminada |
| **T-185** | 014 | T-217 (con sus avisos: pausa del sondeo con la pestaña oculta, Stage.suggestions, motivo de falla con plain_reason… | T-217 (con sus avisos: pausa del sondeo con la pestaña oculta, `Stage.suggestions`, motivo de falla con `plain_reason`, foco del ícono tras el sondeo) |
| **T-186** | 014 | T-218 (con la nota de runbook: reconstruir la imagen con docker compose build app para servir los estáticos) | T-218 (con la nota de runbook: reconstruir la imagen con `docker compose build app` para servir los estáticos) |
| **T-188** | 014 | T-192 (base de la guía visual) y la aplicación en cada tarea de interfaz; revisión final en T-218 | T-192 (base de la guía visual) y la aplicación en cada tarea de interfaz; revisión final en T-218 |
| **T-191** | 014 | T-204 (hoja de compliance que falta) y T-209 (informe técnico que falta) | T-204 (hoja de compliance que falta) y T-209 (informe técnico que falta) |
| **T-233** | 015 | El dato del Portal que coincide con lo que exige el pliego propone «cumple» con la cita del Portal; si difiere, «no… | terminada |
| **T-234** | 015 | Matriz: la cita se amplía por código hasta la unidad de sentido (módulo compartido sentences.py): la oración completa… | terminada |
| **T-250** | 015 | Esquema de los motivos de descarte nuevos (consecuencia en la extracción, condición opcional, pago o factura, forma de… | terminada |
| **T-235** | 015 | Evaluación: la cita de la oferta se amplía a la oración completa, el requisito llega con su punto, el Portal le llega… | terminada |
| **T-236** | 015 | Instrucciones de la matriz, parte 1: bloque común de definiciones (literal de la spec) con versión y huella… | terminada |
| **T-252** | 015 | Instrucciones de la matriz, parte 2: filtro A y B con el bloque común, sin «mantené ante la duda» (la duda va a… | terminada |
| **T-253** | 015 | Razonamiento propio del modelo encendible por paso (extracción, completitud, filtro, evaluación, contraste) con nivel… | terminada |
| **T-254** | 015 | Ronda extra (se perdían requisitos, ADR-0024): las verificaciones externas del oferente (REPSAL, deuda, registro… | terminada |
| **T-255** | 015 | Consulta de normativa con el 27B: la Consulta usa el mismo motor del 27B (sin generation aparte), con las evals de la… | terminada |
| **T-256** | 015 | Medición honesta (sin GPU): corregir los defectos de la medida del comité (pares del Portal sin mirar el resultado, «no… | terminada |
| **T-257** | 015 | Frente evaluación: «no aplica» para la opción que la oferta no usa (por diseño), regla de forma de garantía antes que… | terminada |
| **T-258** | 015 | Frente matriz: definiciones del 2026-10-12, paso de unión de oraciones del mismo asunto, nota de tabla con su cláusula… | terminada |
| **T-259** | 015 | Frente lectura: OCR cuando la extracción del PDF da «(cid:» (croquis), tablas con sus celdas, manuscritos con la visión… | terminada |
| **T-260** | 015 | Medición única de la ronda del comité: caso-00 (desarrollo), casos 01, 02 y 06 (validación), casos 03, 04 y 05 (prueba… | terminada |
| **T-261** | 015 | Contexto de la evaluación (D-260-1): el tope de cada grupo de documentos descuenta la instrucción, el bloque del… | terminada |
| **T-262** | 015 | Presentación física en la matriz (decisión del 2026-10-12, que T-260 vio descartada en los 7 casos por un ejemplo de la… | terminada |
| **T-263** | 015 | Medición de cierre de la 015 con T-261 y T-262: evaluación del caso-00 con la configuración normal (y la corrida… | terminada |
| **T-264** | 015 | Fundamento visible en las pantallas del expediente (dictamen de la 015, hallazgos 1, 2 y 4; decisión del 2026-10-13… | terminada |
| **T-265** | 015 | Extracción sin descartar la nota de un anexo que obliga (D-263-1): la matriz-extraccion-v11 descarta como «formulario»… | terminada |
| **T-266** | 015 | Medición final de la 015 (una sola tanda de GPU): matrices del caso-00, de validación (01, 02 y 06) y de prueba (03, 04… | terminada |
| **T-268** | 015 | Remedición del Gemma 4 12B con el código actual (decisión del 2026-10-14, opción B): caso-00 completo, matrices de los… | terminada |
| **T-237** | 015 | Instrucciones de la evaluación (evaluación, contraste, cláusulas): razonamiento, citas y externo antes del veredicto en… | terminada |
| **T-251** | 015 | Código listo para medir otro modelo: el cuerpo del pedido de lotes dice el modelo que lo atiende y los tokens de los… | terminada |
| **T-238** | 015 | Medidas de la 015 en medir_matriz y medir_evaluacion (filas conservadas, pedazos sin sujeto, recall sin las entradas… | terminada |
| **T-239** | 015 | Medición del 12B con el uso corregido: caso chico como corte vertical, caso-00 (matriz, revisión como en T-229 y… | terminada |
| **T-240** | 015 | Ronda de ajuste única, solo si T-239 no llega a algún umbral: todos los hallazgos en una sola tarea, un commit por… | terminada |
| **T-241** | 015 | Repetición completa de la medición de T-239 sobre el commit ajustado; es la referencia del 12B para la comparación.… | terminada |
| **T-242** | 015 | Servicio de los candidatos: un archivo de compose por modelo (Qwen3.8-27B y Qwen3.6-35B-A3B) a la manera del ADR-0042… | terminada |
| **T-243** | 015 | Qwen3.8-27B en servicio: prueba de humo con texto e imagen, memoria máxima (22.000 MiB), reuso de la caché de prefijo… | terminada |
| **T-244** | 015 | Comparación de Qwen3.8-27B con el 12B, con el protocolo del ADR-0042 y el uso corregido: caso-00 completo primero… | terminada |
| **T-245** | 015 | Qwen3.6-35B-A3B en servicio: las mismas comprobaciones que T-243 con los mismos umbrales | terminada |
| **T-246** | 015 | Comparación de Qwen3.6-35B-A3B con el 12B, con el mismo protocolo y los mismos umbrales | terminada |
| **T-247** | 015 | ADR de resultado (reservado ADR-0057): adopta o descarta cada candidato con las corridas como evidencia; si adopta… | terminada |
| **T-248** | 015 | Resto de las instrucciones (consecuencias, respaldo, ficha, ficha por renglón, reescritura, visión, informe técnico… | terminada |
| **T-249** | 015 | Medición de lo que cambió T-248, solo en las áreas que cambió, con el umbral de que ninguna medida empeore (P7): evals… | terminada |
| **T-270** | 016 | Entorno del clon: docker-compose.clon.yml y scripts/clon.sh (proyecto evaluon-016, servicios clon_*, base restaurada de… | terminada |
| **T-271** | 016 | Formato de la verdad celda por celda y su cargador: no_determinado, fundamento, revisión, huella, congelado, clave por… | terminada |
| **T-272** | 016 | Cargar al clon las ofertas, los datos del Portal y el dictamen de los 3 procesos públicos terminados que aporte o… | pendiente |
| **T-273** | 016 | Verdad celda por celda del caso de ajuste: un agente lo rehace como la Comisión, sin ver nada del sistema, con… | pendiente |
| **T-274** | 016 | Verdad celda por celda del primer caso de aceptación, con el mismo método y el mismo umbral | pendiente |
| **T-275** | 016 | Verdad celda por celda del segundo caso de aceptación, con el mismo método y el mismo umbral | pendiente |
| **T-276** | 016 | Cierre del paso 1: documento de revisión por caso, revisión y firma celda por celda del responsable (quién y cuándo en… | pendiente |
| **T-277** | 016 | Reglas a tres salidas: toda celda lleva su pregunta o su documento nombrado (combine.py, conversiones de evaluate.py… | terminada |
| **T-278** | 016 | Pruebas de las instrucciones y tabla de decisiones: tope de largo (decisoras 90 líneas y 9.000 caracteres; demás 50 y… | terminada |
| **T-279** | 016 | Instrucciones de la matriz, parte 1: bloque común de definiciones, extracción, completitud y unión, nuevas y cortas… | terminada |
| **T-280** | 016 | Instrucciones de la matriz, parte 2: filtro, consecuencias, circulares, cambios de circulares y respaldo normativo… | terminada |
| **T-281** | 016 | Instrucciones de la evaluación: evaluación, contraste, cláusulas y reescritura, nuevas y cortas, con las descripciones… | terminada |
| **T-282** | 016 | Instrucciones auxiliares: visión, ficha, ficha por renglón, informe técnico, nombre del oferente, datos del… | terminada |
| **T-283** | 016 | Medición del paso 2, ronda 1 (matrices y caso-00): matrices de 00, 01, 02 y 06; caso-00 completo (matriz y evaluación… | terminada |
| **T-284** | 016 | Medición del paso 2, ronda 1 (evaluación con verdad): evaluación del caso de ajuste con verdad con el commit de… | pendiente |
| **T-285** | 016 | Ajuste único del paso 2: todos los hallazgos de T-283 y T-284 en una sola tarea, un commit por hallazgo, corregidos… | terminada |
| **T-286** | 016 | Re-medición del paso 2, ronda 2: solo lo que cambió T-285 (más el caso-00 completo, para el tiempo y la comparación con… | terminada |
| **T-287** | 016 | Cierre de los pasos 1 y 2: ADR-0071 (resultado: instrucciones y reglas simples que quedan locales) con las cifras como… | en verificación |
| **T-288** | 016 | Esquema y configuración del uso externo: tipo de hecho external_request y su migración (la única de la feature)… | terminada |
| **T-289** | 016 | Cliente de la API externa, su doble y la salida a internet: evaluon/ai/external/client.py (mensajes directos y lotes… | terminada |
| **T-290** | 016 | Puerta de filtrado, libro de gasto y registro: guard.py (lista permitida, exclusiones, huellas), ledger.py (hecho por… | terminada |
| **T-291** | 016 | Matriz con modelo externo: matriz-externa-v1, proposal/external.py con el contrato de la etapa local, enchufe en run.py… | terminada |
| **T-292** | 016 | Prueba de humo con el proveedor real (caso chico): matriz externa en modo directo con la hoja de compliance inventada… | terminada |
| **T-293** | 016 | Medición del paso 3, ronda 1 (ajuste): propuesta externa de 00, 01, 02 y 06 contra la local simplificada de T-286.… | pendiente |
| **T-294** | 016 | Ajuste único de la matriz externa (matriz-externa-v2 y parámetros) con todos los hallazgos de T-293; se cierra sin… | pendiente |
| **T-295** | 016 | Re-medición del paso 3, ronda 2 (ajuste): lo que cambió T-294. Mismo umbral 16; si no lo pasa, el externo no pasa a… | pendiente |
| **T-296** | 016 | Medición final del paso 3 (aceptación, una sola corrida): matriz local simplificada y externa de 03, 04 y 05, mismo… | pendiente |
| **T-297** | 016 | Segunda comparación con claude-opus-5-5, solo si Sonnet no pasó el umbral 13 o 14 y la etapa pasó la puerta 16: misma… | pendiente |
| **T-298** | 016 | Cierre del paso 3: ADR-0072 (matriz: local o externa, y por qué) con las cifras, gasto real por etapa, registro del… | pendiente |
| **T-299** | 016 | Verificador externo de citas: verifier.py, verificador-v1, enchufe en evaluate_offer después del contraste y de las… | terminada |
| **T-300** | 016 | Línea «Etapas fuera del equipo» en la pantalla de la evaluación y en su exportación, leída de la clave externo de la… | en verificación |
| **T-301** | 016 | Medición del paso 4, ronda 1 (ajuste, sin GPU): humo del verificador con el caso chico y después el verificador sobre… | pendiente |
| **T-302** | 016 | Ajuste único del verificador (verificador-v2 y parámetros) con todos los hallazgos de T-301; se cierra sin cambios si… | pendiente |
| **T-303** | 016 | Re-medición del paso 4, ronda 2 (ajuste, sin GPU): lo que cambió T-302. Mismo umbral 17 como puerta | pendiente |
| **T-304** | 016 | Medición final del paso 4 (aceptación, una sola corrida): evaluación local de los casos de aceptación con verdad y… | pendiente |
| **T-305** | 016 | Segunda comparación del verificador con claude-opus-5-5, solo si Sonnet no pasó el umbral 17 y la etapa pasó la puerta… | pendiente |
| **T-306** | 016 | Cierre del paso 4: ADR-0073 (verificador: con o sin, y por qué) con las cifras, gasto real por etapa, registro del paso… | pendiente |
| **T-307** | 016 | Verificación transversal con el uso externo apagado y encendido: suite completa sobre la combinación; caso-00 completo… | pendiente |

## Requisitos (116)

| Código | Feature | Qué es | · |
|---|---|---|---|
| **REQ-001** | 001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título… |  |
| **REQ-002** | 001 | El sistema debe conservar el documento original de cada norma y permitir verlo |  |
| **REQ-003** | 001 | El sistema debe dividir cada documento en unidades citables, cada una con su ubicación: considerando, artículo, inciso… |  |
| **REQ-004** | 001 | El sistema debe entregar, por cada norma incorporada, un informe de lectura: cuántas unidades reconoció, cuáles páginas… |  |
| **REQ-005** | 001 | Una norma debe quedar disponible para consultas solo después de que una persona valide su informe de lectura |  |
| **REQ-006** | 001 | El sistema debe registrar las relaciones entre normas: cuál modifica, complementa, reglamenta o deroga a cuál. Cuando… |  |
| **REQ-007** | 001 | El sistema debe mantener las versiones de cada norma y, para una fecha dada, indicar qué unidades estaban vigentes y… |  |
| **REQ-008** | 001 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe… |  |
| **REQ-009** | 001 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada |  |
| **REQ-010** | 001 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto, desde la pantalla de… |  |
| **REQ-011** | 001 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada. Si es el mismo archivo, no lo… |  |
| **REQ-012** | 001 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre… |  |
| **REQ-013** | 001 | El sistema debe ofrecer una pantalla de consulta donde una persona escribe su pregunta y ve la respuesta con sus citas… |  |
| **REQ-014** | 001 | La pantalla de consulta debe distinguir a simple vista una respuesta con fundamento de un resultado "no determinado" |  |
| **REQ-015** | 001 | El sistema debe incorporar normas en tres formatos: PDF con texto, PDF escaneado y página web guardada. Cuando el texto… |  |
| **REQ-016** | 001 | El sistema debe exigir usuario y clave para ingresar. Cada usuario tiene un rol: lectura, que permite consultar y… |  |
| **REQ-017** | 001 | El sistema debe registrar la categoría de cada documento: régimen específico, otra normativa aplicable, marco nacional… |  |
| **REQ-018** | 001 | Cada cita debe mostrar la categoría de su documento. En una respuesta, las citas del régimen específico van primero… |  |
| **REQ-019** | 001 | Cuando el régimen específico y el marco nacional tratan el mismo punto de manera distinta, la respuesta debe mostrar… |  |
| **REQ-020** | 001 | Cada consulta y cada búsqueda se hacen para una fecha de autorización del procedimiento, que la persona indica en la… |  |
| **REQ-021** | 001 | El sistema debe permitir registrar que una norma tiene modificatorias todavía no cargadas, identificando cada una.… |  |
| **REQ-022** | 003 | El sistema debe registrar un procedimiento con su número, tipo, objeto y fecha de autorización, y mostrar el régimen de… |  |
| **REQ-023** | 003 | El sistema debe permitir cargar el pliego final de un procedimiento como uno o más documentos, conservando cada… |  |
| **REQ-024** | 003 | El sistema debe proponer, a partir del pliego cargado, la lista de requisitos que debe cumplir una oferta, cada uno… |  |
| **REQ-025** | 003 | Cada requisito propuesto debe citar el texto literal del pliego que lo exige, con el documento y la ubicación (página y… |  |
| **REQ-026** | 003 | La Comisión debe poder confirmar, corregir, quitar o agregar requisitos; cada cambio queda registrado con quién lo hizo… |  |
| **REQ-027** | 003 | Una matriz validada queda fija: cambiarla después genera una versión nueva, sin perder la anterior |  |
| **REQ-028** | 003 | Cuando el sistema no puede ubicar con certeza un tramo del pliego (texto ilegible, tabla mal leída), debe señalarlo… |  |
| **REQ-029** | 003 | Para cada requisito, el sistema debe proponer las consecuencias posibles de no cumplirlo (por ejemplo, desestimación de… |  |
| **REQ-030** | 003 | La matriz se propone siempre con un único proceso de revisión, el más completo disponible, y queda registrado con la… |  |
| **REQ-031** | 003 | El pliego final incluye las circulares modificatorias y aclaratorias y las preguntas de los oferentes con sus… |  |
| **REQ-033** | 003 | Antes de mostrar la matriz propuesta, el sistema debe descartar las filas que no son requisitos de la oferta y unificar… |  |
| **REQ-034** | 003 | La Comisión debe poder confirmar o quitar de una vez un grupo de requisitos propuestos de un mismo tramo o cláusula… |  |
| **REQ-035** | 003 | La matriz propuesta debe separar los requisitos que el sistema da por firmes de las sugerencias de condición… |  |
| **REQ-036** | 003 | Para cada sugerencia de condición y cada fila dudosa, el sistema debe buscar en la normativa aplicable (según REQ-022)… |  |
| **REQ-032** | 003 | Una matriz que todavía no está validada se puede ver en pantalla, imprimir y exportar a PDF, siempre con la leyenda… |  |
| **REQ-052** | 004 | Para cada oferta y cada requisito de la matriz validada, el sistema debe proponer un resultado: cumple, no cumple, no… |  |
| **REQ-053** | 004 | Cada propuesta debe traer su fundamento citado: el texto del requisito (pliego o circular), el texto de la oferta que… |  |
| **REQ-054** | 004 | Para proponer, el sistema debe leer completos los documentos de la oferta que pueden responder el requisito, no solo… |  |
| **REQ-055** | 004 | Cuando no puede resolver un requisito con el pliego, la oferta, la normativa o lo ya respondido, el sistema debe… |  |
| **REQ-056** | 004 | El evaluador debe poder confirmar, corregir o rechazar cada propuesta, y responder las preguntas. Cada decisión y cada… |  |
| **REQ-057** | 004 | La evaluación de una oferta se arma contra una versión de la matriz validada y lo indica; si la matriz cambia, se avisa. |  |
| **REQ-058** | 004 | El sistema debe mostrar, por oferta, el estado de la evaluación: requisitos por estado y preguntas abiertas. |  |
| **REQ-059** | 004 | La evaluación se pide para todas las ofertas del procedimiento a la vez y se presenta como una matriz de evaluación… |  |
| **REQ-060** | 004 | Cuando el pliego exige un documento que no está en la oferta, el resultado es "no se encontró el documento", con la… |  |
| **REQ-109** | 007 | La aplicación se puede usar desde las computadoras de una lista de autorizadas que mantiene el responsable del sistema… |  |
| **REQ-110** | 007 | Toda comunicación entre la computadora del usuario y EVALUON va cifrada. Un pedido sin cifrar no muestra contenido: se… |  |
| **REQ-111** | 007 | Tras 5 intentos fallidos seguidos para un mismo usuario, ese usuario queda bloqueado durante 15 minutos, aunque después… |  |
| **REQ-112** | 007 | El responsable del sistema puede desbloquear un usuario antes de que venza el plazo, desde el equipo del sistema; el… |  |
| **REQ-113** | 007 | Cada ingreso, salida, intento fallido, bloqueo y desbloqueo queda registrado con el usuario (o el nombre tal como se… |  |
| **REQ-114** | 007 | Cada usuario puede cambiar su clave; para hacerlo escribe la actual. El sistema exige una clave nueva de al menos 8… |  |
| **REQ-115** | 007 | Una sesión sin uso durante 30 minutos se cierra; también se cierra a las 8 horas de iniciada y al cerrar el navegador.… |  |
| **REQ-116** | 007 | Desde otra computadora solo se llega a la aplicación: la base de datos, los motores de IA y los demás servicios… |  |
| **REQ-117** | 007 | Los documentos del proceso en curso (reservados hasta el dictamen) y todo lo que el sistema produce sobre ellos… |  |
| **REQ-037** | 008 | El sistema debe permitir registrar las ofertas de un procedimiento, cada una con su oferente, y cargar en cada una… |  |
| **REQ-038** | 008 | El sistema debe leer los documentos con texto y los escaneados o fotografiados, e informar qué páginas no pudo leer o… |  |
| **REQ-039** | 008 | Para cada oferta y cada requisito de la matriz validada, el sistema debe proponer los fragmentos de la oferta que… |  |
| **REQ-040** | 008 | Cuando no encuentra ningún fragmento para un requisito, el sistema debe decirlo expresamente en la ficha ("no se… |  |
| **REQ-041** | 008 | La ficha debe mostrar una síntesis breve de lo ofrecido para cada requisito, sin juicio de cumplimiento. |  |
| **REQ-042** | 008 | La Comisión debe poder confirmar, corregir, quitar o agregar fragmentos de la ficha. Cada cambio queda registrado con… |  |
| **REQ-043** | 008 | La ficha se arma solo contra una matriz validada. Si la matriz cambia de versión, la ficha indica con qué versión se… |  |
| **REQ-044** | 008 | Para la parte técnica, la ficha indica si la oferta trae documentación técnica y, cuando el pliego tiene renglones, si… |  |
| **REQ-045** | 012 | El sistema debe permitir registrar un proceso a partir del enlace público de su página en el Portal de Compras. |  |
| **REQ-046** | 012 | Con ese enlace, el sistema debe explorar lo publicado y proponer, sin cargar nada todavía: los datos del procedimiento… |  |
| **REQ-047** | 012 | Si las ofertas ya están abiertas, la propuesta debe incluir cada oferta con su oferente, su CUIT, su total, su garantía… |  |
| **REQ-048** | 012 | Nada se carga sin la aprobación de un evaluador; el operador puede aprobar solo la carga de documentos. La aprobación… |  |
| **REQ-049** | 012 | Cada documento y cada dato cargado desde el Portal debe conservar su origen (la página o el documento del Portal y la… |  |
| **REQ-050** | 012 | El sistema debe revisar periódicamente los procesos en curso y proponer las novedades (documentos o datos nuevos o… |  |
| **REQ-051** | 012 | La carga a mano sigue disponible para todo lo que el Portal no publique o no deje bajar, y convive con lo importado. |  |
| **REQ-065** | 013 | Una página de entrada lista los procedimientos con su etapa actual y lo pendiente de decidir, y permite empezar uno… |  |
| **REQ-066** | 013 | Cada procedimiento tiene una página de recorrido con sus etapas en orden y el estado de cada una (pendiente, en curso… |  |
| **REQ-067** | 013 | Mientras el sistema trabaja en segundo plano, la página muestra el avance en vivo (tarea, paso, porcentaje o cuenta… |  |
| **REQ-068** | 013 | Cada etapa muestra cuántas decisiones esperan a la Comisión y enlaza a la pantalla existente donde se toman; el… |  |
| **REQ-069** | 013 | El recorrido respeta los roles: el operador ve todo y prepara; solo el evaluador ve las acciones de decisión. |  |
| **REQ-075** | 014 | Cada procedimiento se organiza en cinco secciones: 1 · Procedimiento de compra, 2 · Pliego y matriz, 3 · Ofertas, 4 ·… |  |
| **REQ-076** | 014 | La sección 1 tiene un explorador y cargador inicial del Portal: se pega el enlace del proceso, el sistema muestra lo… |  |
| **REQ-077** | 014 | Sin Portal, el procedimiento se da de alta subiendo el pliego: el sistema lee el archivo y propone los datos del… |  |
| **REQ-078** | 014 | La sección 1 muestra número, expediente, tipo, objeto, fecha de autorización con el régimen que fija (Disp. 247/2022 o… |  |
| **REQ-079** | 014 | El sistema revisa periódicamente el proceso en el Portal y avisa lo nuevo (una circular, el acta de apertura, el… |  |
| **REQ-080** | 014 | En la sección 2, el pliego, sus anexos y las especificaciones técnicas se toman del Portal o se suben. |  |
| **REQ-081** | 014 | En la sección 2, la matriz de cumplimiento es una tabla agrupada por tipo (formales, económicos, técnicos), con filtros… |  |
| **REQ-082** | 014 | La matriz tiene versiones visibles en una lista y se puede imprimir y exportar. |  |
| **REQ-083** | 014 | En la sección 3, el alta de ofertas está a la vista: desde el Portal (acta de apertura con oferente, CUIT, total… |  |
| **REQ-084** | 014 | Los documentos de cada oferta se suben, varios a la vez, dentro de la oferta. |  |
| **REQ-085** | 014 | En la sección 3 se ven las circulares y aclaraciones (modificatorias, aclaratorias, respuestas a consultas), tomadas… |  |
| **REQ-086** | 014 | Cada oferta tiene su ficha: qué presentó frente a cada requisito de la matriz, con el fragmento de la oferta que lo… |  |
| **REQ-087** | 014 | Los anexos técnicos de cada oferta (fichas y folletos técnicos del oferente) se suben dentro de la oferta. |  |
| **REQ-088** | 014 | La hoja de compliance de cada oferta se sube en la sección 3, una vez por oferta, y rige para todos sus requisitos… |  |
| **REQ-089** | 014 | En la sección 4, el sistema propone por oferta y por requisito cumple, no cumple o no determinado, con su fundamento, y… |  |
| **REQ-090** | 014 | En la sección 4 están las preguntas a la Comisión y los pedidos de subsanación, con su respuesta registrada. |  |
| **REQ-091** | 014 | En la sección 4 se ven los descartes propuestos y el orden económico, total y por renglón. La Comisión confirma o… |  |
| **REQ-092** | 014 | El dictamen se toma del Portal si está publicado, o se sube. El sistema no redacta un borrador del dictamen. |  |
| **REQ-093** | 014 | En la sección 4 se exportan la planilla por oferta y el cuadro comparativo. |  |
| **REQ-094** | 014 | En la sección 5, una norma se carga subiendo su archivo; el sistema la lee, muestra el informe de lectura y la Comisión… |  |
| **REQ-095** | 014 | En cada procedimiento, la sección 5 muestra qué normas lo rigen según su fecha de autorización y cuáles faltan cargar. |  |
| **REQ-096** | 014 | La consulta de normativa con citas literales está en la sección 5. |  |
| **REQ-097** | 014 | Cada sección muestra qué hay, qué falta y de dónde vino cada cosa, con «Subir archivo» y, cuando el Portal lo publica… |  |
| **REQ-098** | 014 | Lo pendiente de decidir y las sugerencias del sistema se ven separados y los dos visibles, en cada sección y en la… |  |
| **REQ-099** | 014 | Reemplazar o retirar un archivo no borra nada: la versión anterior o el retirado quedan en el historial y se pueden ver. |  |
| **REQ-100** | 014 | Todas las pantallas usan la guía visual acordada (docs/diseno/guia-visual.md), con la misma jerarquía: título, resumen… |  |
| **REQ-108** | 014 | La aplicación muestra su marca aprobada (docs/diseno/marca/): el logotipo para fondo oscuro en el encabezado de todas… |  |
| **REQ-101** | 015 | Cada requisito propuesto en la matriz cita su unidad de sentido completa: la oración entera, junto con las oraciones… |  |
| **REQ-102** | 015 | La matriz propuesta no incluye consecuencias, obligaciones del organismo, condiciones que solo valen si el oferente… |  |
| **REQ-103** | 015 | Cuando el dato de la oferta está en el Portal y coincide con lo que exige el pliego, la evaluación propone «cumple»… |  |
| **REQ-104** | 015 | En la evaluación, el sistema razona antes de dar el veredicto, revisa todas las condiciones del requisito, cada una con… |  |
| **REQ-105** | 015 | Cada pregunta a la Comisión está dirigida a la Comisión (nunca al oferente) y dice qué requisito, qué conclusión y qué… |  |
| **REQ-106** | 015 | Todas las instrucciones al modelo (matriz, evaluación, contraste, visión, ficha, consulta) se revisan contra las… |  |
| **REQ-107** | 015 | Un modelo nuevo se adopta solo si, con el uso corregido, el mismo caso y la misma lista esperada, mejora las medidas de… |  |
| **REQ-118** | 016 | Existe verdad celda por celda (cumple, no cumple, no aplica o no determinado, con su fundamento) para al menos tres… |  |
| **REQ-119** | 016 | Cada instrucción al modelo local (matriz, evaluación, contraste, visión, ficha, consulta) contiene solo las… |  |
| **REQ-120** | 016 | Toda celda de la evaluación termina en una de tres salidas: «cumple» con fundamento, «no cumple» con cita, o «no… |  |
| **REQ-121** | 016 | El sistema puede usar un modelo externo solo con documentos públicos; ningún pedido externo contiene un documento de… |  |
| **REQ-122** | 016 | Cada pedido a un modelo externo queda en el registro de auditoría con proveedor, modelo, versión de la instrucción… |  |
| **REQ-123** | 016 | La matriz de cumplimiento se puede proponer con un modelo externo que lee el pliego completo, con las mismas medidas y… |  |
| **REQ-124** | 016 | Una verificación con modelo externo puede revisar cada «cumple» o «no cumple» propuesto por el modelo local: confirma… |  |
| **REQ-125** | 016 | Cada paso de la feature (verdad ampliada, simplificación, matriz externa, verificador externo) se mide contra un umbral… |  |

## Decisiones (ADR) (70)

| Código | Feature | Qué es | Estado |
|---|---|---|---|
| **ADR-0001** |  | Marco de trabajo: SDD con Coordinador y cinco agentes | aceptado |
| **ADR-0002** |  | Motor de IA local y modelo de generación | aceptado |
| **ADR-0003** |  | Recuperación: embeddings, reranker y búsqueda combinada sobre Postgres | aceptado |
| **ADR-0004** |  | Lectura y partición de documentos | aceptado |
| **ADR-0005** |  | Aplicación web, pantalla de consulta, acceso y comandos | aceptado |
| **ADR-0006** |  | Dos regímenes específicos según la fecha de autorización del procedimiento | aceptado |
| **ADR-0007** |  | Búsqueda por palabras: tildes, singular y plural | aceptado |
| **ADR-0008** |  | El procedimiento como eje y la hoja de ruta reformulada | aceptado |
| **ADR-0009** |  | Las respuestas de la Comisión como fundamento | aceptado |
| **ADR-0010** |  | AFIP y ARCA son el mismo organismo | aceptado |
| **ADR-0011** |  | Cómo se mide si una respuesta es correcta | aceptado |
| **ADR-0012** |  | Cuándo se corre la suite completa de tests | aceptado |
| **ADR-0013** |  | Asesor de metodología | aceptado |
| **ADR-0014** |  | Recomendaciones del asesor de metodología del 2026-10-03 | aceptado |
| **ADR-0015** |  | Remisión a una norma no cargada y visto bueno del conjunto en el piloto | aceptado |
| **ADR-0016** |  | Validación continua con la Comisión (feature 009) | aceptado |
| **ADR-0017** |  | El núcleo primero y cierre acotado de la 001 | aceptado |
| **ADR-0018** |  | Pedidos largos en segundo plano y motor de generación para lotes | aceptado |
| **ADR-0019** |  | Propuesta de la matriz por tramos, con disposición obligatoria y cita verificada | aceptado |
| **ADR-0020** |  | PDF de la matriz generado en el equipo con WeasyPrint | aceptado |
| **ADR-0021** |  | Filtro de precisión de la matriz: una pasada separada, con descarte visible y recuperable | aceptado |
| **ADR-0022** |  | Sugerencias de condición y respaldo normativo: un tercer destino del filtro, y la norma solo confirma | aceptado |
| **ADR-0023** |  | Pasada de circulares: unidades de cambio aplicadas por clave, con el modelo solo donde no hay clave | aceptado |
| **ADR-0024** |  | Cierre de la 003 con lo medido y revisión de lo menor con el primer producto | aceptado |
| **ADR-0025** |  | Rondas de ajuste con umbral previo, verificación proporcional al riesgo y estado por lote | aceptado |
| **ADR-0026** |  | Las ofertas viven en un módulo propio, con la cola de pedidos compartida | aceptado |
| **ADR-0027** |  | Cómo se encuentran los fragmentos de una oferta: recuperación en pasajes y elección del modelo entre… | aceptado |
| **ADR-0028** |  | Lectura de escaneos y fotos de ofertas con el OCR existente, con preparación de imagen solo si hace falta | aceptado |
| **ADR-0029** |  | El Portal de Compras como primera fuente, con conexión solo para leerlo | aceptado |
| **ADR-0030** |  | La importación del Portal vive en un módulo propio y propone por ítems antes de cargar | aceptado |
| **ADR-0031** |  | Conexión acotada al Portal: un servicio aparte con salida a internet y una lista de destinos permitidos | aceptado |
| **ADR-0032** |  | Lectura de la página del Portal: HTML con las librerías existentes, formularios de ASP.NET con la biblioteca… | aceptado |
| **ADR-0033** |  | Revisión periódica: la hace el servicio del Portal, una vez por día hábil y a demanda | aceptado |
| **ADR-0034** |  | Criterios de aceptación de la 003 después de la auditoría | aceptado |
| **ADR-0035** |  | Cierre de la 008 con la ficha actual y lectura completa de los documentos en la 004 | aceptado |
| **ADR-0036** |  | Auditoría de funcionamiento por feature y de cumplimiento al final | aceptado, reemplazado en parte por ADR-0052 |
| **ADR-0037** |  | Lectura completa por requisito: grupos de documentos completos y contexto de 32.768 tokens en el motor de… | aceptado |
| **ADR-0038** |  | Resultados con cita literal verificada por el sistema y contraste antes de concluir | aceptado |
| **ADR-0039** |  | Módulo de evaluación propio: resultados inmutables, decisiones aparte y recorrido por par | aceptado |
| **ADR-0040** |  | Registro mínimo de preguntas y respuestas de la Comisión dentro de la 004 | aceptado |
| **ADR-0041** |  | Lectura con visión de las páginas de lectura dudosa | aceptado |
| **ADR-0042** |  | Comparación controlada del modelo de generación: Gemma 4 12B contra Gemma 4 26B-A4B | aceptado |
| **ADR-0043** |  | Decisiones literales de la 004: motivos de "no determinado" y reglas antes del modelo | aceptado |
| **ADR-0044** |  | Aceptación de la 004 (evaluación asistida) con la medición de T-176 | aceptado |
| **ADR-0045** |  | Recorrido del procedimiento: estado calculado, actualización por sondeo local y avance de los pedidos | aceptado |
| **ADR-0046** |  | Organización de la aplicación por expediente (maqueta aprobada) | reemplazado en parte por el ADR-0047 (2026-10-07: puntos 1 a 3 y la maqueta de 24 pantallas) |
| **ADR-0047** |  | Cinco secciones sin orden obligatorio | aceptado |
| **ADR-0048** |  | Historial de documentos sin borrar | aceptado |
| **ADR-0049** |  | Alta del procedimiento desde el pliego subido | aceptado |
| **ADR-0050** |  | Formato de las exportaciones de la evaluación | aceptado |
| **ADR-0051** |  | Carga de normas subiendo solo el archivo | aceptado |
| **ADR-0052** |  | Auditoría solo de fallas por feature y completa después de la revisión de la Comisión | aceptado |
| **ADR-0053** |  | El dato del Portal que coincide con el pliego propone «cumple» | aceptado |
| **ADR-0054** |  | Matriz: cita de la oración completa, definiciones del responsable en un bloque común y motivos de descarte… | aceptado |
| **ADR-0055** |  | Cómo se pide al modelo: razonamiento en el JSON antes del veredicto, ejemplos balanceados, contexto en lugar… | aceptado |
| **ADR-0056** |  | Modelos candidatos para el motor de lotes: Qwen3.8-27B y Qwen3.6-35B-A3B, y protocolo de la comparación | aceptado |
| **ADR-0057** |  | Adopción del modelo de evaluación: Qwen3.8-27B con razonamiento solo en el contraste | aceptado |
| **ADR-0058** |  | Criterios de la Comisión para la evaluación y la ausencia verificada como fundamento | aceptado |
| **ADR-0059** |  | Criterios de mejora real | aceptado |
| **ADR-0060** |  | Material reservado del piloto visible para los agentes durante la estabilización (enmienda de P4) | aceptado |
| **ADR-0061** |  | Intermediario cifrado en Windows y lista de computadoras por dirección fija | aceptado (versión 3, mínima) |
| **ADR-0062** |  | Certificado de la conexión cifrada en dos variantes, con los mismos archivos | aceptado (versión 3, mínima) |
| **ADR-0063** |  | Bloqueo, sesión y cambio de clave con lo que trae Django | aceptado (versión 3, mínima) |
| **ADR-0064** |  | Instancia del piloto en la misma notebook, con el motor de generación para una instancia a la vez | rechazado (2026-10-14, versión mínima: una sola instancia) |
| **ADR-0065** |  | Clasificación de datos por transparencia y uso de modelos externos por clase de dato (enmienda de P4) | aceptado |
| **ADR-0066** |  | Cliente de la API externa (Anthropic) y salida a internet de la instancia que lo usa | aceptado |
| **ADR-0067** |  | Un solo punto de filtrado de lo reservado antes de cualquier pedido externo | aceptado |
| **ADR-0068** |  | Registro de los pedidos externos en la auditoría y tope de gasto hecho cumplir en código | aceptado |
| **ADR-0069** |  | Verdad ampliada celda por celda: armada a ciegas del sistema, revisada y firmada por el responsable | aceptado |
| **ADR-0070** |  | Instrucciones y reglas simples: largo máximo, sin ejemplos de casos, desempate a la corta y tres salidas por… | aceptado |

## Decisiones y definiciones de las instrucciones (D-NN) (67)

| Código | Feature | Qué es | Estado |
|---|---|---|---|
| **D-01** | 016 | «Es requisito de la oferta lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o… | decisión literal |
| **D-02** | 016 | Los requisitos técnicos van «en una fila por renglón del pliego, con la cita a sus especificaciones técnicas». «La Comisión no evalúa el detalle… | decisión literal |
| **D-03** | 016 | «La clase sigue la sección del pliego cuando el pliego ordena sus requisitos por secciones. Si no, se clasifica por naturaleza: la garantía, el… | decisión literal |
| **D-04** | 016 | «El sistema no decide si un requisito es subsanable: detecta qué consecuencias tiene su falta, sugiere las posibles con su fundamento, y un… | decisión literal |
| **D-05** | 016 | REQ-031: las circulares y las respuestas a consultas cambian o precisan un requisito; la matriz aplica el cambio, muestra los dos textos y cita el… | decisión literal |
| **D-06** | 016 | REQ-033 y REQ-035: antes de mostrar la matriz se descartan las filas que no son requisitos de la oferta, cada una con su cita y su motivo; las… | decisión literal |
| **D-07** | 016 | REQ-036: para cada sugerencia y cada fila dudosa se busca en la normativa aplicable si el régimen exige esa condición. «La normativa solo sirve para… | decisión literal |
| **D-08** | 016 | «el porcentaje esta bien, aunque no necesariamente sea literal la coincidencia. Lo tecnico verificamos que exista y que en caso de tener renglones si… | decisión literal |
| **D-09** | 016 | «La parte tecnica ya te dije que venia del area correspondiente»; «la comision debiera dar el ok de que tiene el informe tecnico aprobado». REQ-061… | decisión literal |
| **D-10** | 016 | «eso lo integrará un documento que llamamos hoja de compliance. Si detectas que falta uno pueden subir otra. O una que informe que No cumple».… | decisión literal |
| **D-11** | 016 | «Debiste informar que el doc esta en el portal o que falta coincidencia». REQ-062: cuando el dato o el documento está en el Portal, el sistema lo… | decisión literal |
| **D-12** | 016 | «no entran ninguno de los 3. una salvedad la moneda de la oferta si es un requisito.»: no son requisitos de la oferta el pago, la moneda de pago y la… | decisión literal |
| **D-13** | 016 | «Requisito de la forma elegida»: las condiciones de cada forma de garantía entran en la matriz y se evalúan solo en la oferta que eligió esa forma… | decisión literal |
| **D-14** | 016 | «Una fila por oración»: una fila con la oración completa; la evaluación revisa cada condición con su dato y lo muestra por separado dentro de la… | decisión literal |
| **D-15** | 016 | REQ-101: la cita es la oración completa, con el encabezado del punto o del inciso cuando la oración sola no se entiende, nunca un pedazo sin sujeto.… | decisión literal |
| **D-16** | 016 | «Propone cumple»: el sistema propone «cumple» citando el dato del Portal cuando coincide con lo que exige el pliego, y «no cumple» o diferencia… | decisión literal |
| **D-17** | 016 | «enmendar. considera al portal como oficial, porque es oficial»: el dato publicado en el Portal de Compras vale como fundamento (constitución 1.3). | decisión literal |
| **D-18** | 016 | «Cumple por ausencia, con fundamento»: un requisito negativo o supletorio se propone «cumple» diciendo qué documentos se leyeron y que ninguno lo… | decisión literal |
| **D-19** | 016 | «Precio del Portal = final con IVA»: salvo que la oferta diga lo contrario, el precio cotizado en el Portal es precio final con IVA incluido; se… | decisión literal |
| **D-20** | 016 | «En la misma fila del plazo»: una sola fila con el plazo de mantenimiento y su prórroga automática (mismo asunto); se evalúa por ausencia salvo que… | decisión literal |
| **D-21** | 016 | «si requiere presentacion fisica y no la hace (no consta entre los documentos ni en la matriz de compliance) la oferta no cumple se informa con texto… | decisión literal |
| **D-22** | 016 | «lo del pagare es ilegible se informa asi y ese si lo chequea la comision»; «con la aclaracion de que no pudo leer alguno». REQ-064: si el documento… | decisión literal |
| **D-23** | 016 | «Informa 'no se encontró documento' la comisión decide». «el que lo haga la comision no es opcion, asi el sistema no aporta nada. La comision… | decisión literal |
| **D-24** | 016 | Los cuatro resultados (cumple, no cumple, no se encontró el documento, no determinado) no cambian; los motivos de «no determinado» son… | decisión literal |
| **D-25** | 016 | «Mantengo la visión, siempre es preferible a no leída. Obviamente aclarando que proviene de un documento con dificultades de lectura y que conviene… | decisión literal |
| **D-26** | 016 | «Lo que presentó cada oferta»: por oferta, qué presentó frente a cada requisito de la matriz, con el fragmento de la oferta (la ficha de la oferta).… | decisión literal |
| **D-27** | 016 | «El sistema lo propone»: lee los archivos de la oferta y propone nombre y CUIT del oferente con su cita; la Comisión aprueba o corrige. «Escribe el… | decisión literal |
| **D-28** | 016 | Evaluación legible (A): el punto completo del pliego, las preguntas con su contexto, los requisitos externos aparte y qué se leyó y dónde (resumen de… | decisión literal |
| **D-29** | 016 | «La Comisión ve todo»: cada consulta de normativa queda con quién la hizo. La consulta responde con la cita de la norma y se abstiene cuando no la… | decisión literal |
| **D-30** | 016 | «REvisa tambien como se propmtea los modelos exhaustivamente»; «Siempre prefiriendo el uso local cuanto sea posible sin resignar calidad». Las… | decisión literal |
| **D-31** | 016 | Las «formas» que la medición de la 015 mostró y que quedan como definiciones del responsable, sin ejemplo: la presentación física (D-21), el… | decisión literal |
| **D-32** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: “Si . Solo queda garantía de mantenimiento de oferta la… | derivada, confirmada |
| **D-33** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-34** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-35** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-36** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-37** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-38** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-39** | 016 | REQ-104: «En la evaluación, el sistema razona antes de dar el veredicto, revisa todas las condiciones del requisito, cada una con su dato y su… | decisión literal |
| **D-40** | 016 | REQ-105: «Cada pregunta a la Comisión está dirigida a la Comisión (nunca al oferente) y dice qué requisito, qué conclusión y qué texto la motivan; no… | decisión literal |
| **D-41** | 016 | El modelo devuelve el resultado, la exigencia (documento o condición), las citas (documento y texto) y una explicación breve; la página y las… | decisión literal |
| **D-42** | 016 | «Si, de acuerdo. Preguntar mostrando las dos posturas con contradicciones a la comision»: cuando el valor de la oferta y el dato del Portal no… | decisión literal |
| **D-43** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-44** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-45** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo las nueve definiciones derivadas D-33 a D-38 y… | derivada, confirmada |
| **D-46** | 016 | REQ-008: «El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la… | decisión literal |
| **D-47** | 016 | REQ-009: «Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada». Enmienda del 2026-10-03… | decisión literal |
| **D-48** | 016 | REQ-018: «Cada cita debe mostrar la categoría de su documento. En una respuesta, las citas del régimen específico van primero; las del marco nacional… | decisión literal |
| **D-49** | 016 | REQ-039: «el sistema debe proponer los fragmentos de la oferta que responden al requisito, cada uno con el documento, la página y el texto literal».… | decisión literal |
| **D-50** | 016 | REQ-044: «Para la parte técnica, la ficha indica si la oferta trae documentación técnica y, cuando el pliego tiene renglones, si el oferente cotizó o… | decisión literal |
| **D-51** | 016 | ADR-0041, decisión 3: «Una página por pedido: transcribir literalmente el texto visible, sin corregir ni completar, con [ilegible] donde no se lee y… | decisión literal |
| **D-52** | 016 | REQ-074: «La Comisión sube el informe técnico aprobado del área (por procedimiento o por oferta). El sistema lo lee y propone, por oferta y renglón… | decisión literal |
| **D-53** | 016 | REQ-077: «Sin Portal, el procedimiento se da de alta subiendo el pliego: el sistema lee el archivo y propone los datos del procedimiento (número… | decisión literal |
| **D-54** | 016 | P3: «Si no hay fundamento recuperable, el resultado es "no determinado", nunca una afirmación.» «La decisión final es siempre de una persona y queda… | decisión literal |
| **D-55** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-55: en la visión, las líneas de puntos o… | derivada, confirmada |
| **D-56** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-56: el tipo de procedimiento propuesto es el… | derivada, confirmada |
| **D-57** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-57: cotizado con cuatro valores: sí, sin… | derivada, confirmada |
| **D-58** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-58: en el informe técnico, lo condicional, lo… | derivada, confirmada |
| **D-59** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-59: la síntesis de la ficha se apoya en un… | derivada, confirmada |
| **D-60** | 016 | Definición derivada (Coordinador, 2026-10-15), confirmada por el responsable el 2026-10-15: «Confirmo D-60: el nombre del oferente se toma solo de un… | derivada, confirmada |
| **D-61** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): un documento que el pliego exige está en la oferta… | derivada, pendiente de confirmación |
| **D-62** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): lo que afirma el texto de un modelo de declaración… | derivada, pendiente de confirmación |
| **D-63** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): la excepción que dice cuándo algo no se exige no… | derivada, pendiente de confirmación |
| **D-64** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): lo que el pliego le exige a quien no usa una… | derivada, pendiente de confirmación |
| **D-65** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): la conversión a la moneda en que se cotiza la… | derivada, pendiente de confirmación |
| **D-66** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): en un documento de identidad, una credencial o una… | derivada, pendiente de confirmación |
| **D-67** | 016 | Definición derivada (desarrollador, T-285, 2026-10-16, pendiente de confirmación del responsable): la pregunta a la Comisión compara solo valores de… | derivada, pendiente de confirmación |

## Hallazgos de verificación (146)

| Código | Feature | Qué es | Dónde |
|---|---|---|---|
| **D-049-1** | 001 | En una copia limpia, la orden de respaldo falla: backups/ no existe | T-049 |
| **D-049-2** | 001 | La falla 3 dice que el worker «no se detiene solo con la señal de parada» | T-049 |
| **D-049-3** | 001 | «Comprobar: docker compose ps (… migrate terminado con 0)» no muestra migrate: hace falta -a | T-049 |
| **D-233-1** | 015 | (media): la regla propone «cumple» sin comparar el valor que fija el pliego, salvo en la garantía | T-233 |
| **D-234-2** | 015 | (CE2; defecto menor): sentences.is_continuation toma la letra minúscula del rótulo de un inciso que va dentro del mismo tramo… | T-234 |
| **D-235-1** | 015 | (media): combine.addresses_offeror es una lista de patrones y no impide que una pregunta dirigida al oferente llegue a la Comisión | T-235 |
| **D-236-1** | 015 | (media): un ejemplo de la matriz reproduce una cláusula de cotización que está en los pliegos de los casos 00 y 01 | T-236 |
| **D-237-1** | 015 | (media-alta): los ejemplos de la evaluación y del contraste son del mismo rubro y de la misma cláusula que el caso-00, un caso de… | T-237 |
| **D-237-2** | 015 | (media-alta): una condición «cumple» sin dato y sin cita propia pasa como cumplida si hay una sola cita ubicada | T-237 |
| **D-240-1** | 015 | (media): H-1 queda corregido solo para el número de cláusula que lleva punto y mayúscula o va después de… | T-240 |
| **D-240-2** | 015 | (media): dos relajaciones de la regla del Portal dejan pasar un «cumple» sin respaldo (REQ-103: 0 «cumple» con un dato que no… | T-240 |
| **D-240-3** | 015 | (media-alta): evaluacion-v9 repite el escenario de la moneda y el IVA que la verificación de T-237 sacó de los ejemplos | T-240 |
| **D-249-1** | 015 |  | T-249 |
| **D-249-2** | 015 | (media, P7) · La ficha del caso-00 baja de 25 a 16 de 55 fragmentos esperados | T-249 |
| **D-257-1** | 015 | (alta) · Un documento obligatorio que el pliego pide en negativo se da por cumplido por ausencia | T-257 |
| **D-257-2** | 015 | (alta) · Un «cumple» que el contraste rechazó pasa a «cumple por ausencia», aunque su cita contradiga el requisito | T-257 |
| **D-257-3** | 015 | (media-alta) · Un texto dudoso no frena la ausencia ni el IVA | T-257 |
| **D-257-4** | 015 | (media) · Con una sola condición, la condición no se mira | T-257 |
| **D-257-5** | 015 | (media) · Datos que el Portal no trae, dichos con otras palabras | T-257 |
| **D-257-6** | 015 | (media) · «No aplica (opción no usada)» sin fundamento | T-257 |
| **D-257-7** | 015 | (media) · Presentación física: «no cumple» donde no corresponde | T-257 |
| **D-259-1** | 015 | La sugerencia «hoja de compliance» sale en documentos comunes de la oferta (media) | T-259 |
| **D-259-2** | 015 | Ningún test exige la clave en releer_pliego (baja; el código está bien) | T-259 |
| **D-260-1** | 015 | (bloquea) | T-260 |
| **D-260-2** | 015 | (alta para la medida, no del producto) · Las listas congeladas de los casos 03 y 04 no se pueden usar con la lectura del código… | T-260 |
| **D-263-1** | 015 | en el caso-01, de validación, la extracción v11 descarta como formulario la nota del Anexo VI que una circular suprime | T-263 |
| **D-264-1** | 015 | decidir si se arregla en T-264 o se acepta; si se arregla, la reverificación es liviana (las plantillas o las redirecciones de… | T-264 |
| **D-266-1** | 015 | , la garantía de cumplimiento de contrato (obligación del adjudicatario) entra como requisito en el caso-02 (5 filas firmes) y en… | T-266 |
| **D-266-2** | 015 | , en el caso-05 la cláusula de completar la oferta económica por el formulario del Portal entra como fila firme porque la misma… | T-266 |
| **D-269-1** | 007 | La prueba de la regla del firewall deja pasar puertos de más (REQ-116; menor) | T-269 |
| **D-269-2** | 007 | La comprobación de la suma del zip no tiene prueba (REQ-110; menor) | T-269 |
| **D-269-3** | 007 | crear-certificados.sh no tiene prueba automática (ADR-0062; media) | T-269 |
| **D-269-4** | 007 | Correr caddy.exe a mano, como indica «Si algo no anda», crea reglas automáticas del firewall que pueden anular la regla «EVALUON»… | T-269 |
| **D-270-1** | 016 | clon_app y clon_worker alcanzan por nombre a db, generation_batch y app de 8000 en evaluon_internal; entorno.md dice lo contrario… | T-270 (verificación, pasa con la… |
| **D-270-2** | 016 | Resuelto en la ventana real del 2026-10-15: nvidia-smi fallaba solo para el motor de 8000 arrancado antes del reinicio; con el… | T-270 |
| **D-270-3** | 016 | restaurar no tiene test de la condición --forzar | T-270 |
| **D-271-1** | 016 | La verdad tiene que nombrar los documentos sin carpeta si se cargaron con cargar_oferta (baja, condición para las tareas… | T-271 |
| **D-271-1 a D-271-4** | 016 | D-271-1: cargar_oferta guarda el nombre sin carpeta, así que la verdad nombra los documentos sin carpeta y únicos por oferta… | T-271 (verificación, pasa) |
| **D-271-2** | 016 | El «cumple por ausencia» no exige cubrir todos los documentos de la oferta (baja) | T-271 |
| **D-271-3** | 016 | Dos huecos de prueba (baja) | T-271 |
| **D-271-4** | 016 | armada_por no se exige ni se cuenta (baja) | T-271 |
| **D-278-1** | 016 | Ninguna prueba fija las 6 palabras (baja) | T-278 |
| **D-278-1, D-278-2, D-278-3** | 016 | Huecos de cobertura de las pruebas de instrucciones: nada fija las 6 palabras; no se detecta quitar el paso a minúsculas, leer… | T-278 (verificación, pasa) |
| **D-278-2** | 016 | Ninguna prueba cubre el lector del corpus ni la normalización a minúsculas (baja) | T-278 |
| **D-278-3** | 016 | Una sección sin filas no tiene prueba propia, y el informe no fija el conjunto de decisiones (baja) | T-278 |
| **D-283-1** | 016 | (alta, P1: decisión literal del 2026-10-12) · La presentación física (7.1) se descarta en la extracción v13 en los 4 casos | T-283 |
| **D-283-1 a D-283-9** | 016 | Matriz: la presentación física descartada como forma de presentar por el Portal (D-283-1), la condición de una opción descartada… | T-283 (medición del paso 2, ronda 1: no… |
| **D-283-2** | 016 | (alta) · La condición de informar el subcontratista junto con la oferta se descarta como condición opcional | T-283 |
| **D-283-3** | 016 | (media) · Sobrantes: cuerpos de las declaraciones de los Anexos, notas de tabla en fila aparte y la excepción de garantía | T-283 |
| **D-283-4** | 016 | (media) · M-045 del caso-02 (13.2, conversión a pesos de los renglones 3 a 47): tramo_con_requisitos_sin_este, no se pierde en… | T-283 |
| **D-283-5** | 016 | (alta, P3) · Contradicción con el dictamen y erradas nuevas | T-283 |
| **D-283-6** | 016 | (alta) · 9 celdas exactas dejan de serlo (cumple → no determinado): la conversión de la condición sin cita (O1 R22, R24; O2 R22)… | T-283 |
| **D-283-7** | 016 | (media) · Preguntas (REQ-120, escenario 3): 28 en forma, 16 conformes en contenido; piden resolver condiciones que el texto… | T-283 |
| **D-283-8** | 016 | (media) · Consulta con consulta-v5: el modelo se abstiene (model_abstained) donde con la v4 contestaba (EV-029, EV-018, EV-009)… | T-283 |
| **D-283-9** | 016 | (baja) · Visión vision-v5: el DNI omite la fecha de vencimiento (15/18); la constancia REPSAL ya no marca el escudo como ilegible | T-283 |
| **D-286-1** | 016 | (alta, P1: decisión literal del 2026-10-12) · La presentación física (7.1) no llega a firme en ningún caso | T-286 |
| **D-286-1 a D-286-8** | 016 | D-286-1 (alta): la presentación física queda como sugerencia (00, 02, 06) o descartada (01): lista presente a 1 de la referencia… | T-286 (medición del paso 2, ronda 2 y… |
| **D-286-2** | 016 | (media) · M-007 del caso-00 (7.5.1, domicilio físico especial) pasa de firme a sugerencia (no_coinciden) | T-286 |
| **D-286-3** | 016 | (media) · Siete celdas exactas en T-263 siguen en pregunta: tres por citas del modelo que no se ubican (O1 R22, O1 R24, O2 R22… | T-286 |
| **D-286-4** | 016 | (media, P3) · O1 R62: «cumple» (exacto) con una cita del Portal que no dice el plazo | T-286 |
| **D-286-5** | 016 | (media) · Consulta con consulta-v6: el modelo se abstiene (model_abstained) donde con la v4 contestaba (EV-010 y EV-012)… | T-286 |
| **D-286-6** | 016 | (baja) · Visión vision-v6: el DNI sigue sin la fecha de vencimiento (15/18) y el pagaré baja un dato (10/18: una palabra del… | T-286 |
| **D-286-7** | 016 | (baja) · Preguntas (REQ-120, escenario 3): 21 de 24 conformes; las 3 no conformes son R87 (lo que el pliego solo permite), igual… | T-286 |
| **D-286-8** | 016 | (baja) · REQ-031 del caso-06: 0 de 3 (M-004, M-005 y M-025 sin cambio ni marca; T-266 1 de 3; T-283 0 de 3); en el resumen sale… | T-286 |
| **H-241-1** | 015 | (medida, del Coordinador) | T-241 |
| **H-241-2** | 015 | (código) | T-241 |
| **H-241-3** | 015 | (código, deliberado) | T-241 |
| **H-241-4** | 015 | (modelo o código) | T-241 |
| **H-244-1** | 015 | (alta, código) | T-244 |
| **H-244-2** | 015 | (media, modelo) | T-244 |
| **H-244-3** | 015 | (media, P3) | T-244 |
| **H-244-4** | 015 | (baja, código) | T-244 |
| **H-244-5** | 015 | (baja, código) | T-244 |
| **H-244-6** | 015 | (media, medida, del Coordinador) | T-244 |
| **H-246-1** | 015 | (media, modelo) | T-246 |
| **H-246-2** | 015 | (media, modelo) | T-246 |
| **H-246-3** | 015 | (baja, modelo) | T-246 |
| **H-247-1** | 015 | generation.is_available lanza ante una respuesta que no es HTTP (defecto menor, código) | T-247 |
| **H-247-2** | 015 | El test no guarda los 2 s del chequeo (defecto menor, test) | T-247 |
| **H-247-3** | 015 | El «riesgo conocido» del ADR se cumple en 4 pruebas (riesgo del entorno, no bloquea) | T-247 |
| **H-247-4** | 015 | Dos pruebas de documentación se saltean en el comando estándar (defecto menor, infraestructura de pruebas) | T-247 |
| **H-248-1** | 015 | Los ejemplos de matriz-consecuencias-v2 no son inventados (gravedad media; criterio 1.3) | T-248 |
| **H-248-2** | 015 | reescritura-v2 conserva tres ejemplos con la redacción estándar de los pliegos (baja a media; criterio 1.3) | T-248 |
| **H-248-3** | 015 | matriz-respaldo-v2 deja el veredicto antes que su cita (baja; criterio 1.2) | T-248 |
| **H-248-4** | 015 | Tres frases del informe están desactualizadas o son inexactas (baja, documentación) | T-248 |
| **H-248-5** | 015 | El aviso de T-247 sobre el nombre del oferente no se atendió ni se anotó (media en la integración; fuera de los criterios de… | T-248 |
| **H-248-6** | 015 | tests/tenders/test_circular_changes.py::test_the_request_records_model_parameters_instructions_version_and_unit falla con el… | T-248 |
| **H-256-1** | 015 | (menor): la regla de las 3 citas del Portal no tiene test, y depende de un archivo que no escribe el repositorio | T-256-ver |
| **H-256-2** | 015 | (menor): --recalcular pide usuario y clave, y por eso usa la base | T-256-ver |
| **H-256-3** | 015 | (menor, texto): el resumen dice que todas las filas excluidas son «agregadas solo para la medida» | T-256-ver |
| **H-256-4** | 015 | (menor, antes de T-260): la exclusión de pares y de preguntas en la medición en vivo no tiene test | T-256-ver |
| **H-258-1** | 015 | Cinco ejemplos nuevos copian la forma, oración por oración, de cláusulas de la plantilla que se miden en los siete casos… | T-258 |
| **H-258-2** | 015 | Al unir una fila de toda oferta con una fila de una opción, la fila que queda se marca como de la opción | T-258 |
| **H-277-1** | 016 | --recalcular no dice que no calcula las tres salidas (baja) | T-277 |
| **H-277-1 a H-277-5** | 016 | H-277-1: --recalcular de corridas viejas no calcula las tres salidas ni lo dice. H-277-2: cuatro alteraciones sin test (pregunta… | T-277 (verificación, pasa sobre… |
| **H-277-2** | 016 | Cuatro huecos de prueba (baja) | T-277 |
| **H-277-3** | 016 | «No aplica» se guarda como «cumple» con aplica falso (baja, informativa) | T-277 |
| **H-277-4** | 016 | Cada «no determinado» abre una pregunta (efecto, no falla) | T-277 |
| **H-277-5** | 016 | Aserción negativa residual (baja) | T-277 |
| **H-279-1** | 016 | Una regla nacida de un fallo medido en casos, citada a una decisión que no la dice (media) | T-279 |
| **H-279-1 a H-279-7** | 016 | H-279-1 (media): la cláusula de la garantía de cumplimiento de contrato en el bloque v9 no la sostiene D-01 literal (definición… | T-279 (verificación, pasa) |
| **H-279-2** | 016 | La oración de la duda no se puede ejecutar en tres de las instrucciones que leen el bloque (media) | T-279 |
| **H-279-3** | 016 | Cuatro grupos de oraciones que la D-NN citada no sostiene (baja) | T-279 |
| **H-279-4** | 016 | Tres bordes de «ejemplo» (baja) | T-279 |
| **H-279-5** | 016 | Siete alteraciones sin detectar: huecos de cobertura (baja) | T-279 |
| **H-279-6** | 016 | La oración de la clase de la sección repite al código (baja) | T-279 |
| **H-279-7** | 016 | Una prueba de test_definitions.py pasa a mirar archivos congelados (baja, aviso para T-280) | T-279 |
| **H-280-1** | 016 | Dos reglas de contenido sin decisión literal, nacidas de mediciones de la 015 y no marcadas como derivadas (media) | T-280 |
| **H-280-1 a H-280-6** | 016 | H-280-1 (media): dos reglas sin decisión literal nacidas de mediciones de la 015 (alcance por la ruta; «no elegís una ajena… | T-280 (verificación, pasa) |
| **H-280-2** | 016 | Citas que no sostienen o que omiten la fuente (baja) | T-280 |
| **H-280-3** | 016 | La oración de la duda sigue en lo que leen la extracción, la completitud y la unión (baja, aviso para T-283) | T-280 |
| **H-280-4** | 016 | Cuatro alteraciones sin detectar y una prueba que ya no puede fallar (baja) | T-280 |
| **H-280-5** | 016 | Las circulares v8 y los cambios v7 no recogen toda la D-01 (baja) | T-280 |
| **H-280-6** | 016 | Una regla de la v9 que la v10 ya no tiene y ninguna decisión literal respalda (baja, aviso para T-283) | T-280 |
| **H-281-1** | 016 | Una regla de contenido sin decisión que la sostenga, y lecturas propias sin rótulo de derivada (media) | T-281 |
| **H-281-1 a H-281-4** | 016 | H-281-1 (media): «con otras palabras equivalentes, alcanza» (contraste) citaba D-08 que no la sostiene; con la regla de… | T-281 (verificación, pasa con reparos) |
| **H-281-2** | 016 | Lo externo: la instrucción nombra tres tipos y el REQ-063 nombra cuatro, y una frase no tiene decisión (baja, aviso para T-283) | T-281 |
| **H-281-3** | 016 | La prueba del tope del razonamiento admite 100 caracteres de deriva (baja) | T-281 |
| **H-281-4** | 016 | Nada ata las marcas «pendiente» y «confirmada» de las derivadas (baja) | T-281 |
| **H-282-1** | 016 | Reglas de contenido sin decisión que las sostenga y sin rótulo de derivada (media) | T-282 |
| **H-282-1 a H-282-3** | 016 | H-282-1 (media, resuelto en 3179f0b4): seis reglas de contenido sin decisión literal pasan a derivadas D-55 a D-60 pendientes de… | T-282 (verificación, pasa con reparos) |
| **H-282-2** | 016 | Las dos líneas de registro de la consulta se cubren una a la otra (baja) | T-282 |
| **H-282-3** | 016 | La forma del registro no es la misma en los siete (baja) | T-282 |
| **H-285-1** | 016 | (alta, P3/REQ-120) | T-285 |
| **H-285-1 a H-285-7, O-285-7, O-285-8** | 016 | Corregidos: «no aplica» solo desde la opcion de la fila (H-285-1), causas reales de las citas no ubicadas y repetidas (H-285-2)… | T-285 (verificación: no pasa… |
| **H-285-2** | 016 | (media) | T-285 |
| **H-285-3** | 016 | (media, P3) | T-285 |
| **H-285-4** | 016 | (baja) | T-285 |
| **H-285-5** | 016 | Pregunta contradictoria cuando no hay texto señalado (baja) | T-285 |
| **H-285-6** | 016 | Reglas nuevas sin decisión ni fila de derivada (baja) | T-285 |
| **H-285-7** | 016 | Huecos de prueba (baja) | T-285 |
| **H-289-1** | 016 | el anfitrión fijo no tiene prueba que lo defienda de verdad | T-289 |
| **H-289-1, H-289-2, O-289-1 a O-289-6** | 016 | H-289-1 y 2 (huecos de pruebas del anfitrión fijo y de la clave) y O-289-1 a 3 (tapar la clave en errores, cancelar el lote ante… | T-289 (verificación: no pasa por… |
| **H-289-2** | 016 | nada impide imprimir ni registrar la clave | T-289 |
| **H-290-1** | 016 | la comprobación por huellas compara cada mensaje por separado, no el pedido armado | T-290 |
| **H-290-1 a H-290-6, O-290-1 a O-290-10** | 016 | Fugas corregidas: huellas por mensaje, caracteres invisibles, sugerencia de compliance pendiente (enmienda del ADR-0067), ocho… | T-290 (verificación: dos rondas de… |
| **H-290-2** | 016 | las secuencias se parten con caracteres invisibles | T-290 |
| **H-290-3** | 016 | un informe de consultas sin confirmar como hoja sale | T-290 |
| **H-290-4** | 016 | alteraciones de controles reales que ninguna prueba detecta (ver «Alteraciones»): el sello no cubre ningún campo salvo system… | T-290 |
| **H-290-5** | 016 | un error de precios aparece después de pagar | T-290 |
| **H-290-6** | 016 | caracteres invisibles o guion bajo como separador entre palabras | T-290 |
| **H-291-1** | 016 | cinco alteraciones de controles reales que ninguna prueba del desarrollador detecta | T-291 |
| **H-291-1, O-291-1 a O-291-13** | 016 | H-291-1 (cinco controles sin prueba) corregido; el freno de etapa conserva las respuestas pagadas si llega tras el último pedido… | T-291 (verificación: no pasa por… |
| **H-299-1** | 016 | (código, medición) | T-299 |
| **H-299-1, H-299-2, O-299-1 a O-299-9** | 016 | Corregidos: la segunda pasada de --verificador-sobre mide la pregunta de la celda cambiada (H-299-1), 17 controles con prueba… | T-299 (verificación: no pasa… |
| **H-299-2** | 016 | (pruebas) | T-299 |

## Observaciones de verificación (241)

| Código | Feature | Qué es | Dónde |
|---|---|---|---|
| **O-049-1** | 001 | La falla 2 no se repitió | T-049 |
| **O-049-2** | 001 | La falla 3 del motor no se repitió | T-049 |
| **O-049-3** | 001 | El paso 9 no se puede seguir solo con la sección T-049 | T-049 |
| **O-049-4** | 001 | Las fallas están numeradas 1, 2, 3, 4, 5, 7 y 6 | T-049 |
| **O-049-5** | 001 | Con las dos copias en el mismo commit, igual cambia la imagen | T-049 |
| **O-049-6** | 001 | Para el Coordinador: «seis servicios» en tasks.md | T-049 |
| **O-049-7** | 001 | Para quien pruebe por HTTP desde Git Bash: la pregunta llega con caracteres reemplazados | T-049 |
| **O-049-8** | 001 | Para quien arme el runbook: el paso 9 remite a una orden con el proyecto de 8000 | T-049 |
| **O-234-1** | 015 | (CE1, CE3; observación): la unión se decide por la palabra con que empieza la oración («Deberá», «La misma», «El mismo»… | T-234 |
| **O-234-3** | 015 | (media): la corrección se aparta de la spec y del ADR-0054 sin enmendarlos | anexo-correcciones-T-233-T-235-T-234 |
| **O-234-4** | 015 | (baja): «Este» y «Dicho» unen oraciones de otro asunto (ver las sondas) | anexo-correcciones-T-233-T-235-T-234 |
| **O-235-2** | 015 | (media-baja): la corrección amplía la lista, que era lo que el registro pedía como mínimo, pero la defensa sigue siendo una… | anexo-correcciones-T-233-T-235-T-234 |
| **O-236-1** | 015 | (media): la regla de la opción dice «entra solo como condición de esa opción» y nada dice cómo se registra | T-236 |
| **O-236-2** | 015 | (baja): el bloque amplía las decisiones literales | T-236 |
| **O-237-1** | 015 | (media): CONDITIONS_MAX = 6 y «no dejes ninguna afuera» | T-237 |
| **O-237-2** | 015 | (baja): contradicción interna en clausulas-v3 | T-237 |
| **O-237-3** | 015 | (baja): el escenario del IVA aparece en cinco instrucciones (extracción, filtro, evaluación y contraste, más la pregunta de… | T-237 |
| **O-240-1** | 015 | (media): dos caminos para «no aplica» | T-240 |
| **O-240-2** | 015 | (media, P3): requisito de referencia, negativo y mantenimiento | T-240 |
| **O-240-3** | 015 | (baja): is_technical_annex decide por el nombre | T-240 |
| **O-240-4** | 015 | (baja): la medida de coincidencia cuenta «No aplica» como «cumple» | T-240 |
| **O-240-5** | 015 | (baja): la leyenda de íconos de la propuesta (s4_propuesta.html) no incluye el ícono «No aplica»; solo se ve por su nombre al… | T-240 |
| **O-240-6** | 015 | (baja): el registro de una decisión de la Comisión guarda outcome_before = «cumple» para un par «No aplica» (el valor guardado)… | T-240 |
| **O-240-7** | 015 | (baja, P4): los tests nuevos copian texto de los pliegos | T-240 |
| **O-247-1** | 015 | Imprecisiones del ADR (no cambian ninguna conclusión) | T-247 |
| **O-247-2** | 015 | «Apagada cuando corre una evaluación» contra «apagada mientras el 27B esté en el motor de lotes» | T-247 |
| **O-247-3** | 015 | P6 del alta desde el pliego: el motor y la huella no se nombran | T-247 |
| **O-247-4** | 015 | Las variables del .env también llegan a comandos con -f | T-247 |
| **O-248-1** | 015 | Ejemplo y regla del alcance en matriz-consecuencias-v2 (baja) | T-248 |
| **O-248-2** | 015 | Riesgos de vision-v4 que T-249 no cubre como está escrita su fila (baja, sin GPU) | T-248 |
| **O-248-3** | 015 | La consulta no guarda la huella de su instrucción (baja) | T-248 |
| **O-248-4** | 015 | Regla de «no» por tabla en ficha-renglon-v5 (baja, heredada) | T-248 |
| **O-248-5** | 015 | Parecido de tipo de requisito con los casos (baja) | T-248 |
| **O-248-6** | 015 | Textos del mensaje del usuario sin versión ni huella (baja) | T-248 |
| **O-248-7** | 015 | Informe técnico: la cita es una «frase corta» (baja) | T-248 |
| **O-248-8** | 015 | Los fallos de la generalidad muestran también el texto compartido (baja) | T-248 |
| **O-249-1** | 015 | (P3) · El 27B lee mal lo manuscrito difícil sin marcarlo ilegible (pagaré: 7 u 8 de 18 datos; DNI: el dígito verificador del… | T-249 |
| **O-249-2** | 015 | Líneas duplicadas en la unión de dos franjas | T-249 |
| **O-249-3** | 015 | La ficha del caso chico muestra 2 fragmentos sin pareja (la última medición registrada, 0) | T-249 |
| **O-249-4** | 015 | La propuesta del procedimiento no le pregunta nada al 27B en el caso-00 : las reglas hallan tipo y objeto, y el modelo no se pide… | T-249 |
| **O-253-1** | 015 | (baja, P6): la rama de falla del servicio no tiene test con el paso encendido | T-253 |
| **O-253-2** | 015 | (informativa): el contraste incluye el pedido de cláusulas | T-253 |
| **O-253-3** | 015 | (informativa): la parte con el servidor real no se verificó aquí | T-253 |
| **O-254-1** | 015 | (media, generalidad): un ejemplo del filtro v6 calca la forma de la cláusula medida | T-254 |
| **O-254-2** | 015 | (baja, riesgo sin medir): la cláusula de la norma transcripta puede chocar con una lista de excluidos en el cuerpo del pliego | T-254 |
| **O-254-3** | 015 | (cosmética): el filtro v6 dice «Tres cuidados» y lista cuatro (la v5 ya decía «Dos» con tres) | T-254 |
| **O-254-4** | 015 | (informativa): el tiempo de carga de 4,5 minutos de T-254 no consta en ningún documento del repositorio ni en el detalle de la… | T-254 |
| **O-255-1** | 015 | El criterio de tiempo previsto para T-266 no puede cumplirse con el 27B (decisión, no defecto) | T-255 |
| **O-255-10** | 015 | Seleccionar rutas de pruebas intercaladas da errores que no son de la tarea | T-255 |
| **O-255-2** | 015 | GENERATION_CTX_SIZE de 32.768 en app llega a los comandos de medición que se corran en app | T-255 |
| **O-255-3** | 015 | El informe técnico encadenado no cuenta como ocupado (documentado) | T-255 |
| **O-255-4** | 015 | Un pedido running huérfano mantiene el aviso de ocupada | T-255 |
| **O-255-5** | 015 | Las pantallas no distinguen el trabajo | T-255 |
| **O-255-6** | 015 | La combinación de COMPOSE_FILE de la sección nueva no se compara con .env.example (M27) | T-255 |
| **O-255-7** | 015 | La espera del pedido de la Consulta no está fijada en el punto de llamada por las pruebas de la tarea (M29) | T-255 |
| **O-255-8** | 015 | Textos que quedan atrás | T-255 |
| **O-255-9** | 015 | P7 y .env.example | T-255 |
| **O-256-1** | 015 | V1 no pasa hoy el P3 bloqueante del propio ADR: tiene 3 «no se encontró el documento» donde la Comisión dijo «no aplica» (O1 R80… | T-256-ver |
| **O-256-2** | 015 | No dice qué pasa con los umbrales del plan 015 (conservadas ≥ 70 %, lista presente ≥ 95 %, Portal 100 %, «no determinado» ≤ 15 %… | T-256-ver |
| **O-256-3** | 015 | «Exactas con fundamento» es la medida principal, pero no dice quién lee muestra-exactas.md ni cuándo | T-256-ver |
| **O-256-4** | 015 | Sigue escrito «con 51 celdas» | T-256-ver |
| **O-256-5** | 015 | La corrida alterada dice «por ejemplo» (orden invertido, semilla 43, group_tokens +5 %) | T-256-ver |
| **O-256-6** | 015 | La constitución 1.4 (ADR-0058) acepta como fundamento la ausencia verificada en la lectura completa de la oferta | T-256-ver |
| **O-256-7** | 015 | Los casos 03, 04 y 05 quedan «congelados con huella y fecha» desde la aprobación, pero el ADR no da esas huellas | T-256-ver |
| **O-256-8** | 015 | (observación, hoy sin efecto en las cifras): D8 acepta cualquier cita del Portal, también en un «cumple» que concluyó el modelo | T-256-ver |
| **O-257-1** | 015 | El desvío de la marca «Requiere presentar» está escrito solo en el código | T-257 |
| **O-257-2** | 015 | La presentación física no queda en facts.criterios | T-257 |
| **O-257-3** | 015 | GPU, O3 R22 | T-257 |
| **O-257-4** | 015 | Criba | T-257 |
| **O-257-5** | 015 | La opción «otra» de T-258 (su matriz-extraccion-v10 la admite) da la explicación «la opción «otra»» | T-257 |
| **O-257-6** | 015 | (baja) · Si no hay títulos de documentos, la nota de ausencia queda «… (todos los documentos de la oferta)» | T-257 |
| **O-258-1** | 015 | La traza de las fallas de la unión no tiene prueba (baja) | T-258 |
| **O-258-2** | 015 | El derecho posterior en la extracción (baja) | T-258 |
| **O-258-3** | 015 | El informe citado no está (baja) | T-258 |
| **O-258-4** | 015 | Lo que hay entre dos filas unidas (baja) | T-258 |
| **O-258-5** | 015 | El resto de los pasos todavía ve los caracteres de área privada (baja, fuera de la fila) | T-258 |
| **O-258-6** | 015 | Dos reglas que se pueden leer en contra (baja, nueva) | T-258 |
| **O-259-1** | 015 | El umbral del 10 % no tiene escrita su razón en la rama | T-259 |
| **O-259-2** | 015 | not_downloaded deja de listar el faltante solo si se sube un documento con el mismo título que da el Portal (sin distinguir… | T-259 |
| **O-259-3** | 015 | La sugerencia «copia» (90 % de grupos de tres palabras en común) puede salir en dos formularios con la misma plantilla y pocos… | T-259 |
| **O-260-1** | 015 | Opción mal marcada en la matriz nueva | T-260 |
| **O-260-2** | 015 | Una explicación que la cita no sostiene | T-260 |
| **O-260-3** | 015 | El recálculo sin el modelo no reproduce la medida en vivo con reglas-v12 | T-260 |
| **O-260-4** | 015 | Listas y exclusiones incoherentes en el caso-03 | T-260 |
| **O-262-1** | 015 | (baja) · Una forma de descarte que enseña un ejemplo y no está en la tabla | T-262 |
| **O-262-2** | 015 | (media para la medida) · La pregunta B y los vecinos del lote | T-262 |
| **O-262-3** | 015 | (anterior a T-262) · 6.6.3 del caso-02 | T-262 |
| **O-262-4** | 015 | (baja, diseño) · La re-anclada declara la huella de su original | T-262 |
| **O-263-1** | 015 | La corrida alterada no corre bordes de grupo en el caso-00 | T-263 |
| **O-263-2** | 015 | La medición no prueba la visión del 27B | T-263 |
| **O-263-3** | 015 | En el caso-05 (prueba) sale la conversión a pesos de la moneda de cotización | T-263 |
| **O-264-1** | 015 | (media · pruebas): cinco alteraciones del commit final no las detecta ningún test, y una más del lote anterior: F-C4… | T-264 |
| **O-264-10** | 015 | (baja · pruebas): la alteración R-X10 (portal_sources.cited_pages sin quitar las páginas repetidas) no la detecta ningún test: en… | T-264 |
| **O-264-2** | 015 | (baja · rendimiento previo): «ninguna pantalla consulta de a una fila» no vale literalmente para la ficha de la pestaña Ofertas… | T-264 |
| **O-264-3** | 015 | (baja): la nota de la planilla y del cuadro no dice documento ni página ni trae enlace (el archivo no conoce la dirección de la… | T-264 |
| **O-264-4** | 015 | (media · fuera del alcance de T-264): la planilla y el cuadro siguen mostrando el dato del Portal («fuente: Portal», «Total del… | T-264 |
| **O-264-5** | 015 | (baja · previa): para el usuario de lectura (sin rol), la pestaña muestra el aviso y «Ver la imagen de la página», pero el… | T-264 |
| **O-264-6** | 015 | (aviso de despliegue): el CSS nuevo (secciones.css, s4_propuesta.css) llega al navegador solo si se recogen los estáticos; la… | T-264 |
| **O-264-7** | 015 | (baja): el requisito 47 de la oferta 1 cita 6 veces el mismo dato del Portal y la celda repite 6 veces la misma línea de fuente | T-264 |
| **O-264-8** | 015 | (baja): tasks.md, sección «### T-264», sigue con el alcance anterior (tres pantallas, «comparar con el original», visión que… | T-264 |
| **O-264-9** | 015 | (baja): la línea de fuente bajo el orden económico toma la página del ítem de los datos de la oferta (PortalOfferData.item); las… | T-264 |
| **O-265-1** | 015 | (para la medición): la salvedad de la moneda quedó informada por una observación de un caso de prueba | T-265 |
| **O-265-2** | 015 | (media para la medida): en el caso-02, de validación, entra como fila firme una segunda conversión a pesos que la lista no tiene | T-265 |
| **O-265-3** | 015 | (baja) · pre/p-67 del caso-01 pasa de sugerencia a firme por el lote | T-265 |
| **O-265-4** | 015 | (baja) · Clase de las filas de la nota | T-265 |
| **O-265-5** | 015 | (baja, P3) · Descartes que cambian de motivo sin cambiar de destino: 5 tramos | T-265 |
| **O-265-6** | 015 | (baja, pruebas) · La generalidad automática de la matriz no mira el cuerpo de los pliegos | T-265 |
| **O-265-7** | 015 | (baja, P6) · El pedido guardado no conserva el orden de las propiedades del esquema | T-265 |
| **O-266-1** | 015 | El texto de cada caso está en el detalle local (normativa pública) | T-266 |
| **O-266-2** | 015 | (para el responsable) · Las evals no miden la abstención del 27B | T-266 |
| **O-266-3** | 015 | Presentación física en el caso-03 (prueba) | T-266 |
| **O-266-4** | 015 | Sugerencias nuevas en el caso-01 (2 en 15.5, ninguna esperada) y filas sin pareja nuevas en el Anexo VI del caso-04 (p-4 y p-7)… | T-266 |
| **O-268-1** | 015 | Lo que separa la medición | T-268 |
| **O-268-2** | 015 | La garantía de cumplimiento entra como requisito también con el 12B (caso-02: 20.2 a 20.4; caso-00: 20.2 y 20.3): D-266-1 es de… | T-268 |
| **O-268-3** | 015 | Un «no cumple» por la regla de la presentación física con el 12B (O1 R41, sin decisión de la Comisión): la regla depende de que… | T-268 |
| **O-268-4** | 015 | Tiempo y memoria | T-268 |
| **O-269-1** | 007 | Un pedido con otro Host recibe un 200 vacío, también desde una computadora fuera de la lista | T-269 |
| **O-269-2** | 007 | HTTP/3 | T-269 |
| **O-269-3** | 007 | curl.exe -sI no muestra Content-Length: 0 | T-269 |
| **O-269-4** | 007 | Orden de los pasos | T-269 |
| **O-269-5** | 007 | El certificado del servidor empieza a valer en el momento de crearse | T-269 |
| **O-269-6** | 007 | Efectos de esta verificación en el equipo, para que quien administre los conozca | T-269 |
| **O-269-7** | 007 | El script quita toda regla Block de su caddy.exe, de entrada o de salida | T-269 |
| **O-269-8** | 007 | plan.md («Criterio de aceptación numérico y umbrales», páginas sin cifrar) y tasks.md (T-269, segunda parte; T-272, punto 2)… | T-269 |
| **O-270-1** | 016 | subir arranca clon_worker aunque la base traiga pedidos en cola | T-270 |
| **O-270-2** | 016 | Rutas de este equipo en entorno.md (7 apariciones de C:/Users/… o /c/Users/…, como ejemplo) y el test que las exige… | T-270 |
| **O-270-3** | 016 | Si 8000 no vuelve sano en reabrir_8000 , esperar_sano devuelve error y set -e sale antes de arrancar el worker | T-270 |
| **O-270-4** | 016 | restart: unless-stopped de 8000 | T-270 |
| **O-270-5** | 016 | Cada restaurar deja un respaldo de 146 MB en respaldos-clon/ (datos de casos, fuera del repositorio) | T-270 |
| **O-270-6** | 016 | evals/ se monta con escritura desde CLON_CODE_DIR : una corrida del clon con la copia de trabajo de 016-integracion escribe… | T-270 |
| **O-270-7** | 016 | No pude confirmar que el 27B use la GPU : con nvidia-smi en 0 (D-270-2) no hay medida directa; el motor responde y la medición de… | T-270 |
| **O-271-1** | 016 | El umbral 4 del plan no nombra la ausencia | T-271 |
| **O-271-2** | 016 | El mensaje de un nombre ambiguo no lo dice | T-271 |
| **O-271-3** | 016 | El congelado cubre el resultado, no el fundamento | T-271 |
| **O-271-4** | 016 | Un «no se encontró el documento» solo exige nota | T-271 |
| **O-271-5** | 016 | --recalcular con una verdad por requisito se rechaza con un mensaje que lo explica (no hay matriz para traducir M-NNN a fila) | T-271 |
| **O-271-6** | 016 | Tiempo de las pruebas | T-271 |
| **O-277-1** | 016 | cell_problem acepta un «no determinado» por informe pendiente o por página ilegible si la explicación contiene «informe» o… | T-277 |
| **O-277-2** | 016 | three_outputs da por preguntado un par con cualquier pregunta abierta anterior (open_pairs); es la regla de _save_pair, y la… | T-277 |
| **O-277-3** | 016 | La salvedad del punto 1 es de cobertura, no de falla: ver mi enumeración ampliada | T-277 |
| **O-278-1** | 016 | D-28 y D-31 no son literales | T-278 |
| **O-278-2** | 016 | Nombres de T-280 | T-278 |
| **O-278-3** | 016 | La oración inventada de las pruebas coincide con lenguaje normativo | T-278 |
| **O-278-4** | 016 | Límite de la cobertura del corpus | T-278 |
| **O-278-5** | 016 | La tabla SIMPLIFIED repite la versión del bloque de definiciones | T-278 |
| **O-279-1** | 016 | Las cifras del desarrollador (68 y 6.191; 45 y 4.495; 47 y 4.739; 32 y 3.463) son exactas | T-279 |
| **O-279-2** | 016 | Con el corpus en el equipo, las 904 piezas de corpus/casos/caso-0N incluyen imágenes y PDF escaneados sin capa de texto: el… | T-279 |
| **O-279-3** | 016 | El bloque cita «Requiere presentar» y la extracción lleva 12 motivos y 6 opciones por nombre: si el código cambia una… | T-279 |
| **O-279-4** | 016 | No evalué la calidad de la matriz que producen estas instrucciones; es de T-283 | T-279 |
| **O-280-1** | 016 | El nombre matriz-circulares-cambios-v7 es nuevo: hasta la v6 los cambios compartían el nombre matriz-circulares- | T-280 |
| **O-280-2** | 016 | El bloque tiene 3.463 caracteres con el salto final y 3.462 como lo inserta el cargador (strip); T-279 informó 3.463 | T-280 |
| **O-280-3** | 016 | Varias filas de la tabla del filtro y de las circulares cita D-30 para describir qué trae el mensaje (formato de entrada que arma… | T-280 |
| **O-280-4** | 016 | No evalué la calidad de la matriz que producen estas instrucciones; es de T-283 | T-280 |
| **O-280-5** | 016 | Con el corpus en el equipo, las piezas de los casos incluyen imágenes y PDF escaneados sin capa de texto (62 de 74 archivos de… | T-280 |
| **O-281-1** | 016 | D-32 y D-42 citan decisiones de la spec 016 del 2026-10-15 («Garantía de cumplimiento de contrato» y «Falta de coincidencia con… | T-281 |
| **O-281-2** | 016 | Los comentarios de evaluon/assessment/options.py y de prompting.py siguen diciendo evaluacion-v12 para describir el campo… | T-281 |
| **O-281-3** | 016 | Los archivos de la tarea en tasks.md no listan los tests que el cambio de versión obliga a adaptar (test_comite_t257.py… | T-281 |
| **O-281-4** | 016 | La tabla D-21 (presentación física) dice «Aplica a: evaluación», pero la instrucción de la evaluación no la nombra (tampoco la… | T-281 |
| **O-281-5** | 016 | No evalué la calidad de las evaluaciones que producen estas instrucciones; es de T-283 | T-281 |
| **O-282-1** | 016 | El esqueleto con <<FIN>> y «texto plano, sin JSON» (n.º 11) y los esqueletos de las otras seis citan D-30 y no una decisión del… | T-282 |
| **O-282-2** | 016 | La cita de REQ-018 en D-48 corta antes de «, identificados como tales y después del articulado»; la oración 46 («Los… | T-282 |
| **O-282-3** | 016 | consulta-v1 queda fuera de las pruebas de ejemplos, de tabla y de no calco | T-282 |
| **O-282-4** | 016 | pytest -m decision_literal dio 246 (T-281 informó 245) | T-282 |
| **O-282-5** | 016 | No evalué la calidad de lo que producen estas instrucciones; es de T-283 | T-282 |
| **O-283-1** | 016 | La lista de fichas del caso-00 sigue sin poder usarse con medir_fichas (12 anclas, D-249-1): se midió con el arnés | T-283 |
| **O-283-2** | 016 | O2 R29 (la explicación dice «exactamente» ante una diferencia de un centavo entre el Portal y lo exigido) y O3 R62 (cita que no… | T-283 |
| **O-283-3** | 016 | Las formas que antes enseñaban los ejemplos (mantenimiento con prórroga, nota de la DJ de intereses, garantía en dos filas… | T-283 |
| **O-283-4** | 016 | Sigue O-260-1 (la fila 17.3.1 con opcion = oferta_alternativa) y O-249-2 (líneas duplicadas en la unión de franjas de la visión) | T-283 |
| **O-285-1** | 016 | La unión queda en 4.995 de 5.000 caracteres (47 de 50 líneas): cualquier palabra más al bloque rompe matriz-union-v2 | T-285 |
| **O-285-2** | 016 | condicion_citada_por_su_dato relaja D-237-2: el dato de una condición «cumple» puede ser cualquier trozo de 2 o más palabras de… | T-285 |
| **O-285-3** | 016 | T-284 no corrió (la verdad del caso de ajuste está bloqueada): T-285 solo corrige los hallazgos de T-283 | T-285 |
| **O-285-4** | 016 | O1 R32 queda «no determinado» por el contraste (parcial), no por el Portal: T-286 no debe esperar que vuelva a «cumple» | T-285 |
| **O-285-5** | 016 | Reglas redactadas en general pero cuyo alcance lo dicta un caso (no son calco): la excepción, la conversión de moneda, la regla… | T-285 |
| **O-285-6** | 016 | La consulta v6 puede volver a contestar donde la v5 se abstenía; el efecto en la abstención (6/6 de las evals) y en los avisos de… | T-285 |
| **O-285-7** | 016 | marked_rule reemplaza la pregunta y la explicación de una fila general que ya traía una pregunta propia (por ejemplo, la que… | T-285 |
| **O-285-8** | 016 | En evaluon_clon_e las citas de las tres celdas que H-285-2 señalaba se comprobaron con el código nuevo (locate_text sobre el… | T-285 |
| **O-285-9** | 016 | Huecos de prueba bajos: R5 (la lista de negaciones de contenido no tiene un caso mixto como «no consta, pero la oferta limita el… | T-285 |
| **O-286-1** | 016 | La primera apertura de la ventana falló (10:49:07 a 10:55:55): al arrancar el motor del clon, nvidia-container-cli: ldcache… | T-286 |
| **O-286-2** | 016 | La propuesta del oferente (nombre) de las auxiliares no se midió (ver «Auxiliares») | T-286 |
| **O-286-3** | 016 | La salida de correr_evals dice «corrida anterior: ninguna» si la carpeta de corridas es nueva; la comparación con T-266 y T-283… | T-286 |
| **O-286-4** | 016 | scripts/clon.sh ejecutar sigue sin admitir entrada estándar (falta -T en docker compose run); las mediciones con clave por… | T-286 |
| **O-286-5** | 016 | La marca mipyme de la fila 80 es lo que da «no aplica» exacto en O1 R80 y O3 R80; en O2 R80 el modelo no marca que la oferta no… | T-286 |
| **O-286-6** | 016 | No se corrió la evaluación del caso de ajuste con verdad (T-284 no corrió: la verdad está bloqueada) ni la propuesta del… | T-286 |
| **O-287-1** | 016 | 8000 no se actualiza con esta integración | T-287 |
| **O-287-2** | 016 | Suite del Coordinador | T-287 |
| **O-287-3** | 016 | D-61 a D-67 (definiciones derivadas de T-285) fueron confirmadas por el responsable el 2026-10-16 y están en la tabla de la spec… | T-287 |
| **O-288-1** | 016 | pensamiento de la matriz | T-288 |
| **O-288-1 a O-288-5** | 016 | O-288-1: pensamiento de la matriz adaptive, a confirmar con la medición. O-288-2: se aceptan tope negativo, NaN e intervalo 0… | T-288 (verificación, pasa) |
| **O-288-2** | 016 | números sin cotas | T-288 |
| **O-288-3** | 016 | etapa en externo con el uso apagado | T-288 |
| **O-288-4** | 016 | portal_worker | T-288 |
| **O-288-5** | 016 | versión de la tabla de precios | T-288 |
| **O-289-1** | 016 | un proveedor que repite la clave en un error | T-289 |
| **O-289-2** | 016 | un sondeo que falla deja el lote corriendo | T-289 |
| **O-289-3** | 016 | Retry-After sin cota | T-289 |
| **O-289-4** | 016 | dataclasses.replace y copy.copy saltean la puerta | T-289 |
| **O-289-5** | 016 | constantes que las pruebas leen en lugar de fijar | T-289 |
| **O-289-6** | 016 | menores | T-289 |
| **O-290-1** | 016 | dictamen bloqueado | T-290 |
| **O-290-10** | 016 | invisibles dentro de las palabras y como único separador en el mismo párrafo (W4) | T-290 |
| **O-290-2** | 016 | límites del cotejo exacto, por diseño del ADR | T-290 |
| **O-290-3** | 016 | el origen lo declara quien llama | T-290 |
| **O-290-4** | 016 | --verificar-filtro por omisión mira el mes en curso | T-290 |
| **O-290-5** | 016 | la puerta compara con las hojas del procedimiento del pedido; el comando, con todas las de la base | T-290 |
| **O-290-6** | 016 | un lote en vuelo no queda registrado hasta que termina | T-290 |
| **O-290-7** | 016 | el libro solo ve su base | T-290 |
| **O-290-8** | 016 | el costo se guarda como número de coma flotante | T-290 |
| **O-290-9** | 016 | una lectura con texto vacío no cuenta como «sin lectura» | T-290 |
| **O-291-1** | 016 | el freno de etapa puede dejar la medición externa vacía (riesgo declarado, 6a) | T-291 |
| **O-291-10** | 016 | conteos informados distintos de los míos (25 contra 24; 742 contra 696): no hay prueba perdida; los comandos del encargo recogen… | T-291 |
| **O-291-11** | 016 | el resumen no tiene prueba de la cifra «en toda la medición» (M4) | T-291 |
| **O-291-12** | 016 | el freno tras la extracción sigue yendo a lo local | T-291 |
| **O-291-13** | 016 | --medicion sin --externo se ignora en silencio (la medición local no usa libro) | T-291 |
| **O-291-2** | 016 | residual de _record_in_flight | T-291 |
| **O-291-3** | 016 | medir_matriz arma una medición nueva con marca de tiempo en cada invocación (medir_matriz-<procedimiento>-<fecha y hora>) | T-291 |
| **O-291-4** | 016 | la línea dice «Ninguna» cuando la etapa volvió a lo local tras haber mandado pedidos | T-291 |
| **O-291-5** | 016 | la hoja de compliance bloquea más de lo necesario, a favor de P4 | T-291 |
| **O-291-6** | 016 | diferencias de forma con las locales, ya dichas en la revisión de instrucciones | T-291 |
| **O-291-7** | 016 | prompt_versions y parameters.passes de una corrida externa siguen listando extracción, completitud, unión y filtro locales aunque… | T-291 |
| **O-291-8** | 016 | las filas de una tabla van al pedido de filtro externo antes de que keep_tables_pending decida el tramo | T-291 |
| **O-291-9** | 016 | un pedido de filtro con 0 filas y 0 tramos decididos igual sale (ninguna) | T-291 |
| **O-292-1** | 016 | EXTERNAL_CASE_CAP_USD=0 aborta la propuesta en lugar de seguir por lo local | T-292 |
| **O-292-1 a O-292-8** | 016 | O-292-1: EXTERNAL_CASE_CAP_USD=0 aborta la propuesta (ImproperlyConfigured, O-288-2) en vez de volver a local; con tope positivo… | T-292 (prueba de humo con el proveedor… |
| **O-292-2** | 016 | sin aciertos de caché, y la escritura de caché fue el 82 % del gasto | T-292 |
| **O-292-3** | 016 | el estimado de 0,30 USD (O-291-12) depende de los aciertos de caché | T-292 |
| **O-292-4** | 016 | clon_app sí tiene ruta a internet (por clon_web, la red que publica su puerto): urlopen("https://api.anthropic.com") desde… | T-292 |
| **O-292-5** | 016 | alcance de la prueba | T-292 |
| **O-292-6** | 016 | el libro suma por base | T-292 |
| **O-292-7** | 016 | gasto_externo --por-etapa no separa por medición | T-292 |
| **O-292-8** | 016 | el error de la clave inválida deja duracion_s y modelo_respuesta vacíos en el hecho, como es de esperar con un 401; la validación… | T-292 |
| **O-299-1** | 016 | la pregunta dice «el contraste no lo corroboró» cuando fue el verificador | T-299 |
| **O-299-2** | 016 | la línea dice «Ninguna» cuando la etapa volvió a lo local tras haber mandado pedidos (respuesta inválida, vencido, error del… | T-299 |
| **O-299-3** | 016 | _message indexa CONCLUSIONS | T-299 |
| **O-299-4** | 016 | el razonamiento guardado mide hasta 401 caracteres (400 más «…») | T-299 |
| **O-299-5** | 016 | «la oferta con la hoja no manda celdas» vale cuando la hoja está en el grupo de lectura de cada celda o en su cita (caso chico… | T-299 |
| **O-299-6** | 016 | la derivada reabre preguntas respondidas | T-299 |
| **O-299-7** | 016 | el volumen del cuerpo de las preguntas | T-299 |
| **O-299-8** | 016 | facts["verificador"] tiene claves de más (pregunta_usada, instruccion, anomalia) respecto de la lista del encargo; es un… | T-299 |
| **O-299-9** | 016 | EXTERNAL_ENABLED encendido y la etapa en externo con todas las celdas saltadas deja la etapa como local en etapas y escribe igual… | T-299 |
| **O-300-1** | 016 | cerrado: proveedor, modelo o modo con una lista se leen «sin dato» y no rompen… | T-291 |
| **O-300-1 y contrato de la clave `externo`** | 016 | O-300-1: external_stages.line falla si proveedor o modo llegan como lista (arreglo de una línea). Contrato… | T-300 (verificación liviana, cumple… |

## Casos de evals (56)

| Código | Feature | Qué es | · |
|---|---|---|---|
| **EV-001** | 001 | ¿Por cuánto tiempo debe un oferente mantener su oferta cuando el pliego no fija un plazo de mantenimiento? |  |
| **EV-002** | 001 | ¿Qué clases de garantías deben constituir los oferentes y contratistas y por qué porcentaje? |  |
| **EV-003** | 001 | ¿En qué plazo debe integrarse la garantía de cumplimiento del contrato? |  |
| **EV-004** | 001 | Si un proveedor cotiza un importe chico, ¿igual tiene que presentar garantía de oferta? |  |
| **EV-005** | 001 | ¿Cuál es el plazo para observar el dictamen de evaluación de las ofertas? |  |
| **EV-006** | 001 | ¿Cómo y en qué plazo se puede impugnar el acto que aprueba el procedimiento y adjudica? ¿La impugnación… |  |
| **EV-007** | 001 | Si el pliego no prevé multas, ¿qué multa corresponde por entregar fuera de término? |  |
| **EV-008** | 001 | ¿Qué sanciones se pueden aplicar a un oferente, adjudicatario o contratista que incumple sus obligaciones? |  |
| **EV-009** | 001 | ¿Qué modalidades pueden tener los procedimientos de selección? |  |
| **EV-010** | 001 | En una orden de compra abierta, ¿cómo se calcula la garantía de mantenimiento de la oferta? |  |
| **EV-011** | 001 | ¿Cómo se publica la convocatoria de una licitación pública y con cuánta antelación? |  |
| **EV-012** | 001 | Si la oferta económica no está firmada por el oferente ni por su representante legal, ¿se puede pedir que la… |  |
| **EV-013** | 001 | Si hay discrepancias entre los documentos de la contratación, ¿qué orden de prelación se sigue? |  |
| **EV-014** | 001 | ¿Puede el pliego de bases y condiciones particulares agregar causales propias para desestimar ofertas? |  |
| **EV-015** | 001 | ¿Hasta qué porcentaje se puede aumentar o disminuir un contrato y cuándo hace falta la conformidad del… |  |
| **EV-016** | 001 | ¿Por cuánto tiempo debe un oferente mantener su oferta cuando el pliego no fija un plazo de mantenimiento? |  |
| **EV-017** | 001 | ¿En qué plazo debe integrarse la garantía de cumplimiento del contrato? |  |
| **EV-018** | 001 | ¿Puede el pliego de bases y condiciones particulares agregar causales propias para desestimar ofertas? |  |
| **EV-019** | 001 | ¿Qué se necesita para impugnar el acto de adjudicación y en qué plazo? |  |
| **EV-020** | 001 | Si se concede una prórroga del plazo de entrega, ¿qué multa corresponde? |  |
| **EV-021** | 001 | En una contratación directa, ¿hay que presentar garantía de mantenimiento de oferta? |  |
| **EV-022** | 001 | ¿Cómo se integra la Comisión Evaluadora? |  |
| **EV-023** | 001 | En una orden de compra abierta, ¿cómo se calcula la garantía? |  |
| **EV-024** | 001 | ¿Cuál es el plazo para observar el acta de evaluación de las ofertas? |  |
| **EV-025** | 001 | ¿Cuántos días de licencia por maternidad le corresponden a una agente de la AFIP? |  |
| **EV-026** | 001 | ¿Cuál es la alícuota general del impuesto al valor agregado? |  |
| **EV-027** | 001 | ¿Hasta qué monto se puede hacer una licitación privada? |  |
| **EV-028** | 001 | ¿Cómo se integra la Comisión Evaluadora? |  |
| **EV-029** | 001 | ¿Hasta qué monto se puede hacer una contratación directa por monto? |  |
| **EV-030** | 001 | ¿Cuándo vence la presentación de la declaración jurada del impuesto a las ganancias de las personas humanas? |  |
| **EV-031** | 001 | ¿Por cuánto tiempo debe un oferente mantener su oferta cuando el pliego no fija un plazo de mantenimiento? |  |
| **EV-032** | 001 | ¿Cuántas horas de capacitación por año tienen que cumplir los agentes que trabajan en el área de compras? |  |
| **EV-033** | 001 | ¿Cada cuánto tiempo tienen que rotar de puesto los agentes que trabajan en el área de compras? |  |
| **EV-034** | 001 | ¿Cuál es el plazo mínimo para que los interesados formulen observaciones al proyecto de pliego de bases y… |  |
| **EV-035** | 001 | ¿Cuál es el plazo mínimo para que los interesados formulen observaciones al proyecto de pliego de bases y… |  |
| **EV-036** | 001 | ¿Qué se hace cuando dos ofertas quedan empatadas? |  |
| **EV-037** | 001 | ¿Qué se hace cuando dos ofertas quedan empatadas? |  |
| **EV-038** | 001 | ¿Cuánto puede cobrar la AFIP por el pliego de una licitación? |  |
| **EV-039** | 001 | ¿Cuánto puede cobrar la AFIP por el pliego de una licitación? |  |
| **EV-040** | 001 | ¿Pasado cuánto tiempo la AFIP ya no puede aplicarle una penalidad a un proveedor por un incumplimiento? |  |
| **EV-041** | 001 | Si una unidad hace varias convocatorias seguidas para comprar los mismos bienes, ¿cuándo se presume que… |  |
| **EV-042** | 001 | ¿Durante cuánto tiempo responde el contratista por los vicios ocultos de lo que entregó? |  |
| **EV-043** | 001 | ¿El adjudicatario puede rechazar la orden de compra después de que se la notifican? |  |
| **EV-044** | 001 | ¿Qué pasa con las muestras que un oferente nunca pasa a buscar? |  |
| **EV-045** | 001 | ¿Un oferente puede constituir la garantía con un pagaré? |  |
| **EV-046** | 001 | ¿Por cuánto tiempo puede la AFIP suspender a un proveedor como sanción? |  |
| **EV-047** | 001 | En una licitación para alquilar un inmueble, ¿se puede adjudicar al actual locador de la AFIP aunque su… |  |
| **EV-048** | 001 | ¿Cómo se integra la comisión de recepción? |  |
| **EV-049** | 001 | ¿Hasta qué monto se puede usar el trámite simplificado? |  |
| **EV-050** | 001 | ¿Hasta qué monto se puede usar el trámite simplificado? |  |
| **EV-051** | 001 | ¿Cuál es el monto del salario mínimo, vital y móvil? |  |
| **EV-052** | 001 | ¿Qué documentación hay que presentar para tramitar el pasaporte? |  |
| **EV-053** | 001 | ¿Cuál es la velocidad máxima permitida para circular en una autopista? |  |
| **EV-054** | 001 | ¿Qué monto diario de viáticos le corresponde a un agente del área de compras que viaja a otra provincia por… |  |
| **EV-055** | 001 | ¿Cada cuánto tiempo tiene que hacer la unidad de compras una encuesta de satisfacción a las áreas que le… |  |
| **EV-056** | 001 | ¿Cuántos días por semana pueden teletrabajar los agentes del área de compras? |  |
