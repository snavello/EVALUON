# Corpus de trabajo

Documentos públicos usados durante la construcción: normas, pliegos, ofertas y evaluaciones.

## Regla

Solo material público (principio P4). Ante la duda sobre un documento, no se sube.

Los casos de compra (`corpus/casos/`) no se suben al repositorio, que es público: los pliegos, las ofertas y las evaluaciones traen datos personales (copias de DNI, pagarés, pólizas, nóminas de funcionarios con su DNI), aunque el procedimiento esté adjudicado. Quedan solo en el equipo propio, donde corre el sistema, y `.gitignore` los excluye. Tampoco se anotan en el manifiesto del repositorio (decisión del responsable, 2026-10-03).

## Organización

```
corpus/normativa/      Normas, con su fecha de vigencia
corpus/normativa/referencias/  Fichas y listados de la fuente; no son normas y no se cargan
corpus/casos/<caso>/   Un procedimiento de compra por carpeta (solo en el equipo propio, ver "Regla"):
    pliego/            Pliego final, anexos y especificaciones técnicas
    circulares/        Circulares, aclaratorias y preguntas de oferentes (puede estar vacía)
    ofertas/<oferente>/  Documentos de cada oferta
    evaluacion/        Dictamen, acta y adjudicación
    otros/             Otros insumos (compliance, notas)
corpus/manifiesto.csv  Un renglón por documento
```

## Manifiesto

Cada documento se anota en `manifiesto.csv` al incorporarlo:

| Campo | Contenido |
|---|---|
| archivo | Ruta dentro de `corpus/` |
| tipo | normativa, pliego, oferta, evaluación o referencia |
| titulo | Nombre del documento |
| fuente | De dónde se obtuvo |
| fecha_documento | Fecha de emisión o vigencia |
| fecha_incorporacion | Cuándo se sumó al corpus |
| sha256 | Huella del archivo, para comprobar que no cambió |
| observaciones | Por ejemplo: escaneado, incompleto, reemplaza a otro |
