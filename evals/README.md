# Evals · conjunto dorado

Casos públicos ya resueltos contra los que se mide cada versión del sistema (principio P7).

## Qué es un caso

Un caso tiene una pregunta o una tarea de evaluación, los documentos sobre los que se hace, la respuesta esperada y la cita que la sostiene. También hay casos sin respuesta posible, donde lo correcto es "no determinado".

El formato vigente de cada feature lo fija su plan (para la 001, `specs/001-normativa/plan.md`, sección "Evals"). Como punto de partida, un archivo por caso en `evals/casos/`:

```yaml
id: EV-001
tipo: normativa | pliego | oferta
documentos: [ruta en corpus/]
pregunta: "..."
fecha_autorizacion: AAAA-MM-DD   # fecha de autorización del procedimiento (REQ-020)
esperado: "..."            # o "no determinado"
cita: {documento: "...", ubicacion: "artículo o página"}
origen: "de dónde sale la respuesta esperada"
datos_clave:               # lo que la respuesta tiene que contener; vacío si no hay respuesta
  - "30 días"                                  # un texto: el dato tiene una sola forma
  - ["acto de apertura", "fecha de apertura"]  # una lista: variantes del mismo dato
  - ["no", "sin posibilidad"]                  # un "no" y otra forma que el caso prevé
lote: aceptacion           # optativo: ajuste o aceptacion; sin el campo, ajuste
```

## Lote de aceptación

ADR-0014, punto 1; detalle en el plan de la 001, sección "Evals", "Lote de aceptación".

- Los casos se dividen en dos lotes con el campo `lote`: `ajuste` o `aceptacion` (sin tildes ni mayúsculas, se acepta también `Aceptación`). Un caso sin el campo es del lote de ajuste; cualquier otro valor deja el caso mal formado y no se corre.
- **Lote de ajuste:** EV-001 a EV-033 y todo caso sin `lote` o con `lote: ajuste`. Se usa para ajustar el corrector, los datos clave, el umbral y las instrucciones, y para el diagnóstico.
- **Lote de aceptación:** los casos con `lote: aceptacion`. De él salen la respuesta correcta y la abstención que se exigen para aceptar. Condiciones:
  - al menos 10 preguntas con respuesta y 6 sin respuesta, con los dos tipos de pregunta sin respuesta ("ajena a la normativa" y "tema cercano que la normativa no resuelve");
  - se escribe sin correr el sistema: nadie hace esas preguntas, ni otras parecidas, en la pantalla ni con un comando antes de su primera corrida;
  - trata artículos que el lote de ajuste no usa;
  - no se usa nunca para ajustar. Si se usa, pierde su condición: con decisión del responsable, sus casos pasan a `lote: ajuste` y se escribe un lote nuevo.
- `resumen.md` informa los dos lotes por separado, cada medida con su margen de error (intervalo de Wilson al 95 %), y los casos fallados del lote de aceptación aparte.

## Datos clave

Reglas del ADR-0011 (`docs/adr/0011-medicion-de-respuesta-correcta.md`); el detalle está en el plan de la 001, sección "Evals", "Datos clave y corrector".

- Un dato clave es una pieza corta: un número con su unidad ("30 días"), un porcentaje, un término que no puede faltar, o "sí" o "no". No es una frase de la norma ni un resumen.
- Un dato puede traer variantes y se cumple si aparece cualquiera. Las variantes las escribe el caso, con su visto bueno, cuando hay más de una forma correcta de decir el dato; nunca para hacer pasar una corrida. Las de "sí" y "no" también: el corrector no las deduce.
- El corrector compara sin tildes ni mayúsculas, con los números en letras de cualquier tamaño ("treinta" vale "30"), sin punto de miles ("1.000" vale "1000") y con singular y plural ("contratación directa" vale "contrataciones directas"). No acepta sinónimos, cambio de orden ni palabras intercaladas.
- Una lista vacía, un texto vacío o una lista dentro de la lista de variantes dejan el caso mal formado. Conviene escribir los textos entre comillas: sin ellas, `no` se lee como falso y no como texto.
- `correr_evals --recalificar <carpeta de corrida>` vuelve a medir una corrida guardada con los casos y el corrector vigentes, sin consultar: sirve para ver qué cambia en la medida al cambiar los datos clave.

## Reglas

- Solo material público.
- La respuesta esperada la valida una persona que conoce la materia, no un modelo.
- Un caso sin `visto_bueno` (quién de la Comisión lo aprobó y cuándo) no se corre. Los borradores asistidos llevan `redactado_por: borrador asistido` hasta que una persona los valida.
- Los casos existentes no se modifican ni se eliminan sin aprobación del responsable. Se pueden agregar.
- Cada corrida guarda sus resultados en `evals/corridas/` con fecha, commit y modelo, para poder comparar.

## Métricas

Recuperación, respuesta, cita y abstención, medidas por separado. Los umbrales de aceptación se fijan en la spec de cada feature.
