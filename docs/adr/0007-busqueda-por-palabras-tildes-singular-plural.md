# ADR-0007 · Búsqueda por palabras: tildes, singular y plural

Estado: aceptado · Fecha: 2026-10-02 · Decidió: responsable del proyecto, 2026-10-02

## Contexto

La búsqueda por palabras de Postgres es uno de los tres caminos de la consulta (ADR-0003) y la base de la búsqueda directa por palabras (REQ-010). Tiene que cumplir dos cosas a la vez:

- **Sin distinguir tildes.** Los usuarios van a escribir "licitacion" y el texto dice "licitación". Además, hay textos sin tildes en el corpus: Infoleg escribe en mayúsculas sin acento ("ARTICULO 14.- GARANTIAS"), y la lectura sobre imagen puede perderlos.
- **Sin distinguir singular y plural.** Quien busca "licitación" tiene que encontrar un artículo que habla de "licitaciones", y al revés. Para eso se reduce cada palabra a su raíz con el lematizador de español que trae Postgres (Snowball).

El plan aprobado definía una configuración `spanish_unaccent`: la de español de Postgres, quitando los acentos **antes** de reducir a la raíz (ADR-0003, alternativa 3.A). La etapa 0 midió en el Postgres fijado (17.11, imagen `pgvector/pgvector:0.8.7-pg17-bookworm`) que esa definición rompe el singular y el plural de las palabras terminadas en "-ación" y "-ución", que son muchas en compras públicas (`specs/001-normativa/entorno.md`, T-004, sección 5):

| Palabra | `spanish` | Quitar acentos y después raíz (plan) |
|---|---|---|
| licitación | `licit` | `licitacion` |
| licitacion | `licitacion` | `licitacion` |
| licitaciones | `licit` | `licit` |
| adjudicación / adjudicaciones | `adjud` / `adjud` | `adjudicacion` / `adjud` |
| contratación / contrataciones | `contrat` / `contrat` | `contratacion` / `contrat` |
| garantía / garantías | `garant` / `garant` | `garanti` / `garanti` |
| artículo / artículos | `articul` / `articul` | `articul` / `articul` |

Con la definición del plan, ni "licitacion" ni "licitación" encuentran un pasaje que solo dice "licitaciones". Con `spanish` sola, el singular y el plural coinciden, pero solo si la búsqueda lleva la tilde: "licitacion" queda como `licitacion` y no encuentra nada escrito con tilde, y "garantia" queda como `garanti` frente a `garant`.

**Por qué pasa.** El lematizador de Postgres 17 reconoce el sufijo "-ación" con tilde y el plural "-aciones", que no lleva tilde, pero no reconoce "-acion" sin tilde; lo mismo con "-ución". Al final de su algoritmo quita las tildes que quedan [F2]. Los autores de Snowball corrigieron exactamente esto en la versión 3.0.0, del 8 de mayo de 2025: "Handle -acion like -ación and -ucion like -ución" [F3]. Postgres 17.11 trae una versión anterior, como muestra la medición. No verifiqué en qué versión de Postgres entra Snowball 3.

**Restricciones.** Sin servicios externos (P4). Sin cambiar la imagen de la base fijada en T-004 salvo que haga falta (P5). Lo mínimo que cumpla (P10). Los números de norma con barra ("297/03", "247/2022") no tienen que romperse: hoy el analizador los guarda enteros (T-004, sección 6).

## Alternativas

### A. Dejar la definición del plan (quitar acentos y después reducir a la raíz)
Se gana: nada nuevo que construir. Se pierde: singular y plural de "-ación" y "-ución" dejan de coincidir, con tilde y sin tilde. Es la familia de palabras más frecuente del dominio (licitación, adjudicación, contratación, notificación, evaluación, impugnación, resolución).

### B. Usar `spanish` sola
Es la configuración que trae Postgres. Se gana: singular y plural coinciden cuando se escribe con tilde, sin nada propio. Se pierde: la búsqueda sin tilde, que pide el plan para REQ-010 ("licitacion" no encuentra "licitación"; "garantia" no encuentra "garantía"), y los textos del corpus escritos sin tilde quedan con otras raíces.

### C. Reducir a la raíz antes de quitar acentos
Es lo primero que se pensó. No se puede armar con los diccionarios de Postgres: en una configuración, un diccionario le pasa la palabra al siguiente solo si es "filtrante", como `unaccent`; el de Snowball reconoce todo y siempre es el último [F1]. Y aunque se pudiera, daría lo mismo que B: Snowball ya quita las tildes al terminar [F2]. El problema no está en el orden sino en la palabra sin tilde, que el lematizador de esta versión no sabe reducir.

### D. Normalizar el texto y la consulta igual, reponiendo la tilde de "-ación" y "-ución" (recomendada)
Texto del pasaje y texto de la consulta pasan por la misma función antes de la configuración `spanish`:

