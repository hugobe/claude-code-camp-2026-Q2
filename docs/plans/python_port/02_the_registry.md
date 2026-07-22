# Python Port Plan — Step 02 (The Registry)

## Context

Source: `week1_baseline/ruby/02_the_registry` (Ruby gem `boukensha`, step 2 of the 00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).  
Target: `week1_baseline/python/02_the_registry` (currently contains step 01 code and needs to be updated with step 02 changes).

This plan covers **only step 02 (The Tool Registry)**. It builds upon the data structures (`Tool`, `Message`, `Context`) introduced in step 01 by adding a `Registry` class and an `UnknownToolError` exception to handle tool registration and dispatching.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/02_the_registry/README.md` | Design doc detailing `Registry`, `UnknownToolError`, tool dispatching flow, and expected output |
| `week1_baseline/ruby/02_the_registry/lib/boukensha.rb` | Top-level require loading `config`, `player`, `tool`, `message`, `context`, `errors`, and `registry` |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/errors.rb` | `Boukensha::UnknownToolError` exception definition |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/registry.rb` | `Boukensha::Registry` class — registers tools on `Context` and dispatches tool execution calls |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/context.rb` | `Boukensha::Context` class (`task`, `system`, `messages`, `tools`) |
| `week1_baseline/ruby/02_the_registry/lib/boukensha/tool.rb` | `Boukensha::Tool` struct |
| `week1_baseline/ruby/02_the_registry/examples/example.rb` | Smoke test / reference for tool registration, tool dispatching, and error handling |
| `week1_baseline/bin/ruby/02_the_registry` | Bash wrapper that runs the Ruby step 02 smoke test |

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only reference.

## Current State & Key Considerations

1. **Pre-existing Base in Target Directory:**
   - `week1_baseline/python/02_the_registry` currently contains copied code from `01_struct_skeleton` (`config.py`, `context.py`, `message.py`, `tool.py`, `tasks/`, `prompts/`, `requirements.txt`, `.python-version`, `.venv`).
   - `README.md` in `python/02_the_registry` currently still has the header and contents of `01 · Struct Skeleton`.
   - `examples/example.py` in `python/02_the_registry` currently runs the step 01 example (direct `ctx.register_tool` call without `Registry` or `dispatch`).

2. **New Work Required for Step 02:**
   - Create `boukensha/errors.py`: Custom `UnknownToolError` exception.
   - Create `boukensha/registry.py`: `Registry` class with `tool(...)` registration and `dispatch(...)` execution methods.
   - Update `boukensha/__init__.py`: Re-export `Registry` and `UnknownToolError`.
   - Update `examples/example.py`: Replicate step 02 Ruby example (registering tools via `registry.tool`, dispatching `shout` and `move`, catching `UnknownToolError` on `flee`).
   - Update `README.md`: Document step 02 Python usage and mechanics.
   - Create `week1_baseline/bin/python/02_the_registry`: Executable bash runner script.

## Decisions & Architectural Mapping

1. **Error Handling (`UnknownToolError`):**
   - Subclasses Python's built-in `Exception`:
     ```python
     class UnknownToolError(Exception):
         """Raised when attempting to dispatch an unregistered tool."""
         pass
     ```

2. **Registry Class Design (`Registry`):**
   - Receives a `Context` instance upon initialization:
     ```python
     class Registry:
         def __init__(self, context: Context):
             self.context = context
     ```
   - **`tool(...)` method:**
     Registers a new `Tool` onto `self.context` and returns the `Tool` instance. Accepts `name`, `description`, `parameters` (dict), and `block` (Callable).
     ```python
     def tool(
         self,
         name: str,
         description: str,
         parameters: dict | None = None,
         block: Callable | None = None,
     ) -> Tool:
         if parameters is None:
             parameters = {}
         t = Tool(name=str(name), description=description, parameters=parameters, block=block)
         self.context.register_tool(t)
         return t
     ```
   - **`dispatch(...)` method:**
     Looks up tool by string name in `self.context.tools`. Raises `UnknownToolError` if not found. Invokes `tool.block` passing keyword arguments unpacked from `args`:
     ```python
     def dispatch(self, name: str, args: dict | None = None) -> Any:
         tool = self.context.tools.get(str(name))
         if not tool:
             raise UnknownToolError(f"No tool registered as '{name}'")
         kwargs = args if args is not None else {}
         return tool.block(**kwargs)
     ```
   - *Key difference from Ruby:* Ruby converts string keys to symbols (`args.transform_keys(&:to_sym)`). In Python, keyword arguments in `**kwargs` are native string keys matching the parameter names defined in the tool callable (e.g. `lambda direction: ...` or `def shout(message): ...`).

