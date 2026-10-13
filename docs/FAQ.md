# LifelineQ FAQ

Short answers to the questions we expect about the project. The README has the full method and numbers.

## What problem are we solving?

A heat wave knocks out power to eight cooling shelters in a fictional city, and there are three backup generators. We pick exactly three shelters, and at least one must be a priority shelter (Grove Haven or Harbor Hall). Each shelter has a benefit score and a priority score, and two shelters that serve the same area lose points if both are picked. The scores are made up. They stand in for decisions that real emergency managers and communities would have to make.

## Why use quantum computing if a laptop solves it instantly?

That's the point of keeping it small. With eight shelters there are only 256 possible picks, so we can check every quantum answer against the exact best answer. That lets us measure how much to trust the quantum circuit, rather than guess. We don't claim a speedup or quantum advantage, and at this size classical methods are the right tool.

## Is this running on a real quantum computer?

No. Qiskit builds the quantum circuit and Qiskit Aer simulates it on a laptop, including the random measurement results a real device would give. The noise levels are stress tests we chose, not a model of a specific IBM machine.

## How does the problem become a quantum circuit?

Each shelter is one qubit: measuring 1 means it gets a generator. The score and the rules become an energy function, where breaking a rule adds a penalty larger than any possible score difference, so every rule-breaking answer is worse than every valid one. We converted that into the form QAOA needs and checked that it matches the original score for all 256 possible answers.

## What does QAOA actually do?

It alternates two steps. One nudges the circuit toward low-energy (high-score) answers, and the other mixes answers together. Each layer has two angles, and a classical optimizer tunes them. The optimizer never sees the exact best answer; we only use that to grade the results.

## Why does the circuit give answers that break the rules?

The penalty makes rule-breaking answers worse, but a shallow circuit doesn't reliably avoid them, and noise flips bits too. So we report how often the answers are valid, not just the best one we happened to see.

## What did you find?

- **The best answer depends on a value choice.** Changing the priority weight λ changes who gets power. At λ = 1, six different picks tie for the best score.
- **Two shelters are always left out.** Birch Center and Cedar Library never get power at any weight from 0 to 2.
- **Simple classical methods beat QAOA here.** Without noise, QAOA hit a best answer about 3.6% of the time with one layer and 5.4% with two. Picking a random valid answer did that about 16.8% of the time, and a greedy method found the exact best answer in all nine scenario and weight combinations we tested.
- **Noise erased the gain from a deeper circuit.** Valid answers fell from 22% to 16% (one layer) and from 33% to 14% (two layers) between no noise and high noise.
- **Optimized compiling cut gates but didn't reliably improve answers.** It removed two-qubit gates in 24 of 30 runs, but the effect on answer quality was small and went both ways.

## Does a higher λ make the result fair?

No. λ is a dial that says whose needs count more. It shows the trade-off; it doesn't settle it. Real choices about priorities belong to accountable officials and the affected communities.

## How do you know the results are right?

89 automated tests check the encoding, the bit order, the scoring, and the app. Every saved result records the exact code version and library versions that produced it, and the app only shows a saved result when those match.

## What would come next?

Larger instances, circuits that only produce valid answers by design, runs on real IBM hardware, and real-world inputs. A real allocation tool would also need community input, an appeals process and a backup plan that doesn't depend on an algorithm.
