"""Synthetic shelter allocation, exact verification, and its Ising encoding.

The penalty P exceeds the full possible range of utility: for binary monomials,
the range of a sum is at most the sum of the absolute coefficients. Therefore
R = sum(abs(b + weight*v)) + rho*sum(abs(r)) bounds max(U)-min(U), and P=R+1.
Every infeasible assignment incurs at least P, while a feasible assignment has
zero penalty. Hence E(infeasible) > E(feasible) whenever feasibility is possible.
This is deliberately conservative; the large penalty can make QAOA harder.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
import math
from numbers import Integral, Real
from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np
from qiskit.quantum_info import SparsePauliOp


@dataclass(frozen=True)
class Scenario:
    name: str
    benefit: tuple[float, ...]
    priority: tuple[float, ...]
    overlaps: tuple[tuple[int, int, float], ...]
    names: tuple[str, ...]
    coordinates: tuple[tuple[float, float], ...]
    priority_sites: tuple[int, int] = (6, 7)
    rho: float = 1.0

    @property
    def n(self) -> int:
        return len(self.benefit)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "benefit": list(self.benefit),
            "priority": list(self.priority),
            "overlaps": [list(item) for item in self.overlaps],
            "names": list(self.names),
            "coordinates": [list(point) for point in self.coordinates],
            "priority_sites": list(self.priority_sites),
            "rho": self.rho,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        scenario = cls(
            name=data["name"],
            benefit=tuple(data["benefit"]),
            priority=tuple(data["priority"]),
            overlaps=tuple(tuple(item) for item in data["overlaps"]),
            names=tuple(data["names"]),
            coordinates=tuple(tuple(point) for point in data["coordinates"]),
            priority_sites=tuple(data.get("priority_sites", (6, 7))),
            rho=data.get("rho", 1.0),
        )
        validate_inputs(scenario, 0, 1)
        return scenario


def load_scenario(name: str = "base") -> Scenario:
    """Load one of the predefined synthetic scenarios from the repository."""
    if name not in {"base", "demand_shift", "overlap_shift"}:
        raise ValueError(f"Unknown scenario: {name!r}")
    path = Path(__file__).resolve().parents[1] / "data" / f"{name}.json"
    with path.open(encoding="utf-8") as source:
        return Scenario.from_dict(json.load(source))


def _finite_number(value) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def validate_inputs(scenario: Scenario, weight: float, k: int) -> None:
    """Reject malformed scenarios and inputs for which no allocation is feasible."""
    if not _finite_number(weight) or weight < 0:
        raise ValueError("Priority weight must be finite and nonnegative.")
    if not isinstance(k, Integral) or isinstance(k, bool) or not 1 <= k <= scenario.n:
        raise ValueError("Units available must be an integer from 1 through the shelter count.")
    if scenario.n < 2:
        raise ValueError("At least two shelters are needed for two designated priority sites.")
    if len(scenario.priority) != scenario.n or len(scenario.names) != scenario.n:
        raise ValueError("Benefit, priority, and name arrays must have equal lengths.")
    if len(scenario.coordinates) != scenario.n:
        raise ValueError("Each shelter needs one synthetic diagram coordinate.")
    if not all(_finite_number(x) for x in (*scenario.benefit, *scenario.priority)):
        raise ValueError("All scores must be finite numbers.")
    if not _finite_number(scenario.rho) or scenario.rho < 0:
        raise ValueError("Overlap weight rho must be finite and nonnegative.")
    if len(scenario.priority_sites) != 2 or len(set(scenario.priority_sites)) != 2:
        raise ValueError("Exactly two distinct priority sites are required.")
    if any(not isinstance(i, Integral) or isinstance(i, bool) or not 0 <= i < scenario.n
           for i in scenario.priority_sites):
        raise ValueError("Priority-site indices must refer to existing shelters.")
    if any(len(point) != 2 or not all(_finite_number(x) for x in point)
           for point in scenario.coordinates):
        raise ValueError("Coordinates must contain finite x,y pairs.")
    seen = set()
    for item in scenario.overlaps:
        if len(item) != 3:
            raise ValueError("Each overlap must contain i, j, and its score.")
        i, j, r = item
        if (not isinstance(i, Integral) or not isinstance(j, Integral)
                or isinstance(i, bool) or isinstance(j, bool)
                or not 0 <= i < j < scenario.n):
            raise ValueError("Overlap indices must satisfy 0 <= i < j < n.")
        if (i, j) in seen or not _finite_number(r) or r < 0:
            raise ValueError("Overlap penalties must be finite, nonnegative, and unique.")
        seen.add((i, j))


def _validate_bits(bits: Sequence[int], n: int) -> None:
    if len(bits) != n or any(bit not in (0, 1) for bit in bits):
        raise ValueError(f"Expected {n} binary decisions in shelter-index order.")


def utility(bits: Sequence[int], scenario: Scenario, weight: float) -> float:
    _validate_bits(bits, scenario.n)
    linear = sum((b + weight*v)*x for b, v, x in zip(scenario.benefit, scenario.priority, bits))
    overlap = scenario.rho * sum(r*bits[i]*bits[j] for i, j, r in scenario.overlaps)
    return float(linear - overlap)


def feasible(bits: Sequence[int], scenario: Scenario, k: int) -> bool:
    _validate_bits(bits, scenario.n)
    return sum(bits) == k and any(bits[i] for i in scenario.priority_sites)


def penalty_bound(scenario: Scenario, weight: float) -> float:
    validate_inputs(scenario, weight, 1)
    return float(1 + sum(abs(b + weight*v) for b, v in zip(scenario.benefit, scenario.priority))
                 + scenario.rho * sum(abs(r) for _, _, r in scenario.overlaps))


def cost(bits: Sequence[int], scenario: Scenario, weight: float, k: int) -> float:
    validate_inputs(scenario, weight, k)
    _validate_bits(bits, scenario.n)
    a, b = scenario.priority_sites
    violation = (sum(bits) - k)**2 + (1-bits[a])*(1-bits[b])
    return -utility(bits, scenario, weight) + penalty_bound(scenario, weight)*violation


def bits_from_index(index: int, n: int) -> tuple[int, ...]:
    """Qubit i is shelter i; statevector index has qubit zero as its low bit."""
    if not isinstance(n, Integral) or n < 1:
        raise ValueError("The number of bits must be a positive integer.")
    if not isinstance(index, Integral) or isinstance(index, bool) or not 0 <= index < 2**n:
        raise ValueError("Statevector index is outside the n-qubit basis.")
    return tuple((int(index) >> i) & 1 for i in range(n))


def bits_from_count_key(key: str, n: int) -> tuple[int, ...]:
    """Decode Qiskit's MSB-left count key (allowing classical-register spaces).

    Circuits must measure logical qubit i into classical bit i. Transpilation
    preserves those classical destinations, even after physical qubit routing.
    """
    if not isinstance(key, str):
        raise ValueError("A count key must be a binary string.")
    compact = key.replace(" ", "")
    if len(compact) != n or any(char not in "01" for char in compact):
        raise ValueError(f"Expected a {n}-bit Qiskit count key.")
    return tuple(int(char) for char in reversed(compact))


def count_key(bits: Sequence[int]) -> str:
    """Encode shelter-index-ordered decisions as a Qiskit MSB-left count key."""
    _validate_bits(bits, len(bits))
    if not len(bits):
        raise ValueError("At least one bit is required.")
    return "".join(str(int(bit)) for bit in reversed(bits))


def _record(bits: Sequence[int], scenario: Scenario, weight: float) -> dict:
    return {"bits": list(bits), "bitstring": count_key(bits), "utility": utility(bits, scenario, weight)}


def enumerate_feasible(scenario: Scenario, weight: float, k: int) -> list[dict]:
    validate_inputs(scenario, weight, k)
    records = []
    for chosen in combinations(range(scenario.n), k):
        bits = tuple(int(i in chosen) for i in range(scenario.n))
        if feasible(bits, scenario, k):
            records.append(_record(bits, scenario, weight))
    return sorted(records, key=lambda record: int(record["bitstring"], 2))


def exact_solution(scenario: Scenario, weight: float, k: int) -> dict:
    start = perf_counter()
    records = enumerate_feasible(scenario, weight, k)
    best = max(record["utility"] for record in records)
    return {
        "utility": best,
        "optima": [record for record in records if math.isclose(record["utility"], best, rel_tol=1e-12, abs_tol=1e-9)],
        "feasible_count": len(records),
        "elapsed_seconds": perf_counter() - start,
    }


@dataclass(frozen=True)
class Hamiltonian:
    """E = scale * diagonal(normalized_operator) + offset, in utility units.

    Identity terms are represented only by offset. The positive scale is the
    largest absolute nonconstant Pauli coefficient (or 1 for a zero operator).
    Scaling and dropping the offset do not change the ground-state assignments.
    """

    operator: SparsePauliOp
    offset: float
    scale: float

    @property
    def normalized_operator(self) -> SparsePauliOp:
        return self.operator / self.scale


def build_hamiltonian(scenario: Scenario, weight: float, k: int) -> Hamiltonian:
    validate_inputs(scenario, weight, k)
    n = scenario.n
    penalty = penalty_bound(scenario, weight)
    # x_i^2 = x_i: expand the quadratic cardinality and priority constraints.
    linear = np.asarray([-(b + weight*v) + penalty*(1-2*k)
                         for b, v in zip(scenario.benefit, scenario.priority)], dtype=float)
    quadratic = {(i, j): 2*penalty for i, j in combinations(range(n), 2)}
    for i, j, r in scenario.overlaps:
        quadratic[(i, j)] += scenario.rho*r
    a, b = scenario.priority_sites
    linear[a] -= penalty
    linear[b] -= penalty
    quadratic[tuple(sorted((a, b)))] += penalty
    offset = penalty*(k*k + 1) + sum(linear)/2 + sum(quadratic.values())/4
    z = -linear/2
    for (i, j), value in quadratic.items():
        z[i] -= value/4
        z[j] -= value/4

    terms = []
    for i, value in enumerate(z):
        if value:
            terms.append(("Z", [i], float(value)))
    for (i, j), value in quadratic.items():
        if value:
            terms.append(("ZZ", [i, j], float(value/4)))
    operator = SparsePauliOp.from_sparse_list(terms, num_qubits=n)
    scale = max((abs(float(coefficient.real)) for coefficient in operator.coeffs), default=0) or 1.0
    return Hamiltonian(operator=operator, offset=float(offset), scale=float(scale))
