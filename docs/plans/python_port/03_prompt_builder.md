# Python Port Plan — Step 03 (The Prompt Builder)

## Context

Source: `week1_baseline/ruby/03_prompt_builder` (Ruby gem `boukensha`, step 3 of the 00–12 roadmap).
Target: `week1_baseline/python/03_prompt_builder` (currently a byte-for-byte copy of the finished `02_the_registry` Python port, plus an already-copied `prompts/system.md` — confirmed identical to the Ruby version).

This plan covers **only step 03 (The Prompt Builder)**. It adds:
- A `PromptBuilder` that delegates `Context` serialization to a pluggable backend.
- Five backends (`Anthropic`, `OpenAI`, `Gemini`, `Ollama`, `OllamaCloud`) that each know how to turn `Context` into the exact JSON payload their API expects, plus a static per-backend `MODELS` table with context-window/pricing metadata and model validation.
- A new `UnsupportedModelError`.
- A default system prompt shipped in `prompts/system.md` (already present, verified identical).

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only reference.

## Confirmed current state of the Python target

`diff -rq` between `python/02_the_registry` and `python/03_prompt_builder` shows **no differences** except the pre-existing `prompts/system.md`. In other words, none of step 03's work has been done yet:

| File | Status |
|---|---|
| `boukensha/config.py` | Already has `PROMPTS_DIR` (carried over ahead of the Ruby timeline — no change needed here). |
| `boukensha/errors.py` | Still only has `UnknownToolError`. **Needs `UnsupportedModelError` added.** |
| `boukensha/__init__.py` | Still only exports step 02 symbols. **Needs new exports.** |
| `boukensha/backends/` | **Missing entirely.** Must be created. |
| `boukensha/prompt_builder.py` | **Missing entirely.** Must be created. |
| `prompts/system.md` | Present, identical to Ruby. No change needed. |
| `examples/example.py` | Still the step 02 example. **Needs full rewrite.** |
| `README.md` | Still the step 02 README. **Needs full rewrite.** |
| `requirements.txt` | Unchanged from step 02 (`PyYAML`, `python-dotenv`) — Ruby's `Gemfile` for step 03 also only adds `dotenv`, already present. **No new dependency needed** — `PromptBuilder` only builds payloads, it never performs an HTTP call. |
| `bin/python/03_prompt_builder` | **Missing.** Must be created (Ruby has `bin/ruby/03_prompt_builder`). |

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/03_prompt_builder/README.md` | Design doc for `PromptBuilder`, backend responsibilities, per-provider payload shape tables |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha.rb` | Adds requires for `prompt_builder` and all 5 `backends/*` |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/errors.rb` | Adds `UnsupportedModelError` |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/prompt_builder.rb` | Thin delegator: `to_messages`, `to_tools`, `to_api_payload`, `headers`, `url` |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/base.rb` | Shared `MODELS` lookup, `validate_model!`, cost/context-window accessors |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/anthropic.rb` | Anthropic Messages API serialization |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/openai.rb` | OpenAI Chat Completions serialization |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/gemini.rb` | Gemini `generateContent` serialization |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/ollama.rb` | Local Ollama `/api/chat` serialization |
| `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/ollama_cloud.rb` | Ollama Cloud `/api/chat` serialization |
| `week1_baseline/ruby/03_prompt_builder/examples/example.rb` | Builds a context with `look`/`move` tools + a tool-result message, resolves provider/model from `settings.yaml` via the `player` task, constructs the matching backend, prints the pretty-printed API payload |
| `week1_baseline/bin/ruby/03_prompt_builder` | Bash wrapper that runs the Ruby step 03 smoke test |

## Decisions & architectural mapping

### 1. `errors.py` — add `UnsupportedModelError`

```python
class UnsupportedModelError(Exception):
    """Raised when a backend is asked to use a model it doesn't recognize."""
    pass
```

### 2. `backends/base.py` — shared contract

Ruby uses a class-level `MODELS` constant plus `self.class.validate_model!`. Port as a base class where subclasses define a class attribute `MODELS: dict[str, dict]`, and `configure_model` is called from each subclass `__init__`:

```python
class Base:
    MODELS: dict = {}

    @classmethod
    def model_info_for(cls, model):
        return cls.MODELS.get(str(model))

    @classmethod
    def validate_model(cls, model):
        model = str(model)
        if cls.model_info_for(model) is not None:
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    def configure_model(self, model):
        self.model = self.validate_model(model)
        self.model_info = self.model_info_for(self.model)

    @property
    def context_window(self):
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self.model_info["usage_unit"]

    @property
    def usage_level(self):
        return self.model_info.get("usage_level")

    def estimate_cost(self, input_tokens, output_tokens):
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None
        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000.0
