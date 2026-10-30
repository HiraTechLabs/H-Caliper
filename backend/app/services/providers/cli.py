"""CLI-backed agent providers: OpenCode, Codex, Google Antigravity.

These adapters invoke only documented non-interactive interfaces.  They never
construct a shell string, never read provider token files, and report an
actionable error when a runtime or login is missing.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.enums import Capability, ProviderStatus
from app.services.providers.base import (
    AgentRunResult,
    BaseProvider,
    ProviderAuthenticationError,
    ProviderHealth,
    ProviderResponseError,
    ProviderTimeout,
    ProviderUnavailable,
    UnsupportedCapabilityError,
)
from app.services.providers.process import executable_available, run_command

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,199}$")


def _validate_model(model: str) -> str:
    if not model or not MODEL_ID.match(model):
        raise ProviderResponseError("Invalid model identifier")
    return model


def _json_objects(text: str) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith(("{", "[")):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            objects.append(value)
        elif isinstance(value, list):
            objects.extend(v for v in value if isinstance(v, dict))
    if not objects:
        try:
            value = json.loads((text or "").strip())
            if isinstance(value, dict):
                objects = [value]
        except ValueError:
            pass
    return objects


def _deep_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_deep_text(v) for v in value)
    if isinstance(value, dict):
        for key in ("text", "content", "result", "response", "message", "output"):
            if key in value and isinstance(value[key], (str, list, dict)):
                text = _deep_text(value[key])
                if text.strip():
                    return text
    return ""


class _CliProvider(BaseProvider):
    command_setting = ""
    capabilities = {
        Capability.CHAT,
        Capability.AGENT,
        Capability.TOOLS,
        Capability.FILE_EDITING,
        Capability.TERMINAL,
        Capability.MODEL_DISCOVERY,
    }

    def command(self) -> str:
        return str(self.config.get("command") or getattr(settings, self.command_setting))

    async def list_models(self) -> List[str]:
        raise UnsupportedCapabilityError("Model discovery is not supported by this CLI")

    async def _version(self) -> Optional[str]:
        if not executable_available(self.command()):
            return None
        result = await run_command(
            [self.command(), "--version"], cwd="/tmp", timeout=20, max_output=1000
        )
        return (result.stdout or result.stderr).strip().splitlines()[0] if result.stdout or result.stderr else None

    async def health(self) -> ProviderHealth:
        if not executable_available(self.command()):
            return ProviderHealth(
                connected=False,
                status=ProviderStatus.UNREACHABLE.value,
                message=f"Executable '{self.command()}' is not installed",
            )
        try:
            models = await self.list_models()
            return ProviderHealth(
                connected=True,
                status=ProviderStatus.HEALTHY.value,
                models=models,
                version=await self._version(),
            )
        except UnsupportedCapabilityError:
            return ProviderHealth(
                connected=True,
                status=ProviderStatus.HEALTHY.value,
                message="Model discovery unsupported; configure models manually",
                version=await self._version(),
            )
        except ProviderAuthenticationError as exc:
            return ProviderHealth(
                connected=False,
                status=ProviderStatus.AUTH_FAILED.value,
                message=exc.message,
                version=await self._version(),
            )
        except Exception as exc:
            return ProviderHealth(
                connected=False,
                status=ProviderStatus.UNREACHABLE.value,
                message=str(exc),
                version=await self._version(),
            )


class OpenCodeProvider(_CliProvider):
    type = "opencode"
    command_setting = "OPENCODE_COMMAND"
    capabilities = {
        Capability.CHAT,
        Capability.AGENT,
        Capability.TOOLS,
        Capability.FILE_EDITING,
        Capability.TERMINAL,
        Capability.STREAMING,
        Capability.MODEL_DISCOVERY,
    }

    async def list_models(self) -> List[str]:
        if not executable_available(self.command()):
            raise ProviderUnavailable("OpenCode CLI is not installed")
        result = await run_command(
            [self.command(), "models"], cwd="/tmp", timeout=60, max_output=100_000
        )
        if result.exit_code != 0:
            message = (result.stderr or result.stdout)[:500]
            if "auth" in message.lower() or "login" in message.lower():
                raise ProviderAuthenticationError(message)
            raise ProviderUnavailable(f"OpenCode model listing failed: {message}")
        return sorted(
            {
                line.strip()
                for line in result.stdout.splitlines()
                if "/" in line and " " not in line.strip()
            }
        )

    async def _run(
        self, prompt: str, model: str, cwd: str, timeout: int, agent_mode: bool
    ) -> Any:
        if not executable_available(self.command()):
            raise ProviderUnavailable("OpenCode CLI is not installed")
        args = [self.command(), "run", "--format", "json", "-m", _validate_model(model)]
        if agent_mode:
            args.append("--auto")
        args.append(prompt)
        result = await run_command(args, cwd=cwd, timeout=timeout)
        if result.timed_out:
            raise ProviderTimeout(f"OpenCode did not finish within {timeout}s")
        if result.exit_code != 0:
            message = (result.stderr or result.stdout)[:800]
            if "401" in message or "auth" in message.lower() or "login" in message.lower():
                raise ProviderAuthenticationError(message)
            raise ProviderUnavailable(f"OpenCode exited with {result.exit_code}: {message}")
        objects = _json_objects(result.stdout)
        text = ""
        for obj in objects:
            text = _deep_text(obj) or text
        if not text.strip():
            text = result.stdout.strip()
        return text, result

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        prompt = "\n\n".join(
            f"[{m.get('role', 'user').upper()}]\n{m.get('content', '')}" for m in messages
        )
        text, _ = await self._run(
            prompt,
            model,
            "/tmp",
            int(self.config.get("timeout", settings.PROVIDER_REQUEST_TIMEOUT)),
            agent_mode=False,
        )
        return text

    async def run_agent(
        self, *, workspace: str, prompt: str, model: str, timeout: int
    ) -> AgentRunResult:
        text, result = await self._run(prompt, model, workspace, timeout, agent_mode=True)
        return AgentRunResult(
            output=text,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            metadata={"truncated": result.truncated},
        )


class CodexProvider(_CliProvider):
    type = "codex"
    command_setting = "CODEX_COMMAND"
    capabilities = {
        Capability.CHAT,
        Capability.AGENT,
        Capability.TOOLS,
        Capability.FILE_EDITING,
        Capability.TERMINAL,
        Capability.MODEL_DISCOVERY,
    }

    async def list_models(self) -> List[str]:
        # The installed Codex CLI has no public model-list command.  Models are
        # configured manually; do not fabricate a catalogue.
        raise UnsupportedCapabilityError(
            "Codex model discovery is unavailable; enter the model manually"
        )

    async def health(self) -> ProviderHealth:
        base = await super().health()
        if not base.connected:
            return base
        result = await run_command(
            [self.command(), "login", "status"], cwd="/tmp", timeout=20, max_output=5000
        )
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if "not logged in" in combined:
            return ProviderHealth(
                connected=False,
                status=ProviderStatus.AUTH_FAILED.value,
                message="Codex is installed but not logged in",
                version=base.version,
            )
        return base

    async def _exec(
        self, prompt: str, model: str, cwd: str, timeout: int, agent_mode: bool
    ) -> Any:
        if not executable_available(self.command()):
            raise ProviderUnavailable("Codex CLI is not installed")
        args = [
            self.command(),
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "-C",
            cwd,
            "-s",
            "workspace-write" if agent_mode else "read-only",
        ]
        if model:
            args += ["-m", _validate_model(model)]
        args.append("-")
        result = await run_command(args, cwd=cwd, timeout=timeout, input_text=prompt)
        if result.timed_out:
            raise ProviderTimeout(f"Codex did not finish within {timeout}s")
        if result.exit_code != 0:
            message = (result.stderr or result.stdout)[:800]
            if "not logged in" in message.lower() or "authentication" in message.lower():
                raise ProviderAuthenticationError(message)
            raise ProviderUnavailable(f"Codex exited with {result.exit_code}: {message}")
        objects = _json_objects(result.stdout)
        texts = []
        for obj in objects:
            item = obj.get("item") if isinstance(obj.get("item"), dict) else obj
            if item.get("type") in {"agent_message", "assistant_message", "message"}:
                text = _deep_text(item)
                if text:
                    texts.append(text)
        text = "\n".join(texts).strip() or result.stdout.strip()
        return text, result

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        prompt = "\n\n".join(
            f"[{m.get('role', 'user').upper()}]\n{m.get('content', '')}" for m in messages
        )
        text, _ = await self._exec(
            prompt, model, "/tmp", int(self.config.get("timeout", settings.PROVIDER_REQUEST_TIMEOUT)), False
        )
        return text

    async def run_agent(
        self, *, workspace: str, prompt: str, model: str, timeout: int
    ) -> AgentRunResult:
        text, result = await self._exec(prompt, model, workspace, timeout, True)
        return AgentRunResult(
            output=text, exit_code=result.exit_code, duration_ms=result.duration_ms
        )


class AntigravityProvider(_CliProvider):
    type = "antigravity"
    command_setting = "ANTIGRAVITY_COMMAND"
    capabilities = {
        Capability.CHAT,
        Capability.AGENT,
        Capability.TOOLS,
        Capability.FILE_EDITING,
        Capability.TERMINAL,
        Capability.MODEL_DISCOVERY,
    }

    async def list_models(self) -> List[str]:
        if not executable_available(self.command()):
            raise ProviderUnavailable("Antigravity CLI (agy) is not installed")
        result = await run_command(
            [self.command(), "models"], cwd="/tmp", timeout=60, max_output=100_000
        )
        if result.exit_code != 0:
            raise ProviderUnavailable(
                (result.stderr or result.stdout)[:500] or "agy models failed"
            )
        models = []
        for line in result.stdout.splitlines():
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._:-]+)\s+\S", line)
            if match:
                models.append(match.group(1))
        return sorted(set(models))

    async def _run(
        self, prompt: str, model: str, cwd: str, timeout: int, agent_mode: bool
    ) -> Any:
        if not executable_available(self.command()):
            raise ProviderUnavailable("Antigravity CLI (agy) is not installed")
        args = [
            self.command(),
            f"--print={prompt}",
            "--model",
            _validate_model(model),
            "--output-format",
            "json",
        ]
        if agent_mode:
            args += ["--mode", "accept-edits", "--sandbox", "--add-dir", cwd]
        result = await run_command(args, cwd=cwd, timeout=timeout)
        if result.timed_out:
            raise ProviderTimeout(f"Antigravity did not finish within {timeout}s")
        if result.exit_code != 0:
            message = (result.stderr or result.stdout)[:800]
            if "401" in message or "auth" in message.lower() or "login" in message.lower():
                raise ProviderAuthenticationError(message)
            raise ProviderUnavailable(f"agy exited with {result.exit_code}: {message}")
        objects = _json_objects(result.stdout)
        text = ""
        for obj in objects:
            text = _deep_text(obj) or text
        return (text or result.stdout).strip(), result

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        prompt = "\n\n".join(
            f"[{m.get('role', 'user').upper()}]\n{m.get('content', '')}" for m in messages
        )
        text, _ = await self._run(
            prompt, model, "/tmp", int(self.config.get("timeout", settings.PROVIDER_REQUEST_TIMEOUT)), False
        )
        return text

    async def run_agent(
        self, *, workspace: str, prompt: str, model: str, timeout: int
    ) -> AgentRunResult:
        text, result = await self._run(prompt, model, workspace, timeout, True)
        return AgentRunResult(
            output=text, exit_code=result.exit_code, duration_ms=result.duration_ms
        )
