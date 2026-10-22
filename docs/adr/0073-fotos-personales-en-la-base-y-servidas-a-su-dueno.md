# ADR-0073 · Fotos personales: se guardan en la base, ajustadas, y las sirve una vista que solo responde a su dueño

Estado: propuesto · Fecha: 2026-10-21 · Propuso: Planificador (plan 017) · Decidió: —

## Contexto

La feature 017 (REQ-136 a REQ-138) deja que cada usuario suba hasta 10 fotos propias, por ejemplo de un ser querido, para que aparezcan de fondo en el primer panel. Son material privado: se quedan en el equipo, las ve solo su dueño y nunca van al repositorio (público), a las pruebas ni a un servicio externo (P4, P5). Cada una se guarda ya ajustada, en blanco y negro con el brillo medio y el contraste de la foto de la casa, y con 2 MB como máximo.

Lo que hay hoy: la aplicación monta `./evaluon` en solo lectura y no tiene ningún volumen de archivos subidos; todo archivo que el sistema recibe (documentos de pliegos y ofertas, normas, páginas del Portal) se guarda como `bytea` en tablas de Postgres, que vive en el volumen `pgdata`. El `.gitignore` ya cubre `pgdata/` y `backups/`, pero no hay regla para ninguna carpeta de fotos ni para `*.dump`. `scripts/clon.sh` hace respaldos de la base fuera del repositorio. Pillow 12.3.0 ya está instalado.

## Alternativas

### A. En la base (`bytea`), una vista las sirve (propuesta)
Tabla `accounts_photo` con `user`, `slot` (0 a 9, única por usuario), `content`, huella, medidas y tamaño. La vista `accounts:foto` hace `get_object_or_404(Photo, pk=…, user=request.user)`. Se gana: es lo que el proyecto ya hace con todo archivo (mismo respaldo, misma restauración, mismo clon); no hay volumen nuevo ni permisos de disco; el máximo de 10 y el tope de 2 MiB los hacen valer restricciones de la base aun con dos subidas a la vez; no existe una carpeta que pueda terminar versionada; si se da de baja el usuario, las fotos se van con él (CASCADE). Se pierde: cada foto (de unos 100 a 400 KB ajustada) engorda la base y los respaldos (como mucho 20 MB por usuario); servirla pasa por Django en lugar de por el servidor de estáticos (con ETag y caché privada alcanza para un uso de pocos usuarios).

### B. En un volumen de archivos del equipo
Un volumen nuevo montado en `app` (por ejemplo `./fotos`), con una subcarpeta por usuario y las fotos como archivos; la vista las lee del disco. Se gana: la base no crece; las fotos se pueden ver con el explorador de archivos. Se pierde: es una pieza nueva para el `docker-compose.yml` (`app` y `worker` comparten montajes y un test las compara); hay que agregar la carpeta al `.gitignore` y un test que lo verifique para que no se cuele al repositorio (hoy no existe esa regla); el respaldo de la base deja de incluir las fotos y hay que respaldar la carpeta aparte; el máximo de 10 y el tamaño se controlan solo en código; una carpeta suelta en el equipo es fácil de copiar por error junto con el proyecto.

### C. En la base pero solo la foto, sin ajustarla en el servidor (ajustar en el navegador)
Como hace la maqueta: el navegador pasa la foto a blanco y negro con un canvas y sube el resultado. Se gana: no hay procesamiento en el servidor. Se pierde: depende de JavaScript y del navegador (el resultado cambia entre equipos), no se puede garantizar el tono ni el tamaño (el cliente podría subir cualquier cosa), y se pierde el control de metadatos (la ubicación EXIF). El criterio de REQ-137 (diferencia de 10 % o menos) deja de ser comprobable con un test.

## Decisión

Se propone **A**. Además:

1. **Se ajusta en el servidor al subir** (REQ-137): se valida el contenido (JPEG, PNG o WebP; hasta 10 MiB sin procesar y un tope de píxeles), se corrige la orientación, se pasa a luminancia, se reduce a 1600 px de lado mayor, se ajusta el histograma al de la foto de la casa y se guarda como JPEG sin metadatos por debajo de 2 MiB. Solo se guarda la foto ajustada: no se conserva el original.
2. **Servido solo al dueño:** otro usuario recibe 404 (no se revela que existe); sin sesión, va al ingreso. Cabeceras `Cache-Control: private` y ETag con la huella.
3. **Sin ninguna otra salida:** ninguna etapa externa (ADR-0065, ADR-0067) lee `accounts_photo`.
4. **Cómo se evita que entren al repositorio o a lo que se sube** (pedido del Coordinador): no hay carpeta de fotos; la base es el volumen `pgdata` (ya ignorado) y los respaldos van a `backups/` (ya ignorado) o a una carpeta fuera del repositorio (`clon.sh`); se agrega `*.dump` al `.gitignore`; un test falla si aparece un archivo de imagen fuera de `evaluon/static/diseno/casa/` y `evaluon/static/marca/`, o si el `.gitignore` deja de cubrir `backups/`, `pgdata/` y `*.dump`; los tests de fotos generan sus imágenes en memoria con Pillow, nunca con archivos del repositorio.

## Consecuencias

- Más fácil: un solo lugar para respaldar y restaurar; el tope de 10 y el de 2 MiB no se pueden saltear; cambiar el tono de referencia exige solo cambiar la foto de la casa (las ya subidas conservan su ajuste).
- Más difícil: la base crece unos cientos de KB por foto; si algún día hubiera cientos de usuarios con fotos, convendría un servidor de archivos.
- Para revertir a B: crear el volumen, copiar los `bytea` a archivos con un comando de una sola vez y cambiar la vista de lectura; el contrato (`photos.pick_for`, la URL `accounts:foto`) no cambia.
