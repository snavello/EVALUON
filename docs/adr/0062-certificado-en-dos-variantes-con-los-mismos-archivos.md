# ADR-0062 · Certificado de la conexión cifrada en dos variantes, con los mismos archivos

Estado: aceptado (versión 3, mínima) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: responsable del proyecto (2026-10-14, «Ok», con el plan 007)

## Contexto

REQ-110 pide que el navegador de las computadoras de la lista no muestre advertencias. El certificado de Caddy (ADR-0061) tiene que estar firmado por una autoridad en la que esas computadoras confíen, y nombrar la dirección con la que se entra.

El responsable dejó el origen abierto («Todavía no sé»): del área de sistemas, o propio instalado una vez en cada computadora.

- Edge y Chrome toman las raíces del almacén de Windows.
- Firefox 120 o posterior también, salvo que una política lo desactive [1].
- Una política del organismo puede impedir que los usuarios instalen raíces: entonces lo hace el área de sistemas.

## Alternativas

### A. Certificado del área de sistemas

- **Se gana:** nada que instalar en las computadoras.
- **Se pierde:** depende de los tiempos del área y casi siempre pide un nombre en su DNS.

### B. Autoridad propia de EVALUON, con la raíz instalada una vez por computadora

Un script con el `openssl` de Git para Windows crea:

- **la autoridad:** 10 años, que solo sirve para certificados de servidor (`extendedKeyUsage=serverAuth`) y solo para las direcciones de EVALUON (restricciones de nombre de los dos tipos). Así la raíz instalada en computadoras del organismo no sirve para otra cosa;
- **el certificado del servidor:** 397 días, que se renueva sin tocar las computadoras.

- **Se gana:** se empieza ya y funciona con la dirección IP.
- **Se pierde:** instalar la raíz en cada computadora (administrador o el área de sistemas) y renovar el certificado cada año.

### C. Autoridad interna de Caddy (`tls internal`)

- **Se pierde:** no limita lo que la raíz puede firmar, y pasar a A cambia la configuración. Descartada.

## Decisión

Se propone **A y B, con los mismos dos archivos**: Caddy lee siempre `C:\EVALUON-red\certificados\evaluon.crt` y `evaluon.key`.

- Se empieza con B (`scripts/red/crear-certificados.sh`).
- Cuando el área de sistemas entregue su certificado, se reemplazan los dos archivos, se corre `aplicar-red.ps1` y se puede quitar la raíz propia de las computadoras. No se toca el código.

Guardar la clave de la autoridad cifrada y fuera del equipo, y pedirle al organismo que firme un pedido generado en el equipo, están en la lista de revisión con el primer producto.

## Consecuencias

- **Más fácil:** no se espera al organismo; cambiar de variante es una operación de archivos.
- **Más difícil:** con B, la instalación de la raíz y la renovación anual son del responsable.
- **Para revertir:** reemplazar los archivos y quitar la raíz.

## Fuentes

Consultada el 2026-10-14.

1. Mozilla, «Set up Certificate Authorities (CAs) in Firefox»: https://support.mozilla.org/en-US/kb/setting-certificate-authorities-firefox
