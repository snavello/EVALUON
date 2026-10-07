# Prueba con un proceso nuevo (AABN5)

Fecha: 2026-10-07 (10:48 a 11:23, hora local). Proceso: AABN000000-0005-CDI26 (servicio de higiene y seguridad en el trabajo; 4 renglones; 2 ofertas; ya adjudicado). Usuario: `desarrollo-comision`. Base real, con datos públicos. Código: `main` en `0ba51ac`. No se tocó código.

Objetivo: usar el producto como lo usaría la Comisión, de punta a punta, sin los documentos de las ofertas (no son públicos), y contar qué funciona y qué no. El dictamen y su anexo se leyeron recién al final, para comparar.

Respaldo previo: `backups/evaluon-2026-10-07-previo-prueba-aabn5.dump` (126 MB). GPU libre antes de empezar y antes de cada pedido (`docker top ... | grep medir` vacío en `app` y `worker`).

## Resumen por etapa

| Etapa | Resultado | Tiempo |
|---|---|---|
| 012 · registrar y explorar | Funciona | 36 s (pedido `portal_explore`) |
| 012 · aprobar y cargar | Funciona, con una reserva (circular triplicada) | segundos |
| 003 · proponer matriz | Funciona; propuesta con huecos graves | 8 min 41 s (pliego de 23 páginas, 143 tramos) |
| 003 · revisión por la Comisión | Posible, pero lenta y con una limitación del producto | unos 20 min (escritura por script) |
| 003 · validar | Validada, solo después de completar a mano lo que faltaba | inmediato |
| 004 · evaluar | No arranca sin documentos de la oferta; con un documento de relleno corre | 4 min 40 s para 2 ofertas |
| 004 · datos del Portal | Se muestran, pero no se comparan con ningún requisito de garantía ni de presupuesto | |

## 012 · Importación desde el Portal

Qué funcionó:
- Registrar el enlace y explorar: la propuesta apareció en 36 s con el procedimiento, 4 renglones, 9 documentos y actos, 2 ofertas con total, garantía y cotización por renglón.
- Los dos documentos que el Portal sirve con pantalla de error (pliego general y su disposición aprobatoria) quedaron como anomalía en la propuesta, sin frenar el resto, como dice el runbook.
- Los caracteres dañados del Portal (encuadre legal, garantías) se marcaron como dañados y se mostraron tal cual.
- La fecha de autorización, que el Portal no muestra, se propuso como candidata con su origen y se pidió confirmarla.
- Aprobación parcial (procedimiento, renglones, cláusulas particulares, acta, una circular y las 2 ofertas) con resultado «cargado» o «guardado_como_archivo» por ítem. Las ofertas se crearon con los datos del Portal. El pliego se leyó en segundos.
- La revisión del Portal corrió sola justo después de la exploración (pedido `portal_review`), sin pedirla; terminó sin novedades.

Qué no, o con reservas:
- La circular llega tres veces: como acto («Autorización circular»), como anexo PDF sin fecha ni tipo y como página `Circular_1.html` con tipo «Sin consulta». Hay que elegir una; se aprobó la página con tipo «Modificatoria». La circular solo prorroga fechas, pero el sistema no lo sabe de antemano. Menor.
- El objeto del proceso viene cortado a 100 caracteres desde el Portal y se guarda así; no se avisa que está truncado. Menor.

## 003 · Matriz

Propuesta del sistema: 93 formales, 6 económicos, 4 filas técnicas (una por renglón), 34 pendientes de revisión, 4 sugerencias sin decidir, 103 consecuencias sin elegir. Descartó 1 fila y unificó 9. Cobertura: 143 tramos; 73 descartados, 48 con requisitos, 1 fila técnica, 21 pendientes. Consecuencias sugeridas: 59 «intimación a subsanar», 24 «desestimación sin subsanar», 16 sin fundamento («no determinada»). 23 anomalías `circular_cambios_vacios` (esperable: la circular no cambia requisitos).

Revisión contra el pliego (cláusulas particulares):

| Tema | Qué hizo el sistema |
|---|---|
| Visita obligatoria (cláusula 10, con desestimación si no se hace) | No la propuso. El tramo quedó «no ubicado» y pendiente. Solo apareció una oración del anexo del certificado de visita («no podrá alegar ignorancia»), que no es un requisito |
| Anexo del certificado de visita como documento a presentar | No propuesto |
| Título y matrícula profesional (6.2 y 6.3) | No propuestos (tramo pendiente) |
| Domicilio especial (14.1) y declaración jurada de intereses (14.3) | No propuestos (tramo pendiente) |
| Garantía de mantenimiento | Ausente. El pliego particular no la menciona; sale del régimen y de la página del Portal. La sugerencia por norma (REQ-036) no apareció |
| Cotizar en la planilla del Anexo IV (12.2) | Propuesto |
| Requisitos técnicos | 4 filas, una por renglón, con las cláusulas comunes y la del renglón (5.1.x) y la planilla. Razonable |
| Requisitos externos | No hubo (el pliego no los trae) |
| Sobrantes | Muchos: obligaciones del adjudicatario posteriores a la adjudicación (personal, uniformes, ART, responsabilidad) clasificadas como formales; frases partidas en varios requisitos; celdas sueltas de las tablas de los anexos (declaración de intereses, planilla de cotización) tomadas como requisitos |

