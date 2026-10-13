# LifelineQ: 7-minute presentation outline

Target duration: 7 minutes, within the official 5–10 minute submission window. Record using the checked-in measured results and show their provenance. Keep one quick live run as an optional demonstration, not a dependency for the recording. The README contains the measured numbers to quote.

## Measured talking points for this recording

Use the base scenario, lambda=1, K=3. Each mean below summarizes five optimization/evaluation seeds with 2,048 shots per arm; use the plots to show their variability.

- Ideal feasibility rose from **22.49% at p=1 to 32.97% at p=2**, but ordinary high-noise feasibility was **15.99% and 14.46%**, respectively. More layers helped the ideal circuit here and added noise exposure.
- At p=2, compiler search reduced mean two-qubit gates **211.4 → 196.8**. Under high noise, the paired feasibility change was **+0.93 ± 0.74 percentage points** across seeds. The ± is seed standard deviation, not a confidence interval.
- Give the counterexample too: at p=1 under low noise, compiler search reduced feasibility by **0.54 ± 0.65 points** despite fewer two-qubit gates. Its quality effect was mixed.
- Uniform feasible random sampling achieved **16.83% per-shot exact-optimum probability**, versus **5.37% for ideal p=2**; greedy reached the optimum in all nine scenario/lambda cases. Classical methods remain the sensible choice here.
- All **630 quantum executions** saw an optimum at least once; that does not mean a reliable distribution. Only **37/90 selected fits** reported optimizer convergence. These failures to converge were retained.
- The p=2 noise result repeated at lambda=1 in the predefined demand shift (**39.61% ideal → 14.67% ordinary/high**) and overlap shift (**32.36% → 14.40%**).
- Verification: **89 tests passed**, including the full 256-assignment encoding checks; saved and live app paths were also exercised in a browser. Maximum noiseless routed probability error was **1.42e-15**.

The [measurement report](../results/REPORT.md) is the source for these numbers. Do not describe the table's conditional regret as a statistic of all raw shots; it excludes infeasible assignments.

| Time | Screen / action | Message to deliver |
|---|---|---|
| 0:00–0:45 | Title and synthetic city diagram; three units, eight shelters | “A blackout leaves eight fictional shelters competing for three backup units. At least one of two priority shelters must receive power. Who should get the units, and how much should we trust a noisy quantum answer?” Explain that scores are synthetic proxies. |
| 0:45–1:35 | Explore priorities: change lambda from 0 to 1 to 2; show exact allocation | Benefit, priority and overlap are separate inputs. At lambda 0, 1 and 2 the optimum utility is 21, 36 and 59 in the respective objectives. Name the selected sites and the ones displaced. Utility numbers across different lambda are not the same objective. Show all ties at lambda 1. |
| 1:35–2:30 | Expand the objective; show one assignment and its constraints | Eight binary choices become eight qubits. Penalties make any infeasible global minimum more expensive than a feasible assignment. A large penalty does not guarantee every QAOA sample obeys the rules. Explain `x=(1−Z)/2` and the exhaustive 256-assignment verification. |
| 2:30–3:25 | Show QAOA fit settings and raw counts | Cost and mixer layers interfere to change sampling probabilities. A classical optimizer tunes two angles per layer using ideal statevector energy. The exact solution is reserved for evaluation. Distinguish the most frequent raw sample from the best feasible observed sample. |
| 3:25–4:35 | Stress-test quantum noise; fix lambda, p and seed, change zero/low/high | Use the recorded outcomes, including disappointments. Read feasibility and exact-optimum probability with shot intervals, then conditional regret. Show the classical comparators; an optimum found once among thousands of samples is insufficient evidence. |
| 4:35–5:35 | Ordinary vs searched compilation; show two-qubit gates, depth and search time | Same logical circuit, fitted angles, topology, noise and shot budget. Search candidates were selected before noisy evaluation, using gates then depth. State the measured effect and its limits; fewer gates alone do not establish better allocations. This is compilation-based error suppression. |
| 5:35–6:20 | Across-seed and perturbed-scenario plots | Five independent fits per lambda/depth; separate shot intervals from optimizer-seed variation. Show both predefined perturbations. Explain whether the observed conclusion persisted and where it did not. No forced monotonic noise story and no hidden failures. |
| 6:20–7:00 | Limitations, repository and conclusion | Laptop simulation, eight shelters, no speedup or emergency-readiness claim. Human stakeholders must choose priorities and review exclusions. “Our contribution is an auditable allocation experiment: a visible objective, verified encoding and measured failure modes.” |

## Recording checklist

- Run `python -m pytest -q`; retain the output and source/version metadata with the results.
- Launch `streamlit run app.py`; use saved results whose full configuration matches the displayed controls.
- Keep the synthetic label visible. Introduce `p` as QAOA layers, distinct from transpiled depth.
- Read percentage points as percentage points. Do not call a best-observed success a success probability.
- Quote actual measured comparison numbers from the README and show seed variation, including unfavorable cases.
- Mention all tied optima; a deterministic tie choice is a display convenience, not an ethical ranking.
- Demonstrate JSON/CSV downloads and show exact setup commands in the repository.
- Verify video audio, legibility, runtime and repository accessibility before submission.
- Target recording and submission earlier on October 14, 2026. The organizer's deadline wording is 11:59 PM “PST”; do not depend on an interpretation of the daylight-time ambiguity.

## Short answers to likely judge questions

**Why use quantum computing here?** To investigate how a verifiable quantum optimization workflow behaves under allocation constraints and controlled noise. Classical enumeration is better suited to this tiny instance.

**Where is the originality?** In the auditable allocation model, explicit priority tradeoff, controlled compilation experiment, full-distribution metrics and reproducible interface; QAOA itself is established work.

**How do you know the output is correct?** The classical formulation and Hamiltonian agree on all 256 assignments. Every sampled candidate is decoded, checked for feasibility and compared with all exact tied optima. Routing and zero-noise behavior are separately tested.

**Why does the quantum method fail sometimes?** Shallow circuits, a fixed optimization budget, large penalties, routing and noise all limit the distribution. Those failures are part of the measured result.

**What is the societal risk?** A formally optimal result can still encode poor priorities, omit important needs or exclude communities. Lambda and the designated sites are choices that require accountable human review.

See [DEFENSE.md](DEFENSE.md) for fuller explanations and [REFERENCES.md](REFERENCES.md) for sources.
