from lemma_proposer import propose_candidates


def test_propose_candidates_shapes():
    unit, swap = propose_candidates("myadd", counter=3)

    assert unit.kind == "UNIT"
    assert unit.name == "myadd_n_0_v3"
    assert unit.statement == "forall n : nat, myadd n 0 = n"
    assert unit.induction_var == "n"

    assert swap.kind == "SWAP"
    assert swap.name == "myadd_n_Sm_v3"
    assert swap.statement == "forall n m : nat, S (myadd n m) = myadd n (S m)"
    assert swap.induction_var == "n"


def test_propose_candidates_generic_over_fn_name():
    unit, swap = propose_candidates("mymul", counter=1)
    assert "mymul" in unit.statement
    assert "mymul" in swap.statement
