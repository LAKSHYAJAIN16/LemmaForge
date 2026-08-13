"""
tactic_search.py

Stand-in for a learned low-level proof policy (pi_L). A real system would
use something like Graph2Tac or an LLM tactic predictor here; this project's
novelty is the high-level invent-vs-continue decision (pi_H) and the
reusable-library reward, so pi_L is deliberately kept simple and legible:
a bounded portfolio of tactic sequences, tried via Coq's own `first [...]`
backtracking combinator so the whole portfolio is checked in a SINGLE real
kernel call.

This is honestly a heuristic, not a neural policy -- documented as a known
scope limitation in the paper.
"""

from coq_runner import verify_snippet, VerifyResult


def _portfolio_alternatives(lemma_names):
    """
    Build a list of tactic-sequence strings to try, one of which will
    hopefully close a base or inductive-step subgoal after `simpl`.
    Conditioned on whichever helper lemmas are currently in the library,
    so this genuinely gets stronger as the agent invents more lemmas.
    """
    alts = [
        "reflexivity",
        "simpl; reflexivity",
        "simpl; auto",
        "simpl; congruence",
    ]
    # Try IH directly (works for the classic step-case pattern)
    alts += [
        "simpl; rewrite IH; reflexivity",
        "simpl; rewrite IH; auto",
        "simpl; rewrite <- IH; reflexivity",
    ]
    # Try each currently-known lemma, forwards and backwards, alone and
    # combined with the induction hypothesis.
    for lem in lemma_names:
        alts += [
            f"simpl; rewrite {lem}; reflexivity",
            f"simpl; rewrite <- {lem}; reflexivity",
            f"simpl; rewrite IH; rewrite {lem}; reflexivity",
            f"simpl; rewrite IH; rewrite <- {lem}; reflexivity",
            f"simpl; rewrite {lem}; rewrite IH; reflexivity",
            f"rewrite {lem}; reflexivity",
        ]
    return alts


def build_script(name, statement, induction_var, lemma_names):
    """
    Builds a full Lemma/Proof/Qed block. If induction_var is None, we skip
    induction and just throw the portfolio directly at the goal (covers
    theorems that reduce definitionally, like T2 in the toy corpus).
    """
    alts = _portfolio_alternatives(lemma_names)
    combinator = "first [ " + " | ".join(alts) + " ]"

    if induction_var is None:
        proof = f"Proof.\n  {combinator}.\nQed."
    else:
        v = induction_var
        proof = (
            f"Proof.\n"
            f"  induction {v} as [| {v}' IH].\n"
            f"  - {combinator}.\n"
            f"  - {combinator}.\n"
            f"Qed."
        )

    return f"Lemma {name} : {statement}.\n{proof}\n"


def attempt(name, statement, induction_var, library_lemmas_src, lemma_names, timeout_s=10.0) -> VerifyResult:
    """
    One real, kernel-verified attempt to prove `statement` (named `name`)
    given the current library. This is pi_L's entire job: try the
    portfolio, ask the actual Coq kernel, report back pass/fail.
    """
    src = build_script(name, statement, induction_var, lemma_names)
    return verify_snippet(library_lemmas_src, src, timeout_s=timeout_s)