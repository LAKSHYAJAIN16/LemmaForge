from rocq_runner import verify_snippet


def test_true_lemma_compiles():
    res = verify_snippet("", "Lemma trivial_true : 1 + 1 = 2.\nProof. reflexivity. Qed.\n")
    assert res.ok, res.stderr


def test_false_statement_fails():
    res = verify_snippet("", "Lemma trivial_false : 1 + 1 = 3.\nProof. reflexivity. Qed.\n")
    assert not res.ok
