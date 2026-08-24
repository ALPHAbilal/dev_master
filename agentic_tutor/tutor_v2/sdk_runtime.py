"""Claude Agent SDK boundary with closed, wakeup-scoped tutor tools.

The module deliberately has no import-time SDK dependency.  The deterministic
tool gateway and launch specification are testable with plain Python; only a
real wakeup imports ``claude_agent_sdk``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import TutorConfig
from .errors import CapabilityUnavailableError, ValidationError
from .packets import CapabilityPolicy
from .services import EventRecorder, WorkspaceService


DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_BUILTINS_BLOCKED = (
    "Bash", "Skill", "Task", "Agent", "Write", "Edit", "MultiEdit",
    "NotebookEdit", "SlashCommand",
)


class AgentSdkUnavailableError(RuntimeError):
    """The optional real runtime was requested without its project dependency."""


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """Explicit product choices for the local Claude runtime."""

    model: str = DEFAULT_MODEL
    max_turns: int | None = None
    max_budget_usd: float | None = None


@dataclass(frozen=True, slots=True)
class LaunchSpec:
    """SDK-independent proof of exactly what one wakeup may access."""

    model: str
    prompt: str
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]
    cwd: Path
    max_turns: int | None
    max_budget_usd: float | None


class TutorToolGateway:
    """Executes only capabilities contained in one already-validated wakeup."""

    def __init__(
        self, config: TutorConfig, workspace: WorkspaceService, events: EventRecorder,
        wakeup: dict[str, Any], policy: CapabilityPolicy | None = None,
    ) -> None:
        self.config = config
        self.workspace = workspace
        self.events = events
        self.wakeup = wakeup
        self.policy = policy or CapabilityPolicy()
        self.step = str(wakeup["step"])
        self._granted = frozenset(str(item) for item in wakeup["capabilities"])

    def call(self, capability: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one read-only tutor capability or reject it with no side effect."""
        self._require(capability)
        if capability == "read_code_slice":
            self._empty(arguments, capability)
            return dict(self.wakeup["context"]["source"])
        if capability == "read_workspace":
            self._empty(arguments, capability)
            workspace, content = self.workspace.read()
            return {
                "document_id": workspace.document_id, "display_name": workspace.display_name,
                "revision": workspace.revision, "revision_hash": workspace.revision_hash,
                "content": content,
            }
        if capability == "read_axis_evidence":
            self._empty(arguments, capability)
            return dict(self.wakeup["context"]["axis"])
        if capability == "read_probe_history":
            self._empty(arguments, capability)
            return {"probes": list(self.wakeup["context"].get("recent_probes", []))}
        if capability == "read_transcript":
            self._empty(arguments, capability)
            return {"current_evidence": self.wakeup["context"].get("current_evidence", {})}
        if capability == "read_turn_context":
            self._empty(arguments, capability)
            return dict(self.wakeup["context"])
        if capability == "read_event_trace":
            self._empty(arguments, capability)
            return {"events": list(self.wakeup["context"].get("events", []))}
        if capability == "search_repository":
            query = arguments.get("query")
            if set(arguments) != {"query"} or not isinstance(query, str) or not query.strip():
                raise ValidationError("search_repository requires exactly one non-blank query")
            return {"matches": self._search_repository(query.strip())}
        raise CapabilityUnavailableError(f"{capability} has no SDK tool handler")

    def _require(self, capability: str) -> None:
        self.policy.require(self.step, capability)
        if capability not in self._granted:
            raise CapabilityUnavailableError(f"{capability} was not granted in this wakeup")

    @staticmethod
    def _empty(arguments: dict[str, Any], capability: str) -> None:
        if arguments:
            raise ValidationError(f"{capability} takes no arguments")

    def _search_repository(self, query: str) -> list[dict[str, Any]]:
        if self.config.codebase_root is None:
            raise ValidationError("search_repository needs a configured codebase root")
        root = self.config.codebase_root.resolve()
        matches: list[dict[str, Any]] = []
        for path in root.rglob("*"):
            if len(matches) >= 50:
                break
            if not path.is_file() or path.is_symlink():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.relative_to(root).as_posix()
            for number, line in enumerate(lines, start=1):
                if query.casefold() in line.casefold():
                    matches.append({"file": relative, "line": number, "text": line})
                    if len(matches) >= 50:
                        break
        return matches


