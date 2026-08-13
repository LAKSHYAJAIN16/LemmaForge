(* preamble.v
   Base definitions shared by the whole toy corpus.
   `myadd` is a hand-written structurally recursive nat->nat->nat function.
   It is deliberately NOT Coq's built-in `+`, so tactics like `lia`/`omega`/`ring`
   cannot see through it -- any proof about `myadd` has to go through real
   induction and rewriting, which is what makes the lemma-discovery task honest
   rather than trivially solved by decision procedures. *)

Fixpoint myadd (n m : nat) : nat :=
  match n with
  | 0 => m
  | S n' => S (myadd n' m)
  end.