1. Se quitan todos los acentos con `unaccent`.
2. Se vuelve a poner la tilde en las palabras terminadas en "acion" o "ucion": "licitacion" pasa a "licitación". No es una adivinanza: en español toda palabra terminada en "-ación" o "-ución" lleva tilde, y los plurales ("-aciones", "-uciones") no la llevan.
3. Se reduce a la raíz con `spanish`.

Es el mismo arreglo que trae Snowball 3.0.0 [F3], hecho antes del lematizador.

Se gana: con tilde o sin ella, en mayúsculas o minúsculas, singular y plural coinciden; una sola columna `tsv`, un solo índice, la frase exacta sigue funcionando igual; no cambia la imagen de la base. Se pierde:

- Una regla propia, de dos terminaciones, que hay que mantener. Si un Postgres futuro trae Snowball 3, la regla queda de más pero no estorba.
- Las palabras que se distinguen solo por la tilde se confunden ("público" y "publico", "está" y "esta"). Pasaba igual con la definición del plan.
- `unaccent` está marcada en Postgres como función no inmutable, porque depende de qué diccionario encuentre. Para que `tsv` sea una columna calculada por la base, la función propia se declara inmutable y llama a `unaccent` con el diccionario nombrado con su esquema. Es la forma habitual de hacerlo; el costo es que, si cambian las reglas de `unaccent` o el lematizador al actualizar Postgres, hay que recalcular `tsv`.

### E. Dos columnas de búsqueda, con y sin acentos, y la consulta por las dos
Se guarda el resultado de `spanish` y el de quitar acentos y reducir, y la consulta busca en los dos. Sin reponer la tilde no resuelve el caso: "licitacion" da `licitacion` por los dos lados y "licitaciones" da `licit` por los dos lados. Con la regla de D sí funciona, pero suma una segunda columna, una consulta en dos partes y casos raros en las búsquedas con "y" y con frase. Es D con más piezas.

### F. Diccionario `ispell` o `hunspell` de español
Reduce cada palabra a su forma de diccionario ("licitaciones" a "licitación") en lugar de cortar sufijos. Se gana: mejor tratamiento de la morfología en general. Se pierde: hay que sumar los archivos del diccionario a la imagen de la base (cambia la imagen fijada en T-004 o se monta un volumen), fijar su versión y su licencia, pasarlos por `unaccent` para que sirvan sin tildes, y cada conexión los carga en memoria. Las palabras que no están en el diccionario igual caen en Snowball. Ningún requisito pide más que singular y plural (P10).

### G. Vocabulario sacado del corpus
Al indexar, se arma una tabla que dice, para cada palabra escrita sin tilde, qué raíz tiene la forma con tilde que aparece en el corpus ("licitacion" → `licit`). La consulta la usa para completar sus palabras. Se gana: resuelve cualquier caso de tilde, no solo dos terminaciones. Se pierde: una tabla y un proceso de llenado más, y depende de que la forma con tilde esté en el corpus. Hoy no hay evidencia de otros casos que lo justifiquen.

### H. Sin reducir a la raíz
Solo quitar acentos y pasar a minúsculas. Se gana: comportamiento obvio. Se pierde: singular y plural dejan de coincidir para todas las palabras, salvo que la persona busque por prefijo.

## Decisión

Se propone la alternativa D: una normalización común para el texto y la consulta (quitar acentos y reponer la tilde de "-ación" y "-ución") seguida de la configuración `spanish` de Postgres. Motivo principal: es el único cambio chico que deja coincidir singular y plural con y sin tilde, sin sumar piezas a la imagen de la base, y replica una corrección que los autores del lematizador ya adoptaron.

Cómo queda en la base, todo en una migración de T-009, con su reversa:

| Función | Qué hace |
|---|---|
| `search_normalize(texto)` | Quita acentos con `unaccent` y repone la tilde en las palabras terminadas en "acion" o "ucion", sin distinguir mayúsculas |
| `search_document(texto)` | `to_tsvector('spanish', search_normalize(texto))`. Calcula la columna `tsv` de `norms_passage` |
| `search_query(texto)` | `websearch_to_tsquery('spanish', search_normalize(texto))`. La usan el camino por palabras (palabras unidas por "or") y la búsqueda directa (comillas para frase exacta) |

Las tres se declaran inmutables. Nada fuera de ellas arma la columna `tsv` ni una consulta de texto. La configuración `spanish_unaccent` del plan aprobado no se crea.

### Resultado esperado y cómo se comprueba

No pude correrlo en Postgres al redactar este ADR. Lo que sigue se deduce de las mediciones de T-004 (que dan la raíz de `spanish` para cada forma con y sin tilde) y de las reglas de Snowball [F2]. T-009 lo comprueba en la base real como parte de su verificación, y si algún valor difiere se informa antes de seguir.