```

Notes:
- Ruby raises `NotImplementedError` if a subclass forgets `MODELS`; in Python, defaulting `MODELS = {}` on the base class plus each subclass overriding it is simpler and equally safe — an empty table just means `validate_model` always raises `UnsupportedModelError`, which is an acceptable, honest failure mode. Do not add extra guard machinery beyond what Ruby has.
- Ruby's `model_info` is a public no-arg reader for the *instance's own* resolved model info; Python names this the same (`self.model_info` set in `configure_model`) — do not collide with the classmethod `model_info_for`.

### 3. `MODELS` data — copy verbatim

Transcribe the five `MODELS` tables exactly as in the Ruby source (same keys, same numbers, same `None`/`nil` for unpriced Ollama Cloud models, same `usage_level` strings). These are static tutorial data as of 2026-06-16 per the Ruby README — port the values, don't "improve" or re-derive them. Ruby symbols (`:tokens`, `:local_compute`, `:ollama_cloud_usage`, `:medium`, `:high`) become Python strings (`"tokens"`, `"local_compute"`, `"ollama_cloud_usage"`, `"medium"`, `"high"`).

### 4. Backend classes

Each backend is a small class with `__init__`, `to_messages`, `to_tools`, `to_payload`, `headers`, `url`, following the existing `dataclass`-light, plain-class style already used in `registry.py`/`context.py`. Mirror Ruby field-for-field:

- **`Anthropic`** (`backends/anthropic.py`): `BASE_URL = "https://api.anthropic.com/v1/messages"`. `to_messages(messages)` takes **one** arg (no system — Anthropic sends `system` as a top-level payload field). `tool_result` → `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": ..., "content": ...}]}`. `to_tools` → `input_schema` wrapper. Headers: `x-api-key`, `anthropic-version: 2023-06-01`.
- **`OpenAI`** (`backends/openai.py`): `BASE_URL = ".../v1/chat/completions"`. `to_messages(system, messages)` takes **two** args — prepends a `{"role": "system", ...}` message. `tool_result` → `{"role": "tool", "tool_call_id": ..., "content": ...}`. `to_tools` → `{"type": "function", "function": {...}}` wrapper. Payload key is `max_completion_tokens`. Headers: `Authorization: Bearer`.
- **`Gemini`** (`backends/gemini.py`): `BASE_URL = ".../v1beta/models"`, `url` interpolates `{model}:generateContent`. `to_messages(messages)` takes **one** arg. `assistant` role → `"model"`; every message wraps text as `{"parts": [{"text": ...}]}`. `tool_result` → `functionResponse` part on a `"user"` role message. `to_tools` returns `[]` if no tools, else one `{"functionDeclarations": [...]}` entry. Payload uses `systemInstruction`, `contents`, `generationConfig.maxOutputTokens`. Headers: `x-goog-api-key`.
- **`Ollama`** (`backends/ollama.py`): no `BASE_URL` constant in Ruby — `url` is built from an instance `host` param (`__init__(self, model, host="http://localhost:11434")`). `to_messages(system, messages)` takes **two** args, same shape as OpenAI's but `tool_result` → `{"role": "tool", "tool_name": ..., "content": ...}` (note: `tool_name`, not `tool_call_id`). Payload adds `"stream": False`. No API key/auth header.
- **`OllamaCloud`** (`backends/ollama_cloud.py`): `BASE_URL = "https://ollama.com"`, `url` is `f"{BASE_URL}/api/chat"`. Same message/tool shape as `Ollama` (also `tool_name`, also `stream: False`), but requires `api_key` and sends `Authorization: Bearer`.

Keep each backend's constructor signature matching Ruby's keyword args: `Anthropic(api_key, model)`, `OpenAI(api_key, model)`, `Gemini(api_key, model)`, `Ollama(model, host="http://localhost:11434")`, `OllamaCloud(api_key, model)`.

