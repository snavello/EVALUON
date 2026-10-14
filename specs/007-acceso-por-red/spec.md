# Spec 007 · Acceso por red

Estado: aprobada · Fecha: 2026-10-14 · Aprobó: responsable del proyecto (2026-10-14, «todo si.»)

## Problema

Hoy EVALUON se usa solo en el equipo donde corre: la aplicación atiende únicamente pedidos del propio equipo (spec 001, «Fuera de alcance»; spec 014, «Fuera de alcance»). El piloto de evaluación guiada necesita que los miembros de la Comisión Evaluadora entren desde sus computadoras (hoja de ruta, «Alcance del piloto»; ADR-0017). Sin eso, cada miembro tiene que sentarse frente al equipo del sistema y el piloto no puede correr en paralelo con la evaluación habitual.

Abrir el acceso trae riesgos que hoy no existen. Lo que viaja por la red (usuarios, claves, pliegos, ofertas, conclusiones y decisiones de la Comisión) podría leerlo otro equipo de la red. Alguien podría probar claves hasta acertar con una. Y los servicios internos del sistema (base de datos, modelos de IA) quedarían expuestos si se abren junto con la aplicación.

Lo que ya existe y se mantiene: ingreso con usuario y clave, roles (lectura, lectura y escritura; operador y evaluador de la Comisión), sesiones que vencen, y registro de cada ingreso e intento fallido (spec 001, REQ-012 y REQ-016). Lo que falta es usarlo desde otra computadora sin agregar esos riesgos.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-14 | Arranque | «si  avanza»: se empieza la 007 porque es lo único que traba el piloto. |
| 2026-10-14 | Desde dónde se entra | «Solo computadoras de una lista»: únicamente las computadoras de los miembros de la Comisión; las demás de la red no llegan. |
| 2026-10-14 | Certificado de la conexión cifrada | «Todavía no sé»: la spec pide que el navegador no muestre advertencias; el plan prepara las dos variantes (certificado del área de sistemas del organismo, o propio instalado una vez en cada computadora). |
| 2026-10-14 | Bloqueo por claves equivocadas | «5 intentos, 15 min»: tras 5 claves mal seguidas el usuario queda bloqueado 15 minutos; el responsable puede desbloquearlo antes. |
| 2026-10-14 | Revisión del borrador, filas 1 a 8 | «1 si, 2 si 3si  4minimo 8 5si 6si 7 todavia podes ver estamos estabilizando 8si»: se aprueban la lista de hasta 10 computadoras, la conexión cifrada, el bloqueo con mensaje genérico también por comando, el cierre a los 30 minutos sin uso, el registro de accesos y lo que queda fuera de alcance; la clave nueva tiene como mínimo 8 caracteres. La fila 7 (separación del proceso en curso) queda para decidir frente a P4 (ver REQ-117). |
| 2026-10-14 | Material reservado y P4 | «Cargarlo ya y que lo vea todo»: mientras se estabiliza el piloto, los agentes pueden leer el proceso en curso en la instancia del piloto; requiere enmendar P4 (ADR-0060, aceptado). |
| 2026-10-14 | Aprobación | «todo si.»: se aprueban el ADR-0060 (constitución 1.5) y esta spec, y se retoma T-049 de la 001 (levantar todo desde cero para el runbook). |
| 2026-10-14 | Qué se carga en el piloto | «También el proceso en curso»: se cargan ofertas reservadas hasta el dictamen; ese material pasa a la fase de operación de P4 y se separa de los agentes y del repositorio (REQ-117). |

## Usuarios y escenarios

**Escenario 1 · Trabajar desde la propia computadora.** Como miembro de la Comisión, cuando estoy en mi computadora de trabajo (una de las autorizadas), necesito abrir EVALUON en el navegador con una dirección fija, ingresar con mi usuario y clave y usar las cinco secciones igual que en el equipo del sistema, para evaluar sin moverme de mi puesto.

**Escenario 2 · Clave equivocada.** Como sistema, cuando alguien escribe mal la clave varias veces seguidas para un mismo usuario, bloqueo ese usuario por un tiempo, registro cada intento y muestro un mensaje que no revela si el usuario existe ni cuántos intentos quedan, para que nadie pueda adivinar claves probando.

**Escenario 3 · Desbloquear y controlar.** Como responsable del sistema, cuando un miembro de la Comisión quedó bloqueado, necesito desbloquearlo antes de que venza el plazo, y necesito ver quién ingresó, desde qué computadora y cuándo, y los intentos fallidos y bloqueos, para resolver el problema y detectar un uso indebido.

