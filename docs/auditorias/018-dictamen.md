# Dictamen de auditoría de fallas · Feature 018 (el proceso a la vista)

- **Alcance:** `specs/018-proceso-a-la-vista/`, rango b7fcf629^..e30c81a3 (`origin/main`), 148 commits, 141 archivos. Auditoría de fallas según ADR-0036 y ADR-0052: lo que no anda, resultados equivocados, conclusiones sin respaldo (P3) y datos reales o secretos (P4). Copia propia `.claude/worktrees/aud018` y proyecto docker propio `evaluon-aud018` (dado de baja con `down -v`).
- **Resultado:** aprobado con observaciones

## Hallazgos

Sin hallazgos bloqueantes. Nada impide funcionar ni expone datos.

1. **Menor, no bloqueante · P4/P5 (maquetas de diseño con recurso externo).** Las maquetas `docs/diseno/exposicion-proceso/*.html` (a-grafo, a, b, c, d, e) cargan una tipografía desde `https://fonts.googleapis.com` (línea 4 de cada una). No están en el camino de pliegos y ofertas ni en la aplicación (`grep googleapis evaluon/` sin resultados), pero abrir la maqueta consulta un servicio externo. Corregir: tipografía local o sin enlace externo.

## Para la auditoría de cumplimiento (no bloquea)

- No revisé trazabilidad completa commit a tarea ni la redacción de las verificaciones; todas las tareas T-340 a T-363 figuran terminadas en `tasks.md` y cada una tiene archivo en `verificacion/`.

## Lo que se controló y está bien

- **Pruebas de la feature (P7):** `pytest tests/journey/proceso` sobre e30c81a3, en contenedor y base propios (`--no-deps`; los motores de embeddings y reranker no levantan sin GPU y estas pruebas no los usan): **396 pasaron, 0 fallaron, 0 salteadas**, 210 s. No hay `skip` ni `xfail` en esa carpeta. No corrí la suite completa (encargo).
- **Rendimiento:** la prueba de inicio con 20 procedimientos en curso pasó (lista 0,18 s mediana; cada fila 0,35 s).
- **Tablero:** `python tools/tablero.py --check` responde que `docs/tablero.md` está al día.
- **P3:** el detalle del par (`evaluon/templates/journey/_par.html`) reutiliza el panel con el fundamento: texto del pliego y de la oferta con página y enlace al original, marca e imagen de «leída por visión» (`c.by_vision`), dato del Portal con su fuente (`portal/_fuente_dato.html`), explicación rotulada «no es texto de la oferta ni del pliego», y la frase «Es una propuesta: decide la Comisión». Existe el estado «A decidir» y las filas técnicas sin informe muestran «Espera informe» en lugar de una conclusión. Las vistas nuevas (`views/cuadro.py`) solo leen; las decisiones van por la ruta de siempre (`review.decide`), con el registro de auditoría existente.
- **Entradas:** `?celda=` se valida con expresión anclada y pertenencia al procedimiento (404 si no); `?filtro=` solo acepta valores de una lista. El acceso exige sesión (`LoginRequiredMiddleware`, `settings.py:85`); las vistas nuevas usan `@reading` y quitan las acciones al rol de lectura.
- **P4:** sin URLs, claves ni clientes de API en `evaluon/journey/proceso`, plantillas y estáticos nuevos; sin secretos en el diff; los fixtures de `tests/journey/proceso` son sintéticos.
- **Estados de tareas:** coinciden con el código y las pruebas revisadas en el área.

## Lo que no pude verificar

- La suite completa y las evals (el encargo lo excluye).
- La revisión visual en los dos temas y el contraste 4,5:1 (REQ-156): solo vi los tests que lo afirman.
- Los contenedores de las pruebas de IA (embeddings, reranker): sin GPU en este proyecto.
- Historial completo de git en busca de secretos: revisé solo el diff del rango.