**Known inconsistency to preserve, not fix:** In the Ruby source, `Anthropic#to_messages` and `Gemini#to_messages` take one argument (`messages`), while `OpenAI#to_messages`, `Ollama#to_messages`, and `OllamaCloud#to_messages` take two (`system, messages`). `PromptBuilder#to_messages` only ever calls `@backend.to_messages(@context.messages)` (one arg) — so calling `builder.to_messages` directly works for Anthropic/Gemini but would raise an arity error for the other three backends. `to_api_payload` is unaffected because each backend's own `to_payload` calls its own `to_messages` with the correct arity internally. This is a genuine wrinkle in the Ruby tutorial code, not a Python translation choice — port it as-is (same asymmetric signatures, same limitation), since the task is a faithful port of step 03, not a fix. Do not silently "fix" this by giving every backend the same signature; that would diverge from the Ruby reference this port is graded/compared against.

### 5. `boukensha/prompt_builder.py` — thin delegator

```python
class PromptBuilder:
    def __init__(self, context, backend):
        self.context = context
        self.backend = backend

    def to_messages(self):
        return self.backend.to_messages(self.context.messages)

    def to_tools(self):
        return self.backend.to_tools(self.context.tools)

    def to_api_payload(self, max_output_tokens=1024):
        return self.backend.to_payload(self.context, max_output_tokens=max_output_tokens)

    @property
    def headers(self):
        return self.backend.headers

    @property
    def url(self):
        return self.backend.url
```