Causa visible de los huecos: todo el cuerpo de la sección II del pliego (páginas 5 a 13) quedó en 34 «tramos no ubicados», pendientes sin propuesta. El sistema no afirmó nada de ellos (P3), y la matriz quedó marcada «BORRADOR INCOMPLETO». El pendiente no muestra el texto del tramo: hay que abrir el original en la página indicada.

Qué se hizo como Comisión (por la pantalla, con el usuario de desarrollo): se quitaron unos 50 requisitos que no exigen nada a la oferta; se decidieron las 4 sugerencias; se agregaron a mano 7 requisitos (visita obligatoria, no realización de la visita, certificado de asistencia, título, matrícula, domicilio especial, declaración de intereses); se resolvieron los pendientes restantes como «revisado, sin requisitos»; se confirmaron 65 (2 se quitaron después); se aceptaron 51 consecuencias sugeridas y se eligieron 12 a mano; se validó (versión 1, validada).

Decisión sobre la validación: la matriz del sistema no se habría podido validar tal cual (faltaba la visita obligatoria). Se validó solo la versión corregida a mano, para poder seguir con la 004; lo que sigue vale para esa versión.

Hallazgos de uso de la 003:
- Un tramo pendiente admite un solo requisito agregado: el segundo intento falla con «Ese pendiente ya está resuelto». Hay que usar el formulario general de agregar (sin el pendiente), que sí admite varios sobre el mismo tramo. Un tramo con varias cláusulas obliga a rodear la pantalla.
- Cada acción sobre la matriz devuelve la página completa (unos 3 MB de HTML con ~100 requisitos): 2 a 4 s por clic. Quitar 47 requisitos tomó unos 2 min.
- Una consecuencia «consultar al oferente» exige tramo y fragmento literal; las demás, solo motivo. Para las 4 filas técnicas no hay sugerencia ni fundamento y hubo que elegir una consecuencia con motivo para poder validar.
- Un requisito sin sugerencia de consecuencia (los agregados a mano) exige elegirla por completo a mano.

## 004 · Evaluación

Sin documentos de las ofertas:
- Por pantalla y por línea de comandos, el sistema se negó: «La oferta 1 no tiene documentos cargados» («no se va a evaluar»). No usó los datos del Portal ni dijo «no se encontró el documento». Esto contradice lo esperado (evaluar con el Portal como fuente, REQ-062).
- Para poder seguir se cargó a cada oferta una hoja de prueba inventada de una página («sin contenido de oferta»; carpeta ignorada por git `corpus/casos/prueba-aabn5/`). Con eso la evaluación corrió en 4 min 40 s (pedido `evaluate_offers`) sobre 63 requisitos y 2 ofertas, sin falla.

Resultados, 63 requisitos por oferta (casi iguales en las dos ofertas, porque las dos tienen la misma hoja de relleno):

| Tipo de resultado | Oferta 1 | Oferta 2 |
|---|---|---|
| No se encontró el documento | 17 | 17 |
| No determinado: falta un dato | 28 | 27 |
| No determinado: falta la hoja de compliance | 8 | 10 |
| No determinado: el documento está en el Portal | 4 | 4 |
| No determinado: duda | 2 | 1 |
| Técnicos: pendiente del informe técnico (renglones) | 4 | 4 |
| «Cumple» o «no cumple» | 0 | 0 |

Lo que anduvo bien:
- Ningún «cumple» ni «no cumple» sin respaldo; ningún descarte propuesto («no encontrado» y «no determinado» no descartan). P3 respetado.
- Los 4 renglones técnicos quedan «pendiente del informe técnico» con el ok de la Comisión por renglón, como pide la spec (decisiones literales).
- Cuando faltaba un documento exigido (por ejemplo, certificado de asistencia a la visita, título, matrícula, planilla de cotización) dice «no se encontró el documento» y explica que no es un «no cumple»: la Comisión decide si pide subsanar. Se ofrece el pedido de subsanación.
- Los datos del Portal se muestran con fuente, y el orden económico propuesto sale del Portal (total y cotización por renglón de las dos ofertas).
- El «valor total de la oferta» queda «el documento está en el Portal», con el total citado del Portal y el pedido de que la Comisión lo verifique allí.