3. **Module Re-exports:**
   - Update `boukensha/__init__.py` to expose `Registry` and `UnknownToolError`:
     `from .errors import UnknownToolError`  
     `from .registry import Registry`  
     `__all__ = ["Config", "Player", "Tool", "Message", "Context", "Registry", "UnknownToolError"]`

4. **Environment & Bin Script:**
   - Create bash runner script at `week1_baseline/bin/python/02_the_registry` following the structure of `week1_baseline/bin/python/01_struct_skeleton`.

## Target structure

```
week1_baseline/python/02_the_registry/
  requirements.txt               (copied from step 01)
  boukensha/
    __init__.py                  (UPDATE - add Registry, UnknownToolError exports)
    config.py                    (copied from step 01)
    context.py                   (copied from step 01)
    errors.py                    (NEW - implement UnknownToolError exception)
    message.py                   (copied from step 01)
    registry.py                  (NEW - implement Registry class)
    tool.py                      (copied from step 01)
    tasks/                       (copied from step 01)
      __init__.py
      base.py
      player.py
  prompts/                       (copied from step 01)
    system.md
  examples/
    example.py                   (UPDATE - port step 02 example.rb)
  README.md                      (UPDATE - document step 02 Python usage)
```

## File-by-file status & mapping

| Ruby source / Base | Python target | Action Required | Notes |
|---|---|---|---|
| `lib/boukensha/errors.rb` | `boukensha/errors.py` | **Create** | Custom exception `class UnknownToolError(Exception): pass`. |
| `lib/boukensha/registry.rb` | `boukensha/registry.py` | **Create** | `Registry` class with `__init__(context)`, `tool(...)` registration method, and `dispatch(name, args)` dispatch method raising `UnknownToolError` if tool missing. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | **Update** | Re-exports `Config`, `Player`, `Tool`, `Message`, `Context`, `Registry`, `UnknownToolError`. |
| `lib/boukensha/context.rb` | `boukensha/context.py` | **Copied** | Already present from step 01. No changes needed. |
| `lib/boukensha/tool.rb` | `boukensha/tool.py` | **Copied** | Already present from step 01. No changes needed. |
| `lib/boukensha/config.rb` | `boukensha/config.py` | **Copied** | Already present from step 01. No changes needed. |
| `lib/boukensha/tasks/*` | `boukensha/tasks/*` | **Copied** | Already present from step 01. No changes needed. |
| `prompts/system.md` | `prompts/system.md` | **Copied** | Already present from step 01. No changes needed. |
| `examples/example.rb` | `examples/example.py` | **Update** | Update smoke test script to register `move` and `shout` tools via `Registry`, dispatch calls with string arguments dict, print results, and catch `UnknownToolError` when dispatching `flee`. |
| `README.md` | `README.md` | **Update** | Update README to reflect Step 02 (The Tool Registry), detailing `Registry`, `UnknownToolError`, Python example snippets, and run instructions. |
| `bin/ruby/02_the_registry` | `bin/python/02_the_registry` | **Create** | Bash runner script initializing venv, installing dependencies, and running `python examples/example.py`. |

## Bin Script Runner (`week1_baseline/bin/python/02_the_registry`)

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/02_the_registry"

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

- `python examples/example.py` in `week1_baseline/python/02_the_registry` produces matching structure and ordering of output lines as `bundle exec ruby examples/example.rb` in `week1_baseline/ruby/02_the_registry`.
- `from boukensha import Config, Player, Tool, Message, Context, Registry, UnknownToolError` imports cleanly.
- `registry.dispatch("shout", {"message": "dragon spotted"})` returns `"DRAGON SPOTTED"`.
- `registry.dispatch("move", {"direction": "north"})` returns `"You move north into a torch-lit corridor."`.
- `registry.dispatch("flee")` raises `UnknownToolError` with message `"No tool registered as 'flee'"`.
- Executing `./week1_baseline/bin/python/02_the_registry` runs cleanly and displays expected output.
- No code under `week1_baseline/ruby/02_the_registry` is modified.

## Not part of this plan

- Steps 03–12 (API Client, LLM Integration, Tool Execution Loops, etc.).
