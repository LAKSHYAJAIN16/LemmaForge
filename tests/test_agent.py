import random

from agent import QLearningAgent

ACTIONS = ["A", "B"]


def test_update_moves_q_value_toward_target():
    agent = QLearningAgent(ACTIONS, alpha=0.5, gamma=0.9, rng=random.Random(0))
    state, next_state = "s0", "s1"

    agent.update(state, "A", reward=10.0, next_state=next_state, done=True)
    # done=True -> target is just the reward; alpha=0.5 halves the gap from 0.
    assert agent.q[(state, "A")] == 5.0

    agent.update(state, "A", reward=10.0, next_state=next_state, done=True)
    assert agent.q[(state, "A")] == 7.5


def test_update_bootstraps_from_next_state_when_not_done():
    agent = QLearningAgent(ACTIONS, alpha=1.0, gamma=0.5, rng=random.Random(0))
    agent.q[("s1", "A")] = 4.0
    agent.q[("s1", "B")] = 10.0

    agent.update("s0", "A", reward=1.0, next_state="s1", done=False)
    # alpha=1.0 -> Q becomes exactly reward + gamma * max_a Q(s1, a) = 1 + 0.5*10
    assert agent.q[("s0", "A")] == 6.0


def test_greedy_selection_picks_best_action():
    agent = QLearningAgent(ACTIONS, rng=random.Random(0))
    agent.q[("s0", "A")] = 1.0
    agent.q[("s0", "B")] = 5.0
    assert agent.select_action("s0", greedy=True) == "B"


def test_epsilon_decays_toward_min():
    agent = QLearningAgent(ACTIONS, epsilon=1.0, epsilon_decay=0.5, epsilon_min=0.1)
    for _ in range(20):
        agent.decay()
    assert agent.epsilon == 0.1
