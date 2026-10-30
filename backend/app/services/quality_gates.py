"""Deterministic quality gates.

AI review is never the only line of defence.  Gates run project-configured
commands plus built-in checks (secret scanning, worktree hygiene).  Unavailable
or unconfigured gates are reported honestly, never as passes.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.enums import GateStatus
from app.services.providers.process import run_command

ALLOWED_EXECUTABLES = {
    "npm", "npx", "pnpm", "yarn", "node", "bun",
    "python", "python3", "pytest", "ruff", "mypy", "black", "tox", "uv",
    "go", "cargo", "rustc", "make", "cmake",
    "mvn", "gradle", "./gradlew", "dotnet",
    "php", "composer", "ruby", "bundle", "rake",
    "tsc", "eslint", "prettier", "jest", "vitest",
    "swift", "xcodebuild",
    "docker",  # only inside a configured development environment
    "git",
}

DANGEROUS_TOKENS = {
    "rm", "rmdir", "mkfs", "dd", "shutdown", "reboot", "halt", "poweroff",
    "sudo", "su", "chown", "chmod", "curl", "wget", "nc", "ncat", "ssh",
    "scp", "kubectl", "terraform", "helm",
}

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "generic_assignment": re.compile(
        r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]([A-Za-z0-9_\-./+]{16,})['\"]"
    ),
}

DEFAULT_GATE_TIMEOUT = 900


@dataclass
class GateInput:
    name: str
    command: str
    required: bool = True
    timeout: int = DEFAULT_GATE_TIMEOUT
    gate_type: str = "command"


@dataclass
class GateOutcome:
    name: str
    status: str
    required: bool
    command: str
    output: str
    duration_ms: Optional[int] = None


def _validated_command(command: str) -> List[str]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"Invalid gate command: {exc}") from exc
    if not parts:
        raise ValueError("Gate command is empty")
    executable = os.path.basename(parts[0])
    if executable in DANGEROUS_TOKENS or parts[0] in DANGEROUS_TOKENS:
        raise ValueError(f"Executable '{parts[0]}' is not permitted in a quality gate")
    if executable not in ALLOWED_EXECUTABLES and parts[0] not in ALLOWED_EXECUTABLES:
        raise ValueError(
            f"Executable '{parts[0]}' is not in the quality-gate allowlist. "
            "Ask an administrator to extend the list explicitly."
        )
    if any(ch in command for ch in (";", "&&", "||", "`", "$(", "\n")):
        raise ValueError("Shell operators are not supported; configure one command per gate")
    return parts


def detect_gates(project_root: str, stack_hint: Optional[str] = None) -> List[GateInput]:
    """Detect stack-appropriate gates.  Detected gates are optional by default."""
    gates: List[GateInput] = []
    if os.path.isfile(os.path.join(project_root, "package.json")):
        try:
            data = json.loads(open(os.path.join(project_root, "package.json"), encoding="utf-8").read())
        except Exception:
            data = {}
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        runner = "npm" if os.path.isfile(os.path.join(project_root, "package-lock.json")) else "npm"
        if "test" in scripts:
            gates.append(GateInput("unit-tests", f"{runner} test -- --run", required=False))
        if "lint" in scripts:
            gates.append(GateInput("lint", f"{runner} run lint", required=False))
        if "build" in scripts:
            gates.append(GateInput("build", f"{runner} run build", required=False))
    if os.path.isfile(os.path.join(project_root, "pyproject.toml")) or os.path.isfile(
        os.path.join(project_root, "pytest.ini")
    ):
        gates.append(GateInput("unit-tests", "python3 -m pytest -q", required=False))
        gates.append(GateInput("lint", "python3 -m ruff check .", required=False))
    if os.path.isfile(os.path.join(project_root, "go.mod")):
        gates.append(GateInput("unit-tests", "go test ./...", required=False))
        gates.append(GateInput("build", "go build ./...", required=False))
    if os.path.isfile(os.path.join(project_root, "Cargo.toml")):
        gates.append(GateInput("unit-tests", "cargo test", required=False))
    if os.path.isfile(os.path.join(project_root, "composer.json")):
        gates.append(GateInput("unit-tests", "composer test", required=False))
    return gates


def configured_gates(project_quality_gates: List[Dict[str, Any]]) -> List[GateInput]:
    gates: List[GateInput] = []
    for item in project_quality_gates or []:
        if not isinstance(item, dict) or not item.get("name") or not item.get("command"):
            continue
        gates.append(
            GateInput(
                name=str(item["name"])[:120],
                command=str(item["command"])[:2000],
                required=bool(item.get("required", True)),
                timeout=int(item.get("timeout", DEFAULT_GATE_TIMEOUT)),
                gate_type=str(item.get("type", "command")),
            )
        )
    return gates


async def secret_scan(workspace: str, files: List[str]) -> GateOutcome:
    findings: List[str] = []
    scan_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".env",
        ".toml", ".md", ".sh", ".go", ".rb", ".php", ".java", ".cs", ".txt",
    }
    for rel in files:
        if rel.startswith(".git/"):
            continue
        path = os.path.realpath(os.path.join(workspace, rel))
        if not path.startswith(os.path.realpath(workspace) + os.sep):
            continue
        if not os.path.isfile(path) or os.path.getsize(path) > 1_000_000:
            continue
        if os.path.splitext(path)[1].lower() not in scan_extensions and not os.path.basename(path).startswith(".env"):
            continue
        try:
            content = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(content):
                line = content[: match.start()].count("\n") + 1
                findings.append(f"{rel}:{line}: possible {name}")
    if findings:
        return GateOutcome(
            name="secret-scan",
            status=GateStatus.FAILED.value,
            required=True,
            command="built-in secret scan",
            output="\n".join(findings[:100]),
        )
    return GateOutcome(
        name="secret-scan",
        status=GateStatus.PASSED.value,
        required=True,
        command="built-in secret scan",
        output=f"Scanned {len(files)} changed file(s); no secrets detected.",
    )


async def worktree_hygiene(workspace: str, changed: List[str], forbidden_paths: List[str]) -> GateOutcome:
    violations = [f for f in forbidden_paths if f in changed]
    if violations:
        return GateOutcome(
            name="change-policy",
            status=GateStatus.FAILED.value,
            required=True,
            command="built-in change policy",
            output="Protected files were modified: " + ", ".join(violations),
        )
    return GateOutcome(
        name="change-policy",
        status=GateStatus.PASSED.value,
        required=True,
        command="built-in change policy",
        output="No protected files modified.",
    )


def _executable_available(command: List[str], workspace: str) -> bool:
    """Report a missing executable honestly instead of crashing the gate runner."""
    executable = command[0]
    if os.sep in executable or executable.startswith("."):
        path = executable if os.path.isabs(executable) else os.path.join(workspace, executable)
        return os.path.isfile(path) and os.access(path, os.X_OK)
    return shutil.which(executable) is not None


async def run_command_gate(gate: GateInput, workspace: str) -> GateOutcome:
    try:
        command = _validated_command(gate.command)
    except ValueError as exc:
        return GateOutcome(
            name=gate.name,
            status=GateStatus.NOT_CONFIGURED.value,
            required=gate.required,
            command=gate.command,
            output=str(exc),
        )
    if not _executable_available(command, workspace):
        return GateOutcome(
            name=gate.name,
            status=GateStatus.NOT_CONFIGURED.value,
            required=gate.required,
            command=gate.command,
            output=(
                f"Executable '{command[0]}' is not available in this environment; "
                "the gate was not run and is not reported as passed."
            ),
        )
    result = await run_command(
        command, cwd=workspace, timeout=gate.timeout, max_output=200_000
    )
    if result.timed_out:
        status = GateStatus.FAILED.value
    elif result.exit_code == 0:
        status = GateStatus.PASSED.value
    else:
        status = GateStatus.FAILED.value if gate.required else GateStatus.WARNING.value
    output = f"$ {gate.command}\n{result.stdout}\n{result.stderr}".strip()
    return GateOutcome(
        name=gate.name,
        status=status,
        required=gate.required,
        command=gate.command,
        output=output,
        duration_ms=result.duration_ms,
    )


async def run_gates(
    *,
    workspace: str,
    configured: List[Dict[str, Any]],
    changed_files: List[str],
    protected_paths: Optional[List[str]] = None,
    allow_auto_detect: bool = True,
) -> List[GateOutcome]:
    outcomes: List[GateOutcome] = []
    outcomes.append(await secret_scan(workspace, changed_files))
    outcomes.append(await worktree_hygiene(workspace, changed_files, protected_paths or []))
    gates = configured_gates(configured)
    if not gates and allow_auto_detect:
        gates = detect_gates(workspace)
    if not gates:
        outcomes.append(
            GateOutcome(
                name="project-validation",
                status=GateStatus.NOT_CONFIGURED.value,
                required=False,
                command="",
                output=(
                    "No quality gates are configured and none could be detected. "
                    "This is reported as NOT_CONFIGURED, not as a pass."
                ),
            )
        )
    for gate in gates:
        outcomes.append(await run_command_gate(gate, workspace))
    return outcomes


def mandatory_failed(outcomes: List[GateOutcome]) -> List[GateOutcome]:
    return [o for o in outcomes if o.required and o.status == GateStatus.FAILED.value]
