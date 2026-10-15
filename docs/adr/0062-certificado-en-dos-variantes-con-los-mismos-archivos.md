# ADR-0062 · Certificado de la conexión cifrada en dos variantes, con los mismos archivos

Estado: propuesto (versión 2) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

REQ-110 pide que el navegador de las computadoras autorizadas no muestre advertencias. Para eso, el certificado del intermediario (ADR-0061) tiene que estar firmado por una autoridad en la que esas computadoras confíen y nombrar la dirección con la que se entra: un nombre del DNS interno o la IP del equipo.

El responsable dejó el origen abierto («Todavía no sé»): certificado del área de sistemas, o propio instalado una vez en cada computadora. El plan prepara las dos variantes y permite pasar de una a otra sin tocar el código.

Condiciones:

- **Sin internet (P4).**
- **Computadoras del organismo:**
  - una política de grupo puede impedir que los usuarios agreguen autoridades raíz [1];
  - por usuario, sin administrador, se puede instalar una raíz en el almacén del usuario actual [2];
  - instalar una raíz es algo que vigilan las herramientas de seguridad [3].
- **Navegadores:**
  - Edge y Chrome toman las raíces del almacén de Windows, pero, según la revisión del plan, verifican la cadena con su propio verificador: por eso las restricciones se prueban en el navegador, no solo con `certutil`;
  - Firefox 120 o posterior confía por omisión en las autoridades agregadas al almacén de Windows, salvo que se desactive [4].
- **Una autoridad instalada como raíz vale para todo lo que no se le limite.** Hay que limitarle el uso (solo servidor) y los nombres (solo EVALUON), y proteger su clave.
- **Inspección de conexiones cifradas.** Un antivirus o un proxy que la haga en las computadoras de la Comisión haría que el navegador vea su certificado. En el equipo del sistema ya no hay ninguno: Norton se desinstaló el 2026-10-14.

## Alternativas

### A. Certificado del área de sistemas (autoridad interna del organismo)

Mejor con un pedido de firma (CSR) generado en el equipo: la clave no sale del equipo y el certificado vale solo para EVALUON, sin comodín.

- **Se gana:** las computadoras ya confían; la renovación y la revocación son del organismo.
- **Se pierde:** depende de sus tiempos, casi siempre pide un nombre en su DNS, y la renovación sigue su política. Si entregan un PFX, su frase tiene que llegar aparte.

### B. Autoridad propia de EVALUON, limitada, con la raíz instalada una vez por computadora

Un script con el `openssl` de Git para Windows crea la autoridad:

- 3 años;
- `CA:TRUE` con `pathlen:0`;
- uso extendido solo de autenticación de servidor (`extendedKeyUsage=serverAuth`), que Windows aplica a toda la cadena;
- restricciones de nombre críticas de **los dos tipos**: direcciones IP, solo las /32 de EVALUON y del equipo, con IPv6 excluido; nombres DNS, solo el de EVALUON o, si no hay nombre, un subárbol que no puede existir (`.invalid`). Una restricción que nombra un solo tipo deja libre al otro.

Su clave va cifrada con AES-256 y una frase de paso, en una unidad extraíble del responsable; el script se niega a dejarla en el disco del sistema. El certificado del servidor (397 días) se renueva sin tocar las computadoras.

- **Se gana:**
  - se puede empezar ya;
  - no depende de nadie;
  - funciona con la dirección IP;
  - si la clave se filtrara, solo serviría para EVALUON y para servidor.
- **Se pierde:**
  - instalar la raíz en cada computadora (administrador, o el área por política);
  - un antivirus puede marcarla;
  - custodiar la autoridad;
  - renovar el certificado cada año y la autoridad cada 3 (con reinstalación en las computadoras).

### C. Autoridad interna de Caddy (`tls internal`)

- **Se gana:** renovación automática.
- **Se pierde:**
  - sin restricciones de nombre ni de uso;
  - la clave de la autoridad queda en el equipo, accesible a cualquier administrador y a los agentes durante la estabilización;
  - pasar a A cambia la configuración.

### D. Certificado autofirmado sin autoridad

- **Se pierde:** cada renovación obliga a reinstalarlo en todas las computadoras. Descartada.

## Decisión

Se propone **A y B, con los mismos dos archivos**:

1. El intermediario lee siempre `C:\ProgramData\EVALUON-Red\certificados\evaluon.crt` (con la cadena) y `evaluon.key`. Solo los administradores escriben esa carpeta, y solo el servicio y los administradores la leen. Los archivos nuevos llegan por `C:\EVALUON-piloto\entrada\` y los mueve `aplicar-red.ps1`.
2. **Se empieza con B** con el corte vertical. `scripts/red/crear-certificados.sh`:
   - crea la autoridad limitada (una vez) y el certificado del servidor;
   - muestra la huella de la raíz para cotejarla en cada computadora;
   - con `--prueba-otro-nombre`, crea un certificado fuera de la restricción, para comprobar en el navegador que se rechaza.
3. **Se pasa a A** cuando el área de sistemas firme el pedido que genera `crear-certificados.sh --pedido`: se ponen los archivos en `entrada\`, se corre `aplicar-red.ps1`, y se puede quitar la raíz propia de las computadoras. No se toca el código.
4. Al área de sistemas se le pide: firmar el pedido, o instalar la raíz por política (o permitirla); que el antivirus o el proxy no intercepten la dirección de EVALUON; y que los navegadores no desactiven el uso de las raíces de Windows.

## Consecuencias

Más fácil:

- El corte vertical y el piloto no esperan al organismo.
- Cambiar de variante es una operación de archivos.
- Una filtración de la autoridad queda acotada.

Más difícil:

- Con B, la instalación de la raíz y las renovaciones son del responsable, que guarda la autoridad y su frase.
- Hay una autoridad propia en computadoras del organismo: limitada, pero hay que explicarla.

Para revertir: reemplazar los archivos y quitar la raíz propia.

## Sin verificar

- Que Edge y Chrome vigentes rechacen el certificado fuera de la restricción para una dirección IP y para un nombre. Lo prueba T-271 en el navegador, con `certutil -verify` como complemento.
- Las guías de Microsoft sobre la política de grupo [1] son de versiones viejas de Windows Server.
- El dato de que Chrome y Edge verifican con su propio verificador viene de la revisión del plan y no lo verifiqué en una fuente propia: por eso la prueba es en el navegador.

## Fuentes

Consultadas el 2026-10-14.

1. Microsoft, «Prevent users from selecting new root certification authorities with a Group Policy»: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2003/cc781964(v=ws.10)
2. Certificate Depot, raíz en el almacén del usuario actual: https://cert-depot.com/guides/trust-self-signed-cert-windows
3. Regla Sigma «New Root Certificate Installed Via Certutil.EXE»: https://detection.fyi/sigmahq/sigma/windows/process_creation/proc_creation_win_certutil_certificate_installation/
4. Mozilla, «Set up Certificate Authorities (CAs) in Firefox»: https://support.mozilla.org/en-US/kb/setting-certificate-authorities-firefox
