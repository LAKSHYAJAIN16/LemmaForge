from env import LemmaDiscoveryEnv


def test_full_episode_invents_then_reuses_across_theorems():
    """
    End-to-end integration test against the real kernel: T1 (myadd_comm)
    cannot close without both helper lemmas, and once they're invented,
    T2 (myadd_n_1) closes with a single DIRECT call for free -- this is
    the cross-theorem reuse story the environment is built to demonstrate.
    """
    env = LemmaDiscoveryEnv(max_steps_per_theorem=6, timeout_s=20.0)
    env.reset()

    # T1: direct fails with an empty library.
    _, reward, done, info = env.step("DIRECT")
    assert info["result"] == "FAILED"
    assert reward == -1.0
    assert not done

    # Invent both canonical helper lemmas; each should verify standalone.
    _, reward, done, info = env.step("INVENT_UNIT")
    assert info["result"].startswith("LEMMA_VERIFIED"), info
    assert reward == -1.0

    _, reward, done, info = env.step("INVENT_SWAP")
    assert info["result"].startswith("LEMMA_VERIFIED"), info
    assert reward == -1.0
    assert len(env.lemma_names) == 2

    # Now direct succeeds on T1 with both lemmas in the library.
    _, reward, done, info = env.step("DIRECT")
    assert info["result"] == "PROVED", info
    assert reward == 10.0 - 1.0
    assert not done  # T2 still remains

    # T2 should close immediately, for free, purely by reusing T1's lemmas.
    _, reward, done, info = env.step("DIRECT")
    assert info["result"] == "PROVED", info
    assert reward == 10.0 - 1.0
    assert done

    assert env.log.total_kernel_calls == 5
    proved = [r for r in env.log.theorem_results if r["proved"]]
    assert len(proved) == 2


def test_give_up_ends_theorem_without_kernel_call():
    env = LemmaDiscoveryEnv()
    env.reset()
    calls_before = env.log.total_kernel_calls
    _, reward, done, info = env.step("GIVE_UP")
    assert info["result"] == "GAVE_UP"
    assert reward == -5.0
    assert env.log.total_kernel_calls == calls_before
    assert not done  # T2 still remains
    assert env.log.theorem_results[-1] == {
        "id": "T1", "proved": False, "kernel_calls_used": 1,
    }
