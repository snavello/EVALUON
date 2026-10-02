# ADR-0005 · Aplicación web, pantalla de consulta, acceso y comandos

Estado: propuesto · Fecha: 2026-10-02 · Decidió: —

## Contexto

Los otros ADR de la feature deciden cómo se leen las normas, cómo se buscan y con qué modelo se redacta la respuesta. Falta decidir el programa que junta todo eso y lo pone delante de las personas: la pantalla donde la Comisión escribe su pregunta, el ingreso con usuario y clave, y los comandos con los que el responsable de normativa carga y valida las normas. Es una decisión difícil de revertir porque todas las features siguientes (revisión de pliegos, evaluación de ofertas) se construyen encima.

Son cuatro partes que se deciden juntas porque dependen una de otra:

1. **Estructura de la aplicación:** con qué herramienta de Python se arma, cómo se ordena el código, cómo se accede a Postgres y cómo se cambian las tablas con el tiempo.
2. **Pantalla de consulta (REQ-013, REQ-014).**
3. **Acceso (REQ-016):** usuario y clave, dos roles, claves no legibles, sesiones, rechazo con registro.
4. **Operaciones sin pantalla:** cargar una norma, ver y validar su informe de lectura, registrar relaciones y versiones, dar de alta usuarios. La spec las deja sin pantalla en esta feature.

Qué condiciona la decisión:

- **Quién construye.** Una persona con agentes de IA que arrancan cada tarea sin memoria de la anterior. Conviene una herramienta con convenciones fuertes y pocas piezas que ensamblar.
- **Quién usa.** La Comisión Evaluadora, que no es personal técnico. Textos en lenguaje llano.
- **Sin conexión (P4, spec).** La pantalla no puede cargar tipografías, scripts ni estilos desde internet.
- **Espera.** Una consulta puede tardar hasta 30 segundos. El ADR-0002 establece que la respuesta llega completa, sin transmisión parcial, porque el sistema la valida e inserta las citas antes de mostrar nada.
- **Forma de la respuesta (definición compartida).** Texto dividido en afirmaciones; por cada afirmación, las unidades citadas (documento, categoría, tipo y ruta de la unidad, texto literal, enlace al original) y la marca `regimes_differ` cuando el régimen específico y el marco nacional tratan el punto de manera distinta; y un estado: "con fundamento" (`grounded`), "no determinado" (`undetermined`) o falla técnica (`error`). La forma exacta está en el plan.
- **Reuso.** La feature 002 suma carga y revisión de pliegos; la 004, una pantalla donde la Comisión confirma, corrige o rechaza cada requisito. Son formularios con usuarios identificados y registro de quién decidió qué (P3, P6).
- **Auditoría (P6, REQ-012).** Lo que se hace por pantalla y lo que se hace por comando deben pasar por el mismo control de roles y dejar el mismo registro.
- **Volumen (P10).** Menos de 10 documentos y pocos usuarios a la vez.
- **Docker (P5).** Todo se levanta con Docker Compose y se muda a otro equipo.

Entorno (dato a confirmar por el responsable): notebook MSI con Intel Core Ultra 9 (24 núcleos), 32 GB de RAM y GPU NVIDIA RTX 5090 de notebook con 24 GB de memoria de video; Windows con WSL2, Docker Desktop 29, Python 3.12. Ya corre Postgres 17 con pgvector 0.8 (imagen `pgvector/pgvector:pg17`) con una base `evaluon`.

Lo que este ADR recibe de los otros: el motor de generación es un servicio HTTP dentro de la red de Docker (ADR-0002); embeddings y reranker son otros dos servicios HTTP, y la búsqueda se hace con SQL sobre una vista de Postgres (ADR-0003); la lectura de documentos usa bibliotecas de Python y Tesseract, en CPU (ADR-0004). La aplicación los usa; no los decide.

Las versiones y fechas de este documento se consultaron el 2026-10-02; las fuentes están numeradas al final. Lo que no se pudo confirmar está en "Sin verificar".

## Alternativas

### Parte 1 · Estructura de la aplicación

Lo que la spec pide a esta parte es poco habitual para un sistema "de IA": casi nada de lo que hay que construir es una API. Hay que resolver ingreso, sesiones, roles, formularios, tablas que cambian con el tiempo, comandos y pruebas. La IA queda detrás de tres servicios HTTP.

#### A. Django

Marco de trabajo web "con todo incluido". Versión 6.1.1 (2 de septiembre de 2026), requiere Python 3.12 o superior [1]. La serie 6.1 tiene soporte hasta diciembre de 2027; la 6.2, prevista para abril de 2027, es de soporte largo hasta abril de 2030 [2]. Soporta PostgreSQL 15 o superior con psycopg 3 [11].

Qué trae resuelto, sin sumar bibliotecas:

- Usuarios, ingreso y salida, con cambio del identificador de sesión al ingresar y señales para registrar ingresos fallidos [4].
- Claves guardadas con una función de derivación; PBKDF2 por defecto y Argon2 con una línea de configuración [6].
- Sesiones guardadas en la base, con solo un identificador en la cookie [7].
- Protección de formularios contra envíos falsificados (CSRF) y, desde la versión 6.0, cabecera de política de contenido (CSP) [9].
- Acceso a la base y migraciones del esquema generadas a partir de los modelos.
- Comandos propios (`manage.py`), que se prueban con `call_command` [10].
- Plantillas de página con escape automático y cliente de pruebas.

Se gana: la parte más delicada de REQ-016 (claves, sesiones, formularios) no se escribe a mano: se configura y se prueba. Una sola herramienta con una sola documentación y una forma establecida de ordenar el código, lo que ayuda a agentes que arrancan sin contexto. Es la herramienta pensada para lo que piden la 002 y la 004: formularios con usuarios identificados.

Se pierde:

- Trae más de lo que se usa (panel de administración, grupos y permisos finos). No se activan; son piezas que quedan disponibles, no código que mantener.
- El código de normas y consultas queda escrito con los modelos de Django: no corre sin Django configurado. Las evals y los comandos corren dentro de él.
- La búsqueda combinada del ADR-0003 (vista, búsqueda de texto con configuración propia, vectores) no se expresa bien con los modelos: va como SQL directo, y la vista y la configuración de texto se crean con SQL dentro de las migraciones. Django lo permite, pero ahí no ayuda.
- Las versiones que no son de soporte largo duran unos 16 meses: hay que pasar a la 6.2 durante 2027.

