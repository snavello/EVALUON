# ADR-0062 · Certificado de la conexión cifrada en dos variantes, con los mismos archivos

Estado: propuesto · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

REQ-110 pide que el navegador de las computadoras autorizadas no muestre advertencias al entrar. Para eso, el certificado que presenta el intermediario (ADR-0061) tiene que estar firmado por una autoridad en la que esas computadoras confíen, y nombrar la dirección con la que se entra (un nombre del DNS interno o la dirección IP del equipo).

El responsable dejó el origen abierto («Todavía no sé»): un certificado emitido por el área de sistemas del organismo, o uno propio instalado una vez en cada computadora. El plan tiene que preparar las dos variantes y permitir pasar de una a otra sin tocar el código.

Condiciones:

- **Sin internet (P4).** No se piden certificados a servicios externos.
- **Computadoras del organismo.** Una política de grupo puede impedir que los usuarios agreguen autoridades raíz [1]. Por usuario, sin ser administrador, se puede instalar una raíz en el almacén del usuario actual [2]. Instalar una raíz es algo que las herramientas de seguridad vigilan [3].
- **Navegadores.** Edge y Chrome en Windows usan el almacén de Windows. Firefox puede necesitar que se habilite el uso de ese almacén [4]. El navegador de la Comisión no se conoce.
- **Una autoridad propia instalada en una computadora** permite, a quien tenga su clave, hacerse pasar por cualquier sitio ante esa computadora. Hay que acotarla.
- **Norton intercepta las conexiones cifradas en el equipo del sistema** (T-049). Un producto así en las computadoras de la Comisión haría que el navegador vea su certificado y no el de EVALUON.

## Alternativas

### A. Certificado emitido por el área de sistemas (autoridad interna del organismo)

- **Se gana:**
  - Las computadoras ya confían en esa autoridad: no se instala nada en ellas.
  - La renovación y la revocación son del organismo.
- **Se pierde:**
  - Depende de los tiempos del área de sistemas.
  - Casi siempre pide un nombre en su DNS.
  - La clave privada viaja del área al equipo y hay que entregarla con cuidado.
  - El formato puede ser PFX (se convierte una vez).

### B. Autoridad propia de EVALUON, con restricción de nombre; raíz instalada una vez por computadora

Un script (`openssl` de Git para Windows) crea dos cosas:

- **Una autoridad de 10 años**, que solo firma certificados de servidor y lleva una restricción de nombre crítica: solo vale para la dirección de EVALUON y la del equipo.
- **El certificado del servidor**, de 397 días, firmado por ella.

La raíz se instala una vez en cada computadora. El certificado del servidor se renueva en el equipo sin tocarlas. La clave de la autoridad se guarda fuera del equipo (un pendrive) y se usa solo para renovar.

- **Se gana:**
  - Se puede empezar ya (el corte vertical no espera al área de sistemas).
  - No depende de nadie.
  - Funciona con la dirección IP, sin DNS.
  - Si la clave de la autoridad se filtrara, la restricción de nombre impide usarla para otros sitios.
- **Se pierde:**
  - Instalar la raíz en cada computadora: administrador, o el área de sistemas por política. Por usuario, si la política lo permite.
  - Un antivirus o un EDR puede marcar la instalación.
  - Hay que custodiar la clave de la autoridad.
  - Hay que renovar el certificado del servidor cada año.
  - El soporte de la restricción de nombre en Windows, Edge y Chrome se comprueba en T-271.

### C. Autoridad interna de Caddy (`tls internal`)

Caddy crea su autoridad y renueva solo certificados de vida corta.

- **Se gana:** nada que programar y renovación automática.
- **Se pierde:**
  - Sin restricción de nombre: quien tenga la clave puede hacerse pasar por cualquier sitio ante esas computadoras.
  - La clave de la autoridad queda en el equipo, accesible a cualquier administrador, y a los agentes durante la estabilización (ADR-0060).
  - Pasar a A cambia la configuración y no solo dos archivos.

### D. Certificado autofirmado, sin autoridad

- **Se gana:** un solo archivo.
- **Se pierde:** cada renovación obliga a reinstalarlo en todas las computadoras. Descartada.

## Decisión

Se propone **A y B, con los mismos dos archivos**.

1. El intermediario lee siempre `C:\EVALUON-piloto\certificados\evaluon.crt` (certificado con su cadena) y `evaluon.key`. La variante es quién produjo esos archivos.
2. **Se empieza con B**, con el corte vertical. `scripts/red/crear-certificados.sh` crea la autoridad con la restricción de nombre (una sola vez) y el certificado del servidor, y muestra la huella de la raíz para cotejarla en cada computadora. La carpeta de la autoridad se guarda fuera del equipo.
3. **Se pasa a A** cuando el área de sistemas entregue su certificado: se reemplazan los dos archivos (si viene en PFX, se convierte con `openssl pkcs12`), se corre `aplicar-red.ps1`, que recarga el intermediario, y se puede quitar la raíz propia de cada computadora. No se toca el código.
4. Al área de sistemas se le pide: el certificado (A), o que instale la raíz por política o permita instalarla (B), y en los dos casos que el antivirus o el proxy no intercepten la dirección de EVALUON.

## Consecuencias

Más fácil:

- El corte vertical y el piloto no esperan al organismo.
- Cambiar de variante es una operación de archivos.

Más difícil:

- Con B, la instalación de la raíz y la renovación anual quedan a cargo del responsable, que guarda la autoridad.
- Con B hay una autoridad propia en computadoras del organismo: acotada por la restricción de nombre, pero hay que explicarla al área de sistemas.

Para revertir: reemplazar los archivos por los de la otra variante y quitar la raíz propia de las computadoras.

## Sin verificar

- El soporte de la restricción de nombre para una dirección IP y para un nombre en Windows, Edge y Chrome vigentes. T-271 lo comprueba con un certificado de prueba para otro nombre.
- Si Firefox usa hoy, por omisión, las autoridades del almacén de Windows. Las fuentes consultadas [4] no lo confirman.
- Las guías de Microsoft sobre la política de grupo [1] son de versiones viejas de Windows Server. No se verificó cómo la aplican las versiones actuales.

## Fuentes

Consultadas el 2026-10-14.

1. Microsoft, «Prevent users from selecting new root certification authorities with a Group Policy»: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc781964(v=ws.10)
2. Certificate Depot, instalación de una raíz en el almacén del usuario actual: https://cert-depot.com/guides/trust-self-signed-cert-windows
3. Regla Sigma «New Root Certificate Installed Via Certutil.EXE»: https://detection.fyi/sigmahq/sigma/windows/process_creation/proc_creation_win_certutil_certificate_installation/
4. Mozilla, «CA:AddRootToFirefox»: https://wiki.mozilla.org/CA/AddRootToFirefox
