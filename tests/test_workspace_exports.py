from pathlib import Path

from vectorsmith.exports import export_marker_csv, export_trace_csv
from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import ParamDomain
from vectorsmith.plots import GraphSettings, PlotState, TdrSettings
from vectorsmith.session import LoadedFile, PortPairingConfig, Session
from vectorsmith.workspace import (
    graph_settings_from_dict,
    graph_settings_to_dict,
    load_workspace,
    save_workspace,
    session_from_workspace,
    session_to_dict,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _session_with_fixture() -> Session:
    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(
            path=result.path,
            network=result.network,
            display_name=result.display_name,
            pairing=PortPairingConfig(num_diff_ports=1, renumber_map=[0, 1]),
        )
    )
    return session


def test_workspace_json_round_trip(tmp_path):
    session = _session_with_fixture()
    graph = GraphSettings(x_min_ghz=1.0, mag_y_min_db=-80.0)
    data = session_to_dict(
        session,
        graph_settings=graph,
        tdr_settings=TdrSettings(z_ref_ohms=75.0),
        toolbar={"plot_kind": "mag_db"},
        dark_theme=True,
    )
    path = tmp_path / "workspace.vsmith.json"
    save_workspace(path, data)
    loaded = load_workspace(path)
    restored, errors = session_from_workspace(loaded)

    assert not errors
    assert restored.files[0].display_name == "twoport.s2p"
    assert graph_settings_from_dict(loaded["graph_settings"]) == graph
    assert loaded["tdr_settings"]["z_ref_ohms"] == 75.0
    assert loaded["dark_theme"] is True


def test_workspace_missing_file_reports_error():
    restored, errors = session_from_workspace({"files": [{"path": "missing.s2p"}]})
    assert restored.files == []
    assert errors


def test_graph_settings_serialization():
    settings = GraphSettings(x_max_ghz=20.0, mag_y_max_db=5.0)
    assert graph_settings_from_dict(graph_settings_to_dict(settings)) == settings


def test_export_trace_csv(tmp_path):
    path = tmp_path / "trace.csv"
    export_trace_csv(path, _session_with_fixture(), PlotState(domain=ParamDomain.SINGLE_ENDED))
    text = path.read_text(encoding="utf-8")
    assert "filename,trace,domain,x,x_unit,value,unit,plot_kind" in text
    assert "twoport.s2p" in text


def test_export_marker_csv(tmp_path):
    path = tmp_path / "marker.csv"
    export_marker_csv(
        path,
        _session_with_fixture(),
        PlotState(domain=ParamDomain.SINGLE_ENDED),
        1.0,
    )
    text = path.read_text(encoding="utf-8")
    assert "GHz" in text
    assert "mag_db" in text