#### B. FastAPI con piezas elegidas una por una

FastAPI 0.142.2 (30 de septiembre de 2026) [13], sobre Starlette 1.7.0 [16], con plantillas Jinja2 [14], SQLAlchemy 2.1.2 [18] y Alembic 1.20.0 [19] para la base y las migraciones, y Typer 0.27.2 [20] para los comandos. Es la opción más difundida para servicios de IA en Python.

Se gana: más liviano, cada pieza se entiende por separado, validación de datos con tipos, buen soporte para respuestas transmitidas de a poco y documentación automática de la API.

Se pierde:

- Lo que FastAPI hace mejor (API en JSON, transmisión parcial, documentación de la API) acá no se usa: no hay API pública y el ADR-0002 descarta la transmisión parcial.
- No trae usuarios, sesiones ni protección de formularios. Su tutorial de seguridad enseña a guardar claves con `pwdlib` y Argon2 [15], pero el ingreso, la tabla de sesiones, las cookies, el cambio de identificador al ingresar y la protección CSRF hay que escribirlos y probarlos. Es código de seguridad propio, justo el que un auditor mira con más cuidado.
- La sesión que ofrece Starlette guarda los datos en una cookie firmada: se pueden leer y no se pueden anular desde el servidor [17]. Para cumplir con las recomendaciones de sesiones habría que hacer una propia.
- Son seis o siete bibliotecas con sus versiones para fijar y actualizar, y las convenciones de carpetas hay que inventarlas y sostenerlas entre agentes.

#### C. Flask con extensiones

Flask 3.1.3 (19 de febrero de 2026) [21]. Mismo armado por piezas que B (ingreso, formularios, base y migraciones vienen de extensiones de terceros), sin las ventajas de B en tipos y validación. No se evaluó en detalle.

#### Acceso a la base y migraciones

Va atado a la alternativa anterior:

- **Con A:** modelos y migraciones de Django para las tablas comunes; SQL directo por la misma conexión para la búsqueda del ADR-0003; el paquete `pgvector` de Python (0.5.0) trae integración con Django para la columna de vectores [23].
- **Con B o C:** SQLAlchemy y Alembic. Equivalente en capacidad; dos piezas más.
- **SQL a mano con psycopg 3.3.6 [22] y archivos de migración propios:** la menor cantidad de capas, pero habría que escribir el mecanismo que aplica y revierte migraciones, que el implementador necesita probado.

### Parte 2 · Pantalla de consulta

#### P1. Páginas armadas en el servidor, con plantillas

El servidor arma la página completa y el navegador la muestra. Los elementos propios de HTML alcanzan para lo que piden REQ-013 y REQ-014: un formulario para la pregunta y un desplegable nativo (`<details>`) para ver el texto literal de cada cita, sin programar nada en el navegador.

Se gana: una sola tecnología (Python y plantillas), sin paso de compilación ni Node.js; las pruebas piden una página y revisan el HTML, sin navegador; sin conexión por construcción, porque todo sale del propio servidor; el control de roles y el registro ocurren en un solo lugar.

Se pierde: cada acción recarga la página. Para una pregunta y su respuesta no molesta. Para la pantalla de la 004, con decenas de requisitos y botones por fila, recargar todo en cada clic sí molesta.

**Variante con htmx.** htmx es un único archivo de JavaScript (unos 14 KB, sin dependencias) que se copia al proyecto y permite que un botón actualice solo un pedazo de la página, con atributos en el HTML [29]. La versión 2.0.11 es la que npm marca como vigente y tiene soporte indefinido; la 4.0.0 salió el 28 de agosto de 2026 y queda como "próxima" hasta principios de 2027 [30][32]. Se gana: resuelve la pantalla de la 004 sin cambiar de enfoque. Se pierde: agrega casos que hay que manejar a mano (una respuesta de error no se muestra sola; una sesión vencida puede terminar insertando la página de ingreso dentro de un recuadro), y la versión 4 cambia cómo se heredan los atributos, incluidos los que llevan el control CSRF [31].

#### P2. Aplicación de una sola página con un marco de JavaScript

Por ejemplo React 19.3.0 [33] con Vite 8.3.2, que requiere Node.js 20.19 o superior [34]. El navegador recibe un programa que pide datos a una API y dibuja la pantalla.

Se gana: la interacción más rica y fluida.

Se pierde: obliga a construir y proteger una API en JSON que ningún requisito pide; suma un segundo lenguaje, un paso de compilación y un contenedor o etapa de Node.js en Docker; duplica las pruebas (servidor y navegador); el control de sesión hay que resolverlo también del lado del navegador. Para una pantalla con un cuadro de texto y una lista de citas es desproporcionado (P10).

#### P3. Herramienta de prototipos: Streamlit o Gradio

Streamlit 1.64.0 [35] y Gradio 6.29.0 [39]. Se describe la pantalla en Python y la herramienta la dibuja.

Se gana: es la forma más rápida de tener una pantalla de preguntas y respuestas funcionando.

Se pierde:

- **Acceso.** La autenticación propia de Streamlit funciona solo con proveedores de identidad OpenID Connect [36]: no cubre usuario y clave guardados localmente sin sumar un componente de terceros o un proveedor de identidad. Gradio acepta una función que valida usuario y clave, pero su documentación advierte que es una capa básica, sin funciones de seguridad robustas, y que necesita cookies de terceros habilitadas en el navegador [40].
- **Sin conexión.** Streamlit envía estadísticas de uso salvo que se desactive [37]. Sobre Gradio hay un reporte de terceros de que la versión 6.26 hace llamadas a internet (estadísticas, control de versión y tipografías de Google) [41]; las estadísticas se desactivan por configuración [40]. Cumplir P4 pasa a depender de configuraciones.
- **Reuso.** Son herramientas para demostraciones. La pantalla de la 004, los roles y el registro de auditoría habría que forzarlos dentro de un modelo pensado para otra cosa, y los comandos y el ingreso quedarían en un programa aparte.
- **Control de la presentación.** REQ-014 y REQ-018 piden una presentación precisa (aviso propio para "no determinado", categoría y orden de las citas). Se puede, pero dentro de los componentes que la herramienta ofrece.

Streamlit trae una forma propia de probar pantallas sin navegador [38].

### Parte 3 · Claves y sesiones

Referencia usada: las guías vigentes de OWASP.

