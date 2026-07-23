# Python Port Plan — Step 07 (The Run DSL)

## Context

Source: `week1_baseline/ruby/07_the_run_dsl` (Ruby gem `boukensha`, step 7 of
the 00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/07_the_run_dsl` (already seeded as a copy of
`python/06_the_logger`, onto which this step's delta is applied).

This plan covers **only step 07**. It builds on step 06's `Logger`-integrated
`Agent` loop and the full manual wiring shown in step 06's example. What's new:
a single top-level entry point, `Boukensha.run`, that wires up `Context`,
`Registry`, a backend, `PromptBuilder`, `Client`, `Logger`, and `Agent`
internally, plus a small `RunDSL` host object that lets a caller register
tools inline inside the `run` call instead of driving the registry directly.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/07_the_run_dsl/README.md` | Design doc: the `Boukensha.run` option table, before/after code comparison against step 5/6's manual wiring, and the example's expected behavior. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha.rb` | Adds `Boukensha.run(task:, system:, model:, backend:, api_key:, ollama_host:, lm_studio_host:, log:, max_output_tokens:, &block)` — resolves task/config defaults, builds `Context`/`Registry`, evaluates the DSL block, picks and constructs the backend, then builds `PromptBuilder`/`Client`/`Logger`/`Agent` and runs the turn. Adds `require_relative "boukensha/run_dsl"`. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/run_dsl.rb` | **New file.** `Boukensha::RunDSL` — tiny host object `self` becomes inside the `run` block via `instance_eval`. Exposes only `tool(name, description:, parameters: {}, &block)`, which delegates straight to `Registry#tool`. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/logger.rb` | Adds `turn(n:)` (a lightweight per-turn log event, distinct from the existing `turn_end`) and a `subscribe(&block)` pub/sub hook — `write_log` now also calls every subscriber with the raw event hash. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/errors.rb` | Adds `LoopError < StandardError`. **Already present in the Python target** (see below) — no action needed. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/config.rb` | Adds `mud_host`/`mud_port`/`mud_username`/`mud_password` dig-based accessors, plus a purely cosmetic `if/then` reformat of `load_env`. **Already present in the Python target** — no action needed. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/context.rb` | Whitespace-only realignment of `initialize`'s ivar assignments (and a dropped trailing newline). No functional change — no Python action needed. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/agent.rb` | **Unchanged from step 06** (`diff` is empty). No Python action needed. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/registry.rb` | **Unchanged from step 06.** No Python action needed. |
| `week1_baseline/ruby/07_the_run_dsl/lib/boukensha/tasks/*.rb` | **Unchanged from step 06.** No Python action needed. |
| `week1_baseline/ruby/07_the_run_dsl/examples/example.rb` | Rewritten to use `Boukensha.run(task: ...) do ... end` instead of step 06's manual wiring — registers `read_file` and `list_directory` tools inline and prints the config before running. |
| `week1_baseline/ruby/07_the_run_dsl/Gemfile` + `Gemfile.lock` | No diff vs step 06 — no new gem added, so no `requirements.txt` change. |
| `week1_baseline/bin/ruby/07_the_run_dsl` | Bash wrapper — model for the Python equivalent (identical shape to the step 06 one, only the `cd` target changes). |

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only
reference.

## Confirmed current state of the Python target

`week1_baseline/python/07_the_run_dsl` is currently byte-for-byte identical
to `python/06_the_logger` (`diff -rq` between the two trees, ignoring
`.venv`, returns no differences).

Two pieces of this step's Ruby delta turn out to **already be present** in
the Python step 06 codebase (ported ahead of schedule in an earlier session):

| File | Status |
|---|---|
| `boukensha/errors.py` | Already defines `LoopError`, already exported from `__init__.py`. No change needed. |
| `boukensha/config.py` | Already defines `mud_host`/`mud_port`/`mud_username`/`mud_password` properties. No change needed. |

Everything else needs the delta applied:

| File | Status |
|---|---|
| `boukensha/run_dsl.py` | **Missing.** Create new file implementing `RunDSL`. |
| `boukensha/logger.py` | Present, missing `turn(n)` and the `subscribe`/notify mechanism. **Needs update.** |
| `boukensha/__init__.py` | Present. **Needs update** — add the `run(...)` function and export `RunDSL`. |
| `boukensha/context.py`, `boukensha/agent.py`, `boukensha/registry.py`, `boukensha/tasks/*.py` | Present, unchanged — no change needed (mirrors the Ruby diff being empty/cosmetic for these). |
| `examples/example.py` | Still the step 06 manual-wiring example. **Needs rewrite** to use `boukensha.run(...)`. |
| `README.md` | Still the step 06 README. **Needs rewrite** for step 07. |
| `requirements.txt` | Unchanged from step 06 (`PyYAML>=6.0`, `python-dotenv>=1.0`) — Ruby added no gem, so no new dependency here either. |
| `bin/python/07_the_run_dsl` | Missing. Must be created. |

## Decisions & architectural mapping

### 1. `RunDSL` — no `instance_eval` equivalent, so the block becomes an explicit callback

Ruby's `RunDSL.new(registry).instance_eval(&block)` re-parents `self` inside
the block so bare `tool "name", ...` calls resolve against the `RunDSL`
instance. Python has no clean, non-hacky equivalent to `instance_eval` for a
plain `def` block passed by the caller (no metaclass tricks, no `exec`).

The direct, idiomatic translation: `boukensha.run(...)` takes an optional
`configure` callable that receives the `RunDSL` instance as its one
argument, and `run()` calls `configure(dsl)` itself — the moral equivalent of
`instance_eval(&block)`, but explicit instead of implicit:

```python
def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=_read_file,
    )

result = boukensha.run(task="Read lib/boukensha.rb", configure=configure)
```

This keeps `RunDSL` itself a 1:1 structural port (a thin host object
exposing exactly one method, `tool`, that delegates to `Registry#tool`) while
avoiding Ruby-specific metaprogramming Python doesn't have:

```python
class RunDSL:
    def __init__(self, registry):
        self.registry = registry

    def tool(self, name, description, parameters=None, block=None):
        return self.registry.tool(name, description=description, parameters=parameters, block=block)
```

Note this mirrors the already-established Python convention from step 06's
`example.py`, which registers tools via `registry.tool(..., block=some_func)`
rather than a decorator — `RunDSL.tool` uses the same `block=` kwarg shape
for consistency with `Registry.tool`'s existing signature.

### 2. `Boukensha.run` → module-level `run()` function in `boukensha/__init__.py`

Ruby's `Symbols (:anthropic)` → Python `Strings ("anthropic")` per the
standing convention — `backend` is compared/branched on as a plain string,
so no `.to_sym`-equivalent is needed; `Player.provider(settings)` already
returns a string from YAML.

Signature (keyword args mirror Ruby's order and names 1:1, `&block` →
`configure=None`):

```python
def run(
    task,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    lm_studio_host="http://localhost:1234/v1",
    log=None,
    max_output_tokens=None,
    configure=None,
):
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir, default_prompts_dir=Config.PROMPTS_DIR
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)

    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if configure is not None:
        configure(RunDSL(registry))

    if backend == "anthropic":
        be = Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = Ollama(model=model, host=ollama_host)
    elif backend == "ollama_cloud":
        be = OllamaCloud(api_key=api_key, model=model)
    elif backend == "lm_studio":
        be = LmStudio(model=model, host=lm_studio_host)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', "
            "'ollama', 'ollama_cloud', or 'lm_studio'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()
```

`ArgumentError` → `ValueError` per the standing convention (unknown backend
case). `raise ... ensure logger&.close` → Python `try/finally`, matching
Ruby's guarantee that `close` always runs even if `agent.run` raises.

`__init__.py` needs a new top-level `import os` for the `*_API_KEY` env
lookups (not currently imported there).

### 3. `Logger.turn` and `Logger.subscribe`

Straight port, no idiom questions:

```python
def turn(self, n):
    self._write_log({"phase": "turn", "n": n})

def subscribe(self, callback):
    self._subscribers.append(callback)
```

`@subscribers ||= []` (lazy Ruby ivar init) → an eagerly-initialized
`self._subscribers = []` in `__init__`, since Python has no ivar-punning
equivalent and eager init is simpler/equally correct here.

`_write_log` gains one line at the end, notifying every subscriber with the
same event dict that gets written to disk:

```python
def _write_log(self, event):
    log_entry = dict(event)
    log_entry["session_id"] = self.session_id
    log_entry["at"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(log_entry) + "\n"
    self._log_file.write(line)
    self._log_file.flush()
    for subscriber in self._subscribers:
        subscriber(event)
```

Note `event` (pre-enrichment) is what's passed to subscribers, matching
Ruby's `@subscribers&.each { |s| s.call(event) }` which fires with the
original `event` hash, not the `session_id`/`at`-merged one written to disk.

Nothing in this step's `example.rb` or `README.md` actually calls
`subscribe` or `turn` — they exist on `Logger` because the Ruby source adds
them here, so the port includes them for parity, but no caller wires them up
yet.

## Target structure

```
week1_baseline/python/07_the_run_dsl/
  requirements.txt               (unchanged from step 06)
  boukensha/
    __init__.py                  (UPDATE - add run(), import os, export RunDSL)
    run_dsl.py                   (NEW - RunDSL class)
    logger.py                    (UPDATE - add turn(), subscribe(), notify in _write_log)
    config.py                    (no change - mud_* already present)
    errors.py                    (no change - LoopError already present)
    context.py                   (no change - cosmetic-only Ruby diff)
    agent.py                     (no change - empty Ruby diff)
    registry.py                  (no change - empty Ruby diff)
    tasks/                       (no change - empty Ruby diff)
    backends/                    (no change)
    client.py, message.py, prompt_builder.py, tool.py  (no change)
  prompts/
    system.md                    (no change)
  examples/
    example.py                   (REWRITE - port step 07 example.rb, using boukensha.run)
  README.md                      (REWRITE - document step 07 Python usage)
```

## File-by-file mapping

| Ruby source | Python target | Action | Notes |
|---|---|---|---|
| `lib/boukensha/run_dsl.rb` | `boukensha/run_dsl.py` | Create | `RunDSL` class, `tool()` delegates to `Registry.tool` |
| `lib/boukensha.rb` (`self.run`) | `boukensha/__init__.py` (`run()`) | Update | New module-level function; `&block` → `configure=None` callback |
| `lib/boukensha/logger.rb` (`turn`, `subscribe`) | `boukensha/logger.py` | Update | Add both methods + subscriber notification in `_write_log` |
| `lib/boukensha/errors.rb` (`LoopError`) | `boukensha/errors.py` | None | Already present |
| `lib/boukensha/config.rb` (`mud_*`) | `boukensha/config.py` | None | Already present |
| `lib/boukensha/context.rb` | `boukensha/context.py` | None | Cosmetic-only Ruby diff |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | None | No Ruby diff |
| `lib/boukensha/registry.rb` | `boukensha/registry.py` | None | No Ruby diff |
| `lib/boukensha/tasks/*.rb` | `boukensha/tasks/*.py` | None | No Ruby diff |
| `examples/example.rb` | `examples/example.py` | Rewrite | Use `boukensha.run(task=..., configure=...)` |
| `README.md` | `README.md` | Rewrite | Document `run()` options table + before/after |
| `Gemfile`/`Gemfile.lock` | `requirements.txt` | None | No gem added |
| `bin/ruby/07_the_run_dsl` | `bin/python/07_the_run_dsl` | Create | Copy of `bin/python/06_the_logger`, `cd` target changed |

## `examples/example.py` shape

Mirrors `week1_baseline/ruby/07_the_run_dsl/examples/example.rb`'s
before/after story — same task prompt, same two tools, same print ordering
(`Config: ...` header, then `run()`, then `=== FINAL RESPONSE ===`):

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parents[4] / ".boukensha"))

import boukensha

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


def _read_file(path):
    return (base_dir / path).resolve().read_text()


def _list_directory(path):
    target = (base_dir / path).resolve()
    entries = [f for f in os.listdir(target) if not f.startswith(".")]
    return ", ".join(entries)


def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=_read_file,
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=_list_directory,
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    configure=configure,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
```

(`Dir.entries` includes `.` and `..` before the `reject`; Python's
`os.listdir` never returns those, so the `.reject { start_with?(".") }` /
`if not f.startswith(".")` filters are equivalent in effect — no `.sort`
call in either version, so ordering matches whatever the OS returns, same
as Ruby.)

## Bin Script Runner (`week1_baseline/bin/python/07_the_run_dsl`)

Copy verbatim from `week1_baseline/bin/python/06_the_logger`, changing only
the `cd` target from `06_the_logger` to `07_the_run_dsl`. `chmod +x` after
creating.

## Acceptance criteria

- `python examples/example.py` (or `./week1_baseline/bin/python/07_the_run_dsl`)
  produces output in the same structure/order as
  `bundle exec ruby examples/example.rb`: header line, `Config: ...`, a blank
  line, the agent run, `=== FINAL RESPONSE ===`, then the result text.
- `from boukensha import run, RunDSL, Config, Player, Tool, Message, Context, Registry, UnknownToolError, UnsupportedModelError, ApiError, LoopError, PromptBuilder, Anthropic, OpenAI, Gemini, Ollama, OllamaCloud, LmStudio, Client, Agent, Logger, config, quiet, loud, is_quiet, debug, is_debug` imports cleanly.
- `boukensha.run(task="...")` with no `configure` callback runs a tool-less
  turn without error (mirrors Ruby's `if block` guard around
  `instance_eval`).
- `boukensha.run(task="...", backend="nonexistent")` raises `ValueError`
  with the same "Unknown backend" message shape as Ruby's `ArgumentError`.
- A `Logger` with two `subscribe`-registered callbacks receives every
  written event exactly once each, in write order.
- Executing `./week1_baseline/bin/python/07_the_run_dsl` runs cleanly
  end-to-end (requires a real `ANTHROPIC_API_KEY` / configured backend to
  reach the live API call — note explicitly if this can't be verified in
  the current environment).
- `git diff` / `git status` confirms nothing under `week1_baseline/ruby/**`
  changed.

## Not part of this plan

- Step 08 (The REPL Loop) and everything after it in the 00–12 roadmap.
- The `working_dir:` / `context_window:` keyword renames mentioned later in
  `ITERATIONS.md` — those land in a future step, not here.
- Actually wiring a `Logger.subscribe` consumer into `example.py` — the
  Ruby step 07 example doesn't use it either; it's ported for parity only.

## Open detail questions

- Confirm the `configure=` callback name/shape (vs. e.g. a context-manager
  or decorator-based alternative) reads naturally before implementing —
  it's the one genuinely non-mechanical translation choice in this step.
