# Python Port Plan — Step 05 (The Agent Loop)

## Context

Source: `week1_baseline/ruby/05_agent_loop` (Ruby gem `boukensha`, step 5 of the 00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).  
Target: `week1_baseline/python/05_agent_loop` (seeded with a copy of `python/04_api_client`, onto which this step's delta is applied).

This plan covers **step 05**. It builds on step 04's `Client` (which performs single HTTP POST requests) by introducing `Agent` — the core loop that manages multi-turn tool calling, response parsing across backends, iteration limits, and turn wrap-up semantics.

---

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/05_agent_loop/README.md` | Design doc for `Agent`, normalized response shapes (`parse_response`), `assistant_message` / `assistant_parts` helpers, task configuration (`max_iterations`, `max_output_tokens`), and turn wrap-up semantics. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha.rb` | Adds `require_relative "boukensha/agent"`. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/agent.rb` | **New file.** Implements `Boukensha::Agent` class: runs the agent loop, parses backend responses, executes tools via `Registry`, injects results into `Context`, and handles iteration caps with a wrap-up call. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/errors.rb` | Adds `LoopError < StandardError`. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/client.rb` | Updates `call(max_output_tokens: 1024, tools: nil)` to accept optional `tools:` parameter and pass it down to `PromptBuilder#to_api_payload`. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/prompt_builder.rb` | Updates `to_api_payload(max_output_tokens: 1024, tools: nil)` to pass `tools:` down to backend; adds `parse_response(response)` delegating to `@backend.parse_response(response)`. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/tasks/base.rb` | Adds `DEFAULT_MAX_ITERATIONS = 25`, `DEFAULT_MAX_OUTPUT_TOKENS = 1024`, and class methods `.max_iterations(settings)` and `.max_output_tokens(settings)`. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/anthropic.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` for Anthropic format. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/openai.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` and private `assistant_message(content)`; updates `to_messages` to handle `:assistant` messages with tools. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/gemini.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` and private `assistant_parts(content)`; updates `to_messages` to handle `:assistant` messages with function calls. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/ollama.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` and private `assistant_message(content)`; updates `to_messages` to handle `:assistant` messages with tools. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/ollama_cloud.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` and private `assistant_message(content)`; updates `to_messages` to handle `:assistant` messages with tools. |
| `week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/lm_studio.rb` | Updates `to_payload` to accept `tools: nil`; adds `parse_response(response)` and private `assistant_message(content)`; updates `to_messages` to handle `:assistant` messages with tools. |
| `week1_baseline/ruby/05_agent_loop/examples/example.rb` | Rewritten example demonstrating the full agent loop with `read_file` and `list_directory` tools. |
| `week1_baseline/bin/ruby/05_agent_loop` | Bash wrapper script for running the Ruby step 05 example. |

Do not modify anything under `week1_baseline/ruby/**` — it remains a read-only reference.

---

## Confirmed current state of the Python target

`week1_baseline/python/05_agent_loop` currently contains the codebase copied from `python/04_api_client`.

| File | Target Status | Required Action |
|---|---|---|
| `boukensha/agent.py` | **Missing.** | Create new file implementing `Agent`. |
| `boukensha/errors.py` | Exists (has `ApiError`, `UnknownToolError`, `UnsupportedModelError`). | Add `LoopError`. |
| `boukensha/tasks/base.py` | Exists. | Add `DEFAULT_MAX_ITERATIONS`, `DEFAULT_MAX_OUTPUT_TOKENS`, `max_iterations`, `max_output_tokens`, and `_integer_setting`. |
| `boukensha/prompt_builder.py` | Exists. | Update `to_api_payload` to accept `tools=None`; add `parse_response(response)`. |
| `boukensha/client.py` | Exists. | Update `call(max_output_tokens=1024, tools=None)` to pass `tools` parameter down. |
| `boukensha/backends/anthropic.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response`. |
| `boukensha/backends/openai.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response` & `_assistant_message`; update `to_messages`. |
| `boukensha/backends/gemini.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response` & `_assistant_parts`; update `to_messages`. |
| `boukensha/backends/ollama.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response` & `_assistant_message`; update `to_messages`. |
| `boukensha/backends/ollama_cloud.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response` & `_assistant_message`; update `to_messages`. |
| `boukensha/backends/lm_studio.py` | Exists. | Update `to_payload` for `tools=None`; add `parse_response` & `_assistant_message`; update `to_messages`. |
| `boukensha/__init__.py` | Exists. | Import and export `Agent` and `LoopError`. |
| `examples/example.py` | Exists. | Rewrite to demonstrate `Agent.run()` with `read_file` and `list_directory` tools. |
| `README.md` | Exists. | Update documentation to reflect Step 05 (The Agent Loop). |
| `bin/python/05_agent_loop` | **Missing.** | Create executable bash wrapper script. |

---

## Target Directory Structure Overview

```
week1_baseline/python/05_agent_loop/
├── README.md                      # [MODIFIED] Updated doc for Step 05 (Agent Loop)
├── requirements.txt               # [UNTOUCHED] Standard library only (no pip dependencies)
├── .python-version                # [UNTOUCHED] Python version specification
├── prompts/
│   └── system.md                  # [UNTOUCHED] System prompt
├── boukensha/
│   ├── __init__.py                # [MODIFIED] Exports Agent and LoopError
│   ├── agent.py                   # [NEW] The Agent class (ports agent.rb)
│   ├── client.py                  # [MODIFIED] Accepts tools=None parameter in call()
│   ├── config.py                  # [UNTOUCHED] Config loader
│   ├── context.py                 # [UNTOUCHED] Context manager
│   ├── errors.py                  # [MODIFIED] Adds LoopError
│   ├── message.py                 # [UNTOUCHED] Message struct
│   ├── prompt_builder.py          # [MODIFIED] Adds parse_response delegation & tools arg
│   ├── registry.py                # [UNTOUCHED] Tool registry
│   ├── tool.py                    # [UNTOUCHED] Tool definition struct
│   ├── backends/
│   │   ├── __init__.py            # [UNTOUCHED] Package init
│   │   ├── base.py                # [UNTOUCHED] Base backend class
│   │   ├── anthropic.py           # [MODIFIED] Adds parse_response & handles tools=None
│   │   ├── openai.py              # [MODIFIED] Adds parse_response & assistant message reconstruction
│   │   ├── gemini.py              # [MODIFIED] Adds parse_response & assistant parts reconstruction
│   │   ├── ollama.py              # [MODIFIED] Adds parse_response & assistant message reconstruction
│   │   ├── ollama_cloud.py        # [MODIFIED] Adds parse_response & assistant message reconstruction
│   │   └── lm_studio.py           # [MODIFIED] Adds parse_response & assistant message reconstruction
│   └── tasks/
│       ├── __init__.py            # [UNTOUCHED] Package init
│       ├── base.py                # [MODIFIED] Adds max_iterations & max_output_tokens helpers
│       └── player.py              # [UNTOUCHED] Player task definition
├── examples/
│   └── example.py                 # [MODIFIED] Full example driving Agent loop
└── (bin/python/05_agent_loop)     # [NEW] Executable bash runner (in week1_baseline/bin/python/)
```

---

## Key Decisions & Architectural Mapping

### 1. Unified Response Shape Across Backends (`parse_response`)

Each provider API returns tool calls and text in different JSON formats. Every backend must implement `parse_response(response)` to normalize the provider response into a common dictionary format:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..." },
        {"type": "tool_use", "id": "...", "name": "...", "input": { ... }}
    ]
}
```

* **Anthropic**:
  * `stop_reason`: `"tool_use"` if `response.get("stop_reason") == "tool_use"`, else `"end_turn"`.
  * `content`: direct pass-through of `response.get("content", [])`.
* **OpenAI & LM Studio**:
  * Extract choices[0].message `content` and `tool_calls`.
  * Parse stringified JSON in `tc["function"]["arguments"]` into dict for `input`.
  * `stop_reason`: `"tool_use"` if `tool_calls` is non-empty, else `"end_turn"`.
* **Gemini**:
  * Iterate over `candidates[0].content.parts`.
  * Map `functionCall` to `{"type": "tool_use", "id": fc["name"], "name": fc["name"], "input": fc.get("args", {})}`.
  * Map `text` to `{"type": "text", "text": part["text"]}`.
  * `stop_reason`: `"tool_use"` if any `functionCall` was present, else `"end_turn"`.
* **Ollama & OllamaCloud**:
  * Extract `message.content` and `message.tool_calls`.
  * Ollama reuses function `name` as `id`.
  * `stop_reason`: `"tool_use"` if `tool_calls` is non-empty, else `"end_turn"`.

### 2. Assistant Message Reconstruction (`_assistant_message` / `_assistant_parts`)

When replaying message history in subsequent turns, assistant messages in `Context` contain normalized content blocks. Backends (except Anthropic, whose format is native) must rebuild provider-specific assistant message objects:
* **OpenAI / LM Studio**: Convert `tool_use` blocks into `tool_calls` array with `id`, `type="function"`, and `function={"name": b["name"], "arguments": json.dumps(b["input"])}`.
* **Gemini**: Map `tool_use` blocks to `{"functionCall": {"name": b["name"], "args": b["input"]}}`.
* **Ollama / OllamaCloud**: Convert `tool_use` blocks into `tool_calls` array with `{"function": {"name": b["name"], "arguments": b["input"]}}`.

### 3. Disabling Tools During Turn Wrap-Up (`tools=None`)

When the iteration limit is reached, `Agent` calls `client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)`.
To allow passing an explicit empty tools list `[]` (overriding the default tools extracted from context), `Client.call`, `PromptBuilder.to_api_payload`, and all backend `to_payload` methods must accept `tools=None`.
When `tools is None`, `to_tools(context.tools)` is used; when `tools` is a list (e.g. `[]`), that list is used directly in the payload.

---

## Detailed Code Specifications

### 1. `boukensha/errors.py`
Add `LoopError`:
```python
class LoopError(Exception):
    """Raised when an agent loop encounters an unrecoverable condition."""
    pass
