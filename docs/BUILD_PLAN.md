# Build milestones

Completed October 12, 2026. The final suite passed 89 tests. Recorded evidence
contains the quick run and 90 benchmark/robustness fits (630 quantum executions);
the browser loaded saved evidence and completed a small live experiment.
See `results/REPORT.md` for the measured findings and `docs/PRESENTATION.md` for
the recording outline. Source changes invalidate old saved evidence.

1. Verify every eight-bit assignment against the cost Hamiltonian; enumerate all
   feasible allocations and ties; run Qiskit QAOA with actual sampled counts.
2. Freeze fitted parameters and compare ordinary and searched compilation on a
   synthetic ring, with three explicit Aer noise presets and recorded overhead.
3. Build a Streamlit demo that labels saved/live results and invalidates stale
   scenario, settings, source, and dependency combinations.
4. Run the bounded benchmark and predefined perturbations, record failures and
   uncertainties, and finish reproducibility and presentation documentation.

Existing empty `main.py` and the Python 3.10 environment are preserved. Hardware,
custom mixers, mitigation add-ons, deployment, and real-city data are deferred.
