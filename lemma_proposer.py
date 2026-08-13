"""
lemma_proposer.py

This is the actually-interesting piece: given a structurally recursive
binary nat function `f` (recursing on its first argument, wrapping the
recursive call in S in the step case, as in `myadd`), propose the two
canonical generalized helper-lemma *statements* that this recursion pattern
tends to need:

  UNIT  : forall n, f n 0 = n            (identity law, needed when a proof
                                            gets stuck on `f n 0` vs `n`)
  SWAP  : forall n m, S (f n m) = f n (S m)   (commuting S past f, needed
                                            when a proof gets stuck matching
                                            `S (f n' m)` against `f n' (S m)`)

This mirrors the real, well-known Software Foundations pattern (plus_n_O,
plus_n_Sm feeding into plus_comm) -- it is a genuine, if narrow, piece of
theory-exploration-style generalization, not hardcoded to the theorem being
proved. Each candidate is then handed to tactic_search to actually attempt
a kernel-verified proof, recursively reusing the same portfolio machinery.

Scope limitation (documented honestly, see paper): this only covers ONE
recursion shape. A production system would replace this whole module with
a learned generalization model operating on the real Coq proof-state AST
(e.g. via serapi), not a hand-coded pattern for one function shape.
"""

from dataclasses import dataclass
from typing import Optional
import tactic_search
from coq_runner import VerifyResult


@dataclass
class LemmaCandidate:
    kind: str          # "UNIT" or "SWAP"
    name: str
    statement: str
    induction_var: Optional[str]


def propose_candidates(fn_name: str, counter: int):
    """Generate both canonical candidates for function `fn_name`."""
    unit = LemmaCandidate(
        kind="UNIT",
        name=f"{fn_name}_n_0_v{counter}",
        statement=f"forall n : nat, {fn_name} n 0 = n",
        induction_var="n",
    )
    swap = LemmaCandidate(
        kind="SWAP",
        name=f"{fn_name}_n_Sm_v{counter}",
        statement=f"forall n m : nat, S ({fn_name} n m) = {fn_name} n (S m)",
        induction_var="n",
    )
    return [unit, swap]


def try_prove_candidate(cand: LemmaCandidate, library_lemmas_src: str, lemma_names, timeout_s=10.0) -> VerifyResult:
    return tactic_search.attempt(
        cand.name, cand.statement, cand.induction_var,
        library_lemmas_src, lemma_names, timeout_s=timeout_s,
    )