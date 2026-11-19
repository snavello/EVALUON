# Spec 021 · Una imagen por proyecto de trabajo

Estado: aprobada · Fecha: 2026-11-19 · Aprobó: responsable del proyecto (2026-11-19, «Sí, corregir») · Carril: liviano (ADR-0081, elegido por el responsable el 2026-11-19)

> La spec dice qué se necesita y por qué. Cada duda se marca `[A ACLARAR: pregunta concreta]`.

## Problema

El piloto y las copias de trabajo (desarrollo, verificación, auditoría, suite completa) construyen la imagen de la aplicación con el mismo nombre. Cuando una copia construye, pisa el nombre que usa el piloto. En el despliegue de la 020 (2026-11-19) la imagen con la que corría el piloto ya no existía en el equipo: no se pudo guardar tal cual para volver atrás y hubo que reconstruirla. Además, un reinicio del piloto sin reconstruir habría levantado código de otra copia (`specs/020-evi-guia-del-procedimiento/runbook.md`, «Fallas conocidas»).

## Qué se necesita

- **REQ-174 · La imagen del piloto es solo del piloto.** Construir la aplicación desde una copia de trabajo, con un proyecto distinto del piloto, no cambia la imagen que usa el piloto. El piloto conserva el nombre de imagen que tiene hoy, de modo que los runbooks y las imágenes guardadas (`antes-NNN`) siguen valiendo.
- **REQ-175 · El clon y la demo siguen usando la imagen del piloto.** Los entornos que a propósito corren con la imagen ya construida del piloto (clon y demo) no cambian de comportamiento.

## Fuera de alcance

- Fijar las versiones de las dependencias indirectas (queda para decidir aparte).
- Borrar imágenes viejas del equipo.
- Cualquier cambio en la aplicación, los datos o el esquema.

## Criterios de aceptación

1. Con el proyecto del piloto, la configuración resuelve el mismo nombre de imagen que hoy.
2. Con cualquier otro proyecto, resuelve un nombre distinto, propio de ese proyecto.
3. Un test falla si la configuración vuelve a fijar un nombre único para todos los proyectos.
4. Comprobación real del Coordinador: después de construir desde una copia de trabajo con otro proyecto, la huella de la imagen del piloto es la misma que antes.
5. Los tests del clon y de la demo siguen pasando sin cambios en esos entornos.

## Plan corto

Una tarea (T-369): en la configuración común de la aplicación, el nombre de la imagen se arma con el nombre del proyecto, con el del piloto por omisión. Sin cambios en el clon ni en la demo. No requiere desplegar: el piloto resuelve el mismo nombre que ya usa; rige desde el próximo `git pull` de la raíz.
