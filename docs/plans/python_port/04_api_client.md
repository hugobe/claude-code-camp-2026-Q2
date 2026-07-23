# Python Port Plan — Step 04 (The API Client)

## Context

Source: `week1_baseline/ruby/04_api_client` (Ruby gem `boukensha`, step 4 of the
00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/04_api_client` (to be created as a fresh copy of
`python/03_prompt_builder`, then this step's delta applied on top).

This plan covers **only step 04**. It builds on step 03's `PromptBuilder` +
backends (which only *assemble* a payload) by adding a `Client` that actually
performs the HTTP round trip: POST the payload, retry on transient
failures/retryable status codes, raise `ApiError` on a hard failure, and
return the parsed JSON response. No tool-loop / response-parsing yet — that's
step 05.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/04_api_client/README.md` | Design doc for `Client`, retry semantics, "no dependencies" rationale, raw per-backend response shape examples |
| `week1_baseline/ruby/04_api_client/lib/boukensha.rb` | Adds `require_relative "boukensha/client"` (also drops the now-redundant direct `backends/base` require — each backend already requires it itself; no Python-side effect) |
| `week1_baseline/ruby/04_api_client/lib/boukensha/client.rb` | **New.** `Client#call(max_output_tokens:)` — builds the request from `PromptBuilder#url/#headers/#to_api_payload`, retries transient errors and retryable HTTP status codes with exponential backoff, raises `ApiError` past `MAX_RETRIES`, otherwise returns `JSON.parse(response.body)` |
| `week1_baseline/ruby/04_api_client/lib/boukensha/errors.rb` | Adds `ApiError < StandardError` |
| `week1_baseline/ruby/04_api_client/lib/boukensha/config.rb` | `PROMPTS_DIR` changes from `"../../prompts"` to `"../../../prompts"` — see §1, this is a bug, not an intentional move |
| `week1_baseline/ruby/04_api_client/lib/boukensha/tasks/base.rb` | Private `fetch` gains an `is_a?(Hash)` guard; error message wording `settings.yml` → `settings.yaml` (Python already says `.yaml`, see §2) |
| `week1_baseline/ruby/04_api_client/prompts/system.md` | Rewritten prompt text (still a single default system prompt, no structural change) |
| `week1_baseline/ruby/04_api_client/examples/example.rb` | Swaps the `look`/`move` demo tools for `read_file`/`list_directory`, drops the pre-seeded assistant/tool_result messages, constructs a `Client` and actually calls it, prints the raw JSON response instead of the payload |
| `week1_baseline/bin/ruby/04_api_client` | Bash wrapper — model for the Python equivalent |
| `week1_baseline/ruby/04_api_client/Gemfile` + `Gemfile.lock` | Diffed against step 03: **no changes.** `Client` uses only Ruby's stdlib (`net/http`, `json`, `openssl`) |

Do not modify anything under `week1_baseline/ruby/**` — it stays a read-only
reference.

## Confirmed current state of the Python target

Not created yet. Step 1 of implementation is `rsync` from
`python/03_prompt_builder`, which should produce **zero** diff before any
edits (03's target directory is finished and verified). After that copy:

| File | Status |
|---|---|
| `boukensha/client.py` | Missing entirely. Must be created. |
| `boukensha/errors.py` | Has `UnknownToolError`, `UnsupportedModelError`. **Needs `ApiError` added.** |
| `boukensha/config.py` | Has `PROMPTS_DIR` pointing at `parent.parent` (2 levels up from `config.py`, i.e. the step root). **Needs the same off-by-one bump Ruby made** — see §1. |
| `boukensha/tasks/base.py` | `_fetch` calls `settings.get(key)` unconditionally. **Needs an `isinstance(settings, dict)` guard**, matching Ruby's new `is_a?(Hash)` check. Error message text already says `settings.yaml` (no change needed there — the Python port already used the corrected wording). |
| `boukensha/__init__.py` | Exports step 03 symbols only. **Needs `Client`, `ApiError` added** (and see the open question on `LmStudio` below). |
| `boukensha/backends/*.py` | Unchanged in Ruby between 03 and 04 (confirmed via `diff -rq`). No changes needed to any backend's logic. |
| `prompts/system.md` | Needs rewrite to match the new Ruby text. |
| `examples/example.py` | Needs rewrite — new tools, `Client` call, new banner text. |
| `README.md` | Needs full rewrite. |
| `requirements.txt` | **Unchanged** — `Client` is stdlib-only (`urllib.request`, `json`, `ssl`), matching Ruby's "no new gem" choice. |
| `bin/python/04_api_client` | Missing. Must be created. |

## Open detail question — the missing `LmStudio` backend

While researching this step I found that **`boukensha/backends/lm_studio.py`
was never created** in the Python port, even though:
- `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/lm_studio.rb`
  already existed when 03 was ported (added in the same commit as the 03
  port itself) and `lib/boukensha.rb` has required it unconditionally since
  03.
- Both `examples/example.rb` in **03 and 04** include an `"lm_studio"` branch
  in the provider dispatch — it's not new to 04.
- `python/03_prompt_builder`'s `example.py` and `__init__.py` silently omit
  it, and its own plan doc never mentions `LmStudio` at all.

This is unrelated to the 03→04 Ruby diff (`lm_studio.rb` itself is untouched
between the two steps), so strictly speaking it's a step-03 gap, not part of
step 04's delta. But `04_api_client/examples/example.rb`'s own provider
dispatch has 6 branches including `lm_studio`, so a faithful port of *this
step's* example needs it too, or the Python example's dispatch permanently
diverges from Ruby's (5 branches instead of 6).

**Recommendation:** port `boukensha/backends/lm_studio.py` now, as part of
this step, following the exact same shape as `ollama.py` (see §3 below for
the concrete class), and add it to `__init__.py`'s exports. Flagging this
explicitly rather than silently deciding — let me know if you'd rather leave
it out and keep the Python example's dispatch at 5 branches instead of 6.

## Decisions & architectural mapping

### 1. `config.py` — preserve Ruby's `PROMPTS_DIR` off-by-one

Verified by running `File.expand_path` directly: Ruby step 03 used
`File.expand_path("../../prompts", __dir__)` (2 `..`, resolves correctly to
the step root's `prompts/`). Step 04 changed it to `"../../../prompts"` (3
`..`), which resolves one level too high — `week1_baseline/ruby/prompts`,
which doesn't exist. Concretely this means `Boukensha::Config::PROMPTS_DIR`
in the Ruby 04 reference no longer points at a real directory, so
`Tasks::Base.read_default_prompt` silently returns `nil` and
`system_prompt` ends up `nil` unless a user override is configured.

This is a genuine bug introduced in the Ruby reference, not a deliberate
restructuring (directory layout is identical between 03 and 04 — confirmed
via `find`). Per the standing rule to preserve Ruby quirks rather than fix
them, the Python port must reproduce it exactly:

```python
# Default prompts shipped alongside this step.
PROMPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "prompts")
```

(one more `.parent` than step 03's `parent.parent`). Do **not** "fix" this
to keep pointing at the real `prompts/` dir — that would silently diverge
from the Ruby reference this step ports. Note it prominently in code review
so it isn't "corrected" by accident later.

### 2. `tasks/base.py` — add the `isinstance` guard

Ruby's `fetch` gained `return nil unless settings.is_a?(Hash)` before
indexing. Port the equivalent guard into `_fetch`:

```python
@staticmethod
def _fetch(settings, key):
    if not isinstance(settings, dict):
        return None
    return settings.get(key)
```

The Ruby error-message wording change (`settings.yml` → `settings.yaml`)
needs no Python-side change — the existing `ValueError` messages in
`provider`/`model` already say `settings.yaml`.

### 3. `boukensha/backends/lm_studio.py` — new (pending the open question above)

Same shape as `ollama.py`, with LM Studio's specific differences (OpenAI-
compatible local server): two-arg `to_messages(system, messages)`,
`tool_result` → `{"role": "tool", "tool_call_id": ..., "content": ...}` (LM
Studio uses `tool_call_id`, not Ollama's `tool_name`), `to_payload` includes
`"max_tokens"` (Ollama's does not), default `host="http://localhost:1234/v1"`,
`url` → `f"{host}/chat/completions"`.

```python
class LmStudio(Base):
    MODELS = {
        "google/gemma-4-12b-qat": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, model, host="http://localhost:1234/v1"):
        self.host = host
        self.configure_model(model)

    def to_messages(self, system, messages):
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content}
                )
            else:
                conversation.append({"role": str(msg.role), "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024):
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
            "max_tokens": max_output_tokens,
        }

    @property
    def headers(self):
        return {"Content-Type": "application/json"}

    @property
    def url(self):
        return f"{self.host}/chat/completions"
```

### 4. `errors.py` — add `ApiError`

```python
class ApiError(Exception):
    """Raised when an API request fails after exhausting retries."""

    pass
```

### 5. `boukensha/client.py` — the HTTP client

Ruby's `Client` uses `net/http` directly (stdlib, no gem) with an explicit
retry loop: transient network exceptions and retryable HTTP status codes
(`408, 409, 429, 500, 502, 503, 504`) get retried up to `MAX_RETRIES = 3`
times with exponential backoff (`0.5 * 2**(attempt-1)`); anything else past
that raises `ApiError`. The Python nearest-stdlib-equivalent is
`urllib.request` — no new pip dependency, matching Ruby's own "no
dependencies" design choice (see the README's rationale for avoiding
HTTParty/Faraday).

`urllib.request.urlopen` raises `urllib.error.HTTPError` for non-2xx
responses (it still carries `.code` and a readable body, so it's the
natural check point for `RETRYABLE_STATUS_CODES`) and
`urllib.error.URLError`/socket-level exceptions for connection failures —
this maps cleanly onto Ruby's two-branch retry logic (`retryable_response?`
vs. `TRANSIENT_ERRORS`):

```python
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from http.client import HTTPException

from .errors import ApiError


class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    TRANSIENT_ERRORS = (
        EOFError,
        ConnectionResetError,
        ConnectionRefusedError,
        socket.timeout,
        socket.gaierror,
        ssl.SSLError,
        HTTPException,
        urllib.error.URLError,
        TimeoutError,
    )
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder):
        self.builder = builder

    def call(self, max_output_tokens=1024):
        body = json.dumps(
            self.builder.to_api_payload(max_output_tokens=max_output_tokens)
        ).encode("utf-8")

        attempts = 0
        while True:
            attempts += 1
            request = urllib.request.Request(
                self.builder.url, data=body, headers=self.builder.headers, method="POST"
            )
            try:
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                response_body = e.read().decode("utf-8", errors="replace")
                if e.code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                plural = "" if attempts == 1 else "s"
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({e.code}): {response_body}"
                )
            except self.TRANSIENT_ERRORS as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    )
                time.sleep(self._retry_delay(attempts))

    def _retry_delay(self, attempt):
        return self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
```

Notes:
- `urllib.error.HTTPError` is a subclass of `URLError`, so the `HTTPError`
  except clause **must** stay listed before the `TRANSIENT_ERRORS` tuple
  catch (Python tries except clauses in order) — otherwise HTTP error
  responses would be misclassified as transient connection failures.
- Ruby's `Client` has a commented-out, macOS-specific
  `http.ca_file = OpenSSL::X509::DEFAULT_CERT_FILE` workaround (the README's
  "OpenSSL Certificate" section explains it breaks on Linux/WSL2). Python's
  `ssl` module resolves system CA certs automatically without this class of
  problem, so there is nothing to port here — this is a case where the
  Ruby-specific rough edge simply doesn't have a Python equivalent, not a
  gap in the port.
- `builder.headers` in Ruby is a plain string-keyed hash; `urllib.request`
  accepts the same shape as a `dict`, no translation needed.
- Keyword name `max_output_tokens` and default `1024` match `PromptBuilder`
  exactly, mirroring Ruby's `call(max_output_tokens: 1024)`.

### 6. `boukensha/__init__.py` — new exports

Add:
```python
from .client import Client
from .errors import ApiError, UnknownToolError, UnsupportedModelError
```
(plus `LmStudio` if the open question above is resolved in favor of porting
it) and extend `__all__` to include `"Client"`, `"ApiError"` (and
`"LmStudio"`).

### 7. `examples/example.py` — port of the new `example.rb`

Rewrite following the same `sys.path.insert` + `BOUKENSHA_DIR` pattern as
step 03. Behavior to replicate:
- Same `system_prompt`/`Context`/`Registry` setup as step 03 (unchanged).
- Replace the `look`/`move` demo tools with `read_file` (reads a path via
  `Path(path).read_text()`) and `list_directory` (lists a directory,
  filtering out dotfiles — Ruby uses `Dir.entries(path).reject { |f|
  f.start_with?(".") }`; Python equivalent: `sorted(f for f in
  os.listdir(path) if not f.startswith("."))`, joined with `"\n"`).
- Single `ctx.add_message("user", "What files are in the current
  directory?")` — no more pre-seeded assistant/tool_result turns.
- Same provider/backend dispatch as step 03 (`anthropic`, `openai`,
  `gemini`, `ollama`, `ollama_cloud`, and `lm_studio` if ported — see the
  open question).
- Construct `builder = PromptBuilder(ctx, backend)` and `client =
  Client(builder)`.
- Print `"=== BOUKENSHA Step 4: API Client ==="`, then `Config: ...`,
  `Provider: ...`, `Model: ...`, `Sending request to {builder.url}...`,
  blank line, then call `response = client.call()`, print `"Raw response:"`
  followed by `json.dumps(response, indent=2)` (Ruby uses
  `JSON.pretty_generate`).

### 8. `README.md` — full rewrite

Port `week1_baseline/ruby/04_api_client/README.md` section-by-section into
Python terms, same approach as step 03's README rewrite:
- Intro: `Client` takes the `PromptBuilder` payload and performs one HTTP
  POST — no tool loop yet.
- "New Files" table → `boukensha/client.py`.
- "Updated Files" table → `boukensha/errors.py` (`ApiError`),
  `boukensha/config.py` (mention the `PROMPTS_DIR` off-by-one **only if you
  want to document it publicly** — otherwise the Ruby README doesn't call it
  out either, so it's fine to silently carry it; use judgment here, it's a
  step-doc call not a code call), `boukensha/tasks/base.py` (`fetch` type
  guard).
- ASCII flow diagram: `Context → PromptBuilder → Client → POST to API
  endpoint → Raw JSON response`.
- `Boukensha::Client` method table → `call(max_output_tokens=1024)`.
- "No Dependencies" section: adapt to Python — `Client` uses
  `urllib.request` from the standard library, no `pip install` needed
  beyond what step 03 already requires.
- Per-backend raw response JSON examples (Anthropic/Ollama/LM Studio) — copy
  verbatim, these describe wire formats, not language-specific code.
- "Considerations": `ApiError` on failure, SSL handled automatically —
  rephrase the Ruby-specific OpenSSL cert paragraph to note Python's `ssl`
  module doesn't have this problem (see §5 above) rather than porting a
  workaround that doesn't apply.
- "Run Example": `./week1_baseline/bin/python/04_api_client`.

## Target structure

```
week1_baseline/python/04_api_client/
  requirements.txt               (unchanged from step 03)
  boukensha/
    __init__.py                  (UPDATE - add Client, ApiError, [LmStudio?] exports)
    client.py                    (NEW)
    config.py                    (UPDATE - PROMPTS_DIR off-by-one, see §1)
    errors.py                    (UPDATE - add ApiError)
    context.py                   (no change)
    message.py                   (no change)
    registry.py                  (no change)
    tool.py                      (no change)
    prompt_builder.py            (no change)
    backends/
      base.py                    (no change)
      anthropic.py                (no change)
      openai.py                  (no change)
      gemini.py                  (no change)
      ollama.py                  (no change)
      ollama_cloud.py            (no change)
      lm_studio.py                (NEW, pending open question — see §3)
    tasks/
      __init__.py                (no change)
      base.py                    (UPDATE - isinstance guard, see §2)
      player.py                  (no change)
  prompts/
    system.md                    (REWRITE - new prompt text)
  examples/
    example.py                   (REWRITE - port step 04 example.rb)
  README.md                      (REWRITE - document step 04 Python usage)
```

## File-by-file mapping

| Ruby source | Python target | Action | Notes |
|---|---|---|---|
| `lib/boukensha/client.rb` | `boukensha/client.py` | **Create** | See §5. |
| `lib/boukensha/errors.rb` | `boukensha/errors.py` | **Update** | Add `ApiError(Exception)`. |
| `lib/boukensha/config.rb` | `boukensha/config.py` | **Update** | Preserve the `PROMPTS_DIR` off-by-one, see §1. |
| `lib/boukensha/tasks/base.rb` | `boukensha/tasks/base.py` | **Update** | Add `isinstance(settings, dict)` guard, see §2. |
| `lib/boukensha/backends/lm_studio.rb` | `boukensha/backends/lm_studio.py` | **Create (pending confirmation)** | Pre-existing gap from step 03, surfaced above — see §3. |
| `lib/boukensha/backends/{anthropic,openai,gemini,ollama,ollama_cloud}.rb` | same `.py` files | **None** | Unchanged between Ruby 03 and 04. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | **Update** | Add exports, see §6. |
| `prompts/system.md` | `prompts/system.md` | **Rewrite** | New prompt text. |
| `examples/example.rb` | `examples/example.py` | **Rewrite** | See §7. |
| `README.md` | `README.md` | **Rewrite** | See §8. |
| `bin/ruby/04_api_client` | `bin/python/04_api_client` | **Create** | Copy `bin/python/03_prompt_builder` verbatim, change `cd` target only. |

## Acceptance criteria

- `from boukensha import Config, Player, Tool, Message, Context, Registry, UnknownToolError, UnsupportedModelError, PromptBuilder, Anthropic, OpenAI, Gemini, Ollama, OllamaCloud, Client, ApiError` imports cleanly (plus `LmStudio` if ported).
- `Client(builder).call()` against a mocked/broken URL raises `ApiError` after `MAX_RETRIES` retries, with the same message shape as Ruby (`"API request failed after N attempts..."`).
- A non-retryable HTTP status (e.g. 401/404) raises `ApiError` immediately (no retry loop) with the response body included in the message.
- A retryable status (e.g. 429/503) retries up to `MAX_RETRIES` times with exponential backoff before raising.
- `Config.PROMPTS_DIR` resolves one directory above the step root (reproducing the Ruby bug) — confirm this matches Ruby's actual (broken) resolution rather than "fixing" it to point at the real `prompts/` dir.
- Running `python examples/example.py` (with a real provider API key set) prints `"=== BOUKENSHA Step 4: API Client ==="`, config/provider/model/URL lines, then `"Raw response:"` and the pretty-printed JSON actually returned by the API — same structure/ordering as `bundle exec ruby examples/example.rb`. If no API key is available in this environment, note that explicitly instead of claiming it passed.
- Executing `./week1_baseline/bin/python/04_api_client` runs cleanly end-to-end (modulo the same API-key caveat).
- No code under `week1_baseline/ruby/04_api_client` is modified.
- No new pip dependency is introduced (`Client` is stdlib-only, matching Ruby's `Gemfile` having no changes).

## Not part of this plan

- Steps 05–12 (agent loop, response parsing/`stop_reason` handling, tool-call
  dispatch, logging, etc.).
- Fixing the `PROMPTS_DIR` off-by-one — that's a property of the Ruby
  reference this step ports (see §1); changing it would diverge from the
  Ruby source rather than faithfully port it.
- Retrofitting `LmStudio` into step 03 retroactively beyond what's needed to
  keep step 04's own example faithful — if the open question above is
  resolved as "leave it out," step 03 stays as-is and this plan drops the
  `lm_studio` branch from `examples/example.py`'s dispatch instead.
