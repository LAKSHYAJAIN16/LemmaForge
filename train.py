"""
train.py

CLI entry point: trains pi_H (a tabular Q-learning agent, see agent.py) on
LemmaDiscoveryEnv (see env.py) for N episodes, each episode a real pass over
the corpus in dataset.json backed by real `rocq`/`coqc` kernel calls. Then
runs one final greedy rollout to report the learned policy's behavior.
"""

import argparse
import json
import random

from agent import QLearningAgent
from env import ACTIONS, LemmaDiscoveryEnv


def run_episode(env: LemmaDiscoveryEnv, agent: QLearningAgent, learn: bool, greedy: bool):
    state = env.reset()
    while not env.done:
        action = agent.select_action(state, greedy=greedy)
        next_state, reward, done, info = env.step(action)
        if learn:
            agent.update(state, action, reward, next_state, done)
        state = next_state
    return env.log


def main():
    parser = argparse.ArgumentParser(description="Train pi_H on LemmaDiscoveryEnv")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", type=str, default="results.json")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    env = LemmaDiscoveryEnv(timeout_s=args.timeout)
    agent = QLearningAgent(ACTIONS, rng=rng)

    training_summaries = []
    for ep in range(args.episodes):
        log = run_episode(env, agent, learn=True, greedy=False)
        agent.decay()
        proved = sum(1 for r in log.theorem_results if r["proved"])
        training_summaries.append({
            "episode": ep,
            "total_reward": log.total_reward,
            "kernel_calls": log.total_kernel_calls,
            "theorems_proved": proved,
            "epsilon": agent.epsilon,
        })
        print(f"episode {ep:3d}  reward={log.total_reward:6.1f}  "
              f"kernel_calls={log.total_kernel_calls:2d}  "
              f"proved={proved}/{len(log.theorem_results)}  eps={agent.epsilon:.3f}")

    final_log = run_episode(env, agent, learn=False, greedy=True)
    print("\n=== greedy rollout (learned policy) ===")
    for ev in final_log.events:
        print(f"  {ev['theorem']}: {ev['action']:12s} -> {ev.get('result')}")
    print(f"total_reward={final_log.total_reward:.1f}  "
          f"kernel_calls={final_log.total_kernel_calls}  "
          f"invented_lemmas={[l['name'] for l in final_log.invented_lemmas]}")

    with open(args.out, "w") as f:
        json.dump({
            "training": training_summaries,
            "final_greedy_rollout": {
                "events": final_log.events,
                "invented_lemmas": final_log.invented_lemmas,
                "theorem_results": final_log.theorem_results,
                "total_kernel_calls": final_log.total_kernel_calls,
                "total_reward": final_log.total_reward,
            },
        }, f, indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
