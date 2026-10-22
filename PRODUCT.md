# Product

<!-- impeccable:product-schema 1 -->

Registro del producto para la skill impeccable. Lo escribió el Coordinador el 2026-10-21 a partir de `specs/constitution.md`, `CLAUDE.md` y las specs aprobadas; cada dato sale de ahí. Lo que no está decidido figura como abierto. Manda la constitución: si este archivo y ella difieren, se corrige este.

## Platform

web

## Users

- **Comisión Evaluadora de compras de la AFIP (hoy ARCA).** Sus integrantes revisan pliegos y ofertas de un procedimiento de compra y firman el dictamen. Trabajan en la oficina, con luz de día, en jornadas largas, con expedientes, pliegos de decenas de páginas y ofertas en varios documentos.
- **Operador de carga.** Toma datos y documentos del Portal de Compras o sube archivos; no decide.
- **Responsable del proyecto.** Aprueba specs, planes y despliegues.

## Product Purpose

EVALUON consolida la normativa de compras (Disposiciones AFIP 247/2022 y 297/03, complementarias y marco nacional), revisa pliegos contra esa normativa y asiste a la Comisión Evaluadora para determinar si las ofertas cumplen el pliego. El éxito cercano es un piloto de evaluación guiada que corre en paralelo con la evaluación habitual.

## Positioning

El sistema recomienda y la Comisión decide (P3). Toda conclusión muestra su fundamento: el fragmento del pliego o de la oferta con su cita, el dato del Portal con fecha, la ausencia verificada en la lectura completa de la oferta o la respuesta registrada de la Comisión. Sin fundamento, el resultado es «no determinado». Corre en un equipo propio con IA local (P5).

## Operating Context

- El eje es el procedimiento de compra, en cinco secciones sin orden obligatorio: Procedimiento, Pliego y matriz, Ofertas, Evaluación y dictamen, Normativas (decisión del 2026-10-07).
- Nada se tipea si sale del Portal de Compras o de un archivo: se toma del Portal o se sube, y la Comisión aprueba la carga.
- La Comisión cita documentos por expediente y foja, y deja constancia de cada decisión con fecha y persona.

## Capabilities and Constraints

- Aplicación web servida desde el propio equipo; sin dependencias externas en producción (P4, P5). Las tipografías se alojan en el equipo.
- Fase de construcción: solo material público o ficticio en el repositorio y en las maquetas (P4).
- Estados de cumplimiento: cumple, no cumple, no determinado y pendiente. Se muestran como ícono de color con forma propia, y el nombre aparece al pasar el mouse o con el foco (guía visual, decisión del 2026-10-07).
- Tema claro (gris y blanco) u oscuro (negro), elegido por cada usuario (spec 017).

## Brand Commitments

- Nombre: EVALUON. Logotipo «EVALU ON» e isotipo «E + on», aprobados el 2026-10-13 (`docs/diseno/marca/`). Desde el 2026-10-21 se usan recoloreados a negro, gris y verde lima, con la misma forma, vidrio y halo (`docs/diseno/marca/017/`, spec 017).
- Voz: español rioplatense administrativo, claro, sin jerga técnica en pantalla; los controles dicen su acción.

## Evidence on Hand

- Caso de muestra ficticio «Alimento balanceado para perros» (CD 99/2026) en las maquetas de `docs/diseno/`.
- Casos públicos reales de la AFIP en el corpus de pruebas. Lo reservado no entra al repositorio ni a las maquetas.

## Product Principles

1. La Comisión decide; la pantalla muestra el fundamento de cada propuesta.
2. Lo pendiente se ve primero, con su acción a mano.
3. Nada se tipea si existe en el Portal o en un archivo.
4. Constancia de quién hizo qué y cuándo.
5. Simplicidad: solo lo que pide un requisito (P10).

## Accessibility & Inclusion

Contraste WCAG AA en todo texto y componente, uso completo con teclado y un camino con «reducir movimiento».
