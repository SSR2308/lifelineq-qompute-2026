# References and attribution

Official documentation was checked on October 11, 2026. The installed, tested dependency versions are recorded in the repository dependency files and every experiment artifact; documentation labeled “latest” can change.

| Source | Use in LifelineQ |
|---|---|
| [Qompute 2026 official challenge](https://github.com/sandraalhames/Qompute-2026) | Track 2 scope, Qiskit requirement, submission format and deadline. |
| [Farhi, Goldstone and Gutmann (2014), A Quantum Approximate Optimization Algorithm](https://arxiv.org/abs/1411.4028) | Original QAOA research; LifelineQ does not claim to invent the algorithm. |
| [IBM QAOA tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/quantum-approximate-optimization-algorithm) | Conceptual workflow: encode cost, construct ansatz, tune parameters and evaluate samples. |
| [Qiskit `qaoa_ansatz` API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.qaoa_ansatz) | Circuit function used by this implementation. |
| [Qiskit `SparsePauliOp` API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.SparsePauliOp) | Hamiltonian representation. |
| [Qiskit `Statevector` API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Statevector) | Ideal state simulation during parameter fitting and routing verification. |
| [Qiskit bit ordering](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering) | Relationship between shelter indices, qubits, integers and printed count strings. |
| [Qiskit transpilation with pass managers](https://quantum.cloud.ibm.com/docs/en/guides/transpile-with-pass-managers) | Hardware basis translation, layout, routing and reproducible compiler settings. |
| [Aer: Building noise models](https://qiskit.github.io/qiskit-aer/tutorials/3_building_noise_models.html) | Explicit gate and readout channels. |
| [Aer `depolarizing_error` API](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.depolarizing_error.html) | Exact meaning of the depolarizing parameter used in noise presets. |
| [Aer `AerSimulator` API](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html) | CPU density-matrix execution and count sampling. |
| [SciPy COBYLA API](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-cobyla.html) | Derivative-free classical optimizer and objective-evaluation budget. |
| [IBM error mitigation and suppression guide](https://quantum.cloud.ibm.com/docs/en/guides/error-mitigation-and-suppression-techniques) | Terminology: compilation is suppression; sample filtering is classical post-processing. |
| [NIST: Confidence intervals for proportions](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) | Wilson intervals for finite-shot feasibility and exact-optimum probabilities. |

The scenario, names, coordinates, scores, overlaps, application code and tests are original to this prototype. The numerical base fixture and mathematical objective were supplied in the project brief. No challenge starter notebook was copied. Dependencies retain their own licenses. If starter code is added later, record its source, changes and license here and preserve its notices.

The official repository specifies a 5–10 minute video and a team GitHub repository, and gives the deadline as **October 14, 2026, 11:59 PM “PST.”** The quoted zone is the organizer's wording. Los Angeles normally observes daylight time on that date; do not rely on interpreting that ambiguity for an extra hour. Target recording and submission earlier on October 14 and check the official submission page before submitting.
