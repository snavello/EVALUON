# Plan 012 · Importación asistida desde el Portal de Compras

Estado: borrador · Fecha: 2026-10-05 · Aprobó: —

Spec: `specs/012-portal-compras/spec.md` (aprobada el 2026-10-05)

ADR de este plan, todos **propuestos**:

- `docs/adr/0030-importacion-portal-modulo-propio-y-propuesta-por-items.md`: módulo `evaluon/portal/` con una propuesta persistente de ítems; las cargas entran por los servicios de la 003 y la 008.
- `docs/adr/0031-conexion-acotada-al-portal-con-servicio-aparte.md`: servicio `portal_worker` aparte, único con salida a internet, y lista de destinos permitidos.
- `docs/adr/0032-lectura-de-la-pagina-del-portal-sin-navegador.md`: HTML con `lxml` y `beautifulsoup4`, formularios de ASP.NET con `urllib`, y texto mal codificado sin adivinar.
- `docs/adr/0033-revision-periodica-dentro-del-servicio-del-portal.md`: la revisión diaria la encola el bucle de `portal_worker`.

ADR en los que se apoya: 0018 (cola), 0024 y 0025 (ritmo de trabajo), 0026 (módulo propio y cola compartida), 0029 (Portal como primera fuente).

## Resumen del enfoque

Un módulo nuevo `evaluon/portal/`, con el mismo esquema de capas que `tenders/` y `offers/` (funciones de negocio que comprueban el rol y dejan el registro; pantalla y comandos solo traducen). El operador pega el enlace público del proceso. Un pedido en segundo plano (`portal_explore`), que atiende un servicio aparte con salida solo al Portal, baja la página del proceso, el acta, el dictamen, el cuadro comparativo y los documentos, los guarda tal cual con su huella y arma una **propuesta**: una lista de ítems (procedimiento, renglones, documentos, ofertas) con su origen. Nada se carga hasta que una persona aprueba. Al aprobar, cada ítem se carga **llamando a los servicios existentes**: `register_procedure`, `load_document` de la 003, `register_offer` de la 008; lo que esos servicios no pueden guardar (renglones, expediente, encuadre, cronograma, garantías, CUIT, total, garantía y cotización por renglón) va a tablas de `portal`.

La revisión periódica es el mismo pedido de exploración, encolado por el bucle del servicio una vez por día hábil o con un botón; compara con lo ya decidido y propone solo lo nuevo o cambiado.

El trabajo empieza por un **corte vertical** (ADR-0025): registrar el enlace, explorar y proponer datos básicos y renglones, aprobar y cargar el procedimiento, con un proceso inventado (calco de la estructura real). Después, en paralelo, documentos y ofertas; después, la revisión periódica; al final, la medición con el caso-00.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `portal_worker` | Sí | Corre `procesar_portal`: atiende `portal_explore` y `portal_review`, y encola la revisión diaria. Único con salida a internet, solo al Portal (ADR-0031) | `db`; Portal de Compras |
| `app` | Cambia | Páginas de importación: enlaces, propuesta, aprobación, novedades | `db` |
| `worker` | Cambia poco | Sigue atendiendo lectura de documentos y matrices; ignora los pedidos del Portal | `db`, IA |
| `db`, `migrate`, servicios de IA | No | Sin cambios | — |

Los servicios de IA no intervienen: la importación no usa modelos. Los documentos del pliego importados se leen después con el `worker`, como cualquier carga. El camino de pliegos y ofertas **no depende de internet** (P4): `portal_worker` solo baja y guarda; la lectura y la IA siguen en `worker`, que no tiene red de salida.

### Red y conexión (ADR-0029, ADR-0031)

- `docker-compose.yml`: red `egress` nueva (con salida), usada **solo** por `portal_worker`, que además está en `internal` para llegar a la base. La red `internal` sigue con `internal: true`.
- `PORTAL_ALLOWED_HOSTS` (variable de entorno, copiada a `settings.py`): lista de hosts permitidos; por omisión, el del Portal. El cliente (`evaluon/portal/client.py`) solo hace solicitudes HTTPS al puerto 443 de esos hosts, verifica cada redirección (no las sigue solo), limita el tamaño de la respuesta y la espera, y deja una pausa entre solicitudes. El enlace que se registra se valida contra la misma lista.
- Se documenta en `specs/012-portal-compras/entorno.md` (lo escribe T-138): qué servicio sale, a qué destinos, cómo comprobarlo, cómo cortarlo (`docker compose stop portal_worker`; el resto sigue y la carga manual no se afecta). El runbook de despliegue lo toma de ahí.
- Test que protege la regla: lee `docker-compose.yml` y comprueba que solo `portal_worker` usa `egress` y que `internal` sigue siendo interna.

