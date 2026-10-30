"""Safe subprocess execution for CLI agent providers and quality gates.

Commands are always argument lists (never ``shell=True``).  Output is capped and
redacted, process groups are killed on timeout, and the environment is scrubbed
of H-Caliper secrets before it reaches an agent or a project command.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.core.config import settings
from app.core.logging import redact

_SECRET_ENV_KEYS = {
    "SECRET_KEY",
    "ENCRYPTION_KEY",
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    "BOOTSTRAP_ADMIN_EMAIL",
    "GITHUB_TOKEN",
}


@dataclass
class CommandResult:
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False
    env: Dict[str, str] = field(default_factory=dict)


def sanitized_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "TERM": "dumb",
        "CI": "1",
        "GIT_AUTHOR_NAME": settings.GIT_AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": settings.GIT_AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": settings.GIT_AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": settings.GIT_AUTHOR_EMAIL,
    }
    if settings.OPENCODE_COMMAND:
        opencode_dir = os.path.dirname(shutil.which(settings.OPENCODE_COMMAND) or "")
        if opencode_dir:
            env["PATH"] = f"{opencode_dir}:{env['PATH']}"
    for key in list(os.environ):
        if key in _SECRET_ENV_KEYS or key.startswith("HCALIPER_"):
            continue
        if key in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"}:
            continue
    if extra:
        for key, value in extra.items():
            if key in _SECRET_ENV_KEYS:
                continue
            env[key] = value
    return env


async def run_command(
    command: Sequence[str],
    *,
    cwd: str,
    timeout: int,
    env: Optional[Dict[str, str]] = None,
    input_text: Optional[str] = None,
    max_output: Optional[int] = None,
) -> CommandResult:
    started = time.monotonic()
    cap = max_output or settings.AGENT_MAX_OUTPUT_CHARS
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=sanitized_env(env),
        stdin=asyncio.subprocess.PIPE if input_text is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            process.communicate(input=input_text.encode() if input_text else None),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        timed_out = True
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout_b, stderr_b = await process.communicate()
    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
    truncated = len(stdout) > cap
    return CommandResult(
        command=list(command),
        exit_code=124 if timed_out else int(process.returncode or 0),
        stdout=redact(stdout, limit=cap),
        stderr=redact(stderr, limit=min(cap, 40_000)),
        duration_ms=duration_ms,
        timed_out=timed_out,
        truncated=truncated,
        env={},
    )


def executable_available(command: str) -> bool:
    return shutil.which(command) is not None