class ClaudeAgentAdapter:
    """Creates a fresh, closed SDK turn; it owns no routing or state mutation."""

    def __init__(
        self, config: TutorConfig, workspace: WorkspaceService, events: EventRecorder,
        settings: RuntimeSettings | None = None, policy: CapabilityPolicy | None = None,
    ) -> None:
        self.config = config
        self.workspace = workspace
        self.events = events
        self.settings = settings or RuntimeSettings()
        self.policy = policy or CapabilityPolicy()

    def launch_spec(self, wakeup: dict[str, Any], instruction: str) -> LaunchSpec:
        capabilities = tuple(str(value) for value in wakeup["capabilities"])
        expected = self.policy.for_step(str(wakeup["step"]))
        if capabilities != expected:
            raise ValidationError("wakeup capabilities do not match the step policy")
        if not instruction.strip():
            raise ValidationError("agent instruction is required")
        if self.config.codebase_root is None:
            raise ValidationError("Claude runtime needs a configured codebase root")
        return LaunchSpec(
            model=self.settings.model,
            prompt=json.dumps(wakeup, sort_keys=True),
            allowed_tools=tuple(f"mcp__tutor__{name}" for name in capabilities),
            disallowed_tools=_BUILTINS_BLOCKED,
            cwd=self.config.codebase_root.resolve(),
            max_turns=self.settings.max_turns,
            max_budget_usd=self.settings.max_budget_usd,
        )

    def build_options(self, wakeup: dict[str, Any], instruction: str) -> Any:
        """Create real SDK options only when a caller starts an actual model wakeup."""
        spec = self.launch_spec(wakeup, instruction)
        try:
            from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
        except ImportError as error:  # pragma: no cover - depends on local setup
            raise AgentSdkUnavailableError(
                "claude-agent-sdk is not installed in this interpreter; use agentic_tutor/.venv"
            ) from error
        gateway = TutorToolGateway(self.config, self.workspace, self.events, wakeup, self.policy)
        server = create_sdk_mcp_server("tutor", tools=self._sdk_tools(gateway))
        return ClaudeAgentOptions(
            system_prompt=instruction,
            cwd=spec.cwd,
            model=spec.model,
            max_turns=spec.max_turns,
            max_budget_usd=spec.max_budget_usd,
            allowed_tools=list(spec.allowed_tools),
            disallowed_tools=list(spec.disallowed_tools),
            mcp_servers={"tutor": server},
            setting_sources=[],
            permission_mode="dontAsk",
        )

    async def run(self, wakeup: dict[str, Any], instruction: str) -> list[str]:
        """Run one bounded-by-contract SDK wakeup and return its text blocks only."""
        options = self.build_options(wakeup, instruction)
        try:
            from claude_agent_sdk import AssistantMessage, TextBlock, query
        except ImportError as error:  # pragma: no cover - dependency error above normally wins
            raise AgentSdkUnavailableError("claude-agent-sdk is unavailable") from error
        text: list[str] = []
        async for message in query(prompt=json.dumps(wakeup, sort_keys=True), options=options):
            if isinstance(message, AssistantMessage):
                text.extend(
                    block.text.strip() for block in message.content
                    if isinstance(block, TextBlock) and block.text.strip()
                )
        return text

    @staticmethod
    def _sdk_tools(gateway: TutorToolGateway) -> list[Any]:
        try:
            from claude_agent_sdk import tool
        except ImportError as error:  # pragma: no cover - called by build_options
            raise AgentSdkUnavailableError("claude-agent-sdk is unavailable") from error
        tools: list[Any] = []
        for capability in gateway.wakeup["capabilities"]:
            schema: dict[str, type] = {"query": str} if capability == "search_repository" else {}

            @tool(capability, f"Tutor capability: {capability}. Use only for its stated scoped purpose.", schema)
            async def handler(arguments: dict[str, Any], _capability: str = capability) -> dict[str, Any]:
                try:
                    result = gateway.call(_capability, arguments)
                    return {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}]}
                except (CapabilityUnavailableError, ValidationError) as error:
                    return {"content": [{"type": "text", "text": f"REFUSED: {error}"}], "is_error": True}

            tools.append(handler)
        return tools
