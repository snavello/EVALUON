# ADR-0014 · Recomendaciones del asesor de metodología del 2026-10-03

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto, a propuesta del Coordinador

## Contexto

El 2026-10-03 el asesor de metodología (ADR-0013) evaluó por primera vez la forma de trabajo de la feature 001, antes de T-046. Hizo siete recomendaciones: cinco por errores graves (tipo A) y dos por mejoras significativas (tipo B). El Coordinador comprobó la evidencia y estuvo de acuerdo con las siete. El responsable aprobó todas menos la 4.

## Decisión

### Aprobadas

1. **Medida de aceptación independiente del ajuste.** El 85 % de T-046 no se mide solo con los casos que se usaron para ajustar el corrector y los datos clave (ADR-0011, T-059). Las medidas de aceptación se toman de un lote nuevo, de al menos 10 preguntas con respuesta y 6 sin respuesta, que cumple estas condiciones:
   - se escribe sin correr el sistema;
   - trata artículos que el conjunto todavía no usa;
   - no se usa nunca para ajustar nada.
   Además:
   - `resumen.md` informa ese lote por separado y agrega el margen de error de cada medida.
   - Antes de T-046 se decide si la respuesta "lo regula otra norma", con su cita, cuenta como respuesta o como abstención (punto 3 de "Para mirar con atención" en `evals/casos/INDICE.md`).
   - Sobre el visto bueno de la Comisión que pide la spec, el responsable decide entre conseguirlo o enmendar la spec para el piloto.
2. **Regla de calibración del umbral.** El umbral de abstención va en el medio del hueco entre la pregunta ajena a la normativa con el puntaje más alto y la pregunta con respuesta con el puntaje más bajo. El punto medio se calcula en la escala anterior a la sigmoide, y el hueco tiene que tener un margen mínimo. Si no hay hueco, se informa. Las preguntas cercanas que la normativa no resuelve las tiene que frenar el modelo, no el umbral. Reemplaza la regla de T-042 ("frenar a lo sumo el 5 % dejando una afuera"), que con unas 24 preguntas elige siempre el puntaje más bajo observado.
3. **Registro de la verificación de cada tarea.** El testeador evaluador deja `specs/NNN/verificacion/T-NNN.md` en la rama de la tarea, con:
   - los criterios y su evidencia;
   - el commit de main con el que corrió la suite y su resultado;
   - las alteraciones del código y el test que detectó cada una;
   - el veredicto.
   Rige desde T-059. Las verificaciones anteriores quedaron solo en los informes devueltos al Coordinador y en el pull request de cada tarea. No se reconstruyen; se informa así al auditor.
5. **Cierre que frena ante una suite en rojo.** El script de cierre pasa al repositorio (`tools/cerrar.sh`, con `tools/avisos.py` y `tools/resolve_tasks.py`), recibe la feature como parámetro, corre la suite antes de commitear, sale con el código de pytest y, con error, no se integra. Las rutas del equipo quedan fuera del código: entran por `COORD_DIR`.
6. **Documentos compartidos más livianos, desde la próxima spec.** En la próxima feature:
   - `tasks.md` lleva solo la tabla y lo que pide cada tarea;
   - los avisos para una tarea van a `specs/NNN/avisos/T-NNN.md`, y el encargo los nombra;
   - el tablero se regenera solo en main, después de cada integración, y no en las ramas de tarea.
   La feature 001 sigue como está hasta cerrarse.
7. **Evals de la próxima feature desde la spec.** En la próxima feature:
   - la salida que se mide es estructurada (por ejemplo, la lista de requisitos de la matriz con su cita, o cumple / no cumple / no determinado);
   - el conjunto dorado se arma con la Comisión durante la spec, con visto bueno antes del plan;
   - la cantidad de casos se calcula para que el umbral de aceptación sea significativo;
   - una parte de los casos no se usa nunca para ajustar.
   Según la hoja de ruta, la 003 es "Procedimiento, pliego final y matriz de cumplimiento" y la evaluación de ofertas es la 004.

### No aprobada

4. **Registro de la aprobación humana de las compuertas.** El asesor proponía:
   - sacar de la integración por defecto los pull requests de spec, plan y despliegue;
   - anotar en la línea `Estado:` el origen de la aprobación;
   - juntar las aclaraciones del Coordinador al plan para ratificarlas en bloque.
   El responsable no la aprobó: sigue la regla de integración por defecto y su forma actual de aprobar.

## Consecuencias

- T-046 espera tres cosas: la regla nueva del umbral (2), el lote nuevo de casos y el margen de error (1), y las decisiones del responsable sobre T-059.
- Cada tarea suma un archivo de verificación, unos 5 a 10 minutos del testeador.
- Una suite en rojo deja de poder integrarse por descuido.
- Los puntos 6 y 7 se aplican al empezar la próxima spec.
