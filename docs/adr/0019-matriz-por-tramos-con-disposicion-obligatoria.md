# ADR-0019 · Propuesta de la matriz por tramos, con disposición obligatoria y cita verificada

Estado: propuesto · Fecha: 2026-10-03 · Decidió: —

## Contexto

La spec 003 pide que el sistema proponga, desde el pliego final, la lista de requisitos que debe cumplir una oferta (REQ-024), cada uno con la cita literal del pliego (REQ-025), y que señale lo que no pudo leer en lugar de omitirlo (REQ-028). La exigencia es **100 % de los requisitos encontrados**: "un requisito que no corresponde lo quita el evaluador, pero uno que falta no lo evalúa nadie". Además, un requisito es "una condición que se puede verificar por separado: una fila por condición".

Lo que muestra el pliego del caso de referencia (`corpus/casos/caso-00/`, solo en el equipo propio):

- 20 páginas, todas con capa de texto: 19 del pliego y una hoja de firma digital.
- Cuatro secciones: condiciones particulares (cláusulas 1 a 28), especificaciones técnicas generales, especificaciones técnicas particulares (seis renglones) y anexos (dos declaraciones juradas). La numeración vuelve a empezar en cada sección: hay una cláusula "1.1" en tres secciones.
- Cláusulas numeradas en hasta cuatro niveles ("11.6.1.", "17.3.2."), a veces sin espacio después del número ("10.2.1.Una vez…").
- Una cláusula puede tener decenas de condiciones: la 1.1 del renglón 1 enumera unos 30 valores de composición ("Proteína bruta (mín.): 24%; Extracto etéreo (mín.): 15%; …"). Con "una fila por condición", el pliego tiene del orden de 200 a 250 requisitos (estimación de quien escribe; la cifra real sale de la lista esperada).
- Tablas: el detalle de renglones y cantidades, el tipo de cotización, las multas y una nómina de funcionarios con datos personales.
- Las consecuencias están repartidas: una regla general para la documentación (7.3), reglas propias de algunas cláusulas (11.3, 11.7, 13.4, 16.2) y la remisión al régimen (art. 55 del anexo de la Disposición 247/2022, citado en 16.4).

Restricciones: el modelo es Gemma 4 12B con un contexto de 16.384 tokens (ADR-0002); escribe unos 73 tokens por segundo en este equipo; un pliego de 50 páginas no entra en un pedido. La definición de cita literal es la del ADR-0004 y la comprobación, la del plan 001: el texto citado es igual al recorte del texto canónico entre dos posiciones.

## Alternativas

### A. Extracción libre por bloques
El pliego se corta en bloques de tamaño fijo y se le pide al modelo la lista de requisitos de cada bloque.
- Se gana: lo más simple de construir.
- Se pierde: no hay forma de saber si el modelo leyó y descartó un párrafo o si lo pasó por alto. El 100 % no se puede sostener con nada más que la medición sobre un pliego conocido.

### B. Recorrido por tramos con disposición obligatoria (propuesta)
Reglas deterministas parten el pliego en **tramos**: cada cláusula o subcláusula numerada, cada viñeta, cada párrafo de un anexo y cada bloque de tabla. Cada pedido al modelo lleva un lote de tramos consecutivos, y el esquema de salida obliga a devolver, **para cada tramo del lote**, sus requisitos o un motivo de descarte de una lista cerrada. El código comprueba después que todos los tramos tengan disposición y que cada cita esté, palabra por palabra, dentro de su tramo.
- Se gana: ningún tramo queda sin revisar en silencio. Lo que el modelo descarta queda a la vista con su motivo; lo que el sistema no pudo leer queda pendiente de revisión. El control de cobertura es una cuenta, no una opinión.
- Se pierde: reglas de partición de pliegos para mantener, como en la 001 con las normas; más tokens de salida (una disposición por tramo); un pliego con una forma que las reglas no reconocen produce tramos grandes, que el modelo igual recorre, pero con citas menos precisas.

### C. Solo reglas, sin modelo
Se buscan marcadores de obligación ("deberá", "mín.", "máx.", "será requisito", "bajo apercibimiento") y se arma la lista con reglas.
- Se gana: determinista, sin GPU.
- Se pierde: no separa bien las condiciones de una enumeración libre, no clasifica en formal, económico o técnico, y marca como requisito lo que es una obligación de la Agencia o del contrato. Se usa solo como control dentro de B.

### D. Todo el pliego en un pedido
Descartada: un pliego de 50 páginas ocupa más que el contexto del modelo.

## Decisión

Se propone **B**, con estas reglas:

