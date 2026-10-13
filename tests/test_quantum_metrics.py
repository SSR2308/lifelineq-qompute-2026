from dataclasses import replace
import json
import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap
from qiskit.quantum_info import Statevector
from lifelineq.model import load_scenario, count_key, exact_solution, bits_from_count_key
from lifelineq.metrics import evaluate_counts
from lifelineq.quantum import fit_qaoa
from lifelineq.noise import sample_circuit, logical_probabilities, compile_pair, BASIS_GATES
from lifelineq.provenance import cache_key
from lifelineq.experiments import ExperimentConfig, _envelope, save_result, load_saved


def test_distribution_metrics_and_no_feasible():
    s = load_scenario()
    optimal = exact_solution(s, 0, 3)['optima'][0]
    counts = {optimal['bitstring']:2, '00000000':8, '11000001':2}
    m = evaluate_counts(counts, s, 0, 3)
    assert m['feasible_rate'] == pytest.approx(4/12)
    assert m['most_frequent']['feasible'] is False
    assert m['optimal_probability'] == pytest.approx(2/12)
    assert m['best_feasible']['bits'] == optimal['bits']
    assert m['conditional_mean_utility'] == pytest.approx((21+12)/2)
    assert m['conditional_mean_regret'] == pytest.approx(4.5)
    assert m['best_feasible_regret'] == 0
    failed = evaluate_counts({'00000000':20}, s, 0, 3)
    assert failed['no_feasible_sample']
    assert failed['best_feasible'] is None
    assert failed['conditional_mean_regret'] is None
    assert failed['optimal_probability'] == 0


def test_all_tied_optima_count_as_success():
    s = load_scenario()
    exact = exact_solution(s, 1, 3)
    counts = {r['bitstring']:1 for r in exact['optima']}
    assert evaluate_counts(counts, s, 1, 3)['optimal_probability'] == 1


def test_routed_measurement_decoding_with_nontrivial_layout():
    circuit = QuantumCircuit(8)
    circuit.x(0)
    circuit.x(6)
    circuit.cx(0, 3)
    circuit.measure_all()
    routed = transpile(circuit, basis_gates=BASIS_GATES, coupling_map=CouplingMap.from_ring(8),
                       initial_layout=[7,6,5,4,3,2,1,0], seed_transpiler=7, optimization_level=0)
    probs = logical_probabilities(routed)
    assert probs[1+8+64] == pytest.approx(1)
    counts, _ = sample_circuit(routed, 'zero', 100, 9)
    assert counts == {'01001001':100}
    assert bits_from_count_key(next(iter(counts)), 8) == (1,0,0,1,0,0,1,0)


def test_qaoa_zero_noise_equivalence_and_counts():
    s = load_scenario()
    logical, training = fit_qaoa(s, 1, 3, p=1, starts=2, maxiter=10)
    assert len(training['starts']) == 2
    assert training['nfev'] <= 20
    circuits, report = compile_pair(logical, candidates=2)
    expected = Statevector.from_instruction(logical).probabilities()
    for method, circuit in circuits.items():
        np.testing.assert_allclose(logical_probabilities(circuit), expected, atol=1e-9)
        counts, _ = sample_circuit(circuit, 'zero', 128, 12)
        assert sum(counts.values()) == 128
    assert report['searched']['two_qubit_gates'] <= report['ordinary']['two_qubit_gates']


def test_cache_invalidates_on_scenario_settings_source_versions(tmp_path, monkeypatch):
    s = load_scenario()
    config = ExperimentConfig()
    key = cache_key(s, config)
    assert cache_key(replace(s, rho=2), config) != key
    assert cache_key(s, replace(config, k=4)) != key
    assert cache_key(s, replace(config, shots=2048)) != key
    doc = _envelope(config)
    doc['status'] = 'completed'
    save_result(doc, tmp_path)
    assert load_saved(config, tmp_path) is not None
    assert load_saved(replace(config, seed=22), tmp_path) is None
    import lifelineq.provenance as provenance
    monkeypatch.setattr(provenance, 'source_hash', lambda:'changed')
    assert cache_key(s, config) != key
    assert load_saved(config, tmp_path) is None


def test_tampered_metadata_is_rejected(tmp_path):
    config = ExperimentConfig()
    doc = _envelope(config)
    doc['status'] = 'completed'
    doc['metadata']['versions']['qiskit'] = '0.0.0'
    save_result(doc, tmp_path)
    assert load_saved(config, tmp_path) is None


def test_partial_failure_retains_completed_measurements(tmp_path, monkeypatch):
    import lifelineq.experiments as experiments
    config = ExperimentConfig(starts=1, maxiter=10, shots=32, compiler_candidates=1)
    sampler = experiments.sample_circuit
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Deliberate test-only simulator failure')
        return sampler(*args, **kwargs)

    monkeypatch.setattr(experiments, 'sample_circuit', fail_on_second)
    with pytest.raises(experiments.ExperimentFailure) as error:
        experiments.run_experiment(config)
    doc = error.value.document
    assert doc['status'] == 'failed'
    assert doc['stage'] == 'ordinary / zero'
    assert doc['training']['nfev'] > 0
    assert len(doc['executions']) == 1
    assert sum(doc['executions'][0]['counts'].values()) == 32
    first, second = save_result(doc, tmp_path), save_result(doc, tmp_path)
    assert first != second
    assert first.exists() and second.exists()
    assert load_saved(config, tmp_path) is None


def test_successful_attempts_are_retained(tmp_path):
    doc = _envelope(ExperimentConfig())
    doc['status'] = 'completed'
    paths = [save_result(doc, tmp_path) for _ in range(2)]
    assert paths[0] != paths[1]
    assert all(path.exists() for path in paths)


@pytest.mark.parametrize('kwargs', [{'k':0},{'weight':-1},{'p':3},{'shots':0},{'maxiter':1},{'seed':-1}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        ExperimentConfig(**kwargs)
