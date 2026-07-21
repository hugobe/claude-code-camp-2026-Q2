#!/usr/bin/env python3
"""
Interactive driver for the MUD-playing subagents, using the Claude Agent
SDK's programmatic AgentDefinition instead of the filesystem-based
`.claude/agents/*.md` discovery that Claude Code normally uses.

Where the earlier variant of this example (03a_subagent_sdk) relies on
Claude Code auto-discovering `.claude/agents/play-mud-dummy.md` and
`play-mud-smarty.md` from disk (triggered by `setting_sources` including
"project"), this script builds the same two subagents itself: it reads
their prompt text from plain markdown files under `agents/` (a location
Claude Code's own filesystem discovery does NOT scan) and registers them
directly via `ClaudeAgentOptions(agents=...)`. `setting_sources=[]` is
passed as well, so no filesystem agent discovery happens at all -- the
subagents that exist are exactly, and only, the ones built by
`load_agents()` below.

scripts/mud.py and scripts/memory.py are unchanged -- only the
*definition* of the subagents moved off Claude Code's auto-discovery
path, not the tools those subagents call.

Usage:
    python3 scripts/run_agent.py

Type a request at the `>` prompt (e.g. "play as dummy and look around",
"as smarty, reach level 3"); type `exit` or Ctrl-D to quit. Requires
`ANTHROPIC_API_KEY` in the environment and `claude-agent-sdk` installed
(see requirements.txt).
"""
import asyncio
import os
import re
import sys
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TaskUpdatedMessage,
    TERMINAL_TASK_STATUSES,
    TextBlock,
    ToolUseBlock,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"

FRONTMATTER_RE = re.compile(r"^---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)$", re.DOTALL)
DESCRIPTION_RE = re.compile(r"^description:\s*(?P<description>.*)$", re.MULTILINE)


def load_agent_definition(md_path: Path) -> AgentDefinition:
    """Parse one agents/*.md file (frontmatter `description:` + markdown
    body) into an AgentDefinition. This is our own explicit read of a
    known file path -- not the CLI's automatic directory scan -- which is
    what makes `agents/` safe to use for this without re-triggering
    filesystem subagent discovery."""
    text = md_path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{md_path} is missing the expected '---' frontmatter block")
    description_match = DESCRIPTION_RE.search(match.group("frontmatter"))
    if not description_match:
        raise ValueError(f"{md_path} frontmatter has no 'description:' field")
    return AgentDefinition(
        description=description_match.group("description").strip(),
        prompt=match.group("body").strip("\n"),
        model="inherit",
    )


def load_agents() -> dict[str, AgentDefinition]:
    return {
        "play-mud-dummy": load_agent_definition(AGENTS_DIR / "play-mud-dummy.md"),
        "play-mud-smarty": load_agent_definition(AGENTS_DIR / "play-mud-smarty.md"),
    }


def build_options(agents: dict[str, AgentDefinition]) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        agents=agents,
        # Empty list = no filesystem setting sources at all, so nothing
        # under .claude/ (agent or otherwise) is auto-loaded -- `agents`
        # above is the only source of subagents.
        setting_sources=[],
        cwd=PROJECT_ROOT,
    )


async def print_message(msg) -> None:
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(block.text)
            elif isinstance(block, ToolUseBlock):
                print(f"  [tool: {block.name}]")
    elif isinstance(msg, TaskStartedMessage):
        print(f"  [task {msg.task_id[:8]} started: {msg.description}]")
    elif isinstance(msg, TaskProgressMessage):
        print(
            f"  [task {msg.task_id[:8]} progress: {msg.description} "
            f"(tools used: {msg.usage['tool_uses']})]"
        )
    elif isinstance(msg, TaskNotificationMessage):
        print(f"  [task {msg.task_id[:8]} {msg.status}: {msg.summary}]")
    elif isinstance(msg, TaskUpdatedMessage):
        status = msg.status or msg.patch.get("status")
        if status in TERMINAL_TASK_STATUSES:
            print(f"  [task {msg.task_id[:8]} {status}]")
    elif isinstance(msg, ResultMessage) and msg.total_cost_usd:
        print(f"  (cost: ${msg.total_cost_usd:.4f})")


async def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Warning: ANTHROPIC_API_KEY is not set in the environment.", file=sys.stderr)

    agents = load_agents()
    options = build_options(agents)
    print("Registered subagents (via AgentDefinition, loaded from agents/*.md by our own code,")
    print("not Claude Code's filesystem auto-discovery):", ", ".join(agents))
    print("Type a request (e.g. \"play as dummy, look around\"), or `exit`/Ctrl-D to quit.\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                task = input("> ").strip()
            except EOFError:
                print()
                break
            if not task:
                continue
            if task.lower() in ("exit", "quit"):
                break

            await client.query(task)
            async for msg in client.receive_response():
                await print_message(msg)


if __name__ == "__main__":
    asyncio.run(main())