### Cola compartida

`tenders_job` suma los tipos `portal_explore` y `portal_review` (`target_id` = id del enlace). Para el primer pedido, el procedimiento todavía no existe: `procedure` pasa a admitir nulo, solo para esos dos tipos (restricción en la base). `jobs.claim`, `run_next` y `fail_interrupted` reciben qué tipos atender; `procesar_pedidos` excluye los del Portal y `procesar_portal` atiende solo esos, de modo que al arrancar uno no pasa a fallidos los pedidos en curso del otro. El aviso de fin de la 003 sirve tal cual (el pedido lo pide el usuario que registró el enlace o apretó el botón).

## Estructura del código

```
evaluon/portal/
├── models.py  migrations/          tablas de este plan (ADR-0030)
├── client.py                       HTTP: sesión, GET, envío de formulario de ASP.NET, lista de destinos
├── parsing/                        funciones puras sobre bytes: pagina.py, acta.py, cuadro.py, texto.py (codificación)
├── importers/                      un archivo por tipo de ítem: procedure.py, documents.py, offers.py
│                                   (cada uno expone KIND, explore(context) y load(user, item); se descubren por nombre)
├── services/
│   ├── links.py                    registrar y validar el enlace, seguir o dejar de seguir (REQ-045)
│   ├── explore.py                  manejador de portal_explore y portal_review; arma la propuesta (REQ-046, REQ-047, REQ-050)
│   ├── approval.py                 aprobar o rechazar, todo o por ítem, y cargar (REQ-048, REQ-049)
│   └── schedule.py                 qué enlaces tocan hoy y encolar (REQ-050)
├── evaluation.py                   medición con las páginas guardadas (T-145)
├── views/  urls.py                 enlaces, propuesta, novedades
└── management/commands/            procesar_portal, medir_portal
evaluon/templates/portal/           enlaces, propuesta, items/<tipo>.html (un parcial por tipo)
tests/portal/                       conftest.py propio, FakePortal y páginas calcadas en data/
```

`evaluon/tenders/` cambia en tres lugares, todos en T-138: migración de `tenders_job` (dos tipos de pedido, `procedure` nulo para ellos), `jobs.py` (filtro por tipo y manejadores) y `procesar_pedidos.py` (excluir los del Portal). `evaluon/audit/` suma tipos de hecho. Nada de `offers/`.

## Modelo de datos

Nombres en inglés; valores de dominio en español sin tildes, como en la 003. Todo el esquema lo crea T-138 en una sola migración de `portal` (más las de `tenders_job` y `audit`), para que ninguna otra tarea lo toque.

**`portal_link`**: un proceso seguido. `url` (única; es el enlace público con su `qs`), `process_number` (se completa al explorar), `procedure` (FK a `tenders_procedure`, nulo hasta cargarlo o asociarlo), `following` (si se sigue revisando), `last_review_on` (fecha, para la revisión diaria), `created_at`, `created_by`.

**`portal_page`**: cada página o respuesta bajada. `link`, `exploration` (número de exploración del enlace), `kind` (`proceso`, `acta`, `dictamen`, `cuadro`), `url`, `fetched_at`, `sha256`, `content` (los bytes tal cual). Solo se insertan filas.

**`portal_file`**: cada documento bajado del Portal (pliego, circular, acto, acta, dictamen). `link`, `exploration`, `url`, `file_name`, `file_format`, `sha256`, `content`, `fetched_at`, `page` (la página donde aparece). Solo se insertan filas.

**`portal_proposal`**: una propuesta. `link`, `exploration`, `origin` (`importacion` o `revision`), `created_at`, `job`, `anomalies` (páginas que no se pudieron leer, con motivo).

**`portal_item`**: una cosa propuesta. `proposal`, `kind` (`procedimiento`, `renglones`, `documento`, `oferta`), `key` (estable entre exploraciones), `payload` (JSON: los datos propuestos), `content_sha256` (huella del contenido), `damaged_fields` (campos con caracteres dañados), `page` (FK a `portal_page`, el origen) y `file` (FK a `portal_file`, si es documento), `state` (`propuesto`, `aprobado`, `rechazado`, `cargado`, `fallido`), `decided_by`, `decided_at`, `loaded_model` y `loaded_id` (qué objeto creó o asoció: `tenders_procedure`, `tenders_document`, `offers_offer`), `failure` (motivo). El contenido de un ítem no se modifica; solo cambian su estado y sus campos de decisión (trigger de la base).

