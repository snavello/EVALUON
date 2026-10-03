# ADR-0006 · Dos regímenes específicos según la fecha de autorización del procedimiento

Estado: aceptado · Fecha: 2026-10-02 · Decidió: responsable del proyecto

## Contexto

El proyecto nació tomando la Disposición AFIP 297/03 como régimen específico de contrataciones. Al incorporarla al corpus se comprobó en Infoleg que fue abrogada por el artículo 2 de la Disposición AFIP 247/2022 (B.O. 30/11/2022), que aprueba un nuevo régimen general.

La 247/2022 establece además una transición:

- Artículo 2: toda cita a la 297/03 en normas vigentes se entiende referida a la 247/2022.
- Artículo 3: rige a partir de los veinte días hábiles administrativos desde su publicación, para las contrataciones que se autoricen desde esa fecha.
- Artículo 4: los procedimientos autorizados antes tramitan con la normativa entonces vigente.

Por lo tanto, cuál de los dos regímenes se aplica a un caso depende de cuándo se autorizó el procedimiento. Infoleg registra además 33 normas que modificaron o complementaron la 297/03 entre 2005 y 2022.

## Alternativas

### A. Solo la 247/2022
Es el régimen para las contrataciones actuales. Más simple. El sistema no sirve para procedimientos autorizados antes de su entrada en vigencia, y la 297/03 queda solo como antecedente.

### B. Solo la 297/03
Sirve para procedimientos anteriores. Deja afuera el régimen que rige las contrataciones nuevas.

### C. Los dos, según la fecha de autorización
El sistema carga ambos regímenes y aplica uno u otro según la fecha en que se autorizó el procedimiento. Es lo más completo. Obliga a pedir esa fecha en cada consulta y a registrar con precisión la entrada en vigencia de la 247/2022 y los cambios que tuvo la 297/03.

## Decisión

Se adopta la alternativa C.

- Cada consulta y cada búsqueda se hacen para una fecha de autorización del procedimiento, que indica la persona. Por defecto es la del día.
- El sistema responde con las unidades que regían a esa fecha y muestra qué régimen aplicó.
- La fecha exacta de entrada en vigencia de la 247/2022 la registra una persona al cargar la norma: el sistema no la calcula.

## Consecuencias

- La constitución deja de nombrar a la 297/03 como único régimen (versión 1.1).
- La spec 001 suma el requisito REQ-020 y deja sin efecto la exclusión de elegir la fecha en la pantalla.
- El plan 001 ya resolvía la vigencia con una función que recibe una fecha; cambia de dónde sale esa fecha y qué muestra la pantalla.
- Las features 002 a 004 heredan el dato: un pliego o una evaluación se revisan contra el régimen de la fecha de autorización de su procedimiento.
- La calidad de las respuestas bajo la 297/03 depende de cuántas de sus modificatorias estén cargadas y registradas. Queda por decidir con qué profundidad se cargan.
- Para volver a un solo régimen alcanzaría con fijar la fecha y ocultar el campo; no hay que deshacer el modelo de datos.

## Fuentes

- Infoleg, ficha de la Disposición 297/2003: https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=86154
- Infoleg, Disposición 247/2022: https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/375829/norma.htm
- Copias en `corpus/normativa/` y `corpus/normativa/referencias/`, con su huella en `corpus/manifiesto.csv`.

## Datos registrados

- **2026-10-02 · Entrada en vigencia de la Disposición 247/2022:** 1 de enero de 2023, informada por el responsable del proyecto. Los procedimientos autorizados desde esa fecha se rigen por la 247/2022; los anteriores, por la 297/03.
- **2026-10-02 · Entrada en vigencia de la Disposición 297/03:** 14 de junio de 2003, el día siguiente a su publicación en el Boletín Oficial del 13/6/2003, según su propio texto.


- **2026-10-03 · Corrección de la entrada en vigencia de la Disposición 247/2022:** 2 de enero de 2023. El art. 3 la fija en VEINTE (20) días hábiles administrativos desde su publicación en el Boletín Oficial (30/11/2022); descontando como inhábiles el 8/12, el 9/12 (feriado puente) y el 20/12/2022, el día 20 es el lunes 2 de enero de 2023. Decisión del responsable. Los procedimientos autorizados hasta el 1 de enero de 2023 se rigen por la 297/03.
