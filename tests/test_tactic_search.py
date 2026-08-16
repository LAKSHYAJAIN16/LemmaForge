import tactic_search


def test_build_script_with_induction():
    src = tactic_search.build_script("foo", "forall n : nat, foo n = n", "n", [])
    assert "Lemma foo : forall n : nat, foo n = n." in src
    assert "induction n as [| n' IH]." in src
    assert src.strip().endswith("Qed.")


def test_build_script_without_induction():
    src = tactic_search.build_script("foo", "foo 1 = 1", None, [])
    assert "induction" not in src
    assert "first [" in src


def test_attempt_proves_unit_lemma_directly():
    res = tactic_search.attempt(
        "myadd_n_0_test",
        "forall n : nat, myadd n 0 = n",
        "n",
        library_lemmas_src="",
        lemma_names=[],
    )
    assert res.ok, res.stderr