| Palabra | Después de `search_normalize` | Lexema |
|---|---|---|
| licitación, licitacion, LICITACIÓN | licitación (la tercera, `LICITAción`: el lematizador pasa a minúsculas) | `licit` |
| licitaciones | licitaciones | `licit` |
| adjudicación / adjudicaciones | adjudicación / adjudicaciones | `adjud` / `adjud` |
| contratación / contrataciones | contratación / contrataciones | `contrat` / `contrat` |
| artículo, artículos, articulo | articulo, articulos, articulo | `articul` |
| garantía, garantías, garantia | garantia, garantias, garantia | `garanti` |
| 297/03 | 297/03 | `297/03` |
| 247/2022 | 247/2022 | `247/2022` |

Prueba de T-009: cada palabra de una fila, usada como consulta con `search_query`, encuentra un pasaje que contiene cualquiera de las otras formas de la misma familia, y no encuentra los pasajes de las otras familias. "297/03" y "247/2022" se encuentran a sí mismos, como en T-004.

Script de comprobación, para una base de prueba que se borra al terminar:

```sql
CREATE EXTENSION unaccent;
CREATE FUNCTION search_normalize(t text) RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT regexp_replace(public.unaccent('public.unaccent'::regdictionary, t),
                        '([au])cion\M', '\1ción', 'gi') $$;
SELECT w, search_normalize(w), to_tsvector('spanish', search_normalize(w))
FROM unnest(ARRAY['licitación','licitaciones','licitacion','LICITACIÓN',
  'adjudicación','adjudicaciones','contratación','contrataciones',
  'artículo','artículos','articulo','garantía','garantías','garantia',
  'Disposición 297/03','Disposición 247/2022']) AS w;
```

### Comprobación del Coordinador (2026-10-02)

Corrí el script en una base temporal del servicio `db` (Postgres 17.11, imagen fijada en T-004), borrada al terminar. Los lexemas de la tabla de arriba se confirman todos. Además:

- **Coincidencias cruzadas** entre las familias licitación, adjudicación, contratación, artículo, garantía y los números 297/03 y 247/2022, con `to_tsvector('spanish', search_normalize(...)) @@ plainto_tsquery('spanish', search_normalize(...))`: 54 de 54 pares de la misma familia coinciden, y ningún par de familias distintas.
- **Otras terminaciones.** resolución / resoluciones / resolucion dan `resolu`. Las familias en "-ición", "-pción", "-sión" y "-ón" ya coinciden con `spanish` y la regla no las cambia: disposición, condición, sanción, excepción, opción, admisión, comisión y razón, con su plural y sin tilde.
- **Limitación que la regla no resuelve, y que tampoco resuelve la definición del plan ni `spanish` sola:** el singular y el plural de las palabras en "-men" no comparten raíz. "régimen" da `regim` y "regímenes" o "regimenes" dan `regimen`; "dictamen" da `dictam` y "dictámenes" da `dictamen`. Buscar "régimen" no encuentra "regímenes". Si importa, se puede extender la regla de `search_normalize`. Hasta entonces, el camino por significado cubre estos casos.
- **La eñe.** `unaccent` convierte "ñ" en "n", así que "año" y "ano" comparten lexema; pasaba igual con la definición anterior del plan. Lo aceptó el responsable el 2026-10-02: es un caso raro en la normativa de compras y el camino por significado lo compensa (T-009).

## Consecuencias

**Más fácil.** La búsqueda se comporta igual con o sin tildes y en singular o plural, y la regla está en un solo lugar de la base, que usan los dos caminos que buscan por palabras.

**Más difícil.**

- Hay una regla propia que mantener y probar. La prueba de T-009 la cubre con la tabla de arriba.
- Al actualizar Postgres de versión mayor (o la imagen fijada), hay que recalcular `tsv` de todos los pasajes y repetir la prueba: un lematizador nuevo, como Snowball 3, puede cambiar raíces.

**Para revertirla.** Una migración reemplaza las tres funciones y recalcula `tsv`. Los datos no se pierden: `tsv` se deriva del texto del pasaje. Como cambia lo que trae el camino por palabras, hay que correr el conjunto de preguntas (P7).

## Fuentes

Consultadas el 2026-10-02.

- [F1] PostgreSQL 17, diccionarios de búsqueda de texto (diccionarios filtrantes; Snowball reconoce todo y va al final): https://www.postgresql.org/docs/17/textsearch-dictionaries.html
- [F2] Snowball, algoritmo de raíz para español (sufijos del paso 1 y "And finally: Remove acute accents"): https://snowballstem.org/algorithms/spanish/stemmer.html
- [F3] Snowball, notas de versión: 3.0.0 (2025-05-08), "Handle -acion like -ación and -ucion like -ución": https://raw.githubusercontent.com/snowballstem/snowball/master/NEWS
- [F4] PostgreSQL, sincronización de Snowball en la rama principal del 2025-02-19 (sin la versión 3.0.0, que es posterior): https://www.postgresql.org/message-id/E1tkZbJ-0003lu-1z%40gemulon.postgresql.org
- Mediciones propias: `specs/001-normativa/entorno.md`, T-004, secciones 4 a 6.
