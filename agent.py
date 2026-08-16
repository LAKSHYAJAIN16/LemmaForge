"""
agent.py

pi_H as a tabular Q-learning agent over the small discretized state space
LemmaDiscoveryEnv already exposes:
    (theorem_index, direct_failed_so_far, n_invents_tried_this_theorem, lib_size_bucket)

This is deliberately the simplest thing that can learn the invent-vs-continue
decision from real kernel-verified rewards -- a function-approximated policy
(e.g. over a learned proof-state embedding) is future work, not needed for a
state space this small.
"""

import random
from collections import defaultdict


class QLearningAgent:
    def __init__(self, actions, alpha=0.3, gamma=0.95, epsilon=0.3,
                 epsilon_decay=0.97, epsilon_min=0.05, rng=None):
        self.actions = list(actions)
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.rng = rng or random.Random()
        self.q = defaultdict(float)

    def _best_action(self, state):
        return max(self.actions, key=lambda a: self.q[(state, a)])

    def select_action(self, state, greedy=False):
        if not greedy and self.rng.random() < self.epsilon:
            return self.rng.choice(self.actions)
        return self._best_action(state)

    def update(self, state, action, reward, next_state, done):
        best_next = 0.0 if done else max(self.q[(next_state, a)] for a in self.actions)
        td_target = reward + self.gamma * best_next
        td_error = td_target - self.q[(state, action)]
        self.q[(state, action)] += self.alpha * td_error

    def decay(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
