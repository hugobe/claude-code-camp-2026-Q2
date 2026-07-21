# Plan: replace filesystem-discovered subagents with SDK `AgentDefinition`

## What "filesystem loading" means today

Right now `03b_subagent_sdk` has no driver code of its own. The two subagents
(`play-mud-dummy`, `play-mud-smarty`) exist only as
`.claude/agents/*.md` files. When Claude Code (or the Agent SDK with
`setting_sources` including `"project"`) starts in this directory, it
auto-discovers those files from disk, parses the YAML frontmatter
(`name`, `description`) and the markdown body (the system prompt), and
registers them as subagents. That auto-discovery *is* "the code that uses
a filesystem to load the subagents" — it's built into the CLI/SDK, not
something in this repo, which is why there's nothing to edit yet: this
plan is about adding a small Python driver that opts out of it.

Confirmed from the SDK source (`claude_agent_sdk/types.py`) and the SDK's
own examples (`examples/agents.py`, `examples/filesystem_agents.py`,
`examples/setting_sources.py`):

- `ClaudeAgentOptions.agents: dict[str, AgentDefinition]` — lets you
  register subagents programmatically instead of via `.claude/agents/`.
- `AgentDefinition(description, prompt, tools=None, model=None, ...)` —
  the programmatic equivalent of one `.md` file's frontmatter + body.
- `ClaudeAgentOptions.setting_sources: list["user"|"project"|"local"]` —
  controls whether filesystem config (including `.claude/agents/*.md`)
  gets loaded at all. `setting_sources=["project"]` is what causes the
  `.md` files to be picked up; `setting_sources=[]` turns that off, so
  only the subagents passed in `agents=` exist.

## Target change

1. **New driver script**: `scripts/run_agent.py` (Python, matching the
   existing `mud.py`/`memory.py` style — stdlib `argparse` + `anyio`).
   - Imports `AgentDefinition`, `ClaudeAgentOptions`, `ClaudeSDKClient`
     from `claude_agent_sdk`.
   - Builds one `AgentDefinition` per character:
     ```python
     AgentDefinition(
         description="<same text as the current frontmatter description>",
         prompt="<same body text as the current .md file>",
         model="inherit",
     )
     ```
   - Registers both:
     ```python
     options = ClaudeAgentOptions(
         agents={
             "play-mud-dummy": AgentDefinition(...),
             "play-mud-smarty": AgentDefinition(...),
         },
         setting_sources=[],   # <- the actual "stop reading .claude/agents/*.md" switch
         cwd=PROJECT_ROOT,
     )
     ```
   - Runs a top-level session (`ClaudeSDKClient`) with a user-supplied
     task (CLI arg or interactive prompt), the same way you'd type a
     request at the top level today — the top-level model still picks
     which subagent to delegate to via the `Agent` tool, it just now
     finds them in `options.agents` instead of on disk.
   - `scripts/mud.py` / `scripts/memory.py` are untouched — they remain
     filesystem-based CLI tools the *subagents* shell out to. Only the
     subagent *definitions* move off the filesystem, not the whole
     example.

2. **Retire `.claude/agents/*.md`** once their content has been ported,
   so the directory can't accidentally still get picked up if someone
   runs this with default `setting_sources` (i.e. omits the option
   entirely). Content is copied into the new script first, then the old
   files are deleted — not left around silently unused.

3. **Dependency**: `claude-agent-sdk` isn't installed in this
   environment yet (checked — not present locally). Plan includes adding
   a `requirements.txt` (or `pyproject.toml`, matching whatever the rest
   of the repo prefers) pinning it, and installing it as part of this
   change so the script is actually runnable, not just written.

## Decisions (final, superseding an earlier "inline Python string" draft)

1. **Prompt text lives in plain markdown files**, read at startup —
   *not* inlined as Python string constants. The two files that used to
   be auto-discovered from `.claude/agents/*.md` were moved (same
   frontmatter + body format) to `agents/play-mud-dummy.md` and
   `agents/play-mud-smarty.md` — a location Claude Code's own filesystem
   settings loader does not scan. `run_agent.py` parses each file's
   `description:` frontmatter field and markdown body itself
   (`load_agent_definition()`) and builds an `AgentDefinition` from it.
   This keeps prompt prose editable as plain markdown while making the
   *loading* explicit application code instead of implicit CLI discovery.
2. **`run_agent.py` is interactive** — one `ClaudeSDKClient` session,
   a `while True: input("> ")` loop, `client.query()` +
   `client.receive_response()` per turn, `exit`/`quit`/Ctrl-D to stop.

## Implementation (done)

1. Moved `.claude/agents/play-mud-dummy.md` → `agents/play-mud-dummy.md`,
   `.claude/agents/play-mud-smarty.md` → `agents/play-mud-smarty.md`;
   removed the now-empty `.claude/agents/` and `.claude/` directories.
   Filesystem auto-discovery has nothing left to find even with default
   `setting_sources`.
2. Wrote `scripts/run_agent.py`:
   - `load_agent_definition(path)` — regex-parses one `agents/*.md`
     file's frontmatter `description:` + body, returns an
     `AgentDefinition(description=..., prompt=..., model="inherit")`.
   - `load_agents()` — returns `{"play-mud-dummy": ..., "play-mud-smarty": ...}`.
   - `build_options(agents)` — `ClaudeAgentOptions(agents=agents, setting_sources=[], cwd=PROJECT_ROOT)`.
   - `main()` — interactive loop over one `ClaudeSDKClient` session.
3. Added `requirements.txt` pinning `claude-agent-sdk>=0.2.123`.
4. Added `.gitignore` for `.venv/`, `__pycache__/`, `*.pyc`.

## Verification performed

- `claude-agent-sdk` requires Python ≥3.10; the system default `python3`
  is Xcode's bundled 3.9.6. Used `uv venv --python 3.13 .venv` +
  `uv pip install` to get a working environment (`.venv/`) — this is
  local tooling, not committed.
- `AgentDefinition`/`ClaudeAgentOptions` signature inspected on the
  actually-installed SDK version to confirm `agents` and
  `setting_sources` fields exist as expected.
- Reconstructed both `AgentDefinition`s via `load_agents()` and diffed
  their `.description`/`.prompt` against the original `.md` files
  byte-for-byte — exact match (1055/911 char descriptions,
  27149/28225 char prompts).
- **Live end-to-end run**: this sandbox already has Claude Code CLI
  credentials configured, so a real `ClaudeSDKClient` session was run
  against `build_options(load_agents())`. Asked the model (without
  invoking any tool) to list every subagent name + description visible
  to it via the `Agent` tool — `play-mud-dummy` and `play-mud-smarty`
  both appeared with their correct descriptions, confirming the
  SDK-registered agents are live and `.claude/agents/*.md` is no longer
  involved (it no longer exists in this project).
