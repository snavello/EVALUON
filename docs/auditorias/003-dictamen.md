# Dictamen de auditoría · Feature 003 (Procedimiento, pliego final y matriz de cumplimiento)

- **Alcance:** `specs/003-pliego-matriz/`, rango `b85a97e..23a22a9` en `main` (485 commits; los de T-130 a T-132 son de la 008 y no se auditan aquí). Fecha: 2026-10-05.
- **Resultado:** rechazado

## Hallazgos

### 1. Bloqueante · P3 y P1 · REQ-031 no cumple su criterio de aceptación y deja un vigente falso sin aviso
- Evidencia: `specs/003-pliego-matriz/verificacion/T-108.md`, sección 4: REQ-031 en los casos 03 y 04 cumple 3 de 10 y 1 de 4 filas ("no cumple"). `verificacion/T-137.md`, "Veredicto final contra el umbral": 2 de 3, no se alcanza; la fila #183 (M-028) muestra "UN peso" como vigente para los renglones 6 y 14 sin marca, cuando la circular D7 devuelve el renglón 6 a cotización por servicio. El propio informe lo describe como "vigente falso sin aviso".
- La spec exige que la matriz "aplique el cambio, muestre los dos textos y cite el documento" (REQ-031) y el ADR-0024 mantiene REQ-031 como bloqueante de la aceptación. El ADR-0025 punto 1 permite otra ronda cuando se viola un principio de la constitución; presentar como vigente un texto ya modificado, sin marca, es una conclusión sin fundamento válido (P3).
- Corregir: resolver o marcar el cambio de D7 en #183 y repetir la medición de aceptación; o bien enmendar la spec y la decisión con aprobación expresa del responsable. Hoy `tasks.md` dice que T-137 está "terminada" y la sección "Revisión con el primer producto" lo trata como lo menor.

### 2. Mayor · P7 y P1 · Encontrados por debajo de 100 % en el caso-03 sin enmienda de la spec
- Evidencia: T-108.md, tabla 1: caso-03, 62 de 65 (faltan M-030, M-032, M-043). La spec dice "100 %... cada requisito que falte... bloquea la aceptación". El ADR-0024 enmienda solo el tope de sobrantes. T-108 reclasifica los tres como "granularidad, no pérdida" y los manda a la lista de revisión (`tasks.md`, líneas 660 a 661); el mismo informe advierte que otra lectura del ADR cambiaría la clasificación.
- Corregir: el responsable decide por escrito si esos tres faltantes cuentan; si es así, enmendar la spec o la regla de emparejamiento. Hoy una métrica bajó respecto del 100 % pedido sin la aprobación que pide P7.

### 3. Menor · P1 · Estado de tareas incoherente con sus dependencias
- Evidencia: `tasks.md`: T-106 y T-122 figuran "pendiente" (diferidas por ADR-0024), pero T-107 y T-108 figuran "terminada" y dependen de T-106. T-107 pide como entregable `verificacion/T-107.md`, que no existe (`ls verificacion` solo muestra T-106/T-107 ausentes). El tablero muestra 62/64 y "4 de 7 · Desarrollo" sin reflejar que la compuerta de aceptación no pasó.
- Corregir: dejar T-107 con su registro (aunque sea una línea que cite el ADR-0024) o marcarla de otro modo; reflejar en el tablero que la aceptación está sin cumplir.

### 4. Menor · P7 · T-137 se cerró sin verificación independiente de su último cambio de lógica
- Evidencia: `verificacion/T-137.md` termina la ronda 2 con "Vuelve a desarrollo, ajuste menor"; el commit 791260a ("dos raíces en común y tests de las reglas de marca") cambia la regla y no aparece reverificado, solo medido (la cadena 791260a aparece una vez, como código medido). Además la medición registra 23 de 27 filas con marca de más (20 de 22 en el caso-03).
- Corregir: reverificar 791260a o registrar que se aceptó sin hacerlo.

### 5. Menor · P6 · La memoria de video no figura en los resúmenes de medición
- Evidencia: T-108.md, fila "Memoria de video": "no registrada" en los tres casos. P6 exige modelo y parámetros (están en `MatrixRun.models` y `parameters`); el dato de memoria lo pidió el plan para las mediciones.
- Corregir: registrarla en la próxima corrida.

## Controlado y en orden
- **Trazabilidad (P2):** los 15 REQ de la 003 (022 a 036) aparecen en `tasks.md` y en al menos 4 archivos de `tests/` cada uno. Todo commit de código del rango referencia una tarea (los de T-130 a T-132 son de la 008). El código reciente que ningún requisito pide no se encontró. Los requisitos normativos citan norma (ADR-0006, régimen según REQ-022). Tarea terminada sin verificación: solo T-107; T-091 está verificada en el registro conjunto con T-089.
- **P3:** existe `ConsequenceType.NO_DETERMINADA` con restricción de base que impide elegirla como decisión (`models.py` 982 y 1048); `validated_by` y `validated_at` obligatorios para validar (`models.py` 646 y 673); la validación exige que no queden sugerencias sin decidir (REQ-035, T-110).
- **P4:** no hay URLs, clientes de API ni claves en `evaluon/tenders` (búsqueda sin resultados); sin secretos (búsqueda de patrones sin resultados) ni `.env` ni casos reales versionados (`git ls-files corpus` solo trae normativa y manifiesto); los fixtures de los casos chicos son sintéticos. Solo hay identificadores de procedimientos públicos en `spec.md` y `plan.md`. No se revisó el historial completo con una herramienta de secretos.
- **P6 y P8:** `MatrixRun` registra documentos con huella, fecha, régimen, `corpus_version`, modelos, parámetros, versiones de instrucciones, pasos con pedido y salida (`RunStep`); el usuario y el momento salen del pedido (`Job.requested_by`, `requested_at`); `NormSupport` guarda `corpus_version` y `regime`.
- **P7:** suite completa corrida por mí sobre `main` 23a22a9 (proyecto Docker propio, sin GPU): `2876 passed in 910.01s`. Ningún `skip` ni `xfail` en `tests/`. No se encontraron tests sin afirmaciones por búsqueda de patrones.
- **Tablero:** `python tools/tablero.py --check` responde "docs/tablero.md está al día" (rc=0).

## Lo que no pude verificar
- **Evals y mediciones con casos reales:** requieren GPU y los casos (`corpus/casos/`, fuera del repositorio). No las corrí; las cifras de la aceptación son las de los informes `T-108.md`, `T-137.md` y del ADR-0024, tomadas como declaradas. Por eso no pude comparar las métricas con una corrida propia.
- **Runbook (P5):** no existe un runbook de despliegue de la 003 (`Despliegue: pendiente` en `tasks.md`); `specs/001-normativa/entorno.md` no cubre `worker` ni `generation_batch`. Corresponde a la etapa 7, pero no se pudo comprobar el levantado desde cero.
- **Historial de secretos:** solo búsqueda por patrones en el árbol actual.
- **Tests con servicios de IA reales:** la suite usa dobles; el hilo con servicios reales no se corrió.