**Escenario 4 · Clave propia.** Como miembro de la Comisión, cuando recibo mi usuario con una clave inicial, necesito cambiarla por una que solo yo conozca, para que lo que el sistema registra a mi nombre lo haya hecho yo (P3 y P6).

**Escenario 5 · Me levanté del escritorio.** Como miembro de la Comisión, cuando dejo la sesión abierta sin usar, necesito que se cierre sola después de un rato, para que nadie decida en mi nombre desde mi computadora; lo que ya guardé no se pierde.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-109 | La aplicación se puede usar desde las computadoras de una lista de autorizadas que mantiene el responsable del sistema, con una dirección fija, las mismas pantallas y los mismos roles que en el equipo del sistema. Desde las demás computadoras de la red no se llega a la aplicación. Agregar o quitar una computadora no requiere cambiar el código | Decisión del 2026-10-14 |
| REQ-110 | Toda comunicación entre la computadora del usuario y EVALUON va cifrada. Un pedido sin cifrar no muestra contenido: se redirige a la dirección cifrada. El navegador de las computadoras autorizadas no muestra advertencias de seguridad al entrar | Decisión del 2026-10-14 |
| REQ-111 | Tras 5 intentos fallidos seguidos para un mismo usuario, ese usuario queda bloqueado durante 15 minutos, aunque después se escriba la clave correcta. El mensaje de rechazo es el mismo para usuario inexistente, clave equivocada y usuario bloqueado. Las mismas reglas valen para los comandos que piden usuario y clave | Decisión del 2026-10-14 |
| REQ-112 | El responsable del sistema puede desbloquear un usuario antes de que venza el plazo; el desbloqueo queda registrado con quién lo hizo y cuándo | — |
| REQ-113 | Cada ingreso, salida, intento fallido, bloqueo y desbloqueo queda registrado con el usuario (o el nombre tal como se escribió), la computadora de origen, la fecha y la hora, y el responsable del sistema lo puede consultar | P6 |
| REQ-114 | Cada usuario puede cambiar su clave; para hacerlo escribe la actual. El sistema exige una clave nueva de al menos 8 caracteres y rechaza las muy comunes. Un usuario dado de alta con clave inicial debe cambiarla en su primer ingreso | P3, P6 |
| REQ-115 | Una sesión sin uso durante 30 minutos se cierra; también se cierra a las 8 horas de iniciada y al cerrar el navegador. Lo que el usuario ya guardó no se pierde | — |
| REQ-116 | Desde otra computadora solo se llega a la aplicación: la base de datos, los motores de IA y los demás servicios internos no aceptan conexiones de fuera del equipo del sistema | P4 |
| REQ-117 | Los documentos del proceso en curso (reservados hasta el dictamen) y todo lo que el sistema produce sobre ellos (lecturas, matrices, evaluaciones, preguntas, consultas y registros) se procesan solo en el equipo del sistema, con IA local, en una instancia separada de la que usa la construcción. No se copian al repositorio, a las pruebas, a las mediciones ni a los respaldos de construcción, y los agentes de IA que construyen EVALUON no acceden a esa instancia ni a sus respaldos. Lo que el responsable decida compartir del piloto con la construcción son cifras agregadas, sin textos. Excepción mientras se estabiliza el piloto (ADR-0060): los agentes pueden leer la instancia del piloto, pero el material nunca va al repositorio ni a las pruebas | P4 (fase de operación), ADR-0060, decisiones del 2026-10-14 |

## Criterios de aceptación

Criterio numérico de la feature: desde una computadora de la lista, el recorrido del caso chico (procedimiento, pliego y matriz, ofertas, evaluación y dictamen, normativas) se completa en 5 de 5 secciones, con 0 páginas servidas sin cifrar y 0 advertencias del navegador; desde una computadora fuera de la lista, 0 páginas; y desde cualquier computadora de la red, 0 conexiones aceptadas por los servicios internos.

Corte vertical: primero una sola pantalla (el ingreso) servida cifrada a una computadora de la lista, con un usuario de prueba y el caso chico público; después el resto.