```

### 2. `boukensha/tasks/base.py`
Add constants and methods:
```python
DEFAULT_MAX_ITERATIONS = 25
DEFAULT_MAX_OUTPUT_TOKENS = 1024

@classmethod
def max_iterations(cls, settings):
    return cls._integer_setting(settings, "max_iterations", DEFAULT_MAX_ITERATIONS)

@classmethod
def max_output_tokens(cls, settings):
    return cls._integer_setting(settings, "max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)

@classmethod
def _integer_setting(cls, settings, key, default):
    val = cls._fetch(settings, key)
    if val is None:
        return default
    return int(val)
```

### 3. `boukensha/prompt_builder.py`
Update payload and add response parsing delegation:
```python
def to_api_payload(self, max_output_tokens=1024, tools=None):
    return self.backend.to_payload(self.context, max_output_tokens=max_output_tokens, tools=tools)

def parse_response(self, response):
    return self.backend.parse_response(response)
```

### 4. `boukensha/client.py`
Update `call` signature and call:
```python
def call(self, max_output_tokens=1024, tools=None):
    # ...
    payload = self.builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)
    # ...
```

### 5. `boukensha/agent.py` (New File)
```python
from .errors import ApiError


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
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self):
        while True:
            if self._iteration_limit_reached():
                return self._wrap_up("max_iterations")

            self.iteration += 1
            print(f"[iteration {self.iteration}/{self.max_iterations}]")

            response = self.client.call(**self._call_opts())
            parsed = self.builder.parse_response(response)

            if parsed.get("stop_reason") == "tool_use":
                self._handle_tool_calls(parsed.get("content", []))
            else:
                return self._extract_text(parsed.get("content", []))

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
            return text if text.strip() else self._fallback_message(reason)
        except ApiError:
            return self._fallback_message(reason)

    def _fallback_message(self, reason):
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        if isinstance(content, str):
            return content
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _handle_tool_calls(self, content):
        self.context.add_message("assistant", content)

        for block in content:
            if block.get("type") != "tool_use":
                continue

            name = block.get("name")
            args = block.get("input", {})
            use_id = block.get("id")

            print(f"  tool call → {name}({args})")
            result = self.registry.dispatch(name, args)
            print(f"  tool result → {str(result)[:60]}")

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)
```

---

## Implementation Steps

1. **`boukensha/errors.py`**: Add `LoopError`.
2. **`boukensha/tasks/base.py`**: Add `max_iterations`, `max_output_tokens`, and `_integer_setting`.
3. **`boukensha/prompt_builder.py` & `boukensha/client.py`**: Add `tools` parameter forwarding and `parse_response`.
4. **`boukensha/backends/*.py`**: Add `parse_response` and assistant message conversion to all 6 backends (`anthropic.py`, `openai.py`, `gemini.py`, `ollama.py`, `ollama_cloud.py`, `lm_studio.py`).
5. **`boukensha/agent.py`**: Create `Agent` class implementation.
6. **`boukensha/__init__.py`**: Export `Agent` and `LoopError`.
7. **`examples/example.py`**: Port Ruby `05_agent_loop/examples/example.rb`.
8. **`README.md`**: Update Python 05 README documentation.
9. **`bin/python/05_agent_loop`**: Create executable script wrapper.
10. **Verification**: Execute `bin/python/05_agent_loop` or run python example using conda env `fn311` per user preferences.
