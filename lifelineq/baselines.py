"""Transparent classical baselines using the same utility and hard constraints."""

from __future__ import annotations

from numbers import Integral
from time import perf_counter

import numpy as np

from .model import Scenario, count_key, enumerate_feasible, feasible, utility, validate_inputs


def greedy_solution(scenario: Scenario, weight: float, k: int, improve: bool = True) -> dict:
    """Deterministic marginal-gain allocation, then optional improving swaps.

    Each addition must leave a path to feasibility; at the last unit, an unmet
    priority requirement restricts the candidates. Ties favor the lower shelter
    index. One-swap improvement repeats until no strictly improving feasible
    swap exists, with index order breaking ties. This is a heuristic, not a
    promise of a global optimum.
    """
    validate_inputs(scenario, weight, k)
    start = perf_counter()
    bits = [0]*scenario.n
    for step in range(k):
        choices = []
        for candidate in range(scenario.n):
            if bits[candidate]:
                continue
            trial = bits.copy()
            trial[candidate] = 1
            if step == k-1 and not feasible(trial, scenario, k):
                continue
            choices.append((utility(trial, scenario, weight), -candidate, trial))
        bits = max(choices, key=lambda item: item[:2])[2]
    if improve:
        while True:
            current = utility(bits, scenario, weight)
            best_utility, best_bits = current, bits
            for removed in range(scenario.n):
                if not bits[removed]:
                    continue
                for added in range(scenario.n):
                    if bits[added]:
                        continue
                    trial = bits.copy()
                    trial[removed], trial[added] = 0, 1
                    if feasible(trial, scenario, k):
                        trial_utility = utility(trial, scenario, weight)
                        if trial_utility > best_utility + 1e-12:
                            best_utility, best_bits = trial_utility, trial
            if best_bits is bits:
                break
            bits = best_bits
    return {"bits": bits, "bitstring": count_key(bits), "utility": utility(bits, scenario, weight),
            "elapsed_seconds": perf_counter()-start}


def random_feasible_counts(scenario: Scenario, weight: float, k: int, shots: int, seed: int) -> dict[str, int]:
    """Draw exactly shots samples, uniformly over all feasible allocations.

    Enumeration is used to make uniformity explicit for this eight-site toy
    problem; its preprocessing cost does not scale efficiently to large inputs.
    The caller records the sample budget and evaluates the whole distribution.
    """
    if not isinstance(shots, Integral) or isinstance(shots, bool) or shots < 1:
        raise ValueError("The random baseline needs a positive integer shot budget.")
    records = enumerate_feasible(scenario, weight, k)
    draws = np.random.default_rng(seed).integers(0, len(records), size=shots)
    indices, frequencies = np.unique(draws, return_counts=True)
    return {records[int(index)]["bitstring"]: int(frequency)
            for index, frequency in zip(indices, frequencies)}
