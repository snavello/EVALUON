# Spec 003 · Procedimiento, pliego final y matriz de cumplimiento

Estado: aprobada · Fecha: 2026-10-03 · Aprobó: responsable del proyecto · Enmienda: 2026-10-03, requisitos técnicos por renglón, criterio de requisito y de clase, y tipos de consecuencia (al aprobar el plan); REQ-032, matriz sin validar como "BORRADOR INCOMPLETO", decisión del responsable; 2026-10-04, requisitos en tramos pendientes cuentan como "a revisión obligatoria", decisión del responsable; 2026-10-04, tope de sobrantes, filas descartadas por el sistema a la vista y revisión por grupos (REQ-033 y REQ-034), decisión y aprobación del responsable; 2026-10-04, un solo nivel de revisión, el más completo, y el tiempo se informa sin límite, decisión y aprobación del responsable

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

Para evaluar ofertas, la Comisión Evaluadora tiene que saber primero qué exige el pliego. Hoy esos requisitos se buscan a mano, leyendo el pliego de bases y condiciones particulares, sus anexos y las especificaciones técnicas. La lista que arma cada integrante depende de su lectura, y es fácil que falte un requisito o que se confunda una exigencia con una recomendación.

Todo lo que el sistema haga después (la ficha por oferta, la evaluación cumple o no cumple) se apoya en esa lista. Si la lista está incompleta o mal citada, la evaluación también lo está.

Esta feature construye esa lista, la **matriz de cumplimiento**. A partir del pliego final publicado de un procedimiento, el sistema propone los requisitos que debe cumplir una oferta, cada uno con la cita exacta del pliego que lo exige. La Comisión los revisa y los valida. Además, el procedimiento registra su fecha de autorización, que define qué régimen de la AFIP se le aplica (feature 001, ADR-0006).

## Usuarios y escenarios

Roles (decisión del responsable, 2026-10-03):

- **Operador** (personal de apoyo de la Comisión): registra el procedimiento, carga el pliego y propone correcciones a la matriz (corregir, quitar o agregar requisitos).
- **Evaluador** (integrante de la Comisión Evaluadora): puede hacer todo lo que hace el operador y, además, confirma la consecuencia de cada requisito y valida la matriz. Lo que cuenta como decisión queda siempre en manos de un evaluador (P3).

**Escenario 1 · Registrar un procedimiento.** Como integrante de la Comisión, cuando empieza la evaluación de un procedimiento, necesito registrarlo con su número, su objeto y su fecha de autorización, para que el sistema sepa qué régimen se le aplica.

**Escenario 2 · Cargar el pliego final.** Como integrante de la Comisión, cuando tengo el pliego final publicado, necesito cargarlo con todos sus documentos (pliego particular, anexos, especificaciones técnicas), para que el sistema los lea.

**Escenario 3 · Revisar la matriz propuesta.** Como integrante de la Comisión, cuando el sistema terminó de leer el pliego, necesito ver la lista de requisitos que propone, cada uno con el texto del pliego que lo exige, para confirmar, corregir, quitar o agregar requisitos.