(Ruby's `headers`/`url` are zero-arg methods; exposing them as Python `@property` reads naturally as `builder.headers` / `builder.url`, matching call sites in `example.py`.)

### 6. `boukensha/__init__.py` — new exports

Add:
```python
from .errors import UnknownToolError, UnsupportedModelError
from .prompt_builder import PromptBuilder
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
```
and extend `__all__` accordingly (mirrors Ruby's `lib/boukensha.rb` gaining requires for `prompt_builder` and all 5 `backends/*`).

### 7. `examples/example.py` — port of the new `example.rb`

Rewrite following the existing `sys.path.insert` + `os.environ.setdefault("BOUKENSHA_DIR", ...)` pattern already used in the step 02 Python example. Behavior to replicate:
- Build `system_prompt` via `Player.system_prompt(...)` exactly as step 02 does (unchanged).
- Register a `look` tool (no parameters) returning a fixed description string, and a `move` tool (now with a `description` on the `direction` parameter, not just `type`).
- Manually append a `user`, `assistant`, and `tool_result` message to the context (`ctx.add_message(...)` — no dispatch call in this example anymore).
- Resolve `provider = Player.provider(player_settings)` and `model = Player.model(player_settings)`.
- Branch on `provider` (`"anthropic"`, `"ollama"`, `"ollama_cloud"`, `"openai"`, `"gemini"`) to construct the matching backend, reading the relevant API key from `os.environ` (`ANTHROPIC_API_KEY`, `OLLAMA_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) via something like `os.environ[...]` (mirrors Ruby's `ENV.fetch`, which raises if missing — use `os.environ[key]`, not `.get`, so a missing key fails loudly the same way). Raise `ValueError` for an unsupported provider (Ruby raises `ArgumentError`, Python's nearest equivalent is `ValueError`).
- Construct `PromptBuilder(ctx, backend)` and print `config`, `provider`, `model`, then `json.dumps(builder.to_api_payload(), indent=2)` (Ruby uses `JSON.pretty_generate`).
- Header banner changes to `"=== BOUKENSHA Step 3: Prompt Builder ==="`.

### 8. `README.md` — full rewrite

Port `week1_baseline/ruby/03_prompt_builder/README.md` section-by-section into Python terms:
- Same intro (multi-provider rationale, `PromptBuilder` delegates to a backend, does not call the API).
- "New Files" table pointing at the Python paths (`boukensha/prompt_builder.py`, `boukensha/backends/base.py`, `.../anthropic.py`, `.../ollama.py`, `.../ollama_cloud.py`, `.../openai.py`, `.../gemini.py`, `prompts/system.md`).
- Keep the ASCII flow diagram, the per-backend method tables, the model-table key glossary, and all four "System Prompt" / "Tool Results" / "Tool Definitions" / "Message Roles" JSON comparison blocks verbatim (these describe wire formats, not language-specific code, so they don't need translation).
- "Considerations" section: keep Ruby's three points (stateless conversation, Anthropic tool results as user messages, agent only sees schemas) — these are protocol-level facts, identical in Python.
- "Run Example" section: `./week1_baseline/bin/python/03_prompt_builder`.

### 9. `bin/python/03_prompt_builder` — new runner script

Copy the pattern from `bin/python/02_the_registry` verbatim except the directory:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../python/03_prompt_builder"

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
Make it executable (`chmod +x`), matching `bin/ruby/03_prompt_builder` and `bin/python/02_the_registry`.

## Target structure

```
week1_baseline/python/03_prompt_builder/
  requirements.txt               (unchanged from step 02)
  boukensha/
    __init__.py                  (UPDATE - add PromptBuilder, backends, UnsupportedModelError exports)
    config.py                    (no change - PROMPTS_DIR already present)
    context.py                   (no change)
    errors.py                    (UPDATE - add UnsupportedModelError)
    message.py                   (no change)
    registry.py                  (no change)
    tool.py                      (no change)
    prompt_builder.py            (NEW)
    backends/
      __init__.py                (NEW - empty, package marker)
      base.py                    (NEW)
      anthropic.py               (NEW)
      openai.py                  (NEW)
      gemini.py                  (NEW)
      ollama.py                  (NEW)
      ollama_cloud.py            (NEW)
    tasks/                       (no change)
      __init__.py
      base.py
      player.py
  prompts/
    system.md                   (no change - already present, verified identical to Ruby)
  examples/
    example.py                  (REWRITE - port step 03 example.rb)
  README.md                     (REWRITE - document step 03 Python usage)
```

## File-by-file status & mapping

| Ruby source | Python target | Action | Notes |
|---|---|---|---|
| `lib/boukensha/errors.rb` | `boukensha/errors.py` | **Update** | Add `UnsupportedModelError(Exception)`. |
| `lib/boukensha/prompt_builder.rb` | `boukensha/prompt_builder.py` | **Create** | Thin delegator, see §5. |
| `lib/boukensha/backends/base.rb` | `boukensha/backends/base.py` | **Create** | Model validation + cost/context-window accessors, see §2. |
| `lib/boukensha/backends/anthropic.rb` | `boukensha/backends/anthropic.py` | **Create** | See §4. |
| `lib/boukensha/backends/openai.rb` | `boukensha/backends/openai.py` | **Create** | See §4. |
| `lib/boukensha/backends/gemini.rb` | `boukensha/backends/gemini.py` | **Create** | See §4. |
| `lib/boukensha/backends/ollama.rb` | `boukensha/backends/ollama.py` | **Create** | See §4. |
| `lib/boukensha/backends/ollama_cloud.rb` | `boukensha/backends/ollama_cloud.py` | **Create** | See §4. |
| `lib/boukensha/config.rb` | `boukensha/config.py` | **None** | `PROMPTS_DIR` already present in the Python target. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | **Update** | Add exports, see §6. |
| `prompts/system.md` | `prompts/system.md` | **None** | Already present, verified byte-identical. |
| `examples/example.rb` | `examples/example.py` | **Rewrite** | See §7. |
| `README.md` | `README.md` | **Rewrite** | See §8. |
| `bin/ruby/03_prompt_builder` | `bin/python/03_prompt_builder` | **Create** | See §9. |

## Acceptance criteria

- `from boukensha import Config, Player, Tool, Message, Context, Registry, UnknownToolError, UnsupportedModelError, PromptBuilder, Anthropic, OpenAI, Gemini, Ollama, OllamaCloud` imports cleanly.
- Instantiating any backend with an unsupported model raises `UnsupportedModelError` listing the supported models (sorted), matching Ruby's message format: `"{ClassName} does not support model '{model}'. Supported models: {a, b, c}"`.
- `PromptBuilder(ctx, backend).to_api_payload()` produces a plain dict/list structure with the exact key names and nesting shown in the Ruby README's JSON examples, for each of the 5 backends.
- Running `python examples/example.py` (with the relevant provider's API key env var set, or `provider: ollama` for no key needed) prints `"=== BOUKENSHA Step 3: Prompt Builder ==="` followed by config/provider/model lines and a pretty-printed JSON payload — same structure/ordering as `bundle exec ruby examples/example.rb`.
- Executing `./week1_baseline/bin/python/03_prompt_builder` runs cleanly end-to-end.
- No code under `week1_baseline/ruby/03_prompt_builder` is modified.
- No new pip dependency is introduced (`PromptBuilder` never performs an HTTP request).

## Not part of this plan

- Steps 04–12 (actual HTTP calls to provider APIs, agent loop, tool-execution wiring, etc.).
- "Fixing" the `to_messages` arity inconsistency across backends (see §4) — that is a property of the Ruby reference this step ports, and changing it would be out of scope for a faithful port.