- **Guardado de claves:** Argon2id como primera opción, con un mínimo de 19 MiB de memoria, 2 iteraciones y 1 hilo; scrypt si Argon2id no está disponible; bcrypt solo para sistemas heredados, con límite de 72 bytes; PBKDF2 con 600.000 iteraciones o más si se exige FIPS-140 [42].
- **Sesiones:** identificador al azar de al menos 64 bits, sin significado, con los datos del lado del servidor; cookie con `HttpOnly`, `Secure` y `SameSite`; identificador nuevo al ingresar; vencimiento controlado por el servidor (15 a 30 minutos de inactividad para aplicaciones de bajo riesgo, 4 a 8 horas de tope); salida que anule la sesión en el servidor; toda la sesión por HTTPS [43].
- **Ingreso:** mensaje de error genérico, registro de todos los intentos fallidos, claves largas sin reglas de composición (sin segundo factor, menos de 15 caracteres se considera débil) [44].

#### Guardado de claves

**C1. Argon2id, con el mecanismo de Django y la biblioteca `argon2-cffi`.** `argon2-cffi` 25.1.0 (3 de junio de 2025) [46]. Se activa poniendo Argon2 primero en la lista de algoritmos de Django [6]. Se gana: es la primera opción de OWASP. Se pierde: una biblioteca más, cuya última versión tiene más de un año (es una biblioteca madura y chica; no es señal de abandono, pero conviene saberlo).

**C2. PBKDF2, el valor por defecto de Django.** 1.500.000 iteraciones con SHA-256 en la versión 6.1 [3]. Se gana: ninguna biblioteca adicional, y supera el mínimo de OWASP para PBKDF2. Se pierde: OWASP lo ubica como opción para cuando se exige FIPS-140, no como primera elección.

**C3. bcrypt.** Descartado: OWASP lo reserva para sistemas heredados [42].

Con la alternativa B de la parte 1 las opciones serían `argon2-cffi` directo o `pwdlib` 0.3.1 (12 de agosto de 2026), que es joven y nació para reemplazar a `passlib` [48]; `passlib` no publica versiones desde octubre de 2020 [49] y se descarta.

Cambiar entre C1 y C2 más adelante no obliga a nada a los usuarios: Django vuelve a guardar la clave con el algoritmo preferido la próxima vez que cada uno ingresa [6].

#### Sesiones

**S1. Sesiones en Postgres.** Es el valor por defecto de Django: la cookie lleva solo un identificador al azar y los datos están en una tabla [7]. Se gana: la salida anula la sesión en el servidor, una sesión se puede cortar borrando su fila, y coincide con lo que recomienda OWASP. Se pierde: las sesiones vencidas no se borran solas; hay que correr `clearsessions` cada tanto [7].

**S2. Sesión dentro de una cookie firmada.** Sin tabla. La documentación de Django advierte que los datos son legibles por el usuario, que la sesión no se anula al salir y que una cookie robada sigue sirviendo [7]. Es también lo que ofrece Starlette [17]. Descartada.

**S3. Credenciales tipo JWT.** Pensadas para API consumidas por otros programas. Sin una tabla adicional no se pueden anular antes de que venzan. No hay API que proteger. Descartada.

### Parte 4 · Comandos

**L1. Comandos de Django que llaman a las mismas funciones que la pantalla.** Cada operación es un comando de `manage.py`, que se corre dentro del contenedor de la aplicación. El comando pide usuario y clave de EVALUON, los verifica contra la misma tabla y llama a la función de negocio, que es la que controla el rol y deja el registro. Se gana: sin bibliotecas nuevas, un único control de roles y un único registro para pantalla y comandos, y se prueba con `call_command` [10]. Se pierde: hay que escribir la clave en cada comando.

**L2. Comandos sin clave, confiando en quien tiene acceso al equipo.** El comando recibe el nombre de usuario y le cree. Se gana: comodidad. Se pierde: el "quién" del registro (REQ-012) deja de estar comprobado, y la prueba de REQ-016 (un usuario de lectura que intenta cargar es rechazado) pierde sentido.

**L3. Programa de comandos aparte que le habla a la aplicación por una API.** Se gana: se podría usar desde otra máquina. Se pierde: hay que construir, proteger y probar una API que nada más usa (P10).

## Decisión

Se propone: **A + P1 + C1 + S1 + L1.**

1. **Aplicación: Django 6.1**, con PostgreSQL por psycopg 3, migraciones de Django y SQL directo donde el ADR-0003 lo necesita. Se pasa a la 6.2 de soporte largo cuando salga.
2. **Pantalla: páginas armadas en el servidor con plantillas de Django**, HTML y una hoja de estilos propia, todo servido por la aplicación. En la 001 no se incorpora htmx: nada de lo que piden REQ-013 y REQ-014 lo necesita. htmx queda designado como la forma de sumar actualizaciones parciales cuando un requisito las pida (se espera en la 004); la versión se elige en ese momento.
3. **Claves: Argon2id** con el mecanismo de Django y `argon2-cffi`.
4. **Sesiones: en Postgres**, con el mecanismo de Django.
5. **Comandos: de Django**, con usuario y clave de EVALUON, sobre las mismas funciones que usa la pantalla.

Motivo principal: lo que hay que construir fuera de la IA es exactamente lo que Django trae hecho y probado (usuarios, claves, sesiones, formularios protegidos, migraciones, comandos, pruebas). Elegir B obligaría a escribir a mano el código de seguridad y a ensamblar y mantener varias bibliotecas, para ganar ventajas que este sistema no usa. La IA no pesa en la elección: vive detrás de servicios HTTP y le da igual quién la llame.

### Cómo se ordena el código

Cuatro módulos de Django, más un paquete con los clientes de los servicios de IA. La regla de capas es una sola: **las funciones de negocio (`services.py`) reciben al usuario que actúa, comprueban su rol y dejan el registro de auditoría; las vistas de pantalla y los comandos solo traducen y llaman.** Así no hay forma de hacer una operación salteando el control o el registro.

