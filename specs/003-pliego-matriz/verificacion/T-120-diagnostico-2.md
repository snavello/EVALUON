# T-120, diagnóstico 2: caso-01 después de T-124 y T-125 (REQ-024, REQ-031)

Solo diagnóstico: no se cambió código, tests, datos ni corridas. Análisis de archivos, sin modelo, sin GPU y sin consultar la base. Fuentes: las dos corridas del caso-01 (`resumen.md`, `resultados.jsonl`, `muestra-descartadas.md`, `muestra-sugerencias.md`), la lista `matriz-esperada.yaml`, el código en `evaluon/tenders/` a main `26cb1c0` y el diagnóstico 1. El texto de los casos no está en este archivo: las filas se citan por número de fila de la corrida nueva (`#N`), tramo y un resumen de su tipo (los corpus de casos no se versionan).

Corridas: **antes** `20261004-194500-4906d80` (sin T-124/T-125) y **después** `20261005-022547-26cb1c0` (main `26cb1c0`).

Limitación de la comparación: `resultados.jsonl` de la corrida anterior está vacío (0 líneas) y cada corrida vuelve a extraer con el modelo, que no es determinista; el número de fila cambia entre corridas. El seguimiento de qué fila terminó dónde se hizo por tramo (conteos de `resumen.md` de ambas) y por los textos de las muestras. Es una estimación firme a nivel de tramo, no una trazabilidad fila a fila. Para trazarla exacta hay que leer `tenders_discarded_row` y `tenders_requirement` de la versión anterior (consulta de solo lectura, a hacer cuando la GPU y la base estén libres).

## Resumen

| Pregunta | Causa | Defecto de | Dónde |
|---|---|---|---|
| 1. M-015 (Circular 2) no cumple ningún punto | La oración nueva del "Debe decir" usa "debe coincidir"; la lista de marcadores de obligación solo tiene "deberá/deberán", así que `_added_obligations` la descarta y no se crea el requisito | Producto (T-124) | `circular_units.py:584`, `run.py:133-144` |
| 2. Descartadas 45 a 11, sobrantes 153 a 200 | Sobre todo el prompt v2 del filtro (la guarda de oración solo manda filas a sugerencia, nunca a firme); además unas 38 sugerencias viejas pasaron a firmes | Producto (T-125, prompt) | `matriz-filtro-v2.md:5, 11, 13, 44` |
| 3. Recuperar descartadas sin perder M-058 y M-063 | M-063 ya lo cubre la guarda; M-058 necesita una regla estrecha y no una regla general que arrastre a todo | Producto (T-125) | `filter.py:394`, `matriz-filtro-v2.md` |

## 1. M-015 de la Circular 2

**Qué esperaba la lista.** M-015 (`matriz-esperada.yaml:306-319`): fila formal de origen `circular`, bloque `circulares` con la Circular 2 (D16), fecha 2026-07-16, efecto `agrega`. La nota de la lista dice que el "Debe decir" repite 7.5.5 y suma un párrafo, y ese párrafo es la fila propia esperada. El ancla es la oración que pide que los datos del firmante del formulario coincidan con quien suscribe la declaración jurada. Para `agrega`, la medición (`evaluation.py`, `measure_circulars`, rama `block.adds`, `_added_points`) pide una fila firme de origen `circular` con cita en D16.

**Qué produjo la pasada de circulares.** Lo que dicen los archivos de la corrida nueva:
- `resultados.jsonl:422`: M-015 `no_cumple`, `fila: null`, los cuatro puntos en falso: no hay fila de origen `circular` emparejada.
- `resumen.md:56`: "requisitos de origen circular sin esperado: 0". En la versión no hay ningún requisito de origen `circular`, ni siquiera uno sobrante.
- `resumen.md:54`: el ruido de D16 es 5 fuentes. Son las cinco citas de la cláusula 7.5.5 que el par "Donde dice / Debe decir" modificó (efecto `modifica`), igual que en el diagnóstico 1. Es decir, `_resolve_pair` sí corrió, aplicó el reemplazo sobre las citas y llamó a `_added_obligations`, y esta no devolvió nada.
- `muestra-sugerencias.md` y `resumen.md`: tampoco hay una sugerencia en un tramo de la Circular 2. La rama de "reformulación probable" (`suggested=True`) tampoco se activó.

**Causa (verificada con el texto de la circular).** `_added_obligations` (`evaluon/tenders/proposal/circular_units.py:564-591`) descarta toda oración que no tenga un marcador de obligación:

