from dataclasses import replace

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from lifelineq.model import (Scenario, bits_from_count_key, bits_from_index, build_hamiltonian,
                            cost, count_key, enumerate_feasible, exact_solution, feasible,
                            load_scenario, penalty_bound, utility, validate_inputs)


@pytest.mark.parametrize("weight", [0, 1, 2])
@pytest.mark.parametrize("k", [1, 3, 8])
def test_all_256_hamiltonian_diagonals_include_offset_and_scale(weight, k):
    scenario = load_scenario()
    hamiltonian = build_hamiltonian(scenario, weight, k)
    diagonal = np.diag(hamiltonian.operator.to_matrix()).real
    normalized = np.diag(hamiltonian.normalized_operator.to_matrix()).real
    classical = np.asarray([cost(bits_from_index(i, 8), scenario, weight, k) for i in range(256)])
    np.testing.assert_allclose(diagonal + hamiltonian.offset, classical, atol=1e-9)
    np.testing.assert_allclose(hamiltonian.scale*normalized + hamiltonian.offset, classical, atol=1e-9)
    assert hamiltonian.scale > 0


@pytest.mark.parametrize("weight, expected", [(0, 21), (1, 36), (2, 59)])
def test_exact_fixture_and_all_tied_optima(weight, expected):
    scenario = load_scenario()
    result = exact_solution(scenario, weight, 3)
    assert result["utility"] == expected
    assert result["feasible_count"] == 36
    # Independently traverse the entire binary cube, including infeasible rows.
    exhaustive = [bits_from_index(i, 8) for i in range(256)]
    expected_keys = {count_key(bits) for bits in exhaustive
                     if feasible(bits, scenario, 3) and utility(bits, scenario, weight) == expected}
    assert {row["bitstring"] for row in result["optima"]} == expected_keys
    assert all(row["utility"] == expected for row in result["optima"])
    if weight == 1:
        assert len(result["optima"]) > 1


def test_bit_order_matches_qiskit_statevector_and_counts():
    circuit = QuantumCircuit(8)
    circuit.x(0)
    circuit.x(3)
    circuit.x(7)
    state = Statevector.from_instruction(circuit)
    index = int(np.argmax(state.probabilities()))
    assert index == 137
    bits = (1, 0, 0, 1, 0, 0, 0, 1)
    assert bits_from_index(index, 8) == bits
    assert count_key(bits) == "10001001"
    assert bits_from_count_key("1000 1001", 8) == bits
    assert state.probabilities_dict() == {count_key(bits): 1.0}


@pytest.mark.parametrize("weight", [0, 1, 2])
def test_penalty_strictly_separates_feasible_and_infeasible_energy(weight):
    scenario = load_scenario()
    bits = [bits_from_index(i, 8) for i in range(256)]
    values = [utility(row, scenario, weight) for row in bits]
    assert penalty_bound(scenario, weight) > max(values)-min(values)
    feasible_energies = [cost(row, scenario, weight, 3) for row in bits if feasible(row, scenario, 3)]
    infeasible_energies = [cost(row, scenario, weight, 3) for row in bits if not feasible(row, scenario, 3)]
    assert min(infeasible_energies) > max(feasible_energies)


@pytest.mark.parametrize("k", [0, -1, 9, 1.5, True])
def test_impossible_units_rejected(k):
    with pytest.raises(ValueError):
        exact_solution(load_scenario(), 1, k)


@pytest.mark.parametrize("weight", [-1, float("nan"), float("inf"), True])
def test_invalid_weights_rejected(weight):
    with pytest.raises(ValueError):
        build_hamiltonian(load_scenario(), weight, 3)


@pytest.mark.parametrize("changes", [
    {"priority_sites": (6, 6)}, {"priority_sites": (6, 8)}, {"rho": -1},
    {"priority": (1,)}, {"overlaps": ((0, 0, 1),)},
    {"overlaps": ((0, 1, 1), (0, 1, 2))},
    {"benefit": (float("nan"),)*8}, {"coordinates": ((0, float("inf")),)*8},
])
def test_malformed_scenarios_rejected(changes):
    with pytest.raises(ValueError):
        validate_inputs(replace(load_scenario(), **changes), 1, 3)


def test_constraint_decisions_and_invalid_bits():
    scenario = load_scenario()
    assert feasible((1, 0, 0, 1, 0, 0, 1, 0), scenario, 3)
    assert not feasible((1, 1, 1, 0, 0, 0, 0, 0), scenario, 3)
    assert not feasible((0, 0, 0, 0, 0, 0, 1, 0), scenario, 3)
    with pytest.raises(ValueError):
        utility([0]*7, scenario, 1)
    with pytest.raises(ValueError):
        bits_from_count_key("10002", 5)
    with pytest.raises(ValueError):
        bits_from_index(256, 8)


@pytest.mark.parametrize("name", ["base", "demand_shift", "overlap_shift"])
def test_predefined_scenarios_roundtrip(name):
    scenario = load_scenario(name)
    assert Scenario.from_dict(scenario.to_dict()) == scenario
    assert len(enumerate_feasible(scenario, 1, 3)) == 36