```
evaluon/                          raíz del repositorio (existe)
├── docker-compose.yml
├── Dockerfile                    imagen de la aplicación
├── .env.example
├── pyproject.toml                dependencias con versión fija; configuración de pytest
├── manage.py                     entrada de los comandos
├── evaluon/                      código de la aplicación
│   ├── settings.py  urls.py  wsgi.py
│   ├── accounts/                 usuarios, roles, ingreso y salida (REQ-016)
│   │   ├── models.py             usuario con su rol
│   │   ├── permissions.py        comprobación de rol; la usan todas las funciones de negocio
│   │   ├── views.py  urls.py
│   │   ├── migrations/
│   │   └── management/commands/  alta de usuarios
│   ├── audit/                    registro de auditoría (REQ-012, P6)
│   │   ├── models.py  services.py  migrations/
│   ├── norms/                    normas, documentos, lecturas, unidades, pasajes, relaciones, versiones
│   │   ├── models.py  migrations/
│   │   ├── services/             un archivo por operación: carga, validación, relaciones, versiones, listado
│   │   ├── reading/              lectura por formato (ADR-0004)
│   │   ├── splitting/            partición en unidades e informe de lectura (ADR-0004)
│   │   ├── indexing.py           pasajes y vectores de una lectura (ADR-0003)
│   │   ├── views.py  urls.py     entrega del documento original (REQ-002)
│   │   └── management/commands/  carga, relectura, listado, informe, validación, relaciones, versiones
│   ├── queries/                  consulta con cita y búsqueda directa
│   │   ├── retrieval.py          búsqueda combinada sobre la vista (ADR-0003)
│   │   ├── answering.py          pedido al modelo, validación e inserción de citas (ADR-0002)
│   │   ├── prompts/              instrucciones versionadas
│   │   ├── search.py             búsqueda por norma y artículo, y por palabras (REQ-010)
│   │   ├── services.py           una consulta o una búsqueda de punta a punta, con su registro
│   │   ├── evaluation.py         corrida del conjunto de preguntas (P7)
│   │   ├── views.py  urls.py  forms.py
│   │   ├── models.py  migrations/
│   │   └── management/commands/  corrida de evals
│   ├── ai/                       clientes HTTP de los servicios de IA
│   │   ├── generation.py         motor de generación (ADR-0002)
│   │   ├── embeddings.py         (ADR-0003)
│   │   └── reranker.py           (ADR-0003)
│   ├── templates/                base, ingreso, consulta
│   └── static/                   hoja de estilos y script propios; nada externo
├── tests/
│   ├── conftest.py               usuarios de prueba; dobles de los tres servicios de IA
│   ├── accounts/  audit/  norms/  queries/
│   └── fixtures/                 documentos públicos chicos o sintéticos
├── evals/  corpus/               (existen)
└── specs/  docs/  tools/         (existen)
```

- Un módulo por tema, cada uno con sus migraciones, para que dos desarrolladores en paralelo no pisen el mismo archivo de migración. Las features 002 y 004 suman módulos nuevos (pliegos, evaluación) y reusan `accounts`, `audit` y `ai`.
- `ai/` no es un módulo de Django: son tres clientes HTTP chicos. Existen como pieza separada por una razón concreta: las pruebas los reemplazan por dobles, de modo que la suite corre sin GPU y sin modelos. Las evals (P7) usan los servicios reales.
- El rol es un campo del usuario con dos valores (`read`, `read_write`). No se usan los grupos y permisos de Django: la spec define dos roles y deja los demás fuera de alcance.
- El usuario se define como modelo propio desde la primera migración. La documentación de Django lo recomienda al empezar un proyecto, porque cambiarlo después obliga a corregir el esquema a mano [5].
- No se activa el panel de administración de Django: la spec deja fuera de alcance las pantallas de carga y de usuarios.
- Qué tablas y campos lleva cada módulo lo fija el plan, con lo que definen los ADR-0003 y ADR-0004. La vista de unidades consultables, la configuración de búsqueda de texto y las extensiones (`vector`, `unaccent`) se crean con SQL dentro de migraciones, cada una con su reversa.

### Servicios de Docker Compose

| Servicio | Qué es | Lo decide | Puerto publicado |
|---|---|---|---|
| `db` | Postgres con pgvector, imagen fijada a una versión concreta | Existente; ADR-0003 | No |
| `generation` | Motor de generación | ADR-0002 | No |
| `embeddings` | Servidor de embeddings; misma imagen que `generation` | ADR-0003 | No |
| `reranker` | Servidor de reranker; misma imagen que `generation` | ADR-0003 | No |
| `migrate` | Aplica las migraciones si la base está vacía, o comprueba que no haya pendientes, y termina; misma imagen que `app` | Este ADR | No |
| `app` | La aplicación: pantalla y comandos | Este ADR | Sí, solo en `127.0.0.1` |

- **Una sola imagen propia**, sobre Python 3.12. Incluye Tesseract y su modelo de español, porque la carga de normas (ADR-0004) corre en este contenedor, en CPU. La imagen no lleva PyTorch ni usa la GPU.
- **Servidor web:** Gunicorn 26.2.0 [24], para el que la documentación de Django trae una guía propia [12], con un proceso y varios hilos. Su tiempo de espera por defecto es de 30 segundos, pasado el cual reinicia al proceso que no responde [25]: coincide con el máximo de una consulta, así que hay que subirlo (propuesta: 120 segundos).
- **Archivos estáticos:** los sirve la propia aplicación con WhiteNoise 6.12.0 [26]. Evita sumar un servidor web aparte.
- **No se agregan:** servidor web intermedio, cola de tareas ni caché. Ningún requisito los pide y con pocos usuarios no hacen falta (P10).
- **Migraciones al levantar:** `migrate` corre antes que `app`. Sobre una base vacía aplica las migraciones, para que un equipo limpio llegue al sistema funcionando con un solo comando (P5). Sobre una base que ya tiene datos no migra: solo comprueba, y si hay cambios pendientes termina con error y `app` no arranca. En ese caso el runbook indica detener, respaldar la base y aplicar la migración a mano, en ese orden.
- **Pruebas:** `docker compose run --rm app pytest`, contra el servicio `db`, en una base de prueba aparte que pytest-django crea y borra.
- **Comandos:** `docker compose exec app python manage.py <comando>`. La carpeta `corpus/` se monta en el contenedor en modo de solo lectura para poder cargar documentos desde ahí.
- El nombre de los servicios de IA y sus imágenes los fijan sus ADR; acá se listan para mostrar el conjunto. La aplicación los encuentra por variables de entorno.

### Pantalla de consulta

Una página, armada sobre la forma acordada de la respuesta.

