# Python Port Plan — Step 06 (The Logger)

## Context

Source: `week1_baseline/ruby/06_the_logger` (Ruby gem `boukensha`, step 6 of the 00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).  
Target: `week1_baseline/python/06_the_logger` (seeded with a copy of `python/05_agent_loop`, onto which this step's delta is applied).

This plan covers **step 06**. It builds on step 05's `Agent` loop by introducing structured JSONL event logging via `Logger`. It also adds package-level state and mode flags (`quiet`, `debug`, `config`) to `boukensha`, integrates logging into `Agent` (replacing ad-hoc console prints), tracks token usage and estimated USD costs, and outputs log lines to `.boukensha/sessions/<session-id>.jsonl`.

---

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/06_the_logger/README.md` | Documentation for Step 06 (The Logger), detailing session log structure, event phases (`session_start`, `iteration`, `limit_reached`, `prompt`, `tool_call`, `tool_result`, `response`, `turn_end`, `raw`), `Logger` API, and debug flags. |
| `week1_baseline/ruby/06_the_logger/lib/boukensha.rb` | Defines module-level configuration accessor (`self.config`), mode toggles (`quiet!`, `loud!`, `quiet?`, `debug!`, `debug?`), and requires `boukensha/logger`. |
| `week1_baseline/ruby/06_the_logger/lib/boukensha/logger.rb` | **New file.** Implements `Boukensha::Logger`: opens a append-only JSONL session file, emits structured events for each phase, extracts token usage & cost metadata, and serializes messages/tools. |
| `week1_baseline/ruby/06_the_logger/lib/boukensha/agent.rb` | Updates `Agent` constructor to accept `logger: Logger.new` and replaces `puts` statements with structured `@logger` calls across all loop lifecycle events. |
| `week1_baseline/ruby/06_the_logger/lib/boukensha/prompt_builder.rb` | Adds `attr_reader :backend` to expose backend metadata (provider, model, token pricing) to the agent/logger. |
| `week1_baseline/ruby/06_the_logger/lib/boukensha/config.rb` | Code cleanup (removed unused MUD helper methods). |
| `week1_baseline/ruby/06_the_logger/lib/boukensha/context.rb` | Minor whitespace formatting cleanup. |
| `week1_baseline/ruby/06_the_logger/examples/example.rb` | Updated example instantiating `Boukensha::Logger.new`, passing it to `Agent`, and displaying Step 06 header info. |
| `week1_baseline/bin/ruby/06_the_logger` | Bash wrapper script for running the Ruby step 06 example. |

Do not modify anything under `week1_baseline/ruby/**` — it remains a read-only reference.

---

## Confirmed current state of the Python target

`week1_baseline/python/06_the_logger` currently contains the codebase copied from `python/05_agent_loop`.

| File | Target Status | Required Action |
|---|---|---|
| `boukensha/logger.py` | **Missing.** | Create new file implementing `Logger`. |
| `boukensha/__init__.py` | Exists. | Add package-level functions (`config()`, `quiet()`, `loud()`, `is_quiet()`, `debug()`, `is_debug()`) and export `Logger`. |
| `boukensha/prompt_builder.py` | Exists. | Expose `backend` attribute on `PromptBuilder`. |
| `boukensha/agent.py` | Exists. | Update `Agent.__init__` to accept `logger=None` (defaulting to `Logger()`), and replace console prints with structured logger invocations (`iteration`, `prompt`, `raw`, `tool_call`, `tool_result`, `limit_reached`, `response`, `turn_end`). |
| `examples/example.py` | Exists. | Update example to instantiate `Logger`, pass to `Agent`, and update title header for Step 06. |
| `README.md` | Exists. | Update documentation to reflect Step 06 (The Logger). |
| `bin/python/06_the_logger` | **Missing.** | Create executable bash wrapper script in `week1_baseline/bin/python/`. |

---

## Target Directory Structure Overview

```
week1_baseline/python/06_the_logger/
├── README.md                      # [MODIFIED] Updated doc for Step 06 (The Logger)
├── requirements.txt               # [UNTOUCHED] Standard library only (no pip dependencies)
├── .python-version                # [UNTOUCHED] Python version specification
├── prompts/
│   └── system.md                  # [UNTOUCHED] System prompt
├── boukensha/
│   ├── __init__.py                # [MODIFIED] Adds package state/toggles & exports Logger
│   ├── logger.py                  # [NEW] Structured JSONL Logger implementation
│   ├── agent.py                   # [MODIFIED] Integrates Logger into Agent loop
│   ├── prompt_builder.py          # [MODIFIED] Exposes self.backend attribute
│   ├── client.py                  # [UNTOUCHED] HTTP Client
│   ├── config.py                  # [UNTOUCHED] Config loader
│   ├── context.py                 # [UNTOUCHED] Context manager
│   ├── errors.py                  # [UNTOUCHED] Exception definitions
│   ├── message.py                 # [UNTOUCHED] Message struct
│   ├── registry.py                # [UNTOUCHED] Tool registry
│   ├── tool.py                    # [UNTOUCHED] Tool definition struct
│   ├── backends/                  # [UNTOUCHED] Backend adapters with cost estimation metadata
│   └── tasks/                     # [UNTOUCHED] Task definitions
├── examples/
│   └── example.py                 # [MODIFIED] Example script using Logger
└── (bin/python/06_the_logger)     # [NEW] Executable bash runner in week1_baseline/bin/python/
```

---

## Key Decisions & Architectural Mapping

### 1. Package-Level Module State in `boukensha/__init__.py`

In Ruby, `Boukensha` module defines singleton state (`@quiet`, `@debug`, `@config`) and toggle methods (`quiet!`, `debug!`, etc.). In Python, module attributes manage state cleanly:

```python
_quiet = False
_debug = False
_config = None

def config():
    global _config
    if _config is None:
        _config = Config()
    return _config

def quiet():
    global _quiet
    _quiet = True

def loud():
    global _quiet
    _quiet = False

def is_quiet():
    return _quiet

def debug():
    global _debug
    _debug = True

def is_debug():
    return _debug
```

### 2. Structured JSONL Session Logging (`Logger` Class)

The `Logger` class streams machine-readable JSON objects into `.boukensha/sessions/<session-id>.jsonl`.
- **Session File Location**: Defaults to `File.join(config.dir, "sessions", f"{session_id}.jsonl")`.
- **Session ID Format**: `YYYYMMDDTHHMMSSZ-<hex4>` (e.g. `20260723T143000Z-a1b2c3d4`).
- **Event Enrichment**: Every written JSON record automatically includes `"session_id"` and an ISO 8601 UTC timestamp (`"at"`).
- **Phases Logged**:
  1. `session_start`: Logged upon initialization.
  2. `iteration`: At the start of each agent loop turn (`n`, `max`).
  3. `prompt`: Details messages count, tools list, and serialized message objects.
  4. `raw`: Logged only when `boukensha.is_debug()` is `True`.
  5. `tool_call`: Logs tool `name` and `args`.
  6. `tool_result`: Logs tool `name`, stringified `result`, boolean `ok`, and optional `error` message.
  7. `limit_reached`: Logged when `iteration` ceiling is hit (`kind`, `n`, `max`).
  8. `response`: Logs normalized output `text`, `usage`, `stop_reason`, and execution metadata (`task`, `provider`, `model`, `usage_unit`, `usage_level`, `input_tokens`, `output_tokens`, `cost_usd`).
  9. `turn_end`: Logged when the turn completes (`reason`, `iterations`).

### 3. Usage & Cost Metadata Extraction

`Logger` inspects raw response dictionaries across different backend formats to compute `input_tokens`, `output_tokens`, and estimated USD cost (`backend.estimate_cost(...)`).
- Checks keys: `input_tokens` / `prompt_tokens` / `promptTokenCount` / `prompt_eval_count`.
- Checks keys: `output_tokens` / `completion_tokens` / `candidatesTokenCount` / `eval_count`.

---

## Detailed Code Specifications

### 1. `boukensha/__init__.py`

```python
from .agent import Agent
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tool import Tool

_quiet = False
_debug = False
_config = None


def config():
    global _config
    if _config is None:
        _config = Config()
    return _config


def quiet():
    global _quiet
    _quiet = True


def loud():
    global _quiet
    _quiet = False


def is_quiet():
    return _quiet


def debug():
    global _debug
    _debug = True


def is_debug():
    return _debug


__all__ = [
    "Config",
    "Context",
    "PromptBuilder",
    "Registry",
    "Tool",
    "Message",
    "Agent",
    "Logger",
    "UnknownToolError",
    "ApiError",
    "LoopError",
    "UnsupportedModelError",
    "config",
    "quiet",
    "loud",
    "is_quiet",
    "debug",
    "is_debug",
]
```

### 2. `boukensha/logger.py` (New File)

```python
from datetime import datetime, timezone
import json
import os
import secrets

import boukensha


class Logger:
    DEFAULT_SESSION_DIR = "sessions"

    def __init__(self, session_id=None, dir=None, log=None, snapshot=None):
        self.session_id = session_id or self._generate_session_id()
        if log:
            self.path = log
        else:
            base_dir = dir or self._default_dir()
            self.path = os.path.join(base_dir, f"{self.session_id}.jsonl")

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._log_file = open(self.path, "a", encoding="utf-8")

        start_event = {"phase": "session_start"}
        if snapshot:
            start_event.update(snapshot)
        self._write_log(start_event)

    def iteration(self, n, max):
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason, iterations, tokens=None):
        self._write_log({
            "phase": "turn_end",
            "reason": reason,
            "iterations": iterations,
            "tokens": tokens,
        })

    def prompt(self, messages, tools):
        serialized_messages = [self._serialize_message(m) for m in messages]
        tool_names = list(tools.keys()) if isinstance(tools, dict) else []
        self._write_log({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": serialized_messages,
            "tool_count": len(tool_names),
            "tools": tool_names,
        })

    def tool_call(self, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, name, result, ok=True, error=None):
        self._write_log({
            "phase": "tool_result",
            "name": name,
            "result": str(result),
            "ok": ok,
            "error": error,
        })

    def response(self, text, usage=None, stop_reason=None, task=None, backend=None):
        event = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, data):
        if not boukensha.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self):
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    def _default_dir(self):
        return os.path.join(boukensha.config().dir, self.DEFAULT_SESSION_DIR)

    def _write_log(self, event):
        log_entry = dict(event)
        log_entry["session_id"] = self.session_id
        log_entry["at"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(log_entry) + "\n"
        self._log_file.write(line)
        self._log_file.flush()

    def _generate_session_id(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        hex_suffix = secrets.token_hex(4)
        return f"{timestamp}-{hex_suffix}"

    def _serialize_message(self, msg):
        return {"role": getattr(msg, "role", None), "content": getattr(msg, "content", None)}

    def _execution_metadata(self, task, backend, usage):
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        task_name = getattr(task, "task_name", None) if hasattr(task, "task_name") else str(task) if task else None
        
        provider = None
        if backend:
            cls_name = backend.__class__.__name__
            if cls_name.endswith("Backend"):
                cls_name = cls_name[:-7]
            # Convert CamelCase to snake_case
            provider = "".join(["_" + c.lower() if c.isupper() else c for c in cls_name]).lstrip("_")

        metadata = {
            "task": task_name,
            "provider": provider,
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None),
            "usage_level": getattr(backend, "usage_level", None),
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    def _usage_tokens(self, usage):
        if not isinstance(usage, dict):
            usage = {}
        return {
            "input": self._first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"),
            "output": self._first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"),
        }

    def _first_integer(self, hash_dict, *keys):
        for k in keys:
            val = hash_dict.get(k)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
        return None

    def _estimate_cost(self, backend, tokens):
        if not backend or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
```

### 3. `boukensha/prompt_builder.py`

Expose backend property:
```python
class PromptBuilder:
    def __init__(self, context, backend):
        self.context = context
        self.backend = backend  # Expose backend for metadata lookup
```

### 4. `boukensha/agent.py`

Update `Agent` to integrate `Logger`:

```python
from .errors import ApiError
from .logger import Logger


class Agent:
    MAX_ITERATIONS = 25
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools.\n"
        "Briefly summarize what you accomplished, what is still unfinished, and the\n"
        "single next action you would take."
    )

    def __init__(
        self,
        context,
        registry,
        builder,
        client,
        logger=None,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger or Logger()
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self):
        while True:
            if self._iteration_limit_reached():
                self.logger.limit_reached(kind="max_iterations", n=self.iteration, max=self.max_iterations)
                return self._wrap_up("max_iterations")

            self.iteration += 1
            self.logger.iteration(n=self.iteration, max=self.max_iterations)
            self.logger.prompt(messages=self.context.messages, tools=self.context.tools)

            response = self.client.call(**self._call_opts())
            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)

            if parsed.get("stop_reason") == "tool_use":
                self._handle_tool_calls(parsed.get("content", []), response)
            else:
                text = self._extract_text(parsed.get("content", []))
                self._log_response(text=text, response=response)
                self.logger.turn_end(reason="completed", iterations=self.iteration)
                return text

    def _resolve_max_iterations(self, task_settings, explicit):
        if explicit is not None:
            return int(explicit)
        if task_settings and hasattr(self.context.task, "max_iterations"):
            return self.context.task.max_iterations(task_settings)
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(self, task_settings, explicit):
        if explicit is not None:
            return explicit
        if task_settings and hasattr(self.context.task, "max_output_tokens"):
            return self.context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self):
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _call_opts(self):
        return {"max_output_tokens": self.max_output_tokens} if self.max_output_tokens else {}

    def _wrap_up(self, reason):
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(tools=[], max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS)
            parsed = self.builder.parse_response(response)
            text = self._extract_text(parsed.get("content", []))
            if not text.strip():
                text = self._fallback_message(reason)
            self._log_response(text=text, response=response)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return msg

    def _fallback_message(self, reason):
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        if isinstance(content, str):
            return content
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _handle_tool_calls(self, content, response):
        tool_calls = [b for b in content if b.get("type") == "tool_use"]
        reasoning = self._extract_text(content)

        if not reasoning.strip():
            count = len(tool_calls)
            suffix = "s" if count != 1 else ""
            log_text = f"(tool use — {count} call{suffix})"
        else:
            log_text = reasoning

        self._log_response(text=log_text, response=response)
        self.context.add_message("assistant", content)

        for block in tool_calls:
            name = block.get("name")
            args = block.get("input", {})
            use_id = block.get("id")

            self.logger.tool_call(name=name, args=args)
            try:
                result = self.registry.dispatch(name, args)
                self.logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self.logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)

    def _log_response(self, text, response):
        self.logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self.context.task,
            backend=self.builder.backend,
        )

    def _normalized_usage(self, response):
        if not isinstance(response, dict):
            return None
        if "usage" in response:
            return response["usage"]
        if "usageMetadata" in response:
            return response["usageMetadata"]

        usage = {}
        for key in ["prompt_eval_count", "eval_count"]:
            if key in response:
                usage[key] = response[key]
        return usage if usage else None
```

### 5. `examples/example.py`

Update `examples/example.py` to match Ruby step 06 example:

```python
import os
import sys

# Ensure BOUKENSHA_DIR points to root .boukensha directory
if "BOUKENSHA_DIR" not in os.environ:
    os.environ["BOUKENSHA_DIR"] = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../.boukensha")
    )

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import boukensha
from boukensha.backends import (
    AnthropicBackend,
    GeminiBackend,
    LmStudioBackend,
    OllamaBackend,
    OllamaCloudBackend,
    OpenAIBackend,
)


def main():
    config = boukensha.Config()
    player_settings = config.tasks("player")

    system_prompt = boukensha.tasks.PlayerTask.system_prompt(
        player_settings,
        user_prompts_dir=config.user_prompts_dir,
        default_prompts_dir=boukensha.Config.PROMPTS_DIR,
    )

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    ctx = boukensha.Context(task=boukensha.tasks.PlayerTask, system=system_prompt)
    registry = boukensha.Registry(ctx)

    provider = boukensha.tasks.PlayerTask.provider(player_settings)
    model = boukensha.tasks.PlayerTask.model(player_settings)

    if provider == "anthropic":
        backend = AnthropicBackend(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
    elif provider == "openai":
        backend = OpenAIBackend(api_key=os.environ["OPENAI_API_KEY"], model=model)
    elif provider == "gemini":
        backend = GeminiBackend(api_key=os.environ["GEMINI_API_KEY"], model=model)
    elif provider == "ollama":
        backend = OllamaBackend(model=model)
    elif provider == "ollama_cloud":
        backend = OllamaCloudBackend(api_key=os.environ["OLLAMA_API_KEY"], model=model)
    elif provider == "lm_studio":
        backend = LmStudioBackend(model=model)
    else:
        raise ValueError(f"Unsupported provider for player task: {provider}")

    builder = boukensha.PromptBuilder(ctx, backend)
    client = boukensha.Client(builder)
    logger = boukensha.Logger()
    agent = boukensha.Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=player_settings,
    )

    @registry.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path):
        full_path = os.path.abspath(os.path.join(base_dir, path))
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    @registry.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path):
        full_path = os.path.abspath(os.path.join(base_dir, path))
        entries = os.listdir(full_path)
        return ", ".join(e for e in entries if not e.startswith("."))

    ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

    print("=== BOUKENSHA Step 6: The Logger ===")
    print()
    print(f"Config: {config}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"Max iterations: {boukensha.tasks.PlayerTask.max_iterations(player_settings)}")
    print(f"Max output tokens: {boukensha.tasks.PlayerTask.max_output_tokens(player_settings)}")
    print()

    result = agent.run()

    print()
    print("=== FINAL RESPONSE ===")
    print(result)


if __name__ == "__main__":
    main()
```

### 6. `bin/python/06_the_logger`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
python3 "${REPO_ROOT}/week1_baseline/python/06_the_logger/examples/example.py" "$@"
```

---

## Implementation Steps

1. **Create `boukensha/logger.py`**:
   - Implement `Logger` class, session file creation, event writers (`iteration`, `prompt`, `raw`, `tool_call`, `tool_result`, `limit_reached`, `response`, `turn_end`), and metadata extraction helpers.
2. **Update `boukensha/__init__.py`**:
   - Add module-level state (`_quiet`, `_debug`, `_config`) and helper functions (`config()`, `quiet()`, `loud()`, `is_quiet()`, `debug()`, `is_debug()`).
   - Export `Logger`.
3. **Update `boukensha/prompt_builder.py`**:
   - Ensure `self.backend` attribute is stored and accessible.
4. **Update `boukensha/agent.py`**:
   - Accept `logger=None` in `Agent.__init__` (defaulting to `Logger()`).
   - Replace console `print` statements with `@logger` method calls across the agent loop.
   - Support exception catching and error logging in `_handle_tool_calls`.
5. **Update `examples/example.py`**:
   - Instantiate `Logger` and pass to `Agent`.
   - Update output header to `=== BOUKENSHA Step 6: The Logger ===`.
6. **Update `README.md`**:
   - Update documentation to describe Step 06 session logging, JSONL format, and `Logger` API.
7. **Create `bin/python/06_the_logger`**:
   - Create executable bash script and make it executable (`chmod +x`).

---

## Verification Plan

When implementing and validating:
- Activate conda environment `fn311` per user preferences before running python commands.
- Run `python3 week1_baseline/python/06_the_logger/examples/example.py` or `./week1_baseline/bin/python/06_the_logger`.
- Inspect generated JSONL log files under `.boukensha/sessions/` to ensure all phase events (`session_start`, `iteration`, `prompt`, `tool_call`, `tool_result`, `response`, `turn_end`) are logged with valid ISO timestamps and session IDs.
