import pytest

from lifelineq.baselines import greedy_solution, random_feasible_counts
from lifelineq.model import bits_from_count_key, exact_solution, feasible, load_scenario, utility


@pytest.mark.parametrize("name", ["base", "demand_shift", "overlap_shift"])
@pytest.mark.parametrize("weight", [0, 1, 2])
@pytest.mark.parametrize("k", [1, 3, 8])
def test_greedy_is_feasible_deterministic_and_swaps_do_not_degrade(name, weight, k):
    scenario = load_scenario(name)
    raw = greedy_solution(scenario, weight, k, improve=False)
    improved = greedy_solution(scenario, weight, k)
    again = greedy_solution(scenario, weight, k)
    assert feasible(raw["bits"], scenario, k)
    assert feasible(improved["bits"], scenario, k)
    assert improved["utility"] >= raw["utility"]
    assert improved["utility"] <= exact_solution(scenario, weight, k)["utility"]
    assert improved["utility"] == utility(improved["bits"], scenario, weight)
    assert improved["bits"] == again["bits"]


def test_uniform_feasible_baseline_counts_and_reproducibility():
    scenario = load_scenario()
    counts = random_feasible_counts(scenario, 1, 3, 36000, 73)
    assert counts == random_feasible_counts(scenario, 1, 3, 36000, 73)
    assert sum(counts.values()) == 36000
    assert len(counts) == 36
    assert all(feasible(bits_from_count_key(key, 8), scenario, 3) for key in counts)
    # A broad deterministic sanity check catches a badly biased sampler.
    assert all(800 < frequency < 1200 for frequency in counts.values())


@pytest.mark.parametrize("shots", [0, -1, 2.5, True])
def test_invalid_random_shot_budget(shots):
    with pytest.raises(ValueError):
        random_feasible_counts(load_scenario(), 1, 3, shots, 7)
