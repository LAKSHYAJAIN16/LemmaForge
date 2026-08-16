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

from rocq_runner import verify_snippet, VerifyResult

# Bound on how many known lemmas we'll generate pairwise chained-rewrite
# combos for. Combos grow O(n^2 * 4 directions * 2 simpl-variants), so this
# keeps a single `first [...]` block from blowing up as the library grows.
_MAX_LEMMAS_FOR_PAIR_COMBOS = 4


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
    ]
    # Try IH directly (works for the classic step-case pattern).
    # `auto`/`congruence` are deliberately not used here: `auto` can leave an
    # unresolved shelved existential goal while still reporting the bracket
    # as a success inside `first [...]` (verified against the real kernel --
    # the failure only surfaces later as a spurious "incomplete proof" at
    # Qed, not at the tactic itself), and both undercut the project's point
    # that closing a goal has to go through real induction/rewriting rather
    # than a generic decision procedure.
    alts += [
        "simpl; rewrite IH; reflexivity",
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
    # Chained two-lemma combos: some goals (e.g. a target theorem that
    # reduces via one invented lemma into the shape of another) only close
    # after rewriting with two *different* lemmas in sequence, in some
    # combination of directions. This has no IH involved, so it also covers
    # non-inductive targets attacked straight with the combinator.
    if len(lemma_names) <= _MAX_LEMMAS_FOR_PAIR_COMBOS:
        for a in lemma_names:
            for b in lemma_names:
                if a == b:
                    continue
                for a_dir in ("", "<- "):
                    for b_dir in ("", "<- "):
                        step = f"rewrite {a_dir}{a}; rewrite {b_dir}{b}; reflexivity"
                        alts.append(step)
                        alts.append(f"simpl; {step}")
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
        proof = f"Proof.\n  intros.\n  {combinator}.\nQed."
    else:
        v = induction_var
        # `intros.` first, so any variables quantified after `v` (e.g. `m` in
        # `forall n m, ...`) are already fixed in context before induction --
        # otherwise `induction` generalizes them into a forall-quantified IH,
        # and rewriting with that IH under the still-bound goal quantifier
        # picks up the wrong instantiation (verified against the real kernel).
        proof = (
            f"Proof.\n"
            f"  intros.\n"
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