# Runbook 014 · Subir, leer y validar normas desde la pestaña «Normativas» (T-214)

Para cargar y validar una norma sin comandos (REQ-094). Los comandos de la 001 (`cargar_norma`, `validar_informe`, `listar_normas`, `ver_informe`) siguen funcionando y dejan el mismo resultado: la pantalla llama a los mismos servicios (`norms.services.upload`, `loading` y `validation`). Los comandos se corren desde la raíz del repositorio; el resto del entorno, en `specs/014-aplicacion-por-secciones/entorno.md` y en los runbooks de las features anteriores.

## 1. Roles: quién puede qué

Hay dos roles distintos en cada usuario y las normas necesitan los dos:

| Acción en la pestaña | Rol de normativa | Rol de la Comisión |
|---|---|---|
| Ver la lista, los datos propuestos y el informe de lectura | lectura o lectura y escritura | operador o evaluador |
| Subir el archivo, corregir un dato (valor y motivo) y cargar la norma | **lectura y escritura** | operador o evaluador |
| «Validar la norma» | **lectura y escritura** | **evaluador** |

No se cambió el modelo de permisos (decisión operativa 4 del plan): quien valida normas por pantalla es un evaluador que **además** tiene el rol de normativa de lectura y escritura. Un evaluador creado solo con rol de lectura puede mirar todo pero no subir ni validar; la pestaña le dice cuál rol le falta («le falta el rol de normativa de lectura y escritura»). El operador sube y carga, pero el botón «Validar la norma» no se dibuja, y un POST directo recibe 403 y queda registrado (P6).

Crear un evaluador que pueda validar normas (clave pedida dos veces):

```
docker compose run --rm app python manage.py crear_usuario NOMBRE --rol lectura-escritura --rol-comision evaluador
```

Para el operador, `--rol-comision operador`. Un usuario que ya existe con rol de lectura no puede pasar a lectura y escritura con un comando: el rol de normativa se fija al crearlo (`rol_comision` cambia solo el rol de la Comisión). Si hace falta, se crea un usuario nuevo con los dos roles. Después de crearlo, cerrar y abrir sesión.

## 2. Cómo se carga una norma (solo normas públicas, P4)

1. Abrir un procedimiento y la pestaña «Normativas» (la lista de normas es común a todos los procedimientos). Con «Subir archivo» junto al título se llega al formulario.
2. «Subir y leer la norma»: elegir el PDF o la página web guardada (`.htm`). El sistema la lee y propone los diez datos (categoría, tipo, número, año, organismo, título, nombre de cita, fechas de publicación y vigencia, fuente), cada uno con la página y el texto de donde sale. Lo que no reconoce queda marcado «No se reconoció: complételo».
3. Revisar cada dato. Para corregir o completar: «Corregir» o «Completar», escribir el valor **y el motivo** (obligatorio). Queda el valor propuesto, el escrito, el motivo, quién y cuándo. Dos datos que el sistema no calcula y hay que completar con motivo cuando la norma los dice en plazos: la fecha de vigencia (por ejemplo, la 247/2022 y la 297/2003) y la categoría de un anexo.
4. «Cargar la norma»: indicar la parte (`cuerpo` o la clave del anexo), marcar «régimen general» solo si es el cuerpo o el anexo del régimen general de contrataciones, y, si el sistema avisa que ya hay una norma igual, elegir si es otro archivo o una versión nueva. Queda cargada con su lectura pendiente; la pestaña abre su informe de lectura.
5. El evaluador lee el informe y pulsa «Validar la norma». Hace falta el servicio de embeddings en marcha (`docker compose ps`: `embeddings` «healthy»). Al validar, la norma queda disponible para las consultas y se crea una versión de la normativa. Si el servicio no responde, no se guarda nada y la pestaña lo dice.

Cada paso deja su hecho de auditoría con canal «pantalla» (`norm_upload`, `load`, `validation`), también los rechazos.

## 3. Lo que todavía no se puede desde la pantalla

- **Descartar una subida equivocada.** El servicio de subida no tiene «descartar» (aviso de la verificación de T-213). Mientras una subida espera, el mismo archivo no puede volver a subirse («ya se subió y espera confirmación»). Hasta que se agregue, el archivo equivocado se confirma corrigiendo sus datos o se pide a quien administra la base que la deje rechazada.
- **«Devolver para releer»** del informe: se hace con el comando `releer_norma`.
- **Subir una norma sin abrir un procedimiento:** desde la pantalla de alta (`expedientes/nuevo/`) «Normativas» lleva a la consulta general; para subir, abrir cualquier procedimiento.

## 4. Si algo no anda

- La pestaña no muestra estilos nuevos: reconstruir la imagen (`docker compose build app`) y recrear `app`, porque los archivos estáticos se juntan al construirla.
- «Para subir una norma le falta …»: falta uno de los dos roles (sección 1).
- «No se validó … el servicio de embeddings no respondió»: levantar `embeddings` y repetir; la lectura sigue pendiente.
- Comprobación de punta a punta con material público: `docker compose run --rm app pytest tests/journey/temas/test_s5_normas.py tests/norms/test_upload_proposal.py`.