1. **Tramos.** Las reglas de partición de pliegos son propias (no las de normas de la 001), sobre el mismo texto canónico. Cada tramo tiene clave estable (por ejemplo `sec-i/11.3`, `sec-iii/1.1`), ruta legible, páginas, posiciones en el texto canónico y, si cuelga de un renglón, su número de renglón. Control de cobertura igual al de la 001: todo carácter del texto canónico está en un tramo, en lo descartado por la lectura (encabezados, pies, índice) o en un tramo "no ubicado" que queda pendiente de revisión.
2. **Disposición obligatoria.** Para cada tramo, el modelo devuelve una lista de requisitos o un motivo de descarte de una lista cerrada (título, definición o dato del procedimiento, norma aplicable, obligación del organismo, obligación de la ejecución del contrato, formulario a completar, índice o carátula). El esquema enumera las claves de los tramos del lote y las exige todas. Un tramo sin disposición válida se vuelve a pedir una vez, solo; si tampoco, queda **pendiente de revisión**.
3. **Requisito = fragmento literal.** Cada requisito es el fragmento del pliego que lo exige, más su clase (formal, económico o técnico) y su renglón si corresponde. El modelo no redacta el requisito: copia un fragmento corto. El sistema busca ese fragmento, exacto, dentro del tramo; si lo encuentra, guarda sus posiciones y desde ahí muestra el texto. Si no lo encuentra, se vuelve a pedir una vez; si sigue sin aparecer, el requisito queda con el tramo entero como cita y la marca "cita amplia, revisar". Nunca se muestra como cita un texto que no esté en el pliego, y nunca se pierde un requisito por una cita mal copiada.
4. **Lo que el sistema no puede leer** (páginas ilegibles o dudosas, tramos no ubicados, bloques de tabla) queda pendiente de revisión con su página, sin pasar por el modelo o además de pasar por él, según el caso (plan 003).
5. **Niveles por pasadas.** *Media*: una extracción. *Alta*: la extracción y una pasada de completitud por tramo, que recibe el tramo con los requisitos ya encontrados y devuelve los que faltan o divide los que juntan dos condiciones; recibe además los tramos descartados que tienen marcadores de obligación (alternativa C como control). *Exigente*: alta más una segunda extracción independiente, con los lotes desplazados, y la unión de las dos por superposición de cita antes de la completitud. Cada nivel se ofrece solo si la medición demuestra que mejora al anterior (spec, "Tiempo y nivel de revisión").
6. **El mismo patrón para consecuencias y circulares.** El modelo elige de una lista cerrada (tipo de consecuencia; efecto de una circular) y señala los tramos o las unidades de la norma que lo sostienen, por un alias. El sistema pone el texto. Sin fundamento válido, la consecuencia queda "no determinada" (P3).

Motivo principal: el 100 % de la spec necesita un control que no dependa de que el modelo acierte siempre. Con B, lo que falta solo puede faltar porque un tramo revisado se descartó por un motivo visible o porque un requisito quedó junto con otro; las dos cosas se ven en la pantalla y se miden.

## Consecuencias

**Más fácil**
- La revisión del evaluador tiene un mapa completo: cada tramo del pliego con sus requisitos, su descarte o su pendiente.
- La medición puede decir por qué falta cada requisito faltante: tramo descartado, tramo pendiente, requisito agrupado con otro.
- La cita literal se comprueba con una operación, como en la 001.

**Más difícil**
- Las reglas de partición de pliegos se ajustan contra pliegos reales; con un solo pliego disponible, el primer pliego distinto puede traer formas nuevas. Mientras tanto, lo no reconocido queda en tramos grandes o pendientes, nunca afuera.
- Más tokens de salida por la disposición de cada tramo. Se mide en la corrida de la 003.
- La pasada de completitud puede sumar sobrantes. La spec los acepta, sin límite, y los informa.

**Para revertir**
- Pasar a A es quitar la disposición del esquema y el control de cobertura: los datos guardados siguen siendo válidos. Cambiar las reglas de partición crea tramos nuevos en una lectura nueva; las matrices ya propuestas conservan los suyos.

## Sin verificar

- Cuántos tramos y requisitos tiene un pliego de 50 páginas, y cuánto tarda cada nivel. Estimación del plan 003; se mide en T-084 con el caso-00 (20 páginas) y se informa como provisoria.
- Que Gemma 4 12B copie fragmentos exactos con la frecuencia necesaria. Lo mide la corrida (citas reintentadas y citas amplias).
- Que el esquema con una propiedad obligatoria por tramo no vuelva lento al motor con lotes grandes. Se ajusta el tamaño del lote, que es un parámetro.
