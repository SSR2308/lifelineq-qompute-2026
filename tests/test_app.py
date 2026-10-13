"""UI behavior checks using measured result fixtures, never a solver performance target.

On restricted Windows hosts, AppTest needs permission to open its local asyncio
socket pair, just as the Streamlit development server needs a loopback socket.
"""

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lifelineq.experiments as experiments
from lifelineq.metrics import evaluate_counts
from lifelineq.model import load_scenario


ROOT = Path(__file__).resolve().parents[1]


def recorded_result(*, quick=False):
    """UI fixtures reuse actual shipped counts; provenance is tested separately.

    The loader mock below still matches the full configuration. This deliberately
    decouples UI tests from a computational-source edit invalidating saved results.
    """
    wanted = asdict(experiments.ExperimentConfig(shots=1024 if quick else 2048,
                                                maxiter=60 if quick else 80))
    for path in sorted((ROOT / "results").rglob("base_*.json"), reverse=True):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("config") == wanted and doc.get("status") == "completed":
            return doc
    pytest.skip("Run the quick/benchmark experiment to create the measured app fixture.")


@pytest.fixture
def saved_app(monkeypatch):
    document = recorded_result()

    def matching_loader(config, results_dir=None):
        return deepcopy(document) if asdict(config) == document["config"] else None

    monkeypatch.setattr(experiments, "load_saved", matching_loader)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    return app, document


def metric(app, label):
    return next(item.value for item in app.metric if item.label == label)


def selectbox(app, label):
    return next(item for item in app.selectbox if item.label == label)


def test_saved_evidence_is_visible_and_controls_clear_mismatched_data(saved_app):
    app, document = saved_app
    assert "SAVED BENCHMARK RUN" in app.success[0].value
    assert metric(app, "Selected allocation utility") == "36.00"
    assert len(app.get("download_button")) == 2
    assert {tab.label for tab in app.tabs} == {
        "Allocation & evidence", "Explore priorities", "Stress-test quantum noise"
    }

    selectbox(app, "Allocation shown on the city diagram").select(
        "Compiler search · best feasible sample").run()
    app.select_slider[0].set_value(2.).run()
    assert not app.exception
    assert not app.success
    assert any("No matching quantum evidence" in item.value for item in app.info)
    assert metric(app, "Selected allocation utility") == "59.00"
    assert metric(app, "Quantum feasible sample rate") == "—"
    assert selectbox(app, "Allocation shown on the city diagram").options == ["Exact classical optimum"]
    assert len(app.get("download_button")) == 0


def test_live_run_survives_noise_selection_but_not_changed_allocation(saved_app, monkeypatch, tmp_path):
    app, _ = saved_app
    quick = recorded_result(quick=True)
    captured = []

    def recorded_run(config):
        assert asdict(config) == quick["config"]
        return deepcopy(quick)

    def save_record(document, results_dir=None):
        captured.append(document)
        return tmp_path / "live.json"

    monkeypatch.setattr(experiments, "run_experiment", recorded_run)
    monkeypatch.setattr(experiments, "save_result", save_record)
    app.button[0].click().run()
    assert not app.exception
    assert "LIVE RUN" in app.success[0].value
    assert "1,024 shots" in app.success[0].value
    assert len(captured) == 1

    selectbox(app, "Evaluation noise").select("high").run()
    assert not app.exception
    assert "LIVE RUN" in app.success[0].value
    searched = next(row for row in quick["executions"]
                    if row["method"] == "searched" and row["noise"] == "high")
    assert metric(app, "Quantum feasible sample rate") == f"{100 * searched['metrics']['feasible_rate']:.1f}%"

    app.slider[0].set_value(4).run()
    assert not app.exception
    assert not app.success
    assert metric(app, "Quantum feasible sample rate") == "—"
    assert any("No matching quantum evidence" in item.value for item in app.info)


def test_no_feasible_sample_does_not_silently_show_classical_fallback(monkeypatch):
    document = recorded_result()
    scenario = load_scenario()
    # This intentionally invalid distribution is a test fixture only; it is never saved.
    for execution in document["executions"]:
        if execution["method"] == "searched" and execution["noise"] == "low":
            execution["counts"] = {"00000000": document["config"]["shots"]}
            execution["metrics"] = evaluate_counts(execution["counts"], scenario, 1., 3,
                                                    document["exact"])
    monkeypatch.setattr(experiments, "load_saved", lambda config, results_dir=None: deepcopy(document))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    selectbox(app, "Allocation shown on the city diagram").select(
        "Compiler search · best feasible sample").run()
    assert not app.exception
    assert metric(app, "Selected allocation utility") == "—"
    assert metric(app, "Constraints") == "No sample"
    assert any("No sample is available" in item.value for item in app.warning)

    selectbox(app, "Allocation shown on the city diagram").select(
        "Compiler search · most frequent raw sample").run()
    assert not app.exception
    assert metric(app, "Constraints") == "Failed"
    assert metric(app, "Regret vs exact optimum") == "—"
    assert any("violates the allocation constraints" in item.value for item in app.warning)


def test_live_source_change_invalidates_in_session_evidence(saved_app, monkeypatch, tmp_path):
    app, _ = saved_app
    quick = recorded_result(quick=True)
    monkeypatch.setattr(experiments, "run_experiment", lambda config: deepcopy(quick))
    monkeypatch.setattr(experiments, "save_result", lambda document, results_dir=None: tmp_path / "live.json")
    app.button[0].click().run()
    assert "LIVE RUN" in app.success[0].value

    import lifelineq.provenance as provenance
    monkeypatch.setattr(provenance, "source_hash", lambda: "changed-computational-source")
    monkeypatch.setattr(experiments, "load_saved", lambda config, results_dir=None: None)
    app.run()
    assert not app.exception
    assert not app.success
    assert metric(app, "Quantum feasible sample rate") == "—"


@pytest.mark.parametrize("storage_fails", [False, True])
def test_live_failure_keeps_partial_evidence_and_reports_original_error(
        saved_app, monkeypatch, tmp_path, storage_fails):
    app, _ = saved_app
    partial = recorded_result(quick=True)
    partial.update(status="failed", error="Test fixture: noisy execution stopped")
    partial["executions"] = partial["executions"][:1]
    captured = []

    def unsuccessful_run(config):
        raise experiments.ExperimentFailure(partial)

    def save_record(document, results_dir=None):
        if storage_fails:
            raise OSError("Test fixture: storage unavailable")
        captured.append(document)
        return tmp_path / "failed.json"

    monkeypatch.setattr(experiments, "run_experiment", unsuccessful_run)
    monkeypatch.setattr(experiments, "save_result", save_record)
    app.button[0].click().run()
    assert not app.exception
    assert any("noisy execution stopped" in item.value for item in app.error)
    assert not any("LIVE RUN" in item.value for item in app.success)
    if storage_fails:
        assert any("failure record could not be saved" in item.value for item in app.warning)
    else:
        assert captured == [partial]
        assert len(captured[0]["executions"]) == 1