**Escenario 4 · Matriz validada.** Como integrante de la Comisión, cuando terminé la revisión, necesito dejar la matriz validada y registrada, para que la ficha por oferta y la evaluación (features 008 y 004) usen esa lista y no otra.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-022 | El sistema debe registrar un procedimiento con su número, tipo, objeto y fecha de autorización, y mostrar el régimen de la AFIP que le corresponde según esa fecha | ADR-0006 |
| REQ-023 | El sistema debe permitir cargar el pliego final de un procedimiento como uno o más documentos, conservando cada original sin cambios | — |
| REQ-024 | El sistema debe proponer, a partir del pliego cargado, la lista de requisitos que debe cumplir una oferta, cada uno clasificado como formal, económico o técnico | — |
| REQ-025 | Cada requisito propuesto debe citar el texto literal del pliego que lo exige, con el documento y la ubicación (página y cláusula, si la hay) | P3 |
| REQ-026 | La Comisión debe poder confirmar, corregir, quitar o agregar requisitos; cada cambio queda registrado con quién lo hizo y cuándo | P6 |
| REQ-027 | Una matriz validada queda fija: cambiarla después genera una versión nueva, sin perder la anterior | — |
| REQ-028 | Cuando el sistema no puede ubicar con certeza un tramo del pliego (texto ilegible, tabla mal leída), debe señalarlo para revisión en lugar de omitirlo | P3 |
| REQ-029 | Para cada requisito, el sistema debe proponer las consecuencias posibles de no cumplirlo (por ejemplo, desestimación de la oferta o intimación a subsanar), cada una con su fundamento en el pliego o en la norma aplicable; un integrante de la Comisión confirma una. Si el sistema no encuentra fundamento, la consecuencia queda "no determinada" | P3; régimen aplicable según REQ-022 |
| REQ-030 | La matriz se propone siempre con un único proceso de revisión, el más completo disponible, y queda registrado con la matriz qué proceso y qué versión de instrucciones se usaron | — |
| REQ-031 | El pliego final incluye las circulares modificatorias y aclaratorias y las preguntas de los oferentes con sus respuestas, si las hay, cada una con su fecha. Cuando una de ellas cambia o precisa un requisito, la matriz aplica el cambio, muestra los dos textos y cita el documento que lo produjo | — |
| REQ-033 | Antes de mostrar la matriz propuesta, el sistema debe descartar las filas que no son requisitos de la oferta y unificar las que repiten la misma condición. Lo descartado no desaparece: queda en una lista aparte, cada fila con su cita y el motivo, que la Comisión puede abrir y devolver a la matriz | P3 |
| REQ-034 | La Comisión debe poder confirmar o quitar de una vez un grupo de requisitos propuestos de un mismo tramo o cláusula; cada fila del grupo queda registrada como si se hubiera revisado por separado, con quién y cuándo | P6 |
| REQ-032 | Una matriz que todavía no está validada se puede ver en pantalla, imprimir y exportar a PDF, siempre con la leyenda "BORRADOR INCOMPLETO" bien visible en cada página. Una matriz validada sale sin esa leyenda, con su versión y la fecha y el evaluador que la validó | — |

**Qué es un requisito (decisión del responsable, 2026-10-03; enmendada al aprobar el plan).**
- Es requisito de la oferta lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o condicionar, aunque la cumpla el organismo: por ejemplo, la moneda y la forma y el plazo de pago (el pliego dice pago a 90 días y el oferente pide pago a los 3 días de la entrega). No son requisitos de la oferta la ejecución y el control del contrato, como las multas por atraso.
- Los requisitos formales y económicos van en una fila por condición que se pueda verificar por separado, para que un "no cumple" señale la condición exacta.
- Los requisitos técnicos van en una fila por renglón del pliego, con la cita a sus especificaciones técnicas, porque una oferta puede cotizar solo algunos renglones o cumplir solo algunos. La Comisión no evalúa el detalle técnico: se apoya en el informe técnico del área requirente, que es el fundamento de esos renglones en la evaluación (feature 004).
- La clase sigue la sección del pliego cuando el pliego ordena sus requisitos por secciones. Si no, se clasifica por naturaleza: la garantía, el precio, la moneda y el pago son económicos; los documentos y compromisos de la presentación, formales; el bien y su entrega, técnicos.

**Consecuencia del incumplimiento (decisión del responsable, 2026-10-03).** El sistema no decide si un requisito es subsanable: detecta qué consecuencias tiene su falta, sugiere las posibles con su fundamento, y un integrante de la Comisión confirma una. La misma forma de trabajo (el sistema propone opciones fundadas, la persona elige) se aplica a todas las propuestas de esta feature (P3).

  | Tipo de consecuencia | Cuándo |
  |---|---|
  | Desestimación sin posibilidad de subsanar | el pliego o la norma lo establecen |
  | Intimación a subsanar; si no se subsana, desestimación | el pliego o la norma lo permiten |
  | Consultar al oferente | si el pliego lo permite, con la cita |
  | Aprobación condicionada | a criterio del evaluador, con la condición escrita |
  | Aprobar de todas maneras | a criterio del evaluador, con su motivo escrito |
  | Otra consecuencia prevista en el pliego | con su cita |
  | No determinada | el sistema no encontró fundamento |

  El "cumple o no cumple" y la consecuencia los decide siempre el evaluador, con su nombre y su motivo registrados.

## Criterios de aceptación