- **REQ-109.** Dada una computadora de la lista con un navegador común, cuando abre la dirección de EVALUON e ingresa un usuario evaluador, entonces ve las cinco secciones y puede completar el recorrido del caso chico como en el equipo del sistema. Dada una computadora de la red que no está en la lista, cuando intenta abrir la dirección, entonces no llega a la aplicación. Dada una computadora que se agrega a la lista, cuando el responsable sigue el paso del runbook, entonces llega sin que se toque el código.
- **REQ-110.** Dada la dirección sin cifrar, cuando se abre, entonces el navegador termina en la dirección cifrada sin haber recibido contenido de la aplicación. Dada la dirección cifrada en una computadora de la lista, cuando se abre, entonces el navegador no muestra ninguna advertencia de seguridad. Dado el tráfico capturado en la red durante un ingreso, entonces la clave no aparece legible.
- **REQ-111.** Dado un usuario activo, cuando se escribe mal su clave 5 veces seguidas, entonces el intento siguiente con la clave correcta es rechazado con el mismo mensaje genérico durante 15 minutos, y pasado ese tiempo ingresa. Con 4 intentos fallidos y uno correcto, ingresa y la cuenta vuelve a cero. Dado un usuario inexistente, un usuario con clave equivocada y un usuario bloqueado, cuando se intenta ingresar, entonces los tres mensajes son idénticos. Lo mismo por comando.
- **REQ-112.** Dado un usuario bloqueado, cuando el responsable lo desbloquea, entonces puede ingresar enseguida con su clave y el registro muestra el desbloqueo con quién y cuándo.
- **REQ-113.** Dados un ingreso correcto, un intento fallido, un bloqueo y un desbloqueo hechos desde otra computadora, cuando el responsable consulta el registro, entonces ve los cuatro con usuario o nombre escrito, computadora de origen, fecha y hora.
- **REQ-114.** Dado un usuario con clave inicial, cuando ingresa por primera vez, entonces no puede usar ninguna sección hasta cambiarla. Dada una clave nueva más corta que el mínimo o muy común, entonces se rechaza con un mensaje que dice por qué. Dado un cambio de clave sin escribir la actual correcta, entonces se rechaza.
- **REQ-115.** Dada una sesión abierta, cuando pasan 30 minutos sin uso, entonces el siguiente pedido lleva al ingreso y, después de ingresar, lo guardado antes sigue ahí.
- **REQ-116.** Dada una computadora de la red, cuando intenta conectarse a la base de datos, a los motores de IA, a los embeddings o al reranker, entonces la conexión no se establece; solo responde la aplicación.
- **REQ-117.** Dado el fin de la estabilización y un proceso reservado cargado en la instancia del piloto, cuando corren las tareas habituales de construcción (tests, mediciones, respaldos y verificaciones), entonces ninguna usa esa instancia, su base ni sus respaldos; dado el repositorio, en cualquier momento (también durante la estabilización), entonces no contiene ningún documento, texto ni registro de ese proceso. Dada la instancia del piloto, cuando se revisan sus servicios, entonces la IA que procesa pliegos y ofertas es solo la local.

## Requisitos no funcionales

- Computadoras autorizadas y usuarios a la vez: hasta 10 (la Comisión y el operador), sin que una página tarde más que en el equipo del sistema.
- Tiempo de carga de una página desde otra computadora de la red: menos de 2 segundos (el mismo de la 014), sin contar las tareas que corren en segundo plano.
- El sistema se sigue levantando con un único comando (P5); lo que haya que configurar en cada computadora de la Comisión queda en el runbook, en pasos que puede seguir una persona no técnica.
- Ningún recurso de la pantalla se carga desde internet (como hasta ahora).

## Fuera de alcance

- Acceso desde internet.
- Segundo factor de autenticación.
- Ingreso con el usuario del organismo (directorio corporativo o inicio de sesión único).
- Recuperación de clave por correo: si alguien la olvida, el responsable le asigna una clave inicial nueva (REQ-114 obliga a cambiarla).
- Cambios en las pantallas de las secciones, salvo el ingreso, el cambio de clave y el registro de accesos.

## Datos involucrados

- Usuarios, claves (guardadas sin que se puedan leer, como hoy) y el registro de accesos: datos del propio sistema.
- Lo que viaja cifrado por la red: normas (públicas), pliegos, ofertas, conclusiones y decisiones de la Comisión.
- Clasificación (P4): el piloto carga también el proceso en curso, cuyas ofertas son reservadas hasta el dictamen (decisión del 2026-10-14). Ese material está en fase de operación: se procesa solo con IA local y queda separado de la construcción (REQ-117). Mientras se estabiliza el piloto, los agentes pueden leerlo (ADR-0060), sin llevarlo nunca al repositorio ni a las pruebas. Lo demás (casos públicos, normas) sigue en fase de construcción.

## Preguntas abiertas

Ninguna. El origen del certificado (área de sistemas o propio) no cambia lo que pide la spec: lo resuelve el plan con las dos variantes.