Lo que no:
- Requisito de visita obligatoria (el agregado a mano, el que más importa): «No determinado: el documento está en el Portal», citando precio y cantidad del renglón 4. El Portal no tiene nada sobre la visita. Los requisitos agregados a mano (108 a 114) aparecen como «renglón 4» en la pantalla de evaluación (los de la propuesta no) y el sistema les aplica la regla de datos del Portal. Es una cita del Portal que no respalda lo afirmado. Reproducir: agregar a mano un requisito formal sin renglones desde la matriz; evaluar; mirar el par en `/evaluacion/par/OFERTA/REQUISITO/`.
- «Cotizar en la planilla del Anexo IV»: «No se encontró el documento», aunque el Portal trae la cotización por renglón de las dos ofertas. No usa el Portal para ese requisito (relacionado con el hueco ya conocido de M-039).
- La garantía de mantenimiento no se evalúa: no hay requisito en la matriz (ver arriba) y la pantalla de evaluación no muestra las garantías del Portal (total, precio y cantidad sí, garantía no).
- No hay ninguna forma de detectar «supera el presupuesto»: el presupuesto oficial no está en el pliego ni en el Portal (está en actuaciones internas).
- El orden económico propuesto pone primera a la oferta más barata y segunda a la otra, sin avisar que la matriz tiene requisitos eliminatorios sin evaluar. Menor.

## Comparación con el dictamen (leído al final)

El dictamen desestimó la oferta 1 por tres motivos y adjudicó la oferta 2 (la más barata, que no fue desestimada).

| Motivo de desestimación | ¿Lo habría detectado el sistema con lo que tenía? |
|---|---|
| No presentó el certificado de visita obligatoria (Anexo VII) | La propuesta automática no incluyó la visita obligatoria: no. Con el requisito agregado a mano por la Comisión, la oferta quedó «no se encontró el documento» para el certificado de asistencia, que es la señal correcta; pero eso se verificó con una oferta de relleno, no con la oferta real. Con los documentos reales y el requisito presente, lo más probable es que lo marque. Con el sistema solo, sin intervención, no |
| Supera la formulación presupuestaria | No. No existe el dato del presupuesto en nada de lo cargado, y no hay requisito ni regla para compararlo |
| Garantía de mantenimiento: no cumple el monto mínimo | No. No hay requisito de garantía en la matriz. Los datos del Portal (tipo y monto del pagaré) no muestran la deficiencia: el monto del Portal coincide con el porcentaje exigido sobre el total declarado. La deficiencia, si existe, está en el documento de la oferta, que no es público |

Conclusión: de los tres motivos, el sistema solo habría llegado al de la visita, y únicamente si la Comisión completa a mano lo que la propuesta dejó pendiente. Los otros dos exigen datos que no están en el pliego ni en el Portal (presupuesto) o una regla de garantía que el producto todavía no tiene.

## Hallazgos, por importancia

1. **Alta. La propuesta de matriz omite la visita obligatoria y otras exigencias de la sección II** (título, matrícula, domicilio especial, intereses). Todo el cuerpo de la sección II (páginas 5 a 13) queda en «tramos no ubicados» sin propuesta. El sistema no afirma nada (P3) y marca el borrador como incompleto, pero la matriz queda corta de lo esencial. Reproducir: importar este proceso, cargar el pliego y proponer la matriz; ver cobertura.
2. **Alta. Sin documentos de la oferta, la evaluación se niega** («no tiene documentos cargados»). No usa el Portal ni dice «no se encontró el documento». Reproducir: procedimiento con matriz validada y ofertas del Portal sin documentos; pulsar «Evaluar todas las ofertas» o correr `evaluar_ofertas`.
3. **Alta. No hay requisito de garantía de mantenimiento** ni sugerencia por la norma (REQ-036), y las garantías del Portal no se muestran en la evaluación. Se pierde uno de los tres motivos de desestimación del caso.
4. **Media. Cita del Portal que no respalda lo afirmado.** Un requisito agregado a mano sin renglones (la visita) recibe «el documento está en el Portal» con precio y cantidad del renglón 4. La cita es verdadera pero irrelevante; puede hacer creer que el dato está resuelto en el Portal.
5. **Media. «Cotizar en la planilla» no usa la cotización del Portal** y dice «no se encontró el documento».
6. **Media. El pendiente de revisión no muestra el texto del tramo**, solo su ubicación; y cada tramo pendiente admite un solo requisito agregado (el segundo falla). La alternativa (formulario general de agregar) no está señalada.
7. **Media. Sobrantes** (obligaciones del adjudicatario, frases partidas, celdas de tablas como requisitos): unos 50 requisitos quitados de 99, la mitad de la propuesta. Es lo ya aceptado en ADR-0024; aquí fue visible en el trabajo de la Comisión.
8. **Baja. Rendimiento de la pantalla de matriz:** 2 a 4 s por acción, página de unos 3 MB.
9. **Baja. Las 4 filas técnicas exigen elegir una consecuencia sin fundamento** para poder validar.
10. **Baja. La circular llega por tres vías** y el objeto del proceso viene truncado a 100 caracteres; la revisión del Portal corrió sola tras la exploración.

## Estado en que quedó la base real

Quedaron cargados el procedimiento, sus renglones, la cláusula particular y la circular, la matriz versión 1 validada, las 2 ofertas con datos del Portal y una hoja de prueba inventada por oferta, y una evaluación de las 2 ofertas. Todo es de este proceso, con datos públicos; se puede quitar restaurando el respaldo (solo si no se ha usado la base después) o dejarlo como caso de trabajo. El pedido de este informe no incluye borrarlo.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
