"""
rocq_runner.py

Thin wrapper around a real Rocq (`rocq`) or legacy Coq (`coqc`) binary. Every
candidate proof (whether it's an attempt at the target theorem or an
agent-invented helper lemma) gets written out as a standalone .v file,
alongside the shared preamble and whatever lemmas have already been verified
earlier in the episode, and is compiled for real. Nothing in this project
claims a lemma is "proved" without this function returning success.
"""

import glob
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import List

PREAMBLE_PATH = os.path.join(os.path.dirname(__file__), "preamble.v")

with open(PREAMBLE_PATH) as f:
    PREAMBLE_SRC = f.read()

_WINDOWS_GLOBS = [
    r"C:\Rocq-Platform*\bin\rocq.exe",
    r"C:\Program Files\Rocq*\bin\rocq.exe",
    r"C:\Coq-Platform*\bin\coqc.exe",
    r"C:\Program Files\Coq*\bin\coqc.exe",
]


def find_rocq_command() -> List[str]:
    """
    Resolve how to invoke the kernel, in order of preference:

      1. ROCQ_BIN env var - explicit path to a `rocq` or `coqc` executable.
      2. `rocq` on PATH    -> ["<path>", "compile", "-q"]
      3. `coqc` on PATH    -> ["<path>", "-q"]
      4. Windows fallback: glob common install locations (covers a Rocq
         Platform install that never got added to PATH).

    Raises RuntimeError with an actionable message if nothing is found.
    """
    env_bin = os.environ.get("ROCQ_BIN")
    if env_bin:
        if not os.path.isfile(env_bin):
            raise RuntimeError(f"ROCQ_BIN={env_bin!r} does not point to a file")
        base = os.path.basename(env_bin).lower()
        if base.startswith("rocq"):
            return [env_bin, "compile", "-q"]
        return [env_bin, "-q"]

    rocq_path = shutil.which("rocq")
    if rocq_path:
        return [rocq_path, "compile", "-q"]

    coqc_path = shutil.which("coqc")
    if coqc_path:
        return [coqc_path, "-q"]

    for pattern in _WINDOWS_GLOBS:
        matches = sorted(glob.glob(pattern))
        if matches:
            found = matches[-1]
            base = os.path.basename(found).lower()
            if base.startswith("rocq"):
                return [found, "compile", "-q"]
            return [found, "-q"]

    raise RuntimeError(
        "Could not find a `rocq` or `coqc` executable on PATH or in any "
        "known install location. Install Rocq/Coq, or set the ROCQ_BIN "
        "environment variable to the full path of the `rocq` or `coqc` "
        "executable."
    )


_ROCQ_COMMAND = None


def _rocq_command() -> List[str]:
    global _ROCQ_COMMAND
    if _ROCQ_COMMAND is None:
        _ROCQ_COMMAND = find_rocq_command()
    return _ROCQ_COMMAND


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
    theorem/lemma block with a real kernel subprocess call.

    library_lemmas_src : concatenated Coq source of previously verified
                          lemmas (each ending in Qed.), in dependency order.
    candidate_src       : the new Lemma/Theorem statement + proof to check.

    Returns VerifyResult.ok == True iff the kernel accepted the whole file
    (i.e. the compile process exited 0).
    """
    full_src = PREAMBLE_SRC + "\n\n" + library_lemmas_src + "\n\n" + candidate_src + "\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        vfile = os.path.join(tmpdir, "Candidate.v")
        with open(vfile, "w") as f:
            f.write(full_src)

        t0 = time.time()
        try:
            proc = subprocess.run(
                _rocq_command() + [vfile],
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