```
584:            if (not has_obligation_markers(sentence) or len(body) < MIN_CONTAINED_CHARS
585:                    or body in known or body in seen):
586:                continue
```

`has_obligation_markers` (`run.py:169-172`) compara con `OBLIGATION_MARKERS` (`run.py:133-144`): "deberá", "deberán", "será requisito", "mín.", "máx.", "no se aceptarán", "bajo apercibimiento", "desestim", "se considerará", "se entenderá", "quedará". La oración nueva del "Debe decir" dice que la información del firmante "debe coincidir" con la persona que suscribe: el verbo es **"debe"** (presente), y ninguna de las subcadenas "deberá" ni "deberán" está en "debe coincidir". Tampoco tiene ningún otro marcador. Resultado: la oración es la única nueva del lado "Debe decir" (el resto repite el lado "Dice", verificado en el diagnóstico 1: 4 oraciones nuevas, una larga, que es el ancla), pero se filtra por falta de marcador. El resto de las condiciones se cumplen (no está en `known`, supera `MIN_CONTAINED_CHARS = 15`). No es un problema del par, de `found` ni de la medición.

El diagnóstico 1 propuso comparar el lado nuevo contra el viejo; T-124 lo implementó (commit `464d2ca`/`1a296ac`) y la comparación anda; lo que falló es el filtro de marcadores que T-124 puso encima, copiado de la lista del pliego (formulada con futuro: "deberá") y no de lo que escribe una circular (presente: "debe").

**Corrección propuesta (producto, `circular_units.py`, función `_added_obligations`).**
1. Lista propia para circulares, aparte de `OBLIGATION_MARKERS` (que la extracción usa y no conviene tocar sin medir): comparar con regex de palabra completa `\bdeb(e|en|erá|erán|erían)\b`, más "es obligatorio", "tendrá que", "no podrá", "no podrán", "queda prohibido", "es requisito", "será requisito", "se requiere", más los marcadores de T-093. Se aplica en `circular_units.py:584`.
2. Red de seguridad: dentro de un par "Donde dice / Debe decir", una oración **nueva** (ni en el lado viejo, ni en las citas) sin marcador no se descarta en silencio: va como sugerencia (`suggested=True`) con el motivo de "sin marcador", porque lo que suma una circular es un cambio y la Comisión lo tiene que ver. Esto evita que una variante de verbo vuelva a perder un agregado sin dejar rastro.
3. El mismo problema vive en `_resolve_addition` (`circular_units.py:781`, mismo `has_obligation_markers`) para unidades con verbo "agrega": usar la misma lista.
4. Test sintético: cláusula con tres oraciones y "Debe decir" con una cuarta con "debe coincidir" (y otra con "deben presentar") sin cambios en las tres primeras: espera una fila `circular` por cada nueva, y ninguna por las repetidas.
5. Re-medir solo el caso de ajuste de circulares (`alcance: circulares`): M-015 debería pasar los cuatro puntos y REQ-031 llegar a 15 de 15. Verificar que no aparezcan filas `circular` sin esperado (hoy 0): el lado "Debe decir" de la Circular 1 y las demás oraciones nuevas del 7.5.5 podrían agregar ruido.

Aviso lateral (no se toca): `OBLIGATION_MARKERS` no contiene "debe/deben". La regla de datos del procedimiento (`is_procedure_data`, `circular_units.py:781`) y el tramo `run.py:559` usan la misma lista, así que un apartado con solo "debe" se trata como dato del procedimiento. Conviene revisarlo en T-106 y no en esta corrección.

## 2. Descartadas que ahora son sobrantes o sugerencias

**Balance.** Descartadas 45 a 11 (menos 34). Cada una de las 34 se ubica por tramo (conteo de `resumen.md` antes y después) y por el texto de las muestras:

| Destino de las 34 | Cuántas | Cómo se sabe |
|---|---|---|
| Firmes: M-058 y M-063 (ahora encontradas) | 2 | tramos `sec-i/18.6` y `sec-i/27.1`; `resultados.jsonl:65, 70` |
| Firmes: sobrantes | 14 | tramos con menos descartadas y más sobrantes: 4.11 (2), 4.12, 5.1, 28.1 (2), 25.1, 3.4, 12.9, 8.3, 27.2.3, anexo-ix/p-24, anexo-v/p-4, anexo-iv/p-44 |
| Sugerencias | 18 | tramos con menos descartadas y más sugerencias: pre/p-5, 7.3, 7.4, 14.1, 15.4, 17.1, 17.2, 18.3, 19.3, 22.1, 27.2.2, 27.2.4, anexo-ix/p-1, anexo-ix/p-6, anexo-v/p-2, anexo-iv/p-45, anexo-iv/p-82 (2) |

