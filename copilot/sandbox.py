"""Restricted runner for model-written analysis scripts.

This is the security boundary for the one place we execute LLM-generated code. The
script runs in a fresh subprocess with:
  - a temporary working directory (deleted afterwards),
  - a scrubbed environment (no AWS/Anthropic creds passed through),
  - a hard wall-clock timeout,
  - POSIX resource limits (CPU seconds, address space, file size) applied in the
    child before exec, where the platform supports it.

Network is not hard-blocked at the syscall level here (that needs OS-level
sandboxing / containers); for v1 we rely on the scrubbed env + no boto3 session
being importable with credentials. Treat scripts as untrusted regardless.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore

# 1 GB address space, 5 CPU-seconds, 5 MB max file write. RLIMIT_AS is only
# applied on Linux — macOS reserves large virtual address ranges, so a tight AS
# cap makes the interpreter fail to start.
_AS_LIMIT = 1024 * 1024 * 1024
_CPU_LIMIT = 5
_FSIZE_LIMIT = 5 * 1024 * 1024


@dataclass
class SandboxResult:
    ok: bool
    stdout: str
    stderr: str


def _apply_limits() -> None:  # pragma: no cover - runs in child process
    if resource is None:
        return
    limits = [
        (resource.RLIMIT_CPU, (_CPU_LIMIT, _CPU_LIMIT)),
        (resource.RLIMIT_FSIZE, (_FSIZE_LIMIT, _FSIZE_LIMIT)),
    ]
    if sys.platform.startswith("linux"):
        limits.append((resource.RLIMIT_AS, (_AS_LIMIT, _AS_LIMIT)))
    for which, vals in limits:
        try:
            resource.setrlimit(which, vals)
        except (ValueError, OSError):
            pass


def run_script(code: str, timeout: int = 10) -> SandboxResult:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "analysis.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                env={"PATH": "/usr/bin:/bin", "PYTHONUNBUFFERED": "1"},
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_apply_limits if resource is not None else None,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(ok=False, stdout="", stderr=f"timed out after {timeout}s")
        return SandboxResult(ok=proc.returncode == 0, stdout=proc.stdout[:4000], stderr=proc.stderr[:2000])
