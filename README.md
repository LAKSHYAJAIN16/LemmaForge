# lemma-forge

A small hierarchical-RL environment for theorem proving with lemma invention,
kernel-verified end to end by a real Rocq (Coq) compiler subprocess — nothing
here is ever claimed "proved" without an actual `rocq`/`coqc` run succeeding.

```
                          TARGET THEOREM
                                |
                                v
                       +-----------------+
                       | High-Level Agent|
                       |      pi_H       |
                       +--------+--------+
                                |
                    +-----------+-----------+
                    |                       |
                    v                       v
             Continue Search           Invent Lemma
                    |                       |
                    v                       v
             +-------------+         +-------------+
             | Proof Agent |         |    Lemma    |
             |    pi_L     |         |  Generator  |
             +------+------+         +------+------+
                    |                       |
                    |                       v
                    |                 Candidate Lemma
                    |                       |
                    |                       v
                    |                 Lower-Level
                    |                 Proof Search
                    |                       |
                    |                       v
                    |                  Rocq Kernel
                    |                       |
                    |                  Verified?
                    |                       |
                    +-----------+-----------+
                                |
                                v
                       Updated Environment
                                |
                                v
                        Continue Proof
```

## Component map

| Diagram piece            | File               | What it actually is |
|---------------------------|--------------------|----------------------|
| High-Level Agent (π_H)    | `env.py`, `agent.py` | `LemmaDiscoveryEnv` exposes `DIRECT` / `INVENT_UNIT` / `INVENT_SWAP` / `GIVE_UP`; `QLearningAgent` is a tabular Q-learner over a small discretized state |
| Proof Agent (π_L)         | `tactic_search.py` | A bounded portfolio of tactic sequences tried via Rocq's `first [...]` backtracking combinator — one real kernel call checks the whole portfolio |
| Lemma Generator           | `lemma_proposer.py` | Proposes the two canonical generalized helper-lemma shapes for a structurally-recursive `nat -> nat -> nat` function: `UNIT` (`f n 0 = n`) and `SWAP` (`S (f n m) = f n (S m)`) |
| Rocq Kernel                | `rocq_runner.py`   | Writes a real `.v` file (preamble + growing lemma library + candidate) and compiles it with `rocq compile` / `coqc` |
| Target corpus              | `dataset.json`, `preamble.v` | The function under test (`myadd`, a hand-rolled `+` that tactics like `lia` can't see through) and the target theorems |

## Setup

Requires Python 3.9+ and a Rocq or Coq install.

`rocq_runner.py` looks for the kernel in this order:
1. `ROCQ_BIN` env var — explicit path to a `rocq` or `coqc` executable
2. `rocq` on `PATH`
3. `coqc` on `PATH`
4. Common Windows install locations (`C:\Rocq-Platform*\bin\rocq.exe`, etc.)

If none of those find it, set `ROCQ_BIN` explicitly, e.g.:

```
$env:ROCQ_BIN = "C:\Rocq-Platform~9.0~2025.08\bin\rocq.exe"
```

Install test dependencies:

```
pip install -r requirements.txt
```

## Running

Train π_H for N episodes and print the learned greedy rollout:

```
python train.py --episodes 50
```

Each episode is one real pass through `dataset.json`'s target theorems (T1 then
T2), sharing one growing verified-lemma library across both — this is what
lets a converged policy solve T2 with a single free `DIRECT` call by reusing
lemmas it invented while working on T1.

Run the test suite (mix of fast unit tests and real kernel-integration tests):

```
pytest
```

## Scope and honest limitations

- `lemma_proposer.py` only knows one recursion shape (mirrors the classic
  `plus_n_O` / `plus_n_Sm` → `plus_comm` pattern from Software Foundations). A
  production system would replace it with a learned generalization model over
  the real proof-state AST (e.g. via SerAPI), not a hand-coded pattern.
- `tactic_search.py` is a heuristic fixed portfolio, not a learned tactic
  policy — a real π_L would look more like Graph2Tac or an LLM tactic
  predictor.
- `agent.py` is tabular Q-learning over a hand-discretized state — fine for
  this corpus's tiny state space, but doesn't scale past it without a
  function-approximated policy.
