"""Medición de la importación del Portal con páginas guardadas (T-145; REQ-045 a REQ-051).
Sin red: el caso se arma en una carpeta temporal con el calco inventado de T-139."""

import hashlib
import json
import socket

import pytest
import yaml

from evaluon.portal import evaluation
from evaluon.tenders.models import Procedure
from tests.portal.fakeportal import DATA, EXPECTED, LINK_URL, portal_settings  # noqa: F401
from tests.portal.conftest import ALLOWED
from tests.tenders.conftest import evaluator_user  # noqa: F401

pytestmark = pytest.mark.django_db

CIRCULAR_URL = f"https://{ALLOWED}/PLIEGO/VistaPreviaCircularCiudadano.aspx?qs=iChusphEv2uHCOucIGQZCgZt|FAKE0001"
ANEXO_TARGET = "ctl00$CPH1$UCVistaPreviaPliego$UCAnexos$rptAnexos$MiClaveUnica1$btnVerAnexo"


def _save(folder, name, body, **meta):
    (folder / name).write_bytes(body)
    (folder / f"{name}.meta.json").write_text(json.dumps({"status": 200, **meta}), "utf-8")


def make_case(tmp_path, page="proceso.html", circular=False):
    """Una carpeta de caso con el calco: `portal/` (como las guardadas) y `esperado/`."""
    folder = tmp_path / "caso-calco"
    (folder / "portal").mkdir(parents=True)
    (folder / "esperado").mkdir()
    _save(folder / "portal", "proceso.html", (DATA / page).read_bytes(), url=LINK_URL,
          content_type="text/html")
    expected = {
        "caso": "caso-calco", "visto_bueno": "Coordinador",
        "procedimiento": EXPECTED["procedimiento"], "renglones": EXPECTED["renglones"],
        "documentos": [{"archivo": "pb-00-UC_DetalleProductos_lnkVerItem.bin"}],
    }
    if circular:
        body = (DATA / "circular-1.html").read_bytes()
        _save(folder / "portal", "circular-1.bin", body, url=CIRCULAR_URL,
              content_type="text/html")
        _save(folder / "portal", "pb-04-anexo.bin", (DATA / "circular-1.pdf").read_bytes(),
              target=ANEXO_TARGET, content_type="application/pdf",
              content_disposition='attachment;filename="IF-2099-00000004-ARCA-DXXXXX%SDGXXX.pdf"')
        expected["circulares"] = [{
            "numero": 1, "fecha_publicacion": "02/07/2026", "tipo": "Con consulta",
            "archivo": "circular-1.bin", "sha256": hashlib.sha256(body).hexdigest()}]
    (folder / "esperado" / "portal-esperado.yaml").write_text(
        yaml.safe_dump(expected, allow_unicode=True), "utf-8")
    return folder