**Lo que no tenía lugar** (se llena al cargar un ítem aprobado; cada fila apunta al ítem que la originó, que es su origen):

- `portal_procedure_data`: `procedure` (uno a uno), `file_number` (expediente), `legal_framework`, `schedule` (JSON), `guarantees` (JSON), `item`.
- `portal_line`: un renglón. `procedure`, `number`, `description`, `quantity`, `unit`, `item`. Único por procedimiento y número.
- `portal_offer_data`: `offer` (uno a uno), `cuit`, `confirmed_on`, `currency`, `total`, `guarantee_type`, `guarantee_form`, `guarantee_amount`, `item`.
- `portal_quote`: `offer`, `line` (FK a `portal_line`), `price`, `quantity`. Único por oferta y renglón.

**Inmutabilidad.** Triggers rechazan UPDATE y DELETE en `portal_page` y `portal_file`, y UPDATE del contenido de `portal_item`.

**Origen y carga manual (REQ-049, REQ-051).** El origen de un dato o documento cargado es el ítem que lo creó (`loaded_model`, `loaded_id`) y su página (URL y fecha de consulta). Un documento sin ítem es una carga manual: la pantalla de importación lo muestra como "carga manual" y convive con lo importado; no se cambia nada de `tenders` ni de `offers`.

**Parámetros** (`settings.py`): `PORTAL_ALLOWED_HOSTS`, `PORTAL_TIMEOUT_SECONDS`, `PORTAL_MAX_BYTES`, `PORTAL_PAUSE_SECONDS`, `PORTAL_REVIEW_HOUR` (7), versión del lector de la página.

## Roles

Los de la 003:

| Operación | Operador | Evaluador |
|---|---|---|
| Registrar el enlace, explorar, "Revisar ahora", dejar de seguir, ver propuesta | sí | sí |
| Aprobar o rechazar ítems de tipo documento | sí | sí |
| Aprobar o rechazar los demás ítems (procedimiento, renglones, ofertas) o "aprobar todo" | no | sí |

Un usuario sin rol de la Comisión no ve estas páginas; el rechazo se registra como `rejected`.

## Flujo (REQ-045 a REQ-051)

**1. Registrar el enlace (REQ-045).** `links.register_link(user, url)`: comprueba el rol; acepta solo HTTPS de un host permitido y con la forma de enlace de proceso (`/PLIEGO/VistaPreviaPliegoCiudadano.aspx` con `qs`); si no, explica por qué (otro sitio, falta el `qs`, no es la página del proceso, ya está registrado). Guarda el enlace y encola `portal_explore`. Hecho `portal_link`.

**2. Explorar (REQ-046, REQ-047).** Lo hace `portal_worker`, sin IA:

1. Baja la página del proceso y la guarda (`portal_page`). Lee: datos básicos (número, expediente, objeto, tipo, encuadre legal, fecha de autorización), renglones con cantidad, cronograma, garantías y la lista de documentos con su enlace o su envío de formulario.
2. Baja los documentos (los de URL directa con GET; los de "Ver" con el envío de formulario de ASP.NET con los campos ocultos de la página) y los guarda con su huella (`portal_file`).
3. Si hay acta de apertura, la baja y la lee: por oferente, CUIT, fecha de confirmación, moneda, total, y tipo, forma y monto de la garantía. Si hay cuadro comparativo, lo baja con el envío de formulario y lee el precio y la cantidad por renglón de cada oferente.
4. Arma los ítems. Si el número del proceso ya está registrado como procedimiento (carga manual previa), el ítem `procedimiento` es "asociar al existente" y no "crear". Ofertas y documentos se proponen contra el procedimiento que exista o que se apruebe en la misma propuesta.
5. Una parte que no se puede leer o bajar no frena el resto: queda como anomalía de la propuesta ("no se pudo leer el acta: carga a mano") y el pedido termina bien (REQ-051 y requisito no funcional "Cambios del Portal"). Si no se puede leer ni la página del proceso, el pedido falla con el motivo.
6. Dedupe y revisión: para cada ítem, si hay un ítem anterior de la misma clave en estado `aprobado`, `cargado` o `rechazado` con la misma huella de contenido, no se vuelve a proponer. Con otra huella, se propone como cambiado y el ítem anterior queda como referencia.

