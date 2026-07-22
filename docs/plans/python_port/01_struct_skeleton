# Python Port Plan — Step 01 (Struct Skeleton)

## Context

Source: `week1_baseline/ruby/01_struct_skeleton` (Ruby gem `boukensha`, step 1 of the
00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/01_struct_skeleton` (initialized by copying `week1_baseline/python/00_config`).

This plan covers **only step 01 (Struct Skeleton)**. It builds upon the configuration foundation established in `python/00_config` (which has already been copied into `week1_baseline/python/01_struct_skeleton/`) by introducing core data structures (`Tool`, `Message`, and `Context`) needed to manage conversation history, tool definitions, and task execution state.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/01_struct_skeleton/README.md` | Design doc detailing `Tool`, `Message`, and `Context` structures and expected example output |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha.rb` | Top-level require re-exporting `Config`, `Player`, `Tool`, `Message`, `Context` |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/tool.rb` | `Boukensha::Tool` struct (`name`, `description`, `parameters`, `block`) with string representation |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/message.rb` | `Boukensha::Message` struct (`role`, `content`, `tool_use_id`) with string representation |
| `week1_baseline/ruby/01_struct_skeleton/lib/boukensha/context.rb` | `Boukensha::Context` class (`task`, `system`, `messages`, `tools`) with tool registration & message tracking |
| `week1_baseline/ruby/01_struct_skeleton/examples/example.rb` | Smoke test / reference for input/output ordering |
| `week1_baseline/bin/ruby/01_struct_skeleton` | Bash wrapper that runs the Ruby smoke test |

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only reference.

## Current State & Key Considerations

1. **Pre-existing Base (from Step 00):**
   - The contents of `week1_baseline/python/00_config` have already been copied to `week1_baseline/python/01_struct_skeleton`.
   - `config.py`, `tasks/base.py`, `tasks/player.py`, `prompts/system.md`, `requirements.txt`, `.python-version`, and `.venv` are already in place and do not need to be ported from scratch.
2. **New Work Required for Step 01:**
   - Only the new components introduced in Ruby's step 01 need to be ported: `tool.py`, `message.py`, `context.py`, updating `boukensha/__init__.py`, updating `examples/example.py`, updating `README.md`, and creating `bin/python/01_struct_skeleton`.

## Decisions

1. **Python Data Structures:**
   - `Tool` and `Message` are implemented using `@dataclass` from standard library `dataclasses`.
   - `Context` is implemented as a standard Python class with typed list and dict storage for messages and tools.
2. **String Formatting (`__str__` / `__repr__`):**
   - `Tool.__str__`: `#<Tool name={name} description={description[:41]} params={list(parameters.keys())}>` (matches Ruby's `[0..40]` slice and parameter keys).
   - `Message.__str__`: `#<Message role={role}{id_tag} content={content[:61]}...>` where `id_tag` is ` [{tool_use_id}]` when `tool_use_id` is present, matching Ruby's `[0..60]` slice.
   - `Context.__str__`: `#<Context task={task.task_name()} turns={turn_count} tools={tool_count}>`.
3. **Module Re-exports:**
   - `boukensha/__init__.py` will be updated to re-export `Tool`, `Message`, and `Context` in addition to existing `Config` and `Player`.
4. **Environment & Bin Script:**
   - Bin runner script at `week1_baseline/bin/python/01_struct_skeleton` following the pattern set by `week1_baseline/bin/python/00_config`.

## Target structure

```
week1_baseline/python/01_struct_skeleton/
  requirements.txt               (copied from 00_config)
  boukensha/
    __init__.py                  (UPDATE - add re-exports for Tool, Message, Context)
    config.py                    (copied from 00_config)
    context.py                   (NEW - implement Context class)
    message.py                   (NEW - implement Message dataclass)
    tool.py                      (NEW - implement Tool dataclass)
    tasks/                       (copied from 00_config)
      __init__.py
      base.py
      player.py
  prompts/                       (copied from 00_config)
    system.md
  examples/
    example.py                   (UPDATE - port example.rb from 01_struct_skeleton)
  README.md                      (UPDATE - document 01_struct_skeleton Python usage)
```

## File-by-file status & mapping

| Ruby source / Base | Python target | Action Required | Notes |
|---|---|---|---|
| `lib/boukensha/tool.rb` | `boukensha/tool.py` | **Create** | `@dataclass` `Tool` with fields `name: str`, `description: str`, `parameters: dict`, `block: Callable`. Implements `__str__` / `__repr__` matching Ruby's `#<Tool name=... description=... params=...>` format. |
| `lib/boukensha/message.rb` | `boukensha/message.py` | **Create** | `@dataclass` `Message` with fields `role: str`, `content: str`, `tool_use_id: Optional[str] = None`. Implements `__str__` / `__repr__` matching Ruby's `#<Message role=... [tool_use_id] content=...>` format. |
| `lib/boukensha/context.rb` | `boukensha/context.py` | **Create** | `Context` class with attributes `task`, `system`, `messages: list[Message]`, `tools: dict[str, Tool]`. Methods `register_tool(tool)`, `add_message(role, content, tool_use_id=None)`, `@property tool_count`, `@property turn_count`, and `__str__` matching `#<Context task=... turns=... tools=...>`. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | **Update** | Re-exports `Config`, `Player`, `Tool`, `Message`, `Context`. |
| `lib/boukensha/config.rb` | `boukensha/config.py` | **Copied** | Already present from `python/00_config`. No changes needed. |
| `lib/boukensha/tasks/*` | `boukensha/tasks/*` | **Copied** | Already present from `python/00_config`. No changes needed. |
| `prompts/system.md` | `prompts/system.md` | **Copied** | Already present from `python/00_config`. No changes needed. |
| `examples/example.rb` | `examples/example.py` | **Update** | Update smoke test constructing `Config`, `Context`, registering `move` tool, adding messages, and printing formatted representation matching Ruby step 01 output. |
| `Gemfile` / `Gemfile.lock` | `requirements.txt` | **Copied** | Already present from `python/00_config`. |
| `README.md` | `README.md` | **Update** | Translate Ruby step 01 README documentation for Python context. |
| `bin/ruby/01_struct_skeleton` | `bin/python/01_struct_skeleton` | **Create** | Bash wrapper initializing venv (if needed), loading requirements, and executing `python examples/example.py`. |

## Bin Script Runner (`week1_baseline/bin/python/01_struct_skeleton`)

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/01_struct_skeleton"

if command -v uv >/dev/null 2>&1 && PYTHON_BIN="$(uv python find 3.14 2>/dev/null)"; then
  :
else
  PYTHON_BIN="$(command -v python3)"
fi

if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
python examples/example.py
```

## Acceptance criteria

- `python examples/example.py` produces matching structure and ordering of output lines as `bundle exec ruby examples/example.rb` when run against the same configuration/environment.
- `from boukensha import Config, Player, Tool, Message, Context` imports cleanly.
- Executing `./week1_baseline/bin/python/01_struct_skeleton` runs cleanly and displays the expected output.
- No code under `week1_baseline/ruby/01_struct_skeleton` is modified.

## Not part of this plan

- Steps 02–12 (Tool Registry, API Client, LLM Integration, etc.).
