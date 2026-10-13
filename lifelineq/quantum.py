"""QAOA energy fitting on Qiskit's ideal statevector; no optimum injection."""
from time import perf_counter
import numpy as np
from scipy.optimize import minimize
from qiskit import transpile
from qiskit.circuit.library import qaoa_ansatz
from qiskit.quantum_info import Statevector
from .model import build_hamiltonian


def fit_qaoa(scenario, weight, k, p=1, seed=11, starts=2, maxiter=60):
    if p not in (1, 2) or starts < 1 or maxiter < 10:
        raise ValueError('Use p in {1,2}, at least one start and maxiter >= 10')
    started = perf_counter()
    hamiltonian = build_hamiltonian(scenario, weight, k)
    ansatz = qaoa_ansatz(hamiltonian.normalized_operator, reps=p)
    # Keep diagonal interactions as rzz for fast but entirely Qiskit simulation.
    training_circuit = transpile(ansatz, basis_gates=['h', 'rx', 'rz', 'rzz'], optimization_level=0)
    parameter_names = [str(v) for v in training_circuit.parameters]
    diagonal = np.real(np.diag(hamiltonian.normalized_operator.to_matrix()))
    rng = np.random.default_rng(seed)
    records = []
    best = None
    for start in range(starts):
        evaluations = []
        # Both angle families get explicit bounded domains; gamma periodicity is
        # not assumed after scaling a weighted Hamiltonian.
        bounds = [(0., np.pi) if name.startswith('β') else (0., 2*np.pi)
                  for name in parameter_names]
        initial = np.array([rng.uniform(low, high) for low, high in bounds])

        def energy(parameters):
            state = Statevector.from_instruction(training_circuit.assign_parameters(parameters))
            value = float(np.dot(state.probabilities(), diagonal))
            evaluations.append(value)
            return value

        fit_start = perf_counter()
        result = minimize(energy, initial, method='COBYLA', bounds=bounds,
                          options={'maxiter': maxiter, 'rhobeg': 0.5, 'tol': 1e-5})
        record = dict(start=start, initial_parameters=initial.tolist(), parameters=result.x.tolist(),
                      energy=float(result.fun), nfev=int(result.nfev), success=bool(result.success),
                      message=str(result.message), elapsed_seconds=perf_counter()-fit_start,
                      energy_trace=evaluations)
        records.append(record)
        if best is None or record['energy'] < best['energy']:
            best = record
    circuit = training_circuit.assign_parameters(best['parameters'])
    training = dict(parameters=best['parameters'], parameter_names=parameter_names,
                    energy=best['energy'], original_energy=best['energy']*hamiltonian.scale+hamiltonian.offset,
                    offset=hamiltonian.offset, scale=hamiltonian.scale,
                    nfev=sum(r['nfev'] for r in records), elapsed_seconds=perf_counter()-started,
                    starts=records, selected_start=best['start'], seed=seed,
                    simulator='Qiskit Statevector (ideal, full amplitudes)', optimizer='SciPy COBYLA',
                    objective='Expected normalized penalized energy; no noisy evaluation used for fitting',
                    angle_bounds={'beta':[0., float(np.pi)], 'gamma':[0., float(2*np.pi)]})
    return circuit, training