- **REQ-022.** Dado un procedimiento autorizado el 2022-12-15, cuando se registra, entonces el sistema muestra como régimen aplicable la Disposición 297/03; con fecha 2023-01-02 o posterior, la 247/2022.
- **REQ-023.** Dado un pliego compuesto por varios documentos, cuando se cargan, entonces cada original se conserva y se puede abrir tal como se cargó.
- **REQ-024.** Dado el pliego del caso público de referencia, cuando el sistema propone la matriz, entonces la lista contiene **todos** los requisitos que la Comisión identificó en ese caso, cada uno con su clasificación. Ante la duda, el sistema propone de más: un requisito que no corresponde lo quita el evaluador, pero uno que falta no lo evalúa nadie (decisión del responsable, 2026-10-03).
- **REQ-025.** Dado un requisito propuesto, cuando se lo muestra, entonces el texto citado coincide palabra por palabra con el del pliego, en el documento y la ubicación indicados.
- **REQ-026.** Dado un requisito propuesto, cuando la Comisión lo corrige, entonces el cambio queda registrado con el usuario y el momento, y el texto original propuesto se puede consultar.
- **REQ-027.** Dada una matriz validada, cuando se modifica un requisito, entonces existe una versión nueva y la anterior sigue disponible.
- **REQ-028.** Dada una página del pliego que no se pudo leer, cuando se muestra la matriz propuesta, entonces esa página figura como pendiente de revisión.
- **REQ-029.** Dado un requisito cuya falta el pliego sanciona con la desestimación, cuando se muestra la matriz propuesta, entonces el sistema sugiere "desestimación" con la cita de esa cláusula, y la consecuencia queda confirmada solo cuando un integrante de la Comisión la elige; la elección queda registrada con quién y cuándo.
- **REQ-030.** Dado un pliego cargado, cuando se pide la matriz, entonces no se ofrece elegir nivel, se usa el proceso completo y la matriz propuesta registra el proceso y la versión de instrucciones usados.
- **REQ-031.** Dado un pliego que exige "16 GB de RAM" y una circular modificatoria posterior que dice "32 GB", cuando se propone la matriz, entonces el requisito exige 32 GB, muestra los dos textos y cita la circular; una respuesta a una pregunta de un oferente que precisa un requisito figura junto a ese requisito con su cita.
- **REQ-033.** Dada una fila propuesta que no es un requisito de la oferta (por ejemplo, una obligación del organismo o de la ejecución del contrato), cuando se muestra la matriz propuesta, entonces esa fila no está en la matriz y figura en la lista de descartadas por el sistema, con su cita y su motivo; si la Comisión la devuelve a la matriz, el cambio queda registrado. Dadas dos filas que exigen la misma condición, entonces la matriz muestra una sola, con las dos citas.
- **REQ-034.** Dados cinco requisitos propuestos de una misma cláusula, cuando la Comisión los confirma como grupo, entonces los cinco quedan confirmados y el registro muestra, para cada uno, quién lo confirmó y cuándo.
- **REQ-032.** Dada una matriz propuesta sin validar, cuando se la ve, se la imprime o se la exporta a PDF, entonces cada página muestra la leyenda "BORRADOR INCOMPLETO"; dada una matriz validada, la salida no lleva la leyenda y muestra su versión, la fecha y quién la validó.

## Requisitos no funcionales

- **Medición:** la propuesta de matriz se mide con salida estructurada: cada requisito esperado está o no está en la lista, con la clasificación y la cita correctas (ADR-0014, punto 7). No se mide la redacción.
  - Requisitos encontrados: **100 %** de los requisitos reales del pliego. Cada requisito que falte se informa con su causa y bloquea la aceptación.
  - Un requisito esperado que cae en un tramo que el sistema dejó **pendiente de revisión** (por ejemplo, una tabla) cuenta como **"a revisión obligatoria"**, no como perdido: la matriz no se puede validar sin que el evaluador resuelva cada pendiente. Se informa aparte, con su cantidad (decisión del responsable, 2026-10-04).
  - Requisitos sobrantes (filas de la matriz propuesta que no corresponden a un requisito esperado): **hasta el 20 % de la matriz propuesta** con el 100 % de encontrados (decisión del responsable, 2026-10-04: descartar a mano cientos de filas empeora el trabajo de la Comisión en lugar de ayudarlo). Las filas descartadas por el sistema (REQ-033) no cuentan como sobrantes, pero un requisito esperado que el sistema descartó **cuenta como faltante**. Se informan también las filas descartadas, con una muestra revisada de sus motivos.
  - El filtro de sobrantes se ajusta solo con el caso-00. Los casos 01 y 02 se usan después para medirlo, sin mirar antes el contenido de sus sobrantes.
  - Cita literal: 100 %.