- **Arriba:** nombre del sistema, usuario que ingresó y botón "Salir".
- **Pregunta:** un cuadro de texto y el botón "Consultar".
- **Búsqueda (REQ-010):** en la misma página, un formulario para buscar por norma y número de artículo, o por palabras del texto. Cada resultado muestra la unidad con su ruta, su categoría, su texto literal y el enlace al original; una unidad derogada aparece marcada como tal.
- **Resultado:** uno de tres bloques, que se distinguen por título, ícono y color a la vez (no solo por color, para quien no los distingue):
    1. **"Respuesta con fundamento en la normativa".** La lista de afirmaciones. Debajo de cada una, sus citas en el orden en que llegan (el orden por categoría lo fija el código de búsqueda, ADR-0003). Cada cita muestra: la categoría con su papel en palabras ("Régimen específico · es lo que se aplica", "Marco nacional · marco de referencia", "Dictamen legal · criterio que acompaña"), el documento y la ubicación de la unidad. Un considerando se rotula "Considerando · contexto" y va después del articulado. Cuando la afirmación trae la marca `regimes_differ`, se agrega un aviso de texto fijo que dice que los dos regímenes tratan el punto de manera distinta y que se aplica el régimen específico (REQ-019). Al elegirla se despliega el texto literal y el enlace "Abrir el documento original". Si el texto de la unidad salió de reconocimiento sobre imagen (REQ-015), la cita lo dice.
    2. **"No determinado".** Aviso propio, con el texto "La normativa cargada no permite responder esta pregunta", sin afirmaciones y sin citas (REQ-014).
    3. **"No se pudo completar la consulta".** Para una falla técnica o una espera agotada. Es un bloque distinto a propósito: una falla no es un "no determinado" y no debe leerse como tal (P3).
- **Espera.** Al enviar la pregunta, el botón se desactiva y aparece el cartel "Buscando en la normativa. Puede tardar hasta medio minuto." Lo hace un script propio de pocas líneas servido por la aplicación; sin él, el formulario funciona igual. No hay texto que aparezca de a poco: la respuesta se muestra entera o no se muestra (ADR-0002). La aplicación corta la espera a un tiempo configurado (propuesta: 60 segundos) y muestra el tercer bloque.
- **Recarga.** La consulta se guarda con su registro y la página muestra el resultado a partir de lo guardado, de modo que recargar no vuelve a ejecutar la consulta ni duplica el registro. Solo ve ese resultado quien hizo la consulta. No es un historial: no hay listado de consultas anteriores (fuera de alcance en la spec).
- **Sin conexión.** Tipografías del sistema, una hoja de estilos y un script propios. La aplicación envía una política de contenido que solo permite recursos del propio servidor [9], y una prueba revisa que ninguna página referencie direcciones externas.
- **Documento original.** Lo entrega la aplicación solo a usuarios con sesión; no es un archivo público. Un PDF se abre en otra pestaña con el visor del navegador. Una página web guardada se entrega con una política que la aísla: no ejecuta scripts ni carga recursos de internet [50]. Es el mismo archivo que se cargó (REQ-002); la restricción va en la cabecera de la respuesta, no modifica el archivo. Esto responde a lo que el ADR-0004 dejó para este ADR.

### Acceso

- **Ingreso:** formulario de usuario y clave de Django. Mensaje de error único ("Usuario o clave incorrectos"), sin decir cuál de los dos falló [44].
- **Sesión:** cookie con solo el identificador, `HttpOnly` (valor por defecto de Django) y `SameSite` estricto (el valor por defecto es `Lax`; se cambia) [8]; identificador nuevo en cada ingreso [4]; "Salir" anula la sesión en el servidor. Vencimiento propuesto: 8 horas desde el ingreso y al cerrar el navegador. Es un parámetro, no arquitectura.
- **Toda página exige sesión**, salvo la de ingreso. Sin sesión, se redirige al ingreso (primera parte del criterio de REQ-016).
- **Roles:** lectura consulta y busca; lectura y escritura además carga, valida y registra relaciones y versiones. La comprobación está en las funciones de negocio.
- **Registro de intentos sin permiso:** cada ingreso fallido (usuario intentado, momento y canal; nunca la clave) y cada operación rechazada por rol (quién, qué intentó, cuándo, por pantalla o por comando) quedan en el mismo registro de auditoría que las cargas, validaciones y consultas.
- **Claves:** Argon2id. Largo mínimo propuesto de 15 caracteres, sin reglas de composición, siguiendo a OWASP [44]; la spec no fija un mínimo, así que es un valor a confirmar.
- **Formularios:** protección CSRF de Django en todos, incluido el de ingreso [45].

### Comandos

Los nombres se proponen en español. Los identificadores del código van en inglés por convención, pero el nombre de un comando es lo que escribe el responsable de normativa: es texto de cara al usuario, igual que el de la pantalla. Es una excepción que el responsable debe confirmar.

| Comando | Qué hace | Requisito | Rol |
|---|---|---|---|
| `cargar_norma` | Incorpora un documento con sus datos y su categoría; avisa si ya está | REQ-001, 011, 015, 017 | Lectura y escritura |
| `releer_norma` | Vuelve a leer y partir un documento ya cargado; deja una lectura nueva sin validar | REQ-004, 005 | Lectura y escritura |
| `listar_normas` | Lista las normas con sus datos, documentos, estado de validación y vínculos | REQ-001, 006 | Los dos |
| `ver_informe` | Muestra el informe de lectura en texto, con las unidades y sus claves | REQ-004 | Los dos |
| `validar_informe` | Valida una lectura, previa confirmación, y calcula sus pasajes y vectores | REQ-005 | Lectura y escritura |
| `registrar_relacion` | Registra que una norma modifica, complementa, reglamenta o deroga a otra, con fecha y, si corresponde, las unidades | REQ-006, 007 | Lectura y escritura |
| `registrar_version` | Deja un documento validado como versión de su norma, o como el archivo en uso de una versión | REQ-007 | Lectura y escritura |
| `crear_usuario` | Da de alta un usuario con su rol. Lo corre quien administra el equipo, sin rol de EVALUON; queda registrado | REQ-016 | — |
| `correr_evals` | Corre el conjunto de preguntas y guarda la corrida | Calidad (P7) | Lectura |

- Cada comando, salvo `crear_usuario`, recibe `--usuario` y pide la clave por teclado, sin mostrarla. La clave no se pasa como argumento, para que no quede en el historial de la terminal.
- Un usuario de lectura que corre `cargar_norma` o `validar_informe` recibe un rechazo y el intento queda registrado: es la segunda parte del criterio de aceptación de REQ-016, que en esta feature solo puede ocurrir por comando.
- Los textos de ayuda y los mensajes van en español llano.
- El restablecimiento de una clave olvidada usa el comando `changepassword` que Django ya trae.
- Las pruebas y las evals no usan clave: llaman a las funciones de negocio con un usuario de prueba.