Para los tramos con 1 descartada y varias filas nuevas (por ejemplo 7.3, 25.1, 3.4) el destino exacto puede variar entre firme y sugerencia; el total de cada columna tiene una incertidumbre de más o menos 2 filas.

**Qué parte de T-125 las dejó pasar.**
- **La guarda de oración (`filter.py:394-418`, llamada en `:551`) casi no interviene.** Solo convierte a `sugerencia` con la duda `duda`, nunca a firme. Las sugerencias por `duda` en la corrida nueva son 3 (`resumen.md:35`): #103 (15.4, un resto de oración sobre apercibimiento de desestimar), #234 (anexo-ix/p-1) y una más, que puede ser la guarda o una duda de B. Son a lo sumo 3 de las 34. Las 14 filas que quedaron firmes no pudieron salir de la guarda.
- **El prompt v2 explica el resto (31 de 34 como mínimo).** El decisor es A (clasificación) más B (¿la oferta puede condicionarlo?); una fila queda descartada solo si A dice descartar con indicio literal y B dice no (`filter.py:307-348`). En la corrida nueva, para las ex-descartadas A dijo "mantener": si B dijo "sí", la fila es firme (sobrante); si B dijo "no", la fila es sugerencia `no_coinciden`. Las sugerencias `no_coinciden` bajaron de 47 a 31 (`resumen.md:34-35`) a pesar de recibir 18 filas más: más filas con A mantener y B sí pasaron a firme. Qué hay en v2 que empuja a mantener: (a) la regla de `matriz-filtro-v2.md:11` (el organismo verifica o exige algo del oferente: mantener), escrita para M-058 pero que cubre cualquier frase con verbo de control; (b) la regla de `:13` (fragmento que continúa una oración); (c) la frase de `:5` y `:44` ("ante la duda, se mantiene") que ya estaba y ahora se refuerza; (d) el reparto de ejemplos: en A hay 2 de descartar contra 5 de mantener (v1 tenía 2 contra 3), en B 4 "sí", 1 "no", 1 "duda" (v1: 2 "sí", 1 "no", 1 "duda"). El modelo lee el balance de ejemplos como una indicación de qué es lo normal.
- Efecto colateral que no es de la guarda ni del prompt: la corrida nueva tiene 50 filas firmes más (278 contra 228). Por tramo, hay unas 38 filas que antes eran sugerencias y ahora son firmes, concentradas en anexo-i (6 tramos), anexo-ii (4), anexo-iv/p-229 (3), 30.1, 11.7, 25.1 y otras; con 7 filas en el sentido contrario (24.6 a 24.9 pasaron de firmes a sugerencias). Las 14 ex-descartadas explican menos de un tercio del aumento de sobrantes (153 a 200, más 47): casi todo el resto son ex-sugerencias que B ahora responde "sí". Por eso volver a subir descartadas solo corregiría una parte; el tope de sobrantes (20 %) no se logra con estas correcciones y sigue en el plan de T-106.

**Ejemplos (corrida nueva, número de fila; el texto es un resumen, no una cita).**

| Fila nueva | Tramo | Tipo (motivo del descarte anterior) | Patrón del texto | Ahora | Quién la dejó pasar |
|---|---|---|---|---|---|
| #8 | sec-i/4.11 | económico: pago (ejecución del contrato) | las facturas se presentan después de publicado el certificado de recepción definitiva en el sitio del organismo | sobrante | prompt (A mantiene por la regla de forma y plazo de pago; B sí) |
| #10 | sec-i/4.12 | formal (dato del procedimiento) | los documentos se remiten a una casilla de correo del organismo | sobrante | prompt (la guarda no puede dejar firmes) |
| #183 | sec-i/28.1 | formal (ejecución del contrato) | "el deber de confidencialidad alcanza a toda información a la que accedan" | sobrante | prompt (A mantiene, B sí; oración vecina #181 firme) |
| #172 | sec-i/27.2.3 | económico (norma aplicable) | cola de oración: "mediante alguna de las formas previstas en el artículo N del Pliego Único" | sobrante | prompt (regla `:13`: continúa una oración firme; correcto mantenerla, no es un error) |
| #210 | sec-iv/anexo-v/p-2 | formulario (dato del procedimiento) | ejemplos entre paréntesis que ilustran un campo ("Ej. trabajos en altura...") | sugerencia `no_coinciden` | prompt (A mantiene, B no) |
| #237 | sec-iv/anexo-ix/p-6 | título | instrucción al pie de un formulario: marcar una opción con una X | sugerencia `no_coinciden` | prompt (A mantiene, B no) |
| #112 | sec-i/17.1 | formal (dato del procedimiento) | cómputo del plazo: el día de la apertura queda excluido | sugerencia `no_coinciden` | prompt |
| #126 | sec-i/19.3 | formal (indicio no literal) | la falta de cotización de un renglón es causal de desestimación para el grupo | sugerencia `descarte_sin_sustento` | ni guarda ni prompt: A sí quiso descartar pero el indicio no está literal (`filter.py:326-331`); cae en `decide` |
| #103 | sec-i/15.4 | formal (consecuencia) | resto de oración "bajo apercibimiento de desestimar la oferta" | sugerencia `duda` | guarda de oración (comparte oración con una fila firme) o B duda |
| #267 | anexo-iv/p-44 | técnico (ejecución) | el fabricante entrega planos de replanteo con medidas verificadas | sobrante | prompt |

