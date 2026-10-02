"""Pruebas de tools/tablero.py. Correr con: python -m unittest discover tools"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tablero  # noqa: E402

SPEC = """# Spec 001 · Ingesta de normativa

Estado: {estado} · Fecha: 2026-10-02 · Aprobó: —

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-001 | Incorporar una norma | — |
| REQ-002 | Citar el artículo | — |

Duda [A ACLARAR: formato de origen].
"""

PLAN = "# Plan 001\n\nEstado: aprobado · Fecha: 2026-10-03\n"

TASKS = """# Tareas 001

Despliegue: pendiente

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-001 | Esquema de base | REQ-001 | — | terminada |
| T-002 | Cargar una norma | REQ-001 | T-001 | en curso |
| T-003 | Citar artículos | REQ-002 | T-002 | pendiente |
"""


def make_repo(tmp: Path, spec_state="aprobada", plan=True, tasks=True) -> Path:
    feature = tmp / "specs" / "001-ingesta-normativa"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text(SPEC.format(estado=spec_state), encoding="utf-8")
    if plan:
        (feature / "plan.md").write_text(PLAN, encoding="utf-8")
    if tasks:
        (feature / "tasks.md").write_text(TASKS, encoding="utf-8")
    (tmp / "specs" / "hoja-de-ruta.md").write_text(
        "| N.º | Feature | Qué entrega | Depende de |\n|---|---|---|---|\n"
        "| 001 | Ingesta de normativa | Base citable | — |\n"
        "| 002 | Revisión de pliegos | Observaciones | 001 |\n", encoding="utf-8")
    return tmp


class TableroTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def feature(self, **kwargs):
        make_repo(self.root, **kwargs)
        return tablero.load_feature(self.root / "specs" / "001-ingesta-normativa", self.root)

    def test_spec_en_borrador_queda_en_etapa_1(self):
        f = self.feature(spec_state="borrador", plan=False, tasks=False)
        self.assertEqual(f["stages_done"], 0)
        self.assertEqual(f["open_questions"], 1)
        self.assertIn("Resolver 1 duda", tablero.next_step(f))

    def test_plan_no_cuenta_si_la_spec_no_esta_aprobada(self):
        f = self.feature(spec_state="borrador")
        self.assertEqual(f["stages_done"], 0)

    def test_tareas_en_curso_dejan_la_feature_en_desarrollo(self):
        f = self.feature()
        self.assertEqual(f["stages_done"], 3)
        self.assertEqual(tablero.stage_summary(f), "4 de 7 · Desarrollo")
        self.assertEqual([t["state"] for t in f["tasks"]], ["terminada", "en curso", "pendiente"])
        self.assertEqual(f["tasks"][1]["deps"], ["T-001"])

    def test_feature_completa(self):
        make_repo(self.root)
        folder = self.root / "specs" / "001-ingesta-normativa"
        done = TASKS.replace("en curso", "terminada").replace("| pendiente |", "| terminada |")
        (folder / "tasks.md").write_text(done.replace("Despliegue: pendiente", "Despliegue: aprobado 2026-11-01"), encoding="utf-8")
        (folder / "informe-pruebas.md").write_text("ok", encoding="utf-8")
        audits = self.root / "docs" / "auditorias"
        audits.mkdir(parents=True)
        (audits / "001-dictamen.md").write_text("- **Resultado:** aprobado con observaciones\n", encoding="utf-8")
        f = tablero.load_feature(folder, self.root)
        self.assertEqual(f["stages_done"], 7)
        self.assertEqual(tablero.stage_summary(f), "Terminada")

    def test_auditoria_rechazada_frena_el_despliegue(self):
        make_repo(self.root)
        folder = self.root / "specs" / "001-ingesta-normativa"
        done = TASKS.replace("en curso", "terminada").replace("| pendiente |", "| terminada |")
        (folder / "tasks.md").write_text(done, encoding="utf-8")
        (folder / "informe-pruebas.md").write_text("ok", encoding="utf-8")
        audits = self.root / "docs" / "auditorias"
        audits.mkdir(parents=True)
        (audits / "001-dictamen.md").write_text("**Resultado:** rechazado\n", encoding="utf-8")
        self.assertEqual(tablero.load_feature(folder, self.root)["stages_done"], 5)

    def test_documento_generado(self):
        make_repo(self.root)
        doc = tablero.build(self.root)
        self.assertIn("▶ T-002 · Cargar una norma (en curso)", doc)
        self.assertIn("T001 --> T002", doc)
        self.assertIn("F001 --> F002", doc)
        self.assertIn("002 · Revisión de pliegos | Observaciones | No iniciada", doc)
        self.assertIn("| REQ-001 | Incorporar una norma | T-001, T-002 | ▶ en proceso |", doc)
        self.assertIn("| REQ-002 | Citar el artículo | T-003 | ○ pendiente |", doc)
        self.assertEqual(doc, tablero.build(self.root), "la salida debe ser estable")

    def test_requisito_con_tarea_bloqueada(self):
        make_repo(self.root)
        tasks = self.root / "specs" / "001-ingesta-normativa" / "tasks.md"
        tasks.write_text(TASKS.replace("| pendiente |", "| bloqueada |"), encoding="utf-8")
        doc = tablero.build(self.root)
        self.assertIn("| REQ-002 | Citar el artículo | T-003 | ✕ bloqueado |", doc)
        self.assertIn("✕ T-003 · Citar artículos (bloqueada)", doc)

    def test_repo_sin_features(self):
        (self.root / "specs").mkdir()
        self.assertIn("Todavía no hay features", tablero.build(self.root))


if __name__ == "__main__":
    unittest.main()