Límite que conviene conocer: quien puede correr comandos en el equipo también puede entrar a la base directamente. La clave en los comandos no protege contra el administrador del equipo; sirve para que el registro diga, con fundamento, qué usuario de EVALUON hizo cada cosa.

### Cómo se prueba

- pytest 9.1.1 [27] con pytest-django 4.14.0 [28]. Cada test nombra su `REQ-NNN`, como ya exige el marco.
- **Pantalla:** el cliente de pruebas de Django pide la página y revisa el HTML. Con un doble del servicio de generación se prueban los tres bloques: respuesta con citas y texto literal (REQ-013), "no determinado" con aviso propio y sin citas (REQ-014), categoría y orden de citas (REQ-018).
- **Acceso:** sin sesión redirige al ingreso; clave incorrecta deja registro; la clave guardada no es legible y empieza con el identificador de Argon2id; un usuario de lectura rechazado por comando deja registro (REQ-016).
- **Comandos:** con `call_command`, incluido el rechazo por rol.
- **Sin conexión:** ninguna página ni archivo estático referencia direcciones externas; la cabecera de política de contenido está presente.
- **Espera:** una prueba con un doble que tarda más de 30 segundos confirma que el servidor no corta la consulta antes del tiempo configurado.
- No se propone automatizar un navegador real: la pantalla no tiene lógica en el navegador que lo justifique. La prueba con personas es la de la Comisión.

## Consecuencias

Más fácil:

- REQ-016 se cumple configurando y probando, no escribiendo código de seguridad.
- Pantalla y comandos comparten control de roles y registro, porque comparten las funciones de negocio.
- Las features 002 y 004 son módulos nuevos sobre la misma base: usuarios, sesiones, registro, plantillas y clientes de IA ya están.
- Un agente que arranca sin contexto encuentra cada cosa donde Django dice que va.
- La suite corre sin GPU.

Más difícil:

- Hay que seguir el calendario de versiones de Django: pasar a la 6.2 durante 2027.
- La búsqueda del ADR-0003 vive en SQL directo y en migraciones con SQL; hay que mantener sus reversas a mano.
- Cada recarga de página es completa hasta que se incorpore htmx. Cuando se incorpore, hay que resolver sus casos propios (errores, sesión vencida) y elegir entre la versión 2 y la 4.
- Los comandos piden clave cada vez. Con menos de 10 documentos es tolerable; si molesta, la respuesta es una pantalla de carga (otra feature), no relajar el control.

Riesgos y mitigación:

- **Uso desde otras computadoras.** La aplicación se publica solo en `127.0.0.1`: se usa desde el mismo equipo. Si la Comisión va a entrar desde otras máquinas de la red, la clave y la cookie de sesión viajarían sin cifrar; OWASP pide HTTPS para toda la sesión [43]. Antes de abrirla a la red hay que sumar un servicio que termine HTTPS y activar las cookies seguras. Ver "Qué necesita decidir el responsable".
- **Intentos repetidos de clave.** La spec no pide bloqueo ni demora tras varios intentos fallidos, y no se agrega (P10). Los intentos quedan registrados. OWASP lo recomienda [44]; conviene tratarlo como requisito nuevo antes de abrir la aplicación a la red.
- **Bibliotecas que todavía no declaran compatibilidad con Django 6.1** (ver "Sin verificar"). La primera tarea levanta el esqueleto con todo fijado y corre la suite; si alguna falla, se usa Django 6.0 hasta que la declaren o se reemplaza la pieza.
- **La GPU ocupada por otra consulta.** Con pocos usuarios, una segunda consulta simultánea espera a la primera. El cartel de espera y el corte a los 60 segundos cubren el caso. Si el tiempo real se acerca al límite, se mide en las evals (ADR-0002).

Para revertir: los datos quedan en tablas comunes de Postgres y no dependen de Django. Cambiar de marco de trabajo significa reescribir vistas, modelos, migraciones y acceso; las funciones de negocio, la lectura, la partición y los clientes de IA se reusan casi enteros. Cambiar la pantalla a otra tecnología obligaría a construir una API, que hoy no existe. Cambiar el algoritmo de claves no requiere nada de los usuarios.

## Qué necesita decidir el responsable

1. **Aprobar el conjunto:** Django 6.1, páginas armadas en el servidor sin htmx por ahora, Argon2id, sesiones en Postgres y comandos de Django.
2. **Desde dónde va a usar la pantalla la Comisión:** en el mismo equipo donde corre el sistema, o desde otras computadoras de la red. Lo segundo exige HTTPS antes de habilitarlo y es un servicio más. *Decidido: en esta feature, solo en el mismo equipo; el acceso por red es la feature 007.*
3. **Quién puede dar de alta usuarios** (ver la primera duda). *Decidido en la spec: quien administra el equipo, por comandos, con registro.*
4. **Nombres de comandos en español**, como excepción a la convención de identificadores en inglés.
5. **Dos valores de partida:** largo mínimo de clave (propuesta: 15 caracteres) y duración de la sesión (propuesta: 8 horas y al cerrar el navegador).
6. **Confirmar los datos del entorno.**

## Dudas que este ADR no resuelve

No modifican la spec; se informan para que las resuelva quien corresponda. Las cuatro quedaron resueltas: las tres primeras en la sección "Aclaraciones posteriores a la aprobación" de la spec y la cuarta en el plan (ver "Ajustes de integración").

- **Quién da de alta usuarios.** REQ-016 enumera lo que permite cada rol y el alta de usuarios no figura en ninguno; la spec deja fuera de alcance otros roles. Propuesta mínima: `crear_usuario` lo corre quien administra el equipo, sin exigir un rol de EVALUON, y el alta queda registrada. La otra opción es exigir el rol de lectura y escritura, salvo para el primer usuario; eso le daría a ese rol una atribución que la spec no le asigna.
- **Dónde busca el usuario de lectura.** REQ-010 (buscar por norma y artículo, y por palabras) y REQ-007 (qué estaba vigente a una fecha) son operaciones que el rol de lectura puede hacer, pero la spec dice que la única pantalla es la de consulta, definida como pregunta y respuesta. No queda dicho si la búsqueda y la vista a una fecha van en esa pantalla o por comando. Este ADR no agrega pantallas; si se resuelve por comando, se suman `buscar` y `ver_unidad` a la tabla, disponibles para los dos roles.
- **Fecha de referencia.** Coincide con la duda del ADR-0003: la pantalla no ofrece elegir fecha; se usa la del día.
- **Diferencia entre régimen específico y marco nacional (REQ-019).** La forma acordada de la respuesta trae la categoría de cada cita, y con eso la pantalla rotula cuál se aplica y cuál es marco. Si además hay que avisar con un texto que los dos tratan el punto de manera distinta, la respuesta necesita traer esa señal por afirmación. Es una definición del plan.

