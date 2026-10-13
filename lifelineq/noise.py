"""Synthetic hardware experiment: equal resources, circuit-only compilation search."""
from time import perf_counter
import hashlib
import numpy as np
from qiskit import transpile, qasm2
from qiskit.transpiler import CouplingMap
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

BASIS_GATES = ['rz', 'sx', 'x', 'cx']
NOISE_PRESETS = {
    'zero': dict(one_qubit=0., two_qubit=0., readout=0.),
    'low': dict(one_qubit=0.001, two_qubit=0.01, readout=0.01),
    'high': dict(one_qubit=0.005, two_qubit=0.03, readout=0.03),
}


def make_noise_model(preset='zero'):
    rates = NOISE_PRESETS[preset] if isinstance(preset, str) else preset
    if any(not 0 <= rates[key] <= 1 for key in ('one_qubit', 'two_qubit', 'readout')):
        raise ValueError('Noise rates must lie in [0,1]')
    model = NoiseModel(basis_gates=BASIS_GATES)
    if rates['one_qubit']:
        model.add_all_qubit_quantum_error(depolarizing_error(rates['one_qubit'], 1), ['sx', 'x'])
    if rates['two_qubit']:
        model.add_all_qubit_quantum_error(depolarizing_error(rates['two_qubit'], 2), ['cx'])
    if rates['readout']:
        e = rates['readout']
        model.add_all_qubit_readout_error(ReadoutError([[1-e, e], [e, 1-e]]))
    return model


def measurement_mapping(circuit):
    """physical qubit -> logical classical bit (measurements added BEFORE routing)."""
    mapping = {}
    for inst in circuit.data:
        if inst.operation.name == 'measure':
            mapping[circuit.find_bit(inst.qubits[0]).index] = circuit.find_bit(inst.clbits[0]).index
    if len(mapping) != circuit.num_qubits or len(set(mapping.values())) != circuit.num_clbits:
        raise ValueError('Expected complete one-to-one terminal measurement mapping')
    return mapping


def logical_probabilities(circuit):
    mapping = measurement_mapping(circuit)
    physical = Statevector.from_instruction(circuit.remove_final_measurements(inplace=False)).probabilities()
    logical = np.zeros(2**circuit.num_clbits)
    for index, probability in enumerate(physical):
        decoded = sum(((index >> q) & 1) << c for q, c in mapping.items())
        logical[decoded] += probability
    return logical


def circuit_properties(circuit):
    return dict(depth=circuit.depth(), two_qubit_gates=sum(len(inst.qubits) == 2 for inst in circuit.data),
                operations={key:int(value) for key,value in circuit.count_ops().items()},
                physical_to_logical_measurements={str(k):v for k,v in measurement_mapping(circuit).items()},
                circuit_sha256=hashlib.sha256(qasm2.dumps(circuit).encode()).hexdigest())


def compile_pair(logical, seed=17011, candidates=4):
    if not 1 <= candidates <= 16:
        raise ValueError('Compilation search is bounded to 1..16 candidates')
    measured = logical.copy()
    measured.measure_all()
    topology = CouplingMap.from_ring(logical.num_qubits, bidirectional=True)
    compiled, records = [], []
    search_start = perf_counter()
    for index in range(candidates):
        started = perf_counter()
        circuit = transpile(measured, basis_gates=BASIS_GATES, coupling_map=topology,
                            optimization_level=2, seed_transpiler=seed+index,
                            layout_method='sabre', routing_method='sabre')
        record = dict(candidate=index, seed_transpiler=seed+index, **circuit_properties(circuit),
                      compilation_seconds=perf_counter()-started)
        compiled.append(circuit)
        records.append(record)
    search_seconds = perf_counter()-search_start
    winner = min(range(candidates), key=lambda i: (records[i]['two_qubit_gates'], records[i]['depth'], i))
    reference = Statevector.from_instruction(logical).probabilities()
    errors = [float(np.max(np.abs(logical_probabilities(c)-reference))) for c in compiled]
    if max(errors) > 1e-9:
        raise AssertionError(f'Routing changed the logical distribution: {errors}')
    # Unrouted ideal execution: same logical circuit, Aer counts, zero noise.
    ideal = transpile(measured, basis_gates=BASIS_GATES, optimization_level=2, seed_transpiler=seed)
    return {'ideal':ideal, 'ordinary':compiled[0], 'searched':compiled[winner]}, dict(
        ordinary=records[0], searched=records[winner], candidates=records,
        selected_candidate=winner, search_seconds=search_seconds,
        additional_search_seconds=search_seconds-records[0]['compilation_seconds'],
        candidate_count=candidates, basis_gates=BASIS_GATES, optimization_level=2,
        layout_method='sabre', routing_method='sabre', topology='bidirectional synthetic ring',
        coupling_edges=[list(edge) for edge in topology.get_edges()],
        noiseless_max_probability_errors=errors,
        selection_rule='fewest two-qubit gates, then depth, then candidate index')


def sample_circuit(circuit, noise='zero', shots=1024, seed=11):
    if not isinstance(shots, int) or shots < 1:
        raise ValueError('shots must be a positive integer')
    started = perf_counter()
    # Density-matrix evolution avoids costly noisy trajectory simulation per shot.
    simulator = AerSimulator(method='density_matrix', noise_model=make_noise_model(noise),
                             max_parallel_threads=1, max_parallel_experiments=1)
    result = simulator.run(circuit, shots=shots, seed_simulator=seed).result()
    if not result.success:
        raise RuntimeError(str(result.status))
    counts = {str(key):int(value) for key,value in result.get_counts().items()}
    if sum(counts.values()) != shots:
        raise AssertionError('Aer returned an unexpected shot count')
    return counts, perf_counter()-started