@pytest.fixture
def no_sockets(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("la medición abrió un socket")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_replay_serves_the_saved_pages_and_notes_what_is_missing(tmp_path, portal_settings):
    """REQ-049: el transporte sirve lo guardado y anota lo que no está (404), sin red."""
    transport = evaluation.ReplayTransport(make_case(tmp_path, circular=True) / "portal")
    client = transport.client()
    assert client.get(LINK_URL).body == (DATA / "proceso.html").read_bytes()
    assert client.get(CIRCULAR_URL).body == (DATA / "circular-1.html").read_bytes()
    with pytest.raises(Exception):
        client.get(f"https://{ALLOWED}/otra/pagina.aspx")
    assert transport.missing == [f"GET https://{ALLOWED}/otra/pagina.aspx"]


def test_a_folder_without_the_process_page_is_refused(tmp_path):
    """REQ-046: sin la página del proceso no se mide."""
    (tmp_path / "portal").mkdir()
    with pytest.raises(evaluation.MeasurementRefused):
        evaluation.ReplayTransport(tmp_path / "portal")


def test_without_circulars_removes_only_the_circular_rows():
    """REQ-050: la página sin circulares conserva el resto."""
    full = (DATA / "proceso-con-circular.html").read_bytes()
    older = evaluation.without_circulars(full)
    assert b"gvCirculares_ctl02" in full and b"gvCirculares_ctl02" not in older
    assert len(older) > len(full) * 0.9
    assert evaluation.without_circulars(older) == older


def test_measures_the_calco_at_100_percent_and_leaves_the_database_as_it_was(
        tmp_path, evaluator_user, portal_settings, no_sockets):
    """REQ-046, REQ-048: el calco da 100 % en datos y renglones, nada se carga sin aprobar
    y la base queda como estaba."""
    folder = make_case(tmp_path)
    expected, result = evaluation.measure_case(evaluator_user, folder)
    for name in ("procedimiento", "renglones", "sin_aprobacion", "novedad"):
        value = result.ratio(name)
        assert value["total"] and value["ok"] == value["total"], (name, result.checks)
    assert result.ratio("renglones")["total"] == 6
    assert Procedure.objects.count() == 0
    assert not evaluation.PortalLink.objects.exists()


def test_a_wrong_expected_value_does_not_reach_the_threshold(tmp_path, evaluator_user,
                                                             portal_settings, no_sockets):
    """REQ-046: una cantidad esperada distinta de la del Portal se cuenta como falla y
    bloquea."""
    folder = make_case(tmp_path)
    path = folder / "esperado" / "portal-esperado.yaml"
    data = yaml.safe_load(path.read_text("utf-8"))
    data["renglones"][0]["cantidad"] += 1
    data["procedimiento"]["objeto"] = "OTRO OBJETO"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    expected, result = evaluation.measure_case(evaluator_user, folder)
    assert result.ratio("renglones")["ok"] == 5
    assert result.ratio("procedimiento")["ok"] < result.ratio("procedimiento")["total"]
    report = evaluation.Report(tmp_path / "x", [(expected, result)])
    assert any("Renglones" in line for line in report.blocking)


def test_the_new_circular_is_proposed_and_nothing_decided_is_repeated(
        tmp_path, evaluator_user, portal_settings, no_sockets):
    """REQ-050: explorar sin la circular, aprobar y revisar con la página completa propone la
    circular y no repite lo decidido."""
    folder = make_case(tmp_path, page="proceso-con-circular.html", circular=True)
    _, result = evaluation.measure_case(evaluator_user, folder)
    novelty = result.ratio("novedad")
    assert novelty["total"] > 1 and novelty["ok"] == novelty["total"], result.checks
    assert result.info["novedad"]["circulares_nuevas"] == 1
    assert result.info["novedad"]["repetidos"] == []


def test_the_run_folder_has_its_files_and_the_public_summary_has_no_real_data(
        tmp_path, evaluator_user, portal_settings, no_sockets):
    """REQ-049: la carpeta de la corrida tiene los cuatro archivos; el resumen público no
    trae claves ni detalles de los datos."""
    folder = make_case(tmp_path)
    report = evaluation.measure(evaluator_user, [folder], tmp_path / "corridas", commit="abc")
    assert sorted(p.name for p in report.folder.iterdir()) == sorted(evaluation.RUN_FILE_NAMES)
    parameters = json.loads((report.folder / "parametros.json").read_text("utf-8"))
    assert parameters["sin_conexion"] is True and parameters["commit"] == "abc"
    public = (report.folder / "resumen-publico.md").read_text("utf-8")
    assert "YERBA" not in public and "A0ZZ000000" not in public


def test_the_live_pass_uses_the_real_client_and_skips_the_novelty(
        tmp_path, evaluator_user, portal_settings, no_sockets, monkeypatch):
    """REQ-049: `--en-vivo` pide al Portal (aquí, un transporte de mentira en lugar de la
    conexión) con el cliente de la aplicación y no mide la novedad, que necesita dos estados."""
    folder = make_case(tmp_path)
    replay = evaluation.ReplayTransport(folder / "portal")
    asked = []

    def fake_https(request, *, timeout, max_bytes):
        asked.append((request.method, request.url, timeout, max_bytes))
        return replay(request)

    monkeypatch.setattr(evaluation, "https_transport", fake_https)
    report = evaluation.measure(evaluator_user, [folder], tmp_path / "corridas", live=True)
    (expected, result), = report.cases
    assert asked and asked[0][:2] == ("GET", LINK_URL)
    assert result.ratio("renglones")["ok"] == 6 and result.ratio("novedad")["total"] == 0
    assert not any("Novedad" in line for line in report.blocking)
    parameters = json.loads((report.folder / "parametros.json").read_text("utf-8"))
    assert parameters["en_vivo"] is True and parameters["sin_conexion"] is False
