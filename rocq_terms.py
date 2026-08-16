"""
rocq_terms.py

A minimal term representation for the restricted first-order equational
fragment this project works in: variables and prefix application of
functions/constructors over `nat` and `list nat`. Shared by:

  - conjecture_engine.py, which builds terms programmatically (QuickSpec-style
    enumeration) and prints them to Rocq syntax to propose as candidate lemma
    statements.
  - the rippling-style stuck-goal generalizer in conjecture_engine.py, which
    parses a target equation into this representation to symbolically unfold
    it (via known Fixpoint equations) and diff it against the induction
    hypothesis.

Scope: this is NOT a general Rocq parser. It only understands the fragment
this project's own functions/generated statements use: identifiers, bare `0`
as a nat literal, juxtaposed prefix application, and parenthesization. A
single top-level `=` splits an equation into its two sides. Statements mined
from the real Rocq stdlib (mine_corpus.py) use richer notation (`+`, `::`,
`[]`, infix operators) that this parser does not understand -- callers must
catch ParseError and degrade gracefully (e.g. skip rippling for that goal)
rather than assume every statement is parseable.
"""

from dataclasses import dataclass
from typing import Tuple


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class Term:
    head: str
    args: Tuple["Term", ...] = ()
    is_var: bool = False

    def __str__(self):
        return print_term(self)


def Var(name: str) -> Term:
    return Term(name, (), True)


def App(head: str, *args: Term) -> Term:
    return Term(head, tuple(args), False)


def print_term(t: Term) -> str:
    if t.is_var or not t.args:
        return t.head
    parts = [t.head]
    for a in t.args:
        s = print_term(a)
        parts.append(s if (a.is_var or not a.args) else f"({s})")
    return " ".join(parts)


def print_equation(lhs: Term, rhs: Term) -> str:
    return f"{print_term(lhs)} = {print_term(rhs)}"


# ---- tiny tokenizer + recursive-descent parser ----

def _tokenize(s: str):
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "()=":
            toks.append(c)
            i += 1
        elif c.isalnum() or c == "_" or c == "'":
            j = i
            while j < n and (s[j].isalnum() or s[j] in "_'"):
                j += 1
            toks.append(s[i:j])
            i = j
        else:
            raise ParseError(f"unexpected character {c!r} in {s!r}")
    return toks


class _Parser:
    def __init__(self, toks, var_names):
        self.toks = toks
        self.i = 0
        self.var_names = var_names

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self):
        t = self.peek()
        if t is None:
            raise ParseError("unexpected end of input")
        self.i += 1
        return t

    def parse_atom(self) -> Term:
        t = self.next()
        if t == "(":
            inner = self.parse_application()
            if self.next() != ")":
                raise ParseError("expected ')'")
            return inner
        if t == "0":
            return App("O")
        if t in ("=", ")"):
            raise ParseError(f"unexpected token {t!r}")
        return Var(t) if t in self.var_names else App(t)

    def parse_application(self) -> Term:
        head_term = self.parse_atom()
        args = []
        while self.peek() not in (None, ")", "="):
            args.append(self.parse_atom())
        if not args:
            return head_term
        if head_term.args or head_term.is_var and args:
            # a bare variable can't be the head of a further application
            # in this fragment; only constant/function heads take args.
            if head_term.is_var:
                raise ParseError(f"variable {head_term.head!r} applied to arguments")
        return App(head_term.head, *args)

    def parse_equation(self):
        lhs = self.parse_application()
        if self.next() != "=":
            raise ParseError("expected '='")
        rhs = self.parse_application()
        if self.i != len(self.toks):
            raise ParseError("trailing tokens after equation")
        return lhs, rhs


def parse_equation(text: str, var_names) -> Tuple[Term, Term]:
    """
    Parse `<application> = <application>` into (lhs, rhs) Terms.
    `var_names` is the set/iterable of identifiers that should be treated as
    bound variables rather than function/constructor heads.
    """
    toks = _tokenize(text)
    return _Parser(toks, set(var_names)).parse_equation()


def substitute(t: Term, mapping: dict) -> Term:
    """Replace variables (by name) per `mapping` (name -> Term)."""
    if t.is_var:
        return mapping.get(t.head, t)
    if not t.args:
        return t
    return App(t.head, *(substitute(a, mapping) for a in t.args))


def match(pattern: Term, target: Term, bindings: dict) -> bool:
    """
    One-directional syntactic match: try to unify `pattern`'s variables
    against `target`, extending `bindings` (name -> Term) in place.
    Returns False (bindings left partially populated -- caller should copy
    bindings before calling if it needs to roll back) on failure.
    """
    if pattern.is_var:
        if pattern.head in bindings:
            return bindings[pattern.head] == target
        bindings[pattern.head] = target
        return True
    if pattern.head != target.head or len(pattern.args) != len(target.args):
        return False
    return all(match(pa, ta, bindings) for pa, ta in zip(pattern.args, target.args))


def find_and_rewrite(t: Term, lhs_pattern: Term, rhs_pattern: Term):
    """
    Search `t` (top-down, left-to-right) for a subterm matching
    `lhs_pattern`; rewrite the FIRST match to `rhs_pattern` under the
    resulting substitution. Returns (new_term, True) if a rewrite happened,
    else (t, False).
    """
    bindings = {}
    if match(lhs_pattern, t, dict(bindings)):
        bindings = {}
        match(lhs_pattern, t, bindings)
        return substitute(rhs_pattern, bindings), True
    if t.args:
        new_args = list(t.args)
        for i, a in enumerate(t.args):
            new_a, changed = find_and_rewrite(a, lhs_pattern, rhs_pattern)
            if changed:
                new_args[i] = new_a
                return App(t.head, *new_args), True
    return t, False
