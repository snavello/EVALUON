# Corpus de trabajo

Documentos públicos usados durante la construcción: normas, pliegos, ofertas y evaluaciones.

## Regla

Solo material público (principio P4). Ante la duda sobre un documento, no se sube.

## Organización

```
corpus/normativa/      Normas, con su fecha de vigencia
corpus/pliegos/        Pliegos de bases y condiciones
corpus/ofertas/        Ofertas
corpus/evaluaciones/   Evaluaciones ya resueltas
corpus/manifiesto.csv  Un renglón por documento
```

## Manifiesto

Cada documento se anota en `manifiesto.csv` al incorporarlo:

| Campo | Contenido |
|---|---|
| archivo | Ruta dentro de `corpus/` |
| tipo | normativa, pliego, oferta o evaluación |
| titulo | Nombre del documento |
| fuente | De dónde se obtuvo |
| fecha_documento | Fecha de emisión o vigencia |
| fecha_incorporacion | Cuándo se sumó al corpus |
| observaciones | Por ejemplo: escaneado, incompleto, reemplaza a otro |