Cada exploración deja el hecho `portal_explore` (o `portal_review`): URL de cada página y archivo con su huella y fecha, versión del lector, cantidad de ítems por tipo, anomalías, tiempos.

**3. Texto mal codificado (ADR-0032).** El lector intenta decodificar bien la página. Si el daño ya viene en los bytes, el texto se guarda tal cual y el ítem lleva `damaged_fields`; no se adivinan letras (P3). Los números, CUIT, fechas y montos se leen por formato.

**4. Aprobar (REQ-048).** Pantalla "Propuesta": una sola página con todos los ítems agrupados por tipo, cada uno con sus datos, su origen (página o documento, fecha de la consulta) y su marca de texto dañado, o de "ya está cargado", "falta el procedimiento" o "cambiado respecto de lo aprobado". Acciones: aprobar o rechazar un ítem, y "aprobar todo". `approval.decide(user, item_ids, decision)`:

1. Comprueba el rol por tipo de ítem (ver "Roles").
2. Procesa en orden: procedimiento, renglones, documentos, ofertas; un ítem que depende de otro no aprobado se rechaza con motivo ("falta el procedimiento") y queda en `propuesto`.
3. Un ítem aprobado se carga **en la misma transacción** que su decisión, llamando al servicio que corresponde (`importers/<tipo>.load`); si la carga falla (duplicado, formato, dato inválido), el ítem queda `fallido` con el motivo, no se carga nada de ese ítem, y los demás siguen.
4. Hecho `portal_decision` por cada ítem, aprobado, rechazado o fallido, con usuario y fecha.

Qué llama cada tipo de ítem:

| Ítem | Servicio existente | Datos propios |
|---|---|---|
| `procedimiento` (crear) | `tenders.services.procedures.register_procedure(user, number, procedure_type, subject, authorization_date, channel)` | `portal_procedure_data` |
| `procedimiento` (asociar) | ninguno: asocia `link.procedure` | `portal_procedure_data` |
| `renglones` | ninguno | `portal_line` |
| `documento` (pliego, anexo, circular) | `tenders.services.documents.load_document(user, procedure, data, file_name, kind, title, issued_on, channel)`; encola la lectura en la cola de la 003 | — |
| `documento` (acto, acta, dictamen) | ninguno: queda el original en `portal_file` con su origen, visible y descargable desde la pantalla de importación | — |
| `oferta` | `offers.services.offers.register_offer(user, procedure, bidder, channel)` | `portal_offer_data`, `portal_quote` |

Los documentos de las ofertas no son públicos: se cargan a mano con `offers.services.offers.load_document`, que no se toca. Una oferta importada y una oferta registrada a mano son lo mismo para la 008.

**5. Circulares.** El Portal puede no distinguir "modificatoria" de "aclaratoria", y el tipo cambia lo que hace la 003. Si el Portal no lo dice, el ítem lo muestra como "elegir tipo" y quien aprueba lo elige; el ítem no se aprueba sin tipo. La fecha de la circular sale del Portal; si no está, también se pide.

**6. Revisión periódica (REQ-050, ADR-0033).** `procesar_portal` en cada vuelta llama a `schedule.enqueue_due(now)`: encola `portal_review` para cada enlace con `following`, en día hábil (lunes a viernes), pasada la hora (`PORTAL_REVIEW_HOUR`), con `last_review_on` distinto de hoy y sin pedido en espera. "Revisar ahora" encola el mismo pedido. La revisión explora igual y propone solo lo nuevo o cambiado (paso 6 de la exploración). Si la propuesta de revisión no trae ítems, no se crea. En la pantalla "Enlaces" se ve cuántas novedades tiene cada proceso. Deja de seguirse cuando se decide el ítem del dictamen o con un botón.

## Pantalla

Páginas armadas en el servidor, sin htmx (ADR-0005), con la hoja de estilos de la 003.

- **Importar desde el Portal**: lista de enlaces (proceso, estado de la última exploración, novedades pendientes, "Revisar ahora", "Dejar de seguir"), registrar un enlace, y lo ya importado de cada proceso con su origen (página, fecha) o "carga manual".
- **Propuesta**: ver "Flujo, paso 4".
- Aviso de fin de pedido, el de la 003.

## Registro de auditoría (P6)

Tipos nuevos (caben en 20 caracteres): `portal_link`, `portal_explore`, `portal_review`, `portal_decision`.