Lectura: de los 10 ejemplos, 6 son descartes legítimos que el v1 hacía bien (#8, #10, #183, #210, #237, #112); #172 y #103 son colas de oración que conviene proteger (la guarda lo hace como sugerencia, que es lo correcto); #126 es un descarte sin indicio literal que ya iba a sugerencia; #267 es técnico del anexo, discutible.

**Riesgo nuevo.** Quedan descartadas dos filas del mismo tipo que M-058: #128 (sec-i/18.6, "este Organismo verificará el cumplimiento de lo estipulado en una Resolución General y sus complementarias, previo a la adjudicación") y #60 (sec-i/8.3, "la Comisión Evaluadora realizará la verificación de su cumplimiento como condición esencial para la adjudicación"). La regla de `matriz-filtro-v2.md:11` no las alcanzó. No están en la lista esperada como filas propias y por eso no cuentan, pero es el mismo patrón sujeto-organismo/objeto-oferente. Revisarlas con la Comisión: si son requisitos, la regla de v2 es insuficiente además de excesiva.

## 3. Cómo recuperar descartadas legítimas sin perder M-058 y M-063

**Dónde está cubierta cada una.**
- **M-063** es la cola de la misma oración que una fila firme del tramo (R146 en 27.1, diagnóstico 1). La guarda (`protect_shared_sentences`, `filter.py:394`) ya la protege sin necesitar el prompt: pasa a sugerencia con `duda`. Las sugerencias con pareja esperada se suman a los encontrados como "a revisión obligatoria" (`resumen.md:23-24`, mismo mecanismo que M-055), así que M-063 sigue contando.
- **M-058** es otra cosa: no comparte oración con una fila firme; el filtro la leyó por el sujeto ("el organismo verifica") y no por el objeto. Hoy la protege solo la regla general de `matriz-filtro-v2.md:11`, que es lo que arrastra todo lo demás a "mantener".

**Corrección propuesta (en orden): v3 del filtro más una tercera opinión solo sobre los descartes.**
1. **Prompt v3, A y B vuelven al balance de v1** (dos descartar y tres mantener en A, dos "no" en B), con los dos ejemplos nuevos de v2 en forma de contraejemplo estrecho: un ejemplo inventado de "el organismo verifica una condición del oferente (multas pendientes): mantener" y uno de "el organismo cumple una obligación propia sin referencia al oferente: descartar". Se quitan de `:5` y `:44` las frases de "ante la duda, mantener", porque la duda ya la maneja el código (la fila sin acuerdo va a sugerencia). Se agregan al menos tres ejemplos de descarte de los patrones que v2 dejó pasar: presentación de facturas tras la recepción (ejecución del contrato), envío a una casilla de correo (dato del procedimiento) y la instrucción "marque con una X" (formulario). Hay que escribirlos con otro objeto de contratación para no sobreajustar al caso-01.
2. **Una tercera pregunta C solo para filas que A y B descartarían** (hoy 11 a unas 40 filas por corrida, así que cuesta poco): "En la frase, ¿lo que se verifica, controla o exige es algo del oferente o de su oferta (deudas, inscripción, sanciones, habilitación, documentos)? si, no, duda". Si C responde si o duda, la fila va a sugerencia (`doubt_reason: "oferente_verificado"`) y no se descarta. Es independiente de A y B (otro prompt, otra pregunta), a diferencia de B, que contesta con el mismo sesgo que A (diagnóstico 1, sección 4). Esto protege M-058 sin que la regla general empuje a las demás filas a firmes. Se hace en `filter.py` dentro de `decide`/`Filter.run` (donde hoy se llama a `protect_shared_sentences`, `:551`) y se registra como un paso más en `tenders_run_step`.
3. **Mantener la guarda tal como está** (`filter.py:394-418`): cubre M-063 y las colas de oración. Ya tiene tests; no depende del prompt.
4. **Medir en el caso de ajuste del filtro** (antes de la corrida completa): deben cumplirse M-058 y M-063 como encontradas o en "a revisión obligatoria", descartadas de vuelta por encima de 30 (el v1 llegaba a 45), `#128` y `#60` decididas con C, y sugerencias por debajo de 60.

**Alternativa descartada: volver a v1 y solo agregar la guarda.** Recupera las 34 descartadas, pero M-058 vuelve a perderse (la guarda no la ve) y quedan 2 de 93 en riesgo.

**Alternativa descartada: regla de código por palabras ("oferente", "deuda", "verificará").** No generaliza y es lo que el diagnóstico 1 pidió evitar ("sin nombrar cláusulas").

## Tabla de causas

| Efecto observado | Causa | Parte de T-125/T-124 | Evidencia |
|---|---|---|---|
| M-015 no cumple los 4 puntos | marcador "deberá/deberán" no reconoce "debe"; la oración nueva se descarta | T-124 (`_added_obligations`) | `circular_units.py:584`, `run.py:133-144`; `resultados.jsonl:422`; `resumen.md:54, 56` |
| 34 descartadas dejan de serlo | A responde "mantener" y B "sí" o "no" | T-125, prompt v2 | `matriz-filtro-v2.md:5, 11, 13, 44`, ejemplos; sugerencias `no_coinciden` 47 a 31 |
| 14 de esas son sobrantes (más 2 encontradas legítimas) | igual, con B "sí" | T-125, prompt v2 | tramos 4.11, 4.12, 5.1, 28.1, 25.1, 3.4, 12.9, 8.3, 27.2.3, anexo-ix/p-24, anexo-v/p-4, anexo-iv/p-44 |
| 18 de esas son sugerencias | A mantiene y B "no" (o `duda`) | T-125, prompt v2 y a lo sumo 3 de la guarda | `resumen.md:35`; #103, #234 |
| Sobrantes suben 47, más de lo que explican las descartadas | unas 38 sugerencias viejas pasan a firmes (B contesta "sí") y la extracción da 50 filas firmes más | T-125 (prompt) y variación de la extracción | conteos por tramo de `resumen.md` antes y después |
| Guarda de oración casi inerte | solo baja a sugerencia, nunca sube a firme | T-125, `filter.py:394` (como se diseñó) | `duda: 3` en `resumen.md:35` |
| M-058 y M-063 encontradas | M-058 por la regla de `:11`; M-063 por la regla de `:13` o por la guarda | T-125 | `resultados.jsonl:65, 70` |

## Correcciones propuestas, ordenadas por impacto

| Orden | Corrección | Dónde | Efecto esperado | Riesgo |
|---|---|---|---|---|
| 1 | Prompt v3 del filtro: balance de ejemplos de v1, contraejemplos de descarte, sin "ante la duda mantener" | `evaluon/tenders/prompts/matriz-filtro-v3.md`, `filter.py` (`RULE_VERSION`) | recupera hasta 34 descartadas; sobrantes bajan unos 14 a 20; sugerencias de B-sí bajan | M-058 se vuelve a perder si se hace sola |
| 2 | Tercera opinión C solo sobre los descartes: "¿lo que se verifica es del oferente?" | `filter.py` (`decide`, `Filter.run`), prompt nuevo | protege M-058 y #128/#60 sin sesgar a las demás filas | un pedido más por corrida (tiempo menor) |
| 3 | Marcadores propios de circulares con "debe/deben" y red de seguridad como sugerencia | `circular_units.py:584` (y `:781`) | M-015 pasa los 4 puntos; REQ-031 15 de 15 | ruido de filas `circular` a verificar con la medición |
| 4 | Mantener la guarda de oración sin cambios | `filter.py:394` | M-063 protegida por código | ninguno |
| 5 | Revisar con la Comisión las descartadas #128 y #60 | caso-01, sin código | decide si v2 es insuficiente | ninguno |
| 6 | Medir sobrantes tras 1 a 3 (tope 20 %): no se alcanza solo con el filtro; ver T-106 | medición | informa cuánto falta | ninguno |

Las correcciones 1 y 2 van juntas (una sin la otra rompe M-058); la 3 es independiente y se puede hacer en paralelo en otra tarea, porque toca archivos distintos (`circular_units.py` contra `filter.py` y prompts).
