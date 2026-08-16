"""
env.py

The actual hierarchical-RL environment. One episode = one pass through the
corpus (T1 then T2, sharing ONE growing lemma library across both theorems,
which is what lets us measure cross-theorem reuse). At each step, pi_H
picks one of:

    DIRECT        - try the current portfolio on the *target theorem* as-is
    INVENT_UNIT   - propose+attempt the UNIT-shaped helper lemma
    INVENT_SWAP   - propose+attempt the SWAP-shaped helper lemma
    GIVE_UP       - end the episode early for this theorem

Reward:
    -1.0  per real kernel call spent (cost)
    +10.0 for closing the target theorem
    -5.0  for GIVE_UP without having closed the theorem
    -1.0  extra penalty for inventing a lemma that fails to verify
     0.0  extra for inventing a lemma that verifies but the target theorem
          still doesn't close (it's not wasted -- it may help later -- but
          it isn't rewarded on the spot either; this is what forces pi_H to
          learn *useful* invention, not just "any true lemma")

State (small, discretized -> tabular policy):
    (theorem_index, direct_failed_so_far, has_unit_lemma, has_swap_lemma, lib_size_bucket)

has_unit_lemma / has_swap_lemma track whether a lemma of that *kind* is
currently in the shared library (persists across theorems within an
episode, same as the library itself) -- NOT how many INVENT actions have
been taken. An earlier version of this state used a raw per-theorem invent
counter instead of tracking lemma kind, which meant "have SWAP, still need
UNIT" and "have UNIT, still need SWAP" collapsed into the same state; the
agent couldn't represent the difference, so it learned to loop re-inventing
one kind instead of reliably completing both. Tracking kind directly makes
the state properly Markov for this decision.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List

import tactic_search
import lemma_proposer

ACTIONS = ["DIRECT", "INVENT_UNIT", "INVENT_SWAP", "GIVE_UP"]

with open(os.path.join(os.path.dirname(__file__), "dataset.json")) as f:
    DATASET = json.load(f)

FN_NAME = DATASET["function_under_test"]
THEOREMS = DATASET["target_theorems"]


@dataclass
class EpisodeLog:
    events: List[dict] = field(default_factory=list)
    invented_lemmas: List[dict] = field(default_factory=list)  # verified & kept
    theorem_results: List[dict] = field(default_factory=list)
    total_kernel_calls: int = 0
    total_reward: float = 0.0


class LemmaDiscoveryEnv:
    def __init__(self, max_steps_per_theorem=6, timeout_s=10.0):
        self.max_steps_per_theorem = max_steps_per_theorem
        self.timeout_s = timeout_s
        self.reset()

    def reset(self):
        self.library_src = ""          # concatenated verified lemma sources
        self.lemma_names = []          # names currently usable by tactic_search
        self.candidate_counter = 0
        self.has_unit = False          # kind-level, persists across theorems
        self.has_swap = False
        self.log = EpisodeLog()
        self.t_idx = 0
        self._start_theorem()
        return self._state()

    # ---- per-theorem bookkeeping ----
    def _start_theorem(self):
        self.direct_failed = False
        self.steps_this_theorem = 0
        self.theorem_done = False

    def _lib_size_bucket(self):
        n = len(self.lemma_names)
        if n == 0:
            return 0
        if n <= 2:
            return 1
        return 2

    def _state(self):
        return (self.t_idx, int(self.direct_failed), int(self.has_unit), int(self.has_swap),
                self._lib_size_bucket())

    @property
    def done(self):
        return self.t_idx >= len(THEOREMS)

    def current_theorem(self):
        return THEOREMS[self.t_idx]

    def step(self, action: str):
        assert not self.done, "episode already finished"
        assert action in ACTIONS
        thm = self.current_theorem()
        reward = 0.0
        info = {"action": action, "theorem": thm["id"]}

        if action == "DIRECT":
            res = tactic_search.attempt(
                thm["name"], thm["statement"], thm["induction_variable"],
                self.library_src, self.lemma_names, timeout_s=self.timeout_s,
            )
            self.log.total_kernel_calls += 1
            reward -= 1.0
            if res.ok:
                reward += 10.0
                info["result"] = "PROVED"
                self.theorem_done = True
                self.log.theorem_results.append({
                    "id": thm["id"], "proved": True,
                    "kernel_calls_used": self.steps_this_theorem + 1,
                })
            else:
                self.direct_failed = True
                info["result"] = "FAILED"

        elif action in ("INVENT_UNIT", "INVENT_SWAP"):
            self.candidate_counter += 1
            candidates = lemma_proposer.propose_candidates(FN_NAME, self.candidate_counter)
            cand = candidates[0] if action == "INVENT_UNIT" else candidates[1]
            res = lemma_proposer.try_prove_candidate(
                cand, self.library_src, self.lemma_names, timeout_s=self.timeout_s,
            )
            self.log.total_kernel_calls += 1
            reward -= 1.0
            if res.ok:
                self.library_src += f"\n{tactic_search.build_script(cand.name, cand.statement, cand.induction_var, self.lemma_names)}\n"
                self.lemma_names.append(cand.name)
                if cand.kind == "UNIT":
                    self.has_unit = True
                else:
                    self.has_swap = True
                self.log.invented_lemmas.append({
                    "name": cand.name, "kind": cand.kind, "statement": cand.statement,
                    "theorem_context": thm["id"],
                })
                info["result"] = f"LEMMA_VERIFIED:{cand.name}"
            else:
                reward -= 1.0
                info["result"] = "LEMMA_FAILED"

        elif action == "GIVE_UP":
            reward -= 5.0
            info["result"] = "GAVE_UP"
            self.theorem_done = True
            self.log.theorem_results.append({
                "id": thm["id"], "proved": False,
                "kernel_calls_used": self.steps_this_theorem + 1,
            })

        self.steps_this_theorem += 1
        self.log.events.append(info)
        self.log.total_reward += reward

        if self.theorem_done or self.steps_this_theorem >= self.max_steps_per_theorem:
            if self.steps_this_theorem >= self.max_steps_per_theorem and not self.theorem_done:
                # ran out of budget without proving or explicit give-up
                self.log.theorem_results.append({
                    "id": thm["id"], "proved": False,
                    "kernel_calls_used": self.steps_this_theorem,
                })
            self.t_idx += 1
            if not self.done:
                self._start_theorem()

        return self._state(), reward, self.done, info