## Relación con los otros ADR

- **ADR-0002 (motor).** Coincide: un pedido por consulta, sin transmisión parcial, espera con cartel. La aplicación espera a que el motor esté listo antes de aceptar consultas y corta a un tiempo configurado. El doble de pruebas del motor debe poder devolver una respuesta con citas, un "no determinado" y una falla.
- **ADR-0003 (búsqueda).** La vista, la configuración de búsqueda de texto, la extensión `unaccent` y la tabla de pasajes se crean con migraciones de Django que llevan SQL y su reversa. Las consultas de búsqueda van como SQL directo. La columna de vectores usa la integración de `pgvector` para Django. El usuario de la base que usan las pruebas necesita poder crear una base y las extensiones.
- **ADR-0004 (lectura).** Las bibliotecas de lectura y Tesseract se instalan en la imagen de la aplicación; hace más pesada la imagen, sin GPU. El informe de lectura en texto lo muestra `ver_informe`. La confirmación expresa ante "misma norma" es una pregunta del comando `cargar_norma`. El original de una página web se muestra aislado, sin ejecutar scripts. Si se acepta el formato `.mhtml`, "abrir el original" probablemente sea una descarga y no una vista (ver "Sin verificar").
- **Dónde se guarda el archivo original** (en disco, con un volumen de Docker, o dentro de la base) no lo decide ningún ADR. Para la aplicación es indistinto, porque lo entrega una vista con sesión; para el respaldo, guardarlo en la base deja un solo lugar que respaldar. Queda para el plan, que decidió guardarlo en la base.

## Sin verificar

- **Datos del equipo.** Informados en el encargo; a confirmar por el responsable.
- **Compatibilidad declarada con Django 6.1.** WhiteNoise 6.12.0 declara Django 4.2 a 6.0 [26] y pytest-django 4.14.0 declara 5.2, 6.0 y la rama de desarrollo [28]. Ninguna nombra la 6.1, que salió el 5 de agosto de 2026 [3]. No encontré reportes de incompatibilidad, pero tampoco una confirmación. Tampoco verifiqué la integración de `pgvector` 0.5.0 con Django 6.1.
- **Parámetros de Argon2 que usa Django por defecto.** La documentación consultada dice que la variante es Argon2id pero no muestra los valores [6]. Hay que confirmar, con una prueba sobre una clave guardada, que igualan o superan el mínimo de OWASP (19 MiB, 2 iteraciones, 1 hilo). Como referencia, los valores por defecto de la biblioteca `argon2-cffi` usada por su cuenta son 64 MiB, 3 iteraciones y 4 hilos [47], por encima de ese mínimo; Django fija los suyos.
- **Cómo cuenta Django el vencimiento de la sesión** (desde el ingreso o desde el último uso) con la configuración propuesta. Se ajusta y se prueba al implementar.
- **Comportamiento de Gunicorn con hilos ante una consulta larga.** Verifiqué el valor por defecto de 30 segundos y su descripción [25], no cómo se aplica exactamente con hilos. Por eso se propone la prueba de espera.
- **Qué navegador usa la Comisión.** No lo sé. De eso dependen dos detalles que no verifiqué: que el visor de PDF del navegador abra en la página de la unidad citada, y que la política de aislamiento de las páginas web guardadas se comporte como describe la documentación [50].
- **Archivos `.mhtml` servidos por la aplicación.** No verifiqué si los navegadores los muestran o los descargan.
- **Reporte sobre llamadas externas de Gradio [41].** Es de un tercero, sobre la versión 6.26; no lo reproduje ni vi una confirmación del proyecto.
- **Extensiones de Flask.** No revisé su estado de mantenimiento; la alternativa C se descarta por el mismo motivo que la B, no por ese dato.
- **Fecha de la versión 3.1.6 de Jinja2 [51].** La página no la mostró.
- Las páginas se leyeron con una herramienta que las resume. Las versiones deben volver a mirarse en la fuente al fijarlas.

## Fuentes

Consultadas el 2026-10-02.

Django:
1. Django en PyPI (versión, Python requerido): https://pypi.org/project/Django/
2. Django, versiones con soporte: https://www.djangoproject.com/download/
3. Django 6.1, notas de la versión: https://docs.djangoproject.com/en/6.1/releases/6.1/
4. Django, autenticación (ingreso, sesión, señales): https://docs.djangoproject.com/en/6.1/topics/auth/default/
5. Django, modelo de usuario propio: https://docs.djangoproject.com/en/6.1/topics/auth/customizing/
6. Django, manejo de claves: https://docs.djangoproject.com/en/6.1/topics/auth/passwords/
7. Django, sesiones: https://docs.djangoproject.com/en/6.1/topics/http/sessions/
8. Django, referencia de configuración: https://docs.djangoproject.com/en/6.1/ref/settings/
9. Django, política de contenido (CSP): https://docs.djangoproject.com/en/6.1/ref/csp/
10. Django, comandos propios: https://docs.djangoproject.com/en/6.1/howto/custom-management-commands/
11. Django, bases de datos (PostgreSQL y psycopg): https://docs.djangoproject.com/en/6.1/ref/databases/
12. Django con Gunicorn: https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/gunicorn/

Otras piezas de Python:
13. FastAPI en PyPI: https://pypi.org/project/fastapi/
14. FastAPI, plantillas: https://fastapi.tiangolo.com/advanced/templates/
15. FastAPI, tutorial de seguridad (claves con `pwdlib` y Argon2): https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
16. Starlette en PyPI: https://pypi.org/project/starlette/
17. Starlette, sesiones en cookie firmada: https://www.starlette.io/middleware/
18. SQLAlchemy en PyPI: https://pypi.org/project/SQLAlchemy/
19. Alembic en PyPI: https://pypi.org/project/alembic/
20. Typer en PyPI: https://pypi.org/project/typer/
21. Flask en PyPI: https://pypi.org/project/Flask/
22. psycopg en PyPI: https://pypi.org/project/psycopg/
23. pgvector para Python en PyPI: https://pypi.org/project/pgvector/
24. Gunicorn en PyPI: https://pypi.org/project/gunicorn/
25. Gunicorn, configuración (tiempo de espera, hilos): https://gunicorn.org/reference/settings/
26. WhiteNoise en PyPI: https://pypi.org/project/whitenoise/
27. pytest en PyPI: https://pypi.org/project/pytest/
28. pytest-django en PyPI: https://pypi.org/project/pytest-django/

Pantalla:
29. htmx 2, documentación: https://htmx.org/docs/
30. htmx 4.0.0, anuncio: https://four.htmx.org/announcements/2026-08-28-htmx-4.0.0-is-released
31. InfoQ, cambios de htmx 4.0: https://www.infoq.com/news/2026/09/htmx-4-released/
32. htmx en el registro de npm (versión vigente y próxima): https://registry.npmjs.org/htmx.org
33. React en el registro de npm: https://registry.npmjs.org/react/latest
34. Vite en el registro de npm: https://registry.npmjs.org/vite/latest
35. Streamlit en PyPI: https://pypi.org/project/streamlit/
36. Streamlit, autenticación: https://docs.streamlit.io/develop/concepts/connections/authentication
37. Streamlit, configuración (estadísticas de uso, tipografías): https://docs.streamlit.io/develop/api-reference/configuration/config.toml
38. Streamlit, pruebas de aplicaciones: https://docs.streamlit.io/develop/concepts/app-testing
39. Gradio en PyPI: https://pypi.org/project/gradio/
40. Gradio, guía "Sharing your app" (autenticación, estadísticas): https://raw.githubusercontent.com/gradio-app/gradio/main/guides/04_additional-features/07_sharing-your-app.md
41. Reporte de terceros sobre llamadas externas de Gradio 6.26: https://github.com/johnson2006christopher/adaptshot/issues/106

Claves, sesiones y seguridad:
42. OWASP, guardado de claves: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
43. OWASP, manejo de sesiones: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
44. OWASP, autenticación: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
45. OWASP, prevención de CSRF: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
46. argon2-cffi en PyPI: https://pypi.org/project/argon2-cffi/
47. argon2-cffi, referencia: https://argon2-cffi.readthedocs.io/en/stable/api.html
48. pwdlib en PyPI: https://pypi.org/project/pwdlib/
49. passlib en PyPI: https://pypi.org/project/passlib/
50. MDN, directiva `sandbox` de la política de contenido: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox
51. Jinja2 en PyPI: https://pypi.org/project/Jinja2/

## Ajustes de integración

Hechos el 2026-10-02 al integrar el plan (`specs/001-normativa/plan.md`). La decisión (Django, páginas armadas en el servidor, Argon2id, sesiones en la base, comandos de Django) no cambia.

- **Forma de la respuesta.** La definición compartida del contexto sumó el tercer estado (falla técnica), que este ADR ya mostraba como bloque propio, y la marca `regimes_differ`. Con eso queda resuelta la cuarta duda: la respuesta trae, por afirmación, la señal de que el régimen específico y el marco nacional difieren, y la pantalla agrega un aviso de texto fijo (REQ-019).
- **Búsqueda.** Por decisión del responsable, la búsqueda por artículo y por palabras (REQ-010) va en la misma pantalla de consulta. Se agregó a "Pantalla de consulta". No se suman los comandos `buscar` y `ver_unidad` que este ADR dejaba como alternativa.
- **Considerandos.** Se citan como contexto, rotulados y después del articulado (REQ-018). Se agregó a la descripción de las citas.
- **Estructura del código.** `norms/services.py` pasó a ser la carpeta `norms/services/`, con un archivo por operación, para que carga y relaciones se puedan desarrollar en paralelo sin tocar el mismo archivo. Se agregaron `norms/indexing.py`, `queries/search.py`, `queries/prompts/`, `queries/evaluation.py` y el modelo de `queries`. El árbol completo está en el plan.
- **Servicios.** `embeddings` y `reranker` usan la misma imagen que `generation` (ADR-0003 ajustado). Los nombres de los seis servicios no cambian.
- **Migraciones.** El servicio `migrate` aplicaba las migraciones siempre. La regla del proyecto es respaldar la base antes de cada migración, y un servicio que migra solo no puede garantizarlo. Ahora migra solo si la base está vacía; con datos, comprueba y frena. Se actualizaron la tabla de servicios y el punto "Migraciones al levantar".
- **Comandos.** Se agregaron `releer_norma` (sin él, un documento mal partido no se puede volver a leer, porque REQ-011 impide cargar otra vez el mismo archivo) y `correr_evals` (P7). `crear_usuario` quedó sin rol requerido, como definió la spec. `registrar_relacion` acepta unidades y fecha; `registrar_version` y `validar_informe` se precisaron según el modelo de datos del plan. Los nombres en español siguen pendientes de la confirmación del responsable.
- **Archivo original.** El plan decidió guardarlo en la base.
- **Acceso por red.** Es la feature 007. Los riesgos "Uso desde otras computadoras" e "Intentos repetidos de clave" quedan como antecedente para esa feature. Este ADR no la impide: la restricción a `127.0.0.1` está solo en la publicación del puerto, y las cookies seguras se activan por configuración.
- **Formato `.mhtml`.** La spec acepta la página web guardada como un archivo `.html`; lo dicho sobre `.mhtml` no aplica en esta feature.
- **Dudas y decisiones.** Se anotó cuáles quedaron resueltas.

## Consulta del responsable

- **2026-10-02 · Django o FastAPI.** El responsable ya usa FastAPI con Jinja2, SQLModel y Alembic en otros proyectos, dato que este ADR no tenía al compararlos. Se volvió a evaluar con ese dato. A favor de FastAPI: un solo stack entre proyectos y código conocido. A favor de Django: el ingreso, las claves, las sesiones y la protección de formularios vienen hechos y mantenidos por un equipo de seguridad, mientras que con FastAPI serían código propio; el código lo escriben los agentes, de modo que la familiaridad previa pesa menos; y las features 002 a 004 son formularios con usuarios identificados. El responsable confirmó Django.

