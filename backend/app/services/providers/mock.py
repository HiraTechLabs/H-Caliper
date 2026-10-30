"""Deterministic provider used exclusively by the automated test-suite.

The adapter is labelled ``TEST ONLY`` in the UI.  It is never presented as proof
of real model connectivity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.core.enums import Capability, ProviderStatus
from app.services.providers.base import (
    AgentRunResult,
    BaseProvider,
    ProviderHealth,
)


class MockProvider(BaseProvider):
    type = "mock"
    capabilities = {
        Capability.CHAT,
        Capability.AGENT,
        Capability.MODEL_DISCOVERY,
        Capability.FILE_EDITING,
    }

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            connected=True, status=ProviderStatus.HEALTHY.value, models=["mock-model"]
        )

    async def list_models(self) -> List[str]:
        return ["mock-model"]

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        prompt = "\n".join(m.get("content", "") for m in messages)
        if "REVIEW_SCHEMA" in prompt:
            return json.dumps(
                {
                    "decision": "ACCEPTED",
                    "reason": "Mock review: changes match the plan and mandatory gates.",
                    "evidence": {"mock": True},
                    "violated_principles": [],
                    "required_corrections": [],
                    "severity": "MINOR",
                }
            )
        if "DOCUMENTATION_SCHEMA" in prompt:
            return json.dumps(
                {
                    "summary": "Mock documentation summary",
                    "content_md": "# Task Documentation\n\nMock documentation.",
                    "files": [],
                    "decisions": ["Mock decision"],
                    "dependencies": [],
                }
            )
        if "PLAN_SCHEMA" in prompt:
            task = re.search(r"TASK_TITLE:\s*(.+)", prompt)
            title = task.group(1).strip() if task else "Implement requested change"
            return json.dumps(
                {
                    "task_understanding": title,
                    "business_objective": "Deliver the requested behaviour safely.",
                    "technical_objective": "Implement and verify the change.",
                    "relevant_principles": ["clean-code.md", "test.md"],
                    "existing_analysis": "Mock provider analysis.",
                    "files_to_create": ["HCALIPER_TASK.md"],
                    "files_to_modify": [],
                    "files_not_to_modify": [".env"],
                    "steps": ["Create HCALIPER_TASK.md", "Run tests"],
                    "required_tests": ["pytest"],
                    "security_considerations": ["No secrets"],
                    "performance_considerations": ["Negligible"],
                    "breaking_changes": [],
                    "dependencies": [],
                    "acceptance_criteria": ["HCALIPER_TASK.md exists"],
                    "rollback": "Delete HCALIPER_TASK.md",
                    "summary": title,
                }
            )
        return "MOCK_COMPLETION_OK"

    async def run_agent(
        self, *, workspace: str, prompt: str, model: str, timeout: int
    ) -> AgentRunResult:
        root = Path(workspace).resolve()
        changes = self.config.get("mock_changes")
        if not changes:
            changes = [
                {
                    "path": "HCALIPER_TASK.md",
                    "content": "# H-Caliper mock execution\n\nCreated by the deterministic test provider.\n",
                }
            ]
        written: List[str] = []
        for change in changes:
            rel = Path(str(change.get("path", "")))
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("Refusing unsafe mock path")
            target = (root / rel).resolve()
            if root not in target.parents and target != root:
                raise ValueError("Refusing mock path outside workspace")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(change.get("content", "")), encoding="utf-8")
            written.append(str(rel))
        return AgentRunResult(
            output=f"Mock agent wrote: {', '.join(written)}",
            exit_code=0,
            duration_ms=1,
            changed_files=written,
            metadata={"mock": True},
        )
