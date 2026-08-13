"""
coq_runner.py

Thin wrapper around a real `coqc` binary. Every candidate proof (whether it's
an attempt at the target theorem or an attempt at an agent-invented helper
lemma) gets written out as a standalone .v file, alongside the shared
preamble and whatever lemmas have already been verified earlier in the
episode, and is compiled for real. Nothing in this project claims a lemma
is "proved" without this function returning success.
"""

import subprocess
import tempfile
import os
import time
from dataclasses import dataclass

PREAMBLE_PATH = os.path.join(os.path.dirname(__file__), "preamble.v")

with open(PREAMBLE_PATH) as f:
    PREAMBLE_SRC = f.read()


@dataclass
class VerifyResult:
    ok: bool
    stdout: str
    stderr: str
    wall_time_s: float
    source: str


def verify_snippet(library_lemmas_src: str, candidate_src: str, timeout_s: float = 10.0) -> VerifyResult:
    """
    Compiles PREAMBLE + already-verified library lemmas + a new candidate
    theorem/lemma block with a real `coqc` subprocess call.

    library_lemmas_src : concatenated Coq source of previously verified
                          lemmas (each ending in Qed.), in dependency order.
    candidate_src       : the new Lemma/Theorem statement + proof to check.

    Returns VerifyResult.ok == True iff the Coq kernel accepted the whole
    file (i.e. coqc exited 0).
    """
    full_src = PREAMBLE_SRC + "\n\n" + library_lemmas_src + "\n\n" + candidate_src + "\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        vfile = os.path.join(tmpdir, "Candidate.v")
        with open(vfile, "w") as f:
            f.write(full_src)

        t0 = time.time()
        try:
            proc = subprocess.run(
                ["coqc", "-q", vfile],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            ok = proc.returncode == 0
            out, err = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            ok = False
            out, err = "", f"TIMEOUT after {timeout_s}s"
        wall = time.time() - t0

    return VerifyResult(ok=ok, stdout=out, stderr=err, wall_time_s=wall, source=full_src)