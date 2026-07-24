# Python Port Plan — Step 08 (The REPL Loop)

## Context

Source: `week1_baseline/ruby/08_the_repl_loop` (Ruby gem `boukensha`, step 8 of
the 00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/08_the_repl_loop` — the user already made this
directory as a copy of `python/07_the_run_dsl` (renamed after copying), onto
which this step's delta gets applied.

This plan covers **only step 08**. It builds on step 07's `Boukensha.run`
one-shot entry point. What's new: `Boukensha::Repl`, an interactive session
loop that keeps a single shared `Context` alive across many turns (so
conversation history accumulates), built-in slash commands (`/quiet`,
`/loud`, `/clear`, `/help`, `/exit`/`/quit`), a `Boukensha.repl` entry point
mirroring `Boukensha.run` minus `task:`, and a `VERSION` constant shown in
the REPL's banner.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/08_the_repl_loop/README.md` | Design doc: the command table, the `Boukensha.repl` block-form example, the step 6→7 `Context#clear_messages!` / `Agent#run` / `Logger#turn` diffs, sample transcript. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/repl.rb` | **New file.** `Boukensha::Repl` — banner, the `loop do … end` read/dispatch cycle, built-in commands, `run_turn` (builds a fresh `Agent` each turn against the shared `Context`, rescues `LoopError`/`ApiError`). |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/version.rb` | **New file.** `Boukensha::VERSION = "0.8.0"`. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha.rb` | Adds `Boukensha.repl(system:, model:, backend:, api_key:, ollama_host:, lm_studio_host:, log:, max_output_tokens:, &block)` — near-identical duplicate of `Boukensha.run`'s config/backend wiring, except it builds a `Repl` and calls `.start` instead of building an `Agent` and calling `.run`, and wraps the call in `rescue Interrupt`. Adds `require_relative "boukensha/version"` and `"boukensha/repl"`. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/context.rb` | Adds `clear_messages!` — wipes `@messages`, keeps `@tools`. Used by `/clear`. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/agent.rb` | `run` and `wrap_up`'s success/rescue paths now call `@context.add_message(:assistant, text)` before returning, in all three return sites. Needed so a REPL's next turn sees the prior assistant reply in the shared context. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/client.rb` | Adds a 401-specific check ahead of the generic failure raise: `"authentication failed (401) — check your API key"`. |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/config.rb` | `resolve_dir` gains a middle tier: explicit `BOUKENSHA_DIR` env var (unchanged) → **new:** `./.boukensha` in the current working directory, if it exists as a directory → `~/.boukensha` default (unchanged). |
| `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/logger.rb` | **No diff vs step 07** (`turn(n:)` already existed, unused, in step 07 — this step is the first caller). No Python action needed; `logger.py` already has `turn(n)`. |
| `week1_baseline/ruby/08_the_repl_loop/examples/example.rb` | Rewritten to call `Boukensha.repl do … end` instead of `Boukensha.run(task: …)`; registers the same two tools (`read_file`, `list_directory`), rooted at the sibling `07_the_run_dsl` step directory as a read-only playground. |
| `week1_baseline/ruby/08_the_repl_loop/Gemfile` + `Gemfile.lock` | No diff vs step 07 — no new gem, so no `requirements.txt` change. |
| `week1_baseline/bin/ruby/08_the_repl_loop` | Bash wrapper — model for the Python equivalent (identical shape, only the `cd` target changes). |

Ruby files confirmed **unchanged** from step 07 (empty `diff`): `registry.rb`,
`tasks/player.rb`, `prompt_builder.rb`, `message.rb`, `tool.rb`, `errors.rb`,
all `backends/*.rb`. No Python action needed for any of these.

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only
reference.

## Confirmed current state of the Python target

The user already created `week1_baseline/python/08_the_repl_loop` as a copy
of `python/07_the_run_dsl` (with `.venv`/`__pycache__` also copied — harmless
but not part of the diff surface below; the bin script will rebuild `.venv`
from scratch regardless). Excluding `.venv`, the tree is byte-for-byte
identical to step 07's.

| File | Status |
|---|---|
| `boukensha/repl.py` | **Missing.** Create new file implementing `Repl`. |
| `boukensha/version.py` | **Missing.** Create new file: `VERSION = "0.8.0"`. |
| `boukensha/context.py` | Present, missing `clear_messages()`. **Needs update.** |
| `boukensha/agent.py` | Present. **Needs update** — add `self.context.add_message("assistant", text)` at all three return sites in `run()`/`_wrap_up()`. |
| `boukensha/client.py` | Present. **Needs update** — add the 401-specific `ApiError` branch in the `HTTPError` handler. |
| `boukensha/config.py` | Present. **Needs update** — `_resolve_dir` gains the cwd-`.boukensha` middle tier. |
| `boukensha/logger.py` | Present, already has `turn(n)` from step 07 (ported ahead of use). No change needed. |
| `boukensha/__init__.py` | Present. **Needs update** — import/export `VERSION` and `Repl`, add the `repl(...)` function. |
| `examples/example.py` | Still the step 07 `boukensha.run(...)` example. **Needs rewrite** to use `boukensha.repl(...)`. |
| `README.md` | Still the step 07 README. **Needs rewrite** for step 08. |
| `requirements.txt` | Unchanged from step 07 — Ruby added no gem, so no new dependency here either. |
| `bin/python/08_the_repl_loop` | Missing. Must be created. |

## Decisions & architectural mapping

### 1. `Repl` — straight class port, `input()`-free stdin loop

Ruby reads with `$stdin.gets` (blocking readline, `nil` at EOF) rather than a
`readline`-with-history library. The direct Python equivalent is
`sys.stdin.readline()`, which returns `""` at EOF — matching `gets`'s `nil`
more precisely than the builtin `input()` (which raises `EOFError` and would
require an extra `try/except` just to detect EOF; `readline()` doesn't need
one). Prompt printing keeps the same explicit-flush shape as Ruby's
`print PROMPT; $stdout.flush`:

```python
import sys

class Repl:
    PROMPT = "boukensha> "

    def start(self):
        sys.stdout.write(self._banner())

        while True:
            sys.stdout.write(self.PROMPT)
            sys.stdout.flush()

            line = sys.stdin.readline()
            if not line:  # EOF / Ctrl-D
                break

            line = line.strip()
            if not line:
                continue

            if line in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif line == "/help":
                sys.stdout.write(self.HELP)
                continue
            elif line == "/quiet":
                boukensha.quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif line == "/loud":
                boukensha.loud()
                print("(logging enabled)")
                continue
            elif line == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(line)
```

`sys.stdout.write(...)` (not `print(...)`) for `HELP`/banner specifically
because both Ruby heredocs already end in `"\n"`, and Ruby's `puts` does not
add a second trailing newline when the string already ends with one —
`print()` would add an extra blank line each time. Single-line messages
(`"Goodbye."`, the toggle confirmations) use plain `print()`, matching
`puts` on a string with no trailing newline.

`Ctrl-C` (`Interrupt` in Ruby, `KeyboardInterrupt` in Python) is **not**
caught inside `Repl.start` in either language — it propagates up to
`Boukensha.repl`/`boukensha.repl()`, which is the one that rescues it (see
decision 10).

### 2. Constructor — keyword args mirror Ruby 1:1

```python
def __init__(
    self,
    context,
    registry,
    builder,
    client,
    logger,
    config_dir=None,
    provider=None,
    model=None,
    version=None,
    api_key=None,
    task_settings=None,
    max_iterations=None,
    max_output_tokens=None,
):
    self.context = context
    self.registry = registry
    self.builder = builder
    self.client = client
    self.logger = logger
    self.task_settings = task_settings
    self.max_iterations = max_iterations
    self.max_output_tokens = max_output_tokens
    self.config_dir = config_dir
    self.provider = provider
    self.model = model
    self.version = version
    self.api_key = api_key
    self.turn = 0
```

`repl.py` needs `import boukensha` at module scope (not `from . import
quiet, loud`) for the `/quiet`/`/loud` calls — same pattern already used by
`logger.py` for `boukensha.config()`/`boukensha.is_debug()`. This works
despite the circular import (`__init__.py` imports `Repl` from `repl.py`)
because the calls only happen inside method bodies, long after both modules
have fully loaded.

### 3. `banner()` — private helper, string interpolation for the box

```python
def _banner(self):
    key_status = "✗ API key not set" if not self.api_key or not self.api_key.strip() else "✓ API key set"
    provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
    config_exists = self.config_dir and os.path.isdir(self.config_dir)
    if config_exists:
        config_line = self.config_dir
    else:
        config_line = f"{self.config_dir or '(default)'}  ✗ directory not found"
    ver = self.version or "?.?.?"

    return (
        "\n"
        "╔══════════════════════════════════════╗\n"
        f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * (9 - len(ver))}║\n"
        "╚══════════════════════════════════════╝\n"
        f"  config:    {config_line}\n"
        f"  provider:  {provider_line}\n"
        "\n"
        "  /quiet or /loud   toggle logging\n"
        "  /clear           reset conversation history\n"
        "  /exit or /quit    leave the REPL\n"
        "\n"
    )
```

`" " * (9 - ver.length)` ported literally, including the fact that it only
lines up for version strings around 5 characters (`"0.8.0"`) — not touched,
per "preserve Ruby quirks as-is."

`HELP` is a class-level string constant (matches Ruby's `HELP = <<~HELP`
constant, as opposed to `banner` which is a per-instance method since it
interpolates instance state):

```python
HELP = (
    "Commands:\n"
    "  /quiet   suppress logging output\n"
    "  /loud    re-enable logging output\n"
    "  /clear   wipe conversation history (tools stay)\n"
    "  /exit    leave the REPL\n"
    "  /help    show this message\n"
)
```

### 4. `_run_turn` — fresh `Agent` per turn, shared `Context`

```python
def _run_turn(self, text):
    self.turn += 1
    self.logger.turn(self.turn)

    self.context.add_message("user", text)

    agent = Agent(
        context=self.context,
        registry=self.registry,
        builder=self.builder,
        client=self.client,
        logger=self.logger,
        task_settings=self.task_settings,
        max_iterations=self.max_iterations,
        max_output_tokens=self.max_output_tokens,
    )
    try:
        result = agent.run()
        print()
        print(result)
    except LoopError as e:
        print(f"\n[error] {e}")
    except ApiError as e:
        print(f"\n[error] API call failed: {e}")
```

`repl.py` imports `Agent` from `.agent` and `ApiError`/`LoopError` from
`.errors` at module scope — no circularity issue since neither of those
modules imports `repl`.

### 5. `Context.clear_messages()` — bang dropped per standing convention

Ruby's `!`-suffixed mutator names have no Python equivalent marker; the
codebase already drops the bang for `Boukensha.quiet!`/`loud!` →
`boukensha.quiet()`/`loud()` in `__init__.py`. Same here:

```python
def clear_messages(self):
    self.messages = []
```

### 6. `Agent` — persist the final reply into context

Three return sites get one line added each, directly before their `return`,
matching the Ruby diff exactly:

- `run()`'s completed-turn branch: `self.context.add_message("assistant", text)` before `return text`.
- `_wrap_up()`'s success path: same, before `return text`.
- `_wrap_up()`'s `except ApiError` fallback path: `self.context.add_message("assistant", msg)` before `return msg`.

Before step 08 this didn't matter (`boukensha.run()` throws the `Context`
away after one turn); the REPL needs it so turn 2 sees turn 1's reply.

### 7. `Client` — 401-specific error message

Python's HTTP layer raises `urllib.error.HTTPError` instead of returning a
non-success response object, so the Ruby `unless response.is_a?(Net::HTTPSuccess) … if response.code.to_i == 401` check maps to one extra branch inside the existing `except urllib.error.HTTPError as e:` handler, positioned the same way Ruby orders it — after the retry check, before the generic failure raise:

```python
except urllib.error.HTTPError as e:
    response_body = e.read().decode("utf-8", errors="replace")
    if e.code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
        time.sleep(self._retry_delay(attempts))
        continue
    if e.code == 401:
        raise ApiError("authentication failed (401) — check your API key")
    plural = "" if attempts == 1 else "s"
    raise ApiError(
        f"API request failed after {attempts} attempt{plural} ({e.code}): {response_body}"
    )
```

(401 isn't in `RETRYABLE_STATUS_CODES` in either language, so the new branch
is reached on the first attempt.)

### 8. `Config._resolve_dir` — cwd `.boukensha` tier

```python
def _resolve_dir(self):
    if os.environ.get("BOUKENSHA_DIR"):
        return str(Path(os.environ["BOUKENSHA_DIR"]).expanduser().absolute())

    cwd_dir = Path.cwd() / ".boukensha"
    if cwd_dir.is_dir():
        return str(cwd_dir)

    return str(Path(self.DEFAULT_DIR).expanduser().absolute())
```

Keeps the existing `.expanduser().absolute()` idiom for tiers 1 and 3
(already established in step 00/07's port), rather than switching to
`Path.resolve()` — no functional difference, just consistency with what's
already there.

### 9. `boukensha.VERSION`

```python
# boukensha/version.py
VERSION = "0.8.0"
```

Exported from `__init__.py` as `from .version import VERSION`, added to
`__all__`. Used only by `repl()` to pass into `Repl(version=VERSION, ...)`.

### 10. `boukensha.repl(...)` — duplicated wiring, ported as-is

Ruby's `Boukensha.repl` is a near copy-paste of `Boukensha.run` (same
config/task/backend resolution block, ~40 lines), differing only in the
final step: build+`.start` a `Repl` instead of build+`.run` an `Agent`, and
an added `rescue Interrupt` / Python `except KeyboardInterrupt`. This is
Ruby's own choice, not accidental duplication introduced by porting — no
shared-helper refactor here, matching the "preserve as a faithful port, not
a fix" convention (a future Ruby step may factor this out; if it does, the
Python port follows suit then, not now).

```python
def repl(
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
    cfg = config()
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

    try:
        Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
            config_dir=cfg.dir,
            provider=backend,
            model=model,
            version=VERSION,
            api_key=api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

`rescue Interrupt … ensure logger&.close` → Python `try/except
KeyboardInterrupt/finally`, same guarantee that `logger.close()` always runs.

## Target structure

```
week1_baseline/python/08_the_repl_loop/
  requirements.txt               (unchanged from step 07)
  boukensha/
    __init__.py                  (UPDATE - add repl(), import/export VERSION, Repl)
    repl.py                      (NEW - Repl class)
    version.py                   (NEW - VERSION = "0.8.0")
    context.py                   (UPDATE - add clear_messages())
    agent.py                     (UPDATE - persist assistant reply, 3 return sites)
    client.py                    (UPDATE - 401-specific ApiError branch)
    config.py                    (UPDATE - cwd .boukensha tier in _resolve_dir)
    logger.py                    (no change - turn(n) already present from step 07)
    run_dsl.py, registry.py, tasks/, backends/, message.py, prompt_builder.py, tool.py, errors.py  (no change)
  prompts/
    system.md                    (no change)
  examples/
    example.py                   (REWRITE - port step 08 example.rb, using boukensha.repl)
  README.md                      (REWRITE - document step 08 Python usage)
```

## File-by-file mapping

| Ruby source | Python target | Action | Notes |
|---|---|---|---|
| `lib/boukensha/repl.rb` | `boukensha/repl.py` | Create | `Repl` class |
| `lib/boukensha/version.rb` | `boukensha/version.py` | Create | `VERSION = "0.8.0"` |
| `lib/boukensha.rb` (`self.repl`) | `boukensha/__init__.py` (`repl()`) | Update | New module-level function |
| `lib/boukensha/context.rb` (`clear_messages!`) | `boukensha/context.py` | Update | Add `clear_messages()` |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | Update | Persist assistant reply, 3 sites |
| `lib/boukensha/client.rb` | `boukensha/client.py` | Update | 401-specific `ApiError` |
| `lib/boukensha/config.rb` | `boukensha/config.py` | Update | cwd `.boukensha` tier |
| `lib/boukensha/logger.rb` | `boukensha/logger.py` | None | No Ruby diff (already ported in step 07) |
| `lib/boukensha/registry.rb`, `tasks/*.rb`, `prompt_builder.rb`, `message.rb`, `tool.rb`, `errors.rb`, `backends/*.rb` | (matching `.py` files) | None | No Ruby diff |
| `examples/example.rb` | `examples/example.py` | Rewrite | Use `boukensha.repl(configure=...)` |
| `README.md` | `README.md` | Rewrite | Document `Repl`/`repl()`, command table, sample transcript |
| `Gemfile`/`Gemfile.lock` | `requirements.txt` | None | No gem added |
| `bin/ruby/08_the_repl_loop` | `bin/python/08_the_repl_loop` | Create | Copy of `bin/python/07_the_run_dsl`, `cd` target changed |

## `examples/example.py` shape

Mirrors `week1_baseline/ruby/08_the_repl_loop/examples/example.rb`: prints
the config, then hands off to `boukensha.repl(configure=...)` with the same
two tools rooted at the sibling `07_the_run_dsl` step directory (Python
tree, not Ruby, since that's the sibling that actually exists here):

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parents[4] / ".boukensha"))

import boukensha

print("=== BOUKENSHA Step 8: The REPL Loop ===")
print()
print(f"Config: {boukensha.config()}")
print()

# The base directory tools will operate relative to — the step 7 folder
# makes a good playground since it already has source files to read.
base_dir = Path(__file__).resolve().parent.parent.parent / "07_the_run_dsl"


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
        parameters={"path": {"type": "string", "description": "File path (relative to the working directory)"}},
        block=_read_file,
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "Directory path (relative to the working directory, or '.' for root)"}},
        block=_list_directory,
    )


boukensha.repl(configure=configure)
```

No `=== FINAL RESPONSE ===` footer this time — `repl()` doesn't return a
value; it runs until the user exits, matching Ruby's example (a bare
`Boukensha.repl do … end` call with nothing after it).

## Bin Script Runner (`week1_baseline/bin/python/08_the_repl_loop`)

Copy verbatim from `week1_baseline/bin/python/07_the_run_dsl`, changing only
the `cd` target from `07_the_run_dsl` to `08_the_repl_loop`. `chmod +x` after
creating.

## Acceptance criteria

- `from boukensha import repl, Repl, VERSION, run, RunDSL, Config, Player, Tool, Message, Context, Registry, UnknownToolError, UnsupportedModelError, ApiError, LoopError, PromptBuilder, Anthropic, OpenAI, Gemini, Ollama, OllamaCloud, LmStudio, Client, Agent, Logger, config, quiet, loud, is_quiet, debug, is_debug` imports cleanly.
- `Context().clear_messages()` empties `.messages` while leaving `.tools` untouched.
- A fake two-turn REPL exchange (feed `_run_turn` twice against a shared `Context`) shows turn 2's prompt includes turn 1's `"assistant"`-role message — proving the `Agent.run` persistence change actually takes effect.
- `Client.call` against a mocked 401 response raises `ApiError` with the message `"authentication failed (401) — check your API key"`, not the generic "API request failed…" message.
- `Config()._resolve_dir()` picks a `./.boukensha` directory in `os.getcwd()` over the `~/.boukensha` default when both exist and `BOUKENSHA_DIR` is unset; still honors `BOUKENSHA_DIR` first when set.
- `boukensha.repl(backend="nonexistent")` raises `ValueError` (same "Unknown backend" shape as `run()`).
- Piping EOF into stdin (`echo -n | python examples/example.py` equivalent, or a scripted `sys.stdin` with no lines) causes `Repl.start()` to return cleanly without raising.
- Executing `./week1_baseline/bin/python/08_the_repl_loop` starts the REPL and prints the banner without error (requires a real `ANTHROPIC_API_KEY` / configured backend for actual conversation turns — note explicitly if a live turn can't be verified in the current environment; the banner/prompt/`/help`/`/exit` path can be checked without one).
- `git diff` / `git status` confirms nothing under `week1_baseline/ruby/**` changed.

## Not part of this plan

- Step 09 (Global Executable) and everything after it in the 00–12 roadmap.
- Factoring `run()`/`repl()`'s duplicated config-and-backend wiring into a
  shared helper — Ruby doesn't do this either at this step; not this port's
  job to fix.
- Wiring up `Logger.subscribe` to anything REPL-related — still unused by
  this step's example, same as step 07.

## Open detail questions

- None — this step's translation choices (stdin EOF handling, bang-method
  naming, the 401 branch placement, the duplicated `run`/`repl` wiring) all
  follow directly from existing conventions already established in prior
  steps' plans; no new judgment calls needed before implementing.