| Hecho | Qué guarda además de los datos comunes |
|---|---|
| `portal_link` | URL, enlace, resultado y motivo si se rechazó; también los rechazos |
| `portal_explore` / `portal_review` | Enlace, exploración, URL, huella y fecha de cada página y archivo, versión del lector, ítems por tipo, ítems omitidos por ya decididos, anomalías, tiempos; con resultado `failed` y motivo si no se pudo |
| `portal_decision` | Enlace, ítem (tipo, clave, huella), decisión, usuario, resultado de la carga, objeto cargado (modelo e id) o motivo del fallo |
| `rejected` | Como en la 001 |

Las cargas por los servicios existentes dejan además sus propios hechos (`procedure`, `tender_load`, `offer_register`). Con eso se reconstruye de dónde salió cada dato, quién lo aprobó y cuándo.

## Medición (ADR-0025)

Con las páginas guardadas, sin conexión. Lista esperada de caso-00 preparada por el Coordinador leyendo el Portal (T-139), fuera del repositorio, en `corpus/casos/caso-00/esperado/portal-esperado.yaml`, con huella y visto bueno, como las de la 003 y la 008. Para los tests y el corte vertical hay un caso chico en el repositorio: páginas **calcadas** (misma estructura HTML, mismos problemas de codificación, CUIT y nombres inventados) en `tests/portal/data/`. Las páginas reales viven solo en `corpus/casos/caso-00/portal/` (P4); los tests nunca las leen.

### Umbrales, escritos antes de medir

| Medida | Caso chico (T-141 a T-143) | Caso-00 real y proceso con circulares (T-145) |
|---|---|---|
| Datos del procedimiento propuestos iguales a los del Portal (número, expediente, objeto, tipo, encuadre, fecha de autorización, cronograma, garantías) | 100 % | 100 % |
| Renglones con su cantidad (REQ-046) | 6 de 6 | 6 de 6 |
| Documentos de la lista con su origen (REQ-046) | 100 % | 100 % |
| Huella del documento cargado = huella del archivo bajado (REQ-049) | 100 % | 100 % |
| Ofertas con total y garantía (REQ-047) | 3 de 3 | 3 de 3 |
| Pares oferta y renglón con precio y cantidad (REQ-047) | 18 de 18 | 18 de 18 |
| Novedad (circular agregada) propuesta, y nada ya aprobado repetido (REQ-050) | 100 % | 100 % |
| Nada cargado sin aprobación (REQ-048) | 100 % | 100 % |

Todos bloquean. "Igual al Portal" es igual a lo que el Portal muestra, incluidos los caracteres dañados.

### Rondas

Caso chico: se corrige dentro de cada tarea. Caso-00 (T-145): una medición base; si no llega al umbral, una sola ronda de corrección en la misma tarea y una medición más; lo que falte después pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024). Una ronda más solo si el faltante hace perder un requisito o viola un principio (ADR-0025).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-045 | "Flujo, paso 1": `links.register_link`, validación de host, pedido `portal_explore`; "Red y conexión" | T-141: test de enlace válido, de otro sitio, sin `qs` y repetido; T-138: lista de destinos |
| REQ-046 | "Flujo, paso 2": lector de la página (`parsing/pagina.py`), renglones, cronograma, garantías, lista de documentos (T-140); documentos (T-142) | Tests con el caso chico (100 %, 6 renglones); medición T-145 con caso-00 |
| REQ-047 | "Flujo, paso 2, ítem 3": lector de acta y cuadro (`parsing/acta.py`, `cuadro.py`), ítem `oferta` y `portal_quote` (T-143) | Tests con el caso chico (3 ofertas, 18 pares); medición T-145 |
| REQ-048 | "Flujo, paso 4": `approval.decide`, roles por tipo de ítem, hecho `portal_decision` (T-141; documentos T-142; ofertas T-143) | Test: aprobar una parte y rechazar otra, solo se carga lo aprobado, ambos quedan con autor y fecha; sin aprobación nada se carga; el operador solo aprueba documentos |
| REQ-049 | `portal_page`, `portal_file`, `portal_item` con página y fecha; huella del archivo (T-141, T-142) | Test: documento importado con su página, su fecha y su huella igual a la del archivo bajado |
| REQ-050 | "Flujo, paso 6" y ADR-0033: `schedule.enqueue_due`, revisión y dedupe por huella (T-144) | Test con reloj falso (día hábil, fin de semana, ya revisado hoy) y con una circular agregada que aparece y no repite lo aprobado |
| REQ-051 | La carga manual no se toca; el origen "carga manual" es la ausencia de ítem (T-142, T-143); una parte no leída del Portal queda como anomalía y no frena el resto | Test: documento de una oferta cargado a mano junto a una oferta importada, con origen "carga manual"; test de una página que cambió |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada tarea nombra sus REQ |
| P2 Trazabilidad | sí | Tabla de cobertura; tareas con REQ |
| P3 El sistema recomienda | sí | El sistema propone y una persona aprueba; el texto dañado no se adivina; lo que no se puede leer figura como anomalía |
| P4 Datos | sí, con la excepción del ADR-0029 | Solo `portal_worker` sale, solo al Portal y solo a leer; pliegos y ofertas siguen en el equipo y en `worker` sin red; los tests usan calcos inventados; las páginas reales, fuera del repositorio |
| P5 Local y reproducible | sí | Un servicio más con la misma imagen; entorno documentado en `entorno.md` |
| P6 Auditoría | sí | Ver "Registro de auditoría" |
| P7 Evals | sí | Medición con lista esperada; no hay cambios de IA |
| P10 Simplicidad | sí | Sin navegador, sin proxy, sin programador externo, sin calendario de feriados; no compara ofertas ni usa IA |
| P11 Compuertas | sí | El plan queda en borrador hasta que lo apruebe el responsable |

