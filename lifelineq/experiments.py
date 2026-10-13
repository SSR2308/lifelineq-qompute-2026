"""Reproducible CLI and app API. Fits are frozen across compilation/noise arms."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import platform
from time import perf_counter
import traceback

from .baselines import greedy_solution, random_feasible_counts
from .metrics import evaluate_counts
from .model import load_scenario, exact_solution, validate_inputs
from .noise import compile_pair, sample_circuit, circuit_properties, NOISE_PRESETS
from .provenance import ROOT, SCHEMA_VERSION, cache_key, source_hash, versions
from .quantum import fit_qaoa

LOADED_SOURCE_HASH = source_hash()


class ExperimentFailure(RuntimeError):
    """An unsuccessful attempt, retaining all completed measurements and fitting."""

    def __init__(self, document):
        super().__init__(document['error'])
        self.document = document


@dataclass(frozen=True)
class ExperimentConfig:
    scenario_name: str = 'base'
    weight: float = 1.0
    k: int = 3
    p: int = 1
    seed: int = 11
    shots: int = 1024
    starts: int = 2
    maxiter: int = 60
    compiler_candidates: int = 4

    def __post_init__(self):
        # Canonical float prevents 1 versus 1.0 creating different cache keys.
        object.__setattr__(self, 'weight', float(self.weight))
        validate_inputs(load_scenario(self.scenario_name), self.weight, self.k)
        for name in ('seed', 'shots', 'starts', 'maxiter', 'compiler_candidates', 'p'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f'{name} must be an integer')
        if self.p not in (1, 2) or self.seed < 0 or self.shots < 1 or self.starts < 1 or self.maxiter < 10:
            raise ValueError('Invalid depth, seed, shots, starts, or optimizer budget')
        if not 1 <= self.compiler_candidates <= 16:
            raise ValueError('Use 1..16 compilation candidates')


def _envelope(config):
    if source_hash() != LOADED_SOURCE_HASH:
        raise RuntimeError('Solver source changed after import. Restart the process before recording a run.')
    scenario = load_scenario(config.scenario_name)
    return dict(schema_version=SCHEMA_VERSION, cache_key=cache_key(scenario, asdict(config)),
                config=asdict(config), scenario=scenario.to_dict(),
                metadata=dict(source_hash=source_hash(), versions=versions(),
                              created_utc=datetime.now(timezone.utc).isoformat(),
                              platform=platform.platform(), machine=platform.machine(),
                              synthetic=True, noise_presets=NOISE_PRESETS,
                              simulator_threads=1, independent_seed_unit='one optimization fit',
                              noise_scope='sx/x and cx depolarization, symmetric readout; rz ideal'),
                executions=[])


def failure_record(config, error):
    document = _envelope(config)
    document.update(status='failed', error=str(error))
    return document


def run_experiment(config):
    document = _envelope(config)
    started = perf_counter()
    try:
        completed = _execute_experiment(config, document)
        if source_hash() != document['metadata']['source_hash']:
            raise RuntimeError('Solver source changed during execution; this attempt cannot be used as current evidence.')
        completed['elapsed_seconds'] = perf_counter()-started
        completed['status'] = 'completed'
        completed.pop('stage', None)
        return completed
    except Exception as exc:
        document.update(status='failed', error=traceback.format_exc(),
                        elapsed_seconds=perf_counter()-started)
        raise ExperimentFailure(document) from exc


def _execute_experiment(config, document):
    scenario = load_scenario(config.scenario_name)
    document['stage'] = 'classical baselines'
    document['exact'] = exact_solution(scenario, config.weight, config.k)
    document['greedy'] = greedy_solution(scenario, config.weight, config.k)
    document['stage'] = 'QAOA fitting'
    logical, document['training'] = fit_qaoa(scenario, config.weight, config.k, config.p,
                                            config.seed, config.starts, config.maxiter)
    document['stage'] = 'compilation'
    circuits, document['compilation'] = compile_pair(logical, 17000+config.seed, config.compiler_candidates)
    for method, circuit in circuits.items():
        for noise in (['zero'] if method == 'ideal' else list(NOISE_PRESETS)):
            document['stage'] = f'{method} / {noise}'
            # Same fitted circuit and number of shots. No outcomes enter selection.
            evaluation_seed = 100000+config.seed
            counts, seconds = sample_circuit(circuit, noise, config.shots, evaluation_seed)
            document['executions'].append(dict(method=method, noise=noise, counts=counts,
                metrics=evaluate_counts(counts, scenario, config.weight, config.k, document['exact']),
                circuit=circuit_properties(circuit), simulation_seconds=seconds,
                evaluation_seed=evaluation_seed, simulator='Qiskit Aer density_matrix'))
    document['stage'] = 'uniform feasible baseline'
    baseline_start = perf_counter()
    counts = random_feasible_counts(scenario, config.weight, config.k, config.shots, 200000+config.seed)
    document['executions'].append(dict(method='uniform_feasible', noise='zero', counts=counts,
        metrics=evaluate_counts(counts, scenario, config.weight, config.k, document['exact']),
        circuit=None, simulation_seconds=perf_counter()-baseline_start, evaluation_seed=200000+config.seed,
        simulator='NumPy classical sampling over enumerated feasible set'))
    return document


def save_result(document, results_dir='results'):
    directory = Path(results_dir)
    if not directory.is_absolute():
        directory = ROOT/directory
    directory.mkdir(parents=True, exist_ok=True)
    c = document['config']
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    status = document.get('status', 'unknown')
    path = directory/f"{c['scenario_name']}_l{c['weight']:g}_p{c['p']}_s{c['seed']}_{document['cache_key'][:12]}_{status}_{timestamp}.json"
    # Every attempt has its own file; failed and successful reruns are retained.
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(document, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)
    return path


def load_saved(config, results_dir='results'):
    directory = Path(results_dir)
    if not directory.is_absolute():
        directory = ROOT/directory
    scenario = load_scenario(config.scenario_name)
    expected = cache_key(scenario, asdict(config))
    for path in sorted(directory.glob(f'{config.scenario_name}_*.json'), reverse=True):
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if (doc.get('cache_key') == expected and doc.get('config') == asdict(config)
                and doc.get('scenario') == scenario.to_dict()
                and doc.get('metadata', {}).get('source_hash') == source_hash()
                and doc.get('metadata', {}).get('versions') == versions()
                and doc.get('schema_version') == SCHEMA_VERSION and doc.get('status') == 'completed'):
            return doc
    return None


def results_rows(document):
    rows = []
    for execution in document.get('executions', []):
        m, c = execution['metrics'], execution.get('circuit') or {}
        row = dict(**document['config'], method=execution['method'], noise=execution['noise'],
                   source_hash=document['metadata']['source_hash'], cache_key=document['cache_key'],
                   exact_utility=document['exact']['utility'], greedy_utility=document['greedy']['utility'],
                   depth=c.get('depth'), two_qubit_gates=c.get('two_qubit_gates'),
                   simulation_seconds=execution['simulation_seconds'],
                   optimization_seconds=document['training']['elapsed_seconds'],
                   nfev=document['training']['nfev'], search_seconds=document['compilation']['search_seconds'])
        for field in ('feasible_shots', 'feasible_rate', 'optimal_probability', 'conditional_mean_utility',
                      'conditional_mean_regret', 'conditional_mean_utility_se', 'best_feasible_regret',
                      'no_feasible_sample'):
            row[field] = m[field]
        for field in ('feasible_rate', 'optimal_probability'):
            row[field+'_ci_low'], row[field+'_ci_high'] = m[field+'_ci']
        rows.append(row)
    return rows


def write_summary(documents, directory, preset):
    import pandas as pd
    frame = pd.DataFrame([row for doc in documents for row in results_rows(doc)])
    if frame.empty:
        return
    frame.to_csv(directory/f'{preset}_runs.csv', index=False)
    metrics = ['feasible_rate', 'optimal_probability', 'conditional_mean_regret',
               'best_feasible_regret', 'two_qubit_gates', 'depth', 'simulation_seconds']
    summary = frame.groupby(['scenario_name', 'weight', 'p', 'method', 'noise'])[metrics].agg(['mean','std','count'])
    summary.columns = ['_'.join(column) for column in summary.columns]
    summary.to_csv(directory/f'{preset}_summary.csv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset', choices=['quick','benchmark','robustness'], default='quick')
    parser.add_argument('--output', default='results')
    parser.add_argument('--force', action='store_true', help='Re-run even matching cached experiments')
    args = parser.parse_args()
    directory = Path(args.output)
    if not directory.is_absolute():
        directory = ROOT/directory
    directory.mkdir(parents=True, exist_ok=True)
    scenarios = ['demand_shift','overlap_shift'] if args.preset == 'robustness' else ['base']
    quick = args.preset == 'quick'
    configs = [ExperimentConfig(scenario_name=s, weight=w, p=p, seed=seed,
                                shots=1024 if quick else 2048, maxiter=60 if quick else 80)
               for s in scenarios for w in ([1.] if quick else [0.,1.,2.])
               for p in ([1] if quick else [1,2]) for seed in ([11] if quick else [11,22,33,44,55])]
    documents, failures = [], 0
    for index, config in enumerate(configs, 1):
        print(f'[{index}/{len(configs)}] {config}', flush=True)
        doc = None if args.force else load_saved(config, directory)
        if doc is None:
            try:
                doc = run_experiment(config)
                print(f"  completed in {doc['elapsed_seconds']:.2f}s; {save_result(doc, directory).name}", flush=True)
            except Exception as exc:
                doc = exc.document if isinstance(exc, ExperimentFailure) else failure_record(config, traceback.format_exc())
                save_result(doc, directory)
                failures += 1
                print(doc['error'], flush=True)
                continue
        else:
            print('  using matching saved result', flush=True)
        documents.append(doc)
        write_summary(documents, directory, args.preset)
    print(f'Completed {len(documents)} experiments; {failures} failures. Results: {directory}', flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
