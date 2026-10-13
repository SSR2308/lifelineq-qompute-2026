# Explain and defend LifelineQ

## What problem are we actually solving?

There are eight fictional cooling shelters and three identical compatible backup units. One unit powers one shelter for a fixed period. We choose exactly three shelters and must include at least one of designated priority sites 6 or 7. The utility is a transparent proxy, not a measurement of lives saved or electricity delivered.

The benefit score, priority score and overlap penalty are assumptions. They stand in for a difficult conversation about allocation; they do not settle that conversation. The project author chose the priority sites for this synthetic demonstration. In a real process, accountable emergency managers and affected communities would have to choose and validate those inputs, review exclusions and retain authority over allocations. Unselected shelters receive no backup unit in this model; their needs do not disappear.

## Why call it quantum if it runs on a laptop?

Qiskit constructs and simulates a quantum circuit using eight qubits. We run a real QAOA circuit simulation and collect actual Aer measurement counts. The laptop emulates that circuit; no quantum processor was used. This is a reproducible quantum-algorithm experiment, not evidence of a faster computer.

## What does one qubit mean?

The measured bit on qubit `i` means whether shelter `i` is selected. Eight qubits represent 256 possible assignments. The initial `|+>` state gives all assignments equal amplitude. A measurement returns one assignment, not an accessible list of every answer at once. Interference changes their probabilities during QAOA.

## What is a Hamiltonian here?

It is the circuit-compatible representation of the allocation cost. The Pauli `Z` eigenvalue is +1 for bit 0 and −1 for bit 1, so `x=(1−Z)/2`. The resulting Hamiltonian has single-qubit `Z` and two-qubit `ZZ` terms plus a constant offset. Its computational-basis energy equals the classical penalized cost. All 256 assignments are checked to catch sign, offset, scaling and bit-order mistakes.

## What does QAOA do?

Each layer first changes phases according to cost, then mixes amplitudes using X rotations. Each layer has two tunable angles. A classical SciPy optimizer adjusts those angles to lower expected energy on an ideal Qiskit statevector. `p=1` and `p=2` mean one and two alternating layers, not physical circuit depth. Compiling a layer into local gates can make it much deeper.

The exact solution is used for evaluation, not for preparing the state, inserting an optimal bitstring or choosing fitted angles. The optimizer sees only expected penalized energy. We select the best fit from a fixed number of random starts using that energy before noise evaluation.

## Why can a quantum sample violate a constraint?

The penalty makes infeasible global minima unfavorable. It does not force every sample of a shallow approximate circuit to be feasible. The usual X mixer explores infeasible assignments, and noise can also change bits. We therefore report the feasible fraction of all shots, not just the best surviving answer.

## How do we know the penalty is large enough?

Write `s_i=b_i+lambda*v_i` and `B=sum |s_i| + rho*sum |r_ij|`. Between any two binary assignments each monomial changes by at most one, so the utility difference is no more than `B`. Any violated constraint contributes at least `P=1+B`. Consequently every infeasible assignment has higher penalized energy than every feasible assignment. This proof assumes the validated nonnegative `lambda` and `rho`, binary variables and existence of a feasible assignment. A large conservative penalty can still make optimization difficult by emphasizing feasibility over differences between good feasible solutions.

## Does increasing lambda make the answer fair?

It gives more influence to a chosen priority score. It does not create an objective definition of fairness. The hard priority rule and the soft priority weight are different: at least one designated priority shelter must always be selected, while lambda controls a tradeoff among all scores. Report who gains and who loses when lambda changes, and do not compare utility numbers across different lambda values as if their units were unchanged.

## Why enumerate if we want a quantum algorithm?

At eight bits exact enumeration is cheap and is the reference answer. It reveals every tied optimum. The reference allocator enumerates 36 feasible combinations; separate encoding tests check all 256 assignments. We intentionally use a small, fully checkable instance. The greedy allocator and uniform feasible sampler test whether the quantum distribution offers anything beyond simple classical choices. This project establishes no quantum advantage, and the classical methods are the practical choice at this size.

The feasible-random baseline samples uniformly from the enumerated feasible set with the same stated shot budget. This uses a classical feasibility oracle and is not a scalable random-generation algorithm. It does not use utility to bias sampling. Its frequent discovery of an optimum over thousands of shots is a reminder that “we saw an optimum once” is weak evidence.

## What is a fair noise comparison?

Fit once for each scenario, lambda, QAOA layer count and optimization seed. Freeze those angles for both compiler strategies and all three noise presets. Use the same synthetic coupling graph, basis, noise channels and shots. Compile before evaluating noise and choose the searched circuit using gate count and depth only. No noisy score decides the compiler winner.

The ring is a synthetic hardware constraint, not a model calibrated to an IBM device. Depolarizing and readout channels are controlled stress tests. They omit drift, coherent errors, leakage, detailed timing, crosstalk and hardware-specific calibration. A density-matrix simulation evolves the specified noisy channel and Aer samples counts from it.

## What did compilation improve?

Use the measured table in the README. Reducing two-qubit gates reduces one source of exposure to the modeled noise, but does not prove better allocations. The compiler search can tie the ordinary circuit, and probabilities can fluctuate across evaluation shots. The search includes the ordinary candidate and is scored first by two-qubit gates, then by depth. If it ties, say so. Report the extra compilation time too.

In the measured base lambda=1 results, p=2 search reduced mean two-qubit gates from 211.4 to 196.8; high-noise feasible probability improved by a paired 0.93 ± 0.74 percentage points across five seeds. But p=1 low-noise feasibility fell by 0.54 ± 0.65 points despite gate savings. The correct conclusion is a measured gate reduction with mixed allocation effects, not a universal quality improvement. Those ± values describe seed standard deviation.

Call this **error suppression through compilation**. Discarding infeasible outcomes for a conditional statistic is **classical post-processing**, not quantum error correction. It also discards information, so report the original denominator and feasibility rate.

## How do we avoid reversed shelter indices after routing?

Qiskit count strings put classical bit 0 on the right. String `01001001` means sites 0, 3 and 6. Measurements attach logical qubit `i` to classical bit `i` before compilation. Routing may move quantum states to physical wires, but those classical destinations preserve the intended meaning. Tests independently decode routed probabilities and check noiseless equivalence.

## Which performance metric matters?

Read the full distribution together:

- Feasible rate: feasible shots divided by all shots.
- Exact-optimum probability: shots at any tied exact optimum divided by all shots.
- Conditional mean utility: count-weighted utility among feasible shots only.
- Conditional regret: exact feasible optimum minus that conditional mean, for the same inputs.
- Best feasible observed regret: a useful candidate diagnostic, strongly affected by shot budget.
- Most frequent raw sample: displayed even if infeasible; never relabeled as the best answer.
- No-feasible failure: zero feasible shots; conditional metrics and best feasible allocation are undefined.

The 95% Wilson intervals describe finite-shot uncertainty for each fixed run. Conditional utility standard errors describe only its finite feasible-shot sample. Variation across the five independent optimizer seeds is separately summarized by sample standard deviation. Neither is uncertainty in the social scores, a guarantee about a single future run, or a confidence interval for real-world emergency outcomes.

## What would be needed next?

First investigate better classical comparators, tighter penalties and constraint-preserving quantum mixers on additional prespecified instances. A hardware study would need recorded calibration and queue/runtime costs. Any real allocation system would need engineering validation, demand and travel models, stakeholder governance, transparent appeals and a tested operational fallback. Those are outside this demonstrator.

The strongest defensible claim is: **we built and verified a small allocation experiment that makes priorities, quantum failures and compilation costs visible.**
