"""Whole-distribution evaluation; exact solutions are evaluation-only."""
from math import sqrt, isclose
from .model import bits_from_count_key, utility, feasible, exact_solution


def wilson_interval(successes, total, z=1.959963984540054):
    if total == 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    radius = z * sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0., center-radius), min(1., center+radius)]


def evaluate_counts(counts, scenario, weight, k, exact=None):
    exact = exact if exact is not None else exact_solution(scenario, weight, k)
    rows = []
    for key, count in counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Counts must be nonnegative integers")
        if count == 0:
            continue
        bits = bits_from_count_key(key, scenario.n)
        value = float(utility(bits, scenario, weight))
        rows.append(dict(bits=list(bits), bitstring=key, count=count, utility=value,
                         feasible=bool(feasible(bits, scenario, k)),
                         regret=float(exact['utility']-value)))
    shots = sum(r['count'] for r in rows)
    valid = [r for r in rows if r['feasible']]
    feasible_shots = sum(r['count'] for r in valid)
    optimal_shots = sum(r['count'] for r in valid
                        if isclose(r['utility'], exact['utility'], abs_tol=1e-9, rel_tol=1e-12))
    best = sorted(valid, key=lambda r: (-r['utility'], r['bitstring']))[0] if valid else None
    modal = sorted(rows, key=lambda r: (-r['count'], r['bitstring']))[0] if rows else None
    mean = sum(r['utility']*r['count'] for r in valid)/feasible_shots if valid else None
    variance = (sum(r['count']*(r['utility']-mean)**2 for r in valid)/(feasible_shots-1)
                if feasible_shots > 1 else None)
    return dict(shots=shots, feasible_shots=feasible_shots,
                feasible_rate=feasible_shots/shots if shots else None,
                feasible_rate_ci=wilson_interval(feasible_shots, shots),
                optimal_probability=optimal_shots/shots if shots else None,
                optimal_probability_ci=wilson_interval(optimal_shots, shots),
                conditional_mean_utility=mean,
                conditional_mean_regret=exact['utility']-mean if mean is not None else None,
                conditional_mean_utility_se=sqrt(variance/feasible_shots) if variance is not None else None,
                best_feasible=best, most_frequent=modal,
                best_feasible_regret=best['regret'] if best else None,
                no_feasible_sample=not bool(valid))