## Qué no se hace

Buscar procesos en el Portal (CAPTCHA); los documentos de las ofertas (no son públicos); escribir en el Portal; resolver o evitar el CAPTCHA; comparar la cotización del Portal con la de la oferta (006/004); calendario de feriados.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El Portal cambia el HTML o el formulario | No se puede leer una parte | Lectores puros por parte, anomalía visible, el resto sigue; carga manual (REQ-051); los calcos sirven para detectar el cambio al comparar con una página nueva |
| Los postbacks de ASP.NET no se pueden armar sin JavaScript | No se bajan el pliego o el cuadro comparativo | T-142 y T-143 lo comprueban primero con las páginas reales; si falla, la parte queda "no se pudo importar" y se vuelve al ADR-0032 |
| Texto con caracteres dañados que ya viene roto | `¿¿` en el objeto o los títulos | No se adivina; marca visible en la propuesta; se mide contra lo que muestra el Portal; T-140 confirma cuál de los dos casos es |
| El Portal no informa la fecha de autorización o el tipo de circular | Falta un dato obligatorio | La propuesta lo marca y quien aprueba lo completa; sin él el ítem no se aprueba |
| `portal_worker` sale a cualquier destino si se altera el código | Se rompe P4 | Lista de destinos probada en el cliente, test del compose, `entorno.md`; el proxy filtrante queda como paso siguiente (ADR-0031) |
| Dos consumidores de la cola se pisan | Pedidos tomados o cortados por el otro | Filtro por tipo en `claim` y en `fail_interrupted`, con test de ambos |
| Cargar en la base datos de oferentes con nombres de personas físicas | Datos personales en el repositorio | Solo en la base y en `corpus/casos/`; los tests y las fixtures usan calcos con datos inventados |
| Exceso de pedidos al Portal | Bloqueo del equipo | Una revisión por día y enlace, pausa entre solicitudes, tope de tamaño y de espera, `User-Agent` identificado |
| Una propuesta de revisión repite lo ya decidido | Ruido para la Comisión | Dedupe por clave y huella, con test |

## Decisiones

ADR 0030, 0031, 0032 y 0033, propuestos.

## Puntos para el responsable

1. Acta de apertura, dictamen y actos administrativos: ¿se guardan como archivos del Portal con su origen y huella, sin pasar a documentos del pliego de la 003 (no son pliego; la 003 no los lee)? Propuesta: sí.
2. Tipo de circular (modificatoria o aclaratoria): si el Portal no lo dice, lo elige quien aprueba. Propuesta: sí.
3. Revisión periódica: "día hábil" es lunes a viernes, sin feriados, a las 7:00 hora de Buenos Aires; el seguimiento termina al decidirse el dictamen o con un botón. Propuesta: sí.
4. Texto con caracteres dañados que el Portal ya entrega roto: se muestra tal cual y marcado, sin adivinar letras. Propuesta: sí.
5. Conexión: `portal_worker` con salida a internet a nivel de red y filtro por destino en el código; el proxy con filtro de dominio queda para después (ADR-0031). Propuesta: sí.
6. Para medir hace falta un segundo proceso público, con circulares, y el host real del Portal para `PORTAL_ALLOWED_HOSTS`: los consigue el Coordinador (T-139).