- **Tiempo y nivel de revisión (decisión del responsable, 2026-10-04; reemplaza la del 2026-10-03):** la confección de la matriz es el proceso central y su calidad manda sobre el tiempo. Hay un solo proceso, el más completo; no se ofrecen niveles más rápidos ("media" deja de existir). Se le pueden sumar pasadas o filtros cuando la medición muestre que mejoran la matriz (más requisitos encontrados, menos sobrantes o mejores citas). El tiempo se mide y se informa por pliego y por página, pero no tiene máximo ni bloquea la aceptación. Mientras tanto se puede seguir trabajando, y el sistema avisa cuando termina.
- **Funcionamiento sin conexión:** como en la 001, todo corre en el equipo propio.

## Fuera de alcance

- La revisión del pliego borrador contra la normativa (feature 002).
- La carga de ofertas y su comparación con la matriz (features 008 y 004).
- Redactar o modificar el pliego.

## Datos involucrados

- Pliegos, ofertas y evaluaciones de procedimientos ya publicados: material público (P4), que igual queda solo en el equipo propio porque trae datos personales.
- **El caso de referencia `corpus/casos/caso-00/`, aportado por el responsable.** Es un procedimiento ya adjudicado, por lo tanto público. Es sencillo: el pliego PLIEG-2025-04092776-ARCA-DVGDCO en un solo documento, sin circulares ni preguntas de oferentes, tres ofertas con varios documentos cada una y la evaluación EX-2025-03389993. Con él se arma el conjunto para medir la matriz: la lista de requisitos esperada la prepara el Coordinador desde el pliego, sin correr el sistema, la contrasta con lo que la evaluación verificó y la aprueba el responsable con tabla de ejemplos; después la confirma la Comisión (feature 009).
- **Ningún documento del caso se sube al repositorio,** que es público: las ofertas traen datos personales de los oferentes (copia de DNI, pagarés, pólizas) y el pliego, la nómina de funcionarios con su DNI. Todo el caso queda en el equipo propio, donde corre el sistema (decisión del responsable, 2026-10-03; P4). Las listas esperadas para medir la matriz tampoco transcriben datos personales.
- **Un solo caso alcanza para empezar,** pero no para dar por medida la feature con un único pliego. Por ahora no hay otro pliego disponible: se arranca con el caso-00 y, más adelante, la Comisión aporta otros pliegos (decisión del responsable, 2026-10-03). Hasta entonces, la medición de REQ-024 con un solo pliego se informa como provisoria y se repite cuando haya más casos.

  **Casos sumados el 2026-10-03** (aportados por el responsable; descargados del portal público de compras de ARCA, `afipcompras.afip.gob.ar`; solo en el equipo propio):

  | Caso | Procedimiento | Pliego | Circulares |
  |---|---|---|---|
  | caso-01 | Licitación pública A0PC000000-0001-LPU26, señalética de edificios (247/2022, art. 21 inc. a) | PLIEG-2026-01953220, 52 páginas, con 13 anexos técnicos | 2 (modificaciones al pliego y al cronograma) |
  | caso-02 | Contratación directa A0PC000000-0003-CDI26, mantenimiento de UPS (247/2022, art. 21 inc. d) | PLIEG-2026-02965389, 31 páginas | — |

  El caso-01 sirve además para REQ-031 (circulares reales) y para el tiempo de un pliego de unas 50 páginas. **El caso-01 y el caso-02 se reservan para la aceptación** (ADR-0014): nadie corre el sistema sobre ellos ni los usa para ajustar hasta la medición; sus listas esperadas se preparan solo desde el texto, como la del caso-00. El caso-00 queda para el hilo mínimo y el ajuste.

## Preguntas abiertas

Ninguna. Las decisiones del responsable del 2026-10-03 están anotadas en cada sección.
