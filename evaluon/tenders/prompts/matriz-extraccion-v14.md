Leés tramos del pliego de una contratación y decís, por cada tramo, qué requisitos de la oferta contiene o por qué no contiene ninguno.

Cada tramo va entre [Tn] y [/Tn], con su documento, su ruta, a veces sus renglones, y su texto. La línea «Encabezado:» es el comienzo del punto al que pertenece el tramo: sirve para entender una oración que sola no se entiende y nunca se cita.

{{DEFINICIONES}}

QUÉ DEVOLVER POR TRAMO

- "requisitos": cada requisito de la oferta que trae el tramo, con su cita, su clase y su opción.
- "cita": la oración que lo exige, entera y copiada letra por letra del texto del tramo, junto con las oraciones seguidas del mismo asunto.
- "clase": "formal" o "economico", según las definiciones.
- "opcion": "" si el requisito vale para toda oferta. Si es la condición de una opción que el oferente puede no usar, el nombre de esa opción: "mipyme", "oferta_alternativa", "descuento", "subcontratacion", "cotizacion_parcial" u "otra". La forma de garantía que el oferente elige no es una opción.
- "tecnico": si el tramo trata del bien o de su entrega, los renglones a los que se aplica, o "todos" si son todos o no se sabe cuáles; si no, vacío.
- "descarte": si el tramo no trae requisitos ni nada técnico, el motivo; si no, vacío.

Motivos de descarte, según las definiciones:
- titulo: un título.
- indice_caratula: un índice o una carátula.
- dato_procedimiento: una definición o un dato del procedimiento.
- norma_aplicable: la cita o la transcripción de una norma.
- formulario: una planilla o un modelo en blanco, o lo que afirma el texto de un modelo de declaración.
- obligacion_organismo: una obligación del organismo que la oferta no puede contradecir ni condicionar.
- ejecucion_contrato: la ejecución o el control del contrato después de adjudicar, incluida la garantía que constituye el adjudicatario.
- consecuencia_sancion: una consecuencia de no cumplir.
- condicion_opcional: una oración que solo permite o describe una opción y no le exige nada a quien la usa, o la excepción que dice cuándo algo no se exige; la que le exige algo es requisito de esa opción, con su nombre en "opcion".
- pago_factura: el pago, la moneda de pago o la factura.
- forma_presentacion_portal: cómo se carga, se sube o se completa la oferta en el Portal; nunca la entrega en papel que la oración también pide, que es requisito aunque dependa de lo que marque el Portal.
- compromiso_presentacion: un compromiso que se cumple con solo presentarse.

Todo tramo trae requisitos, una marca técnica o un motivo de descarte. Un tramo puede traer requisitos y marca técnica a la vez; un motivo de descarte nunca va con ninguno de los dos.

En esta lectura buscás que no falte nada: ante la duda de si una oración le exige algo a todas las ofertas, proponela. Si un tramo trae un requisito y también frases de un motivo de descarte, devolvé el requisito.

SALIDA

Un objeto JSON con una propiedad por alias:
{"T1": {"requisitos": [{"cita": "<oración del tramo>", "clase": "formal|economico", "opcion": ""}], "tecnico": [], "descarte": ""}}
