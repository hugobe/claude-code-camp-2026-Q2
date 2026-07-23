# The API Client

The API Client takes the payload assembled by `PromptBuilder` and sends it to the API. One HTTP POST, one response. No tool loop yet — just proving the round trip works.

## New Files

| File | Description |
|---|---|
| `boukensha/client.py` | Makes the HTTP request and parses the response |
| `boukensha/backends/base.py` | Shared backend model validation and model metadata helpers |
| `boukensha/tasks/base.py` | Shared task configuration helpers for provider, model, and prompts |
| `boukensha/tasks/player.py` | Player task definition |
| `prompts/system.md` | Default system prompt used when the player task does not override it |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `ApiError` for failed HTTP requests |
| `boukensha/config.py` | Reads `tasks.player` instead of top-level provider/model settings |
| `boukensha/backends/*.py` | Backends now own supported model tables with context windows and cost metadata |

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint
      ↓
Raw JSON response
```

## boukensha.Client

| Method | Description |
|---|---|
| `call(max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response |

## Task Configuration

This step uses the task-based configuration introduced in the earlier baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, Boukensha reads `.boukensha/prompts/player/system.md`.
Otherwise it falls back to this step's shipped `prompts/system.md`.

Each backend validates the configured model at construction time. Unsupported model names raise `UnsupportedModelError`, and supported models expose backend-owned metadata such as `context_window`, `usage_unit`, and token cost estimates for later logging steps.

## No Dependencies

`Client` uses Python's standard `urllib.request` module. No pip packages, no changes to `requirements.txt`. This is intentional — the HTTP call itself is trivial and should be visible, not hidden behind a library.

## What the Response Looks Like

The raw response shape differs between backends. This is what you get back from `client.call()` before any processing:

### Anthropic
```json
{
  "id": "msg_01XY",
  "type": "message",
  "role": "assistant",
  "content": [
    { "type": "text", "text": "Sure, let me read that file." }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 42, "output_tokens": 18 }
}
```

### Ollama
```json
{
  "model": "llama3.2",
  "message": {
    "role": "assistant",
    "content": "Sure, let me read that file."
  },
  "done_reason": "stop",
  "done": true
}
```

### LM Studio
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "google/gemma-4-12b-qat",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "Sure, let me read that file.", "tool_calls": [] },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 29, "completion_tokens": 12, "total_tokens": 41 }
}
```

LM Studio uses the same OpenAI Chat Completions shape, since its local server is
OpenAI-compatible. Requires the "Local Server" running in LM Studio (or `lms server
start`), no API key.

When the model wants to call a tool the response looks different. Anthropic uses `stop_reason: "tool_use"` and adds a `tool_use` block to `content`. Ollama and LM Studio add a `tool_calls` array to the message. Handling those differences is the job of step 5 — the Agent Loop.

## Output example

```
$ ./week1_baseline/bin/python/04_api_client
=== BOUKENSHA Step 4: API Client ===

Sending request to https://api.anthropic.com/v1/messages...

Raw response:
{
  "model": "claude-opus-4-5-20251101",
  "id": "msg_01Y3zL8dZKrdLqry6BoiyC4r",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I don't have a function available to list directory contents. I can only read files if you provide me with the specific file path.\n\nCould you either:\n1. Tell me which specific file(s) you'd like me to read\n2. Provide me with a list of the files in your directory\n\nIf you're working in a terminal, you can run `ls` (on Mac/Linux) or `dir` (on Windows) to see what files are available, and then let me know which ones you'd like me to look at!"
    }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 585, "output_tokens": 118 }
}
```

> The response is what we'd expect from Claude. It got the message, saw the `read_file` tool, but told us it can't list directory contents because we only gave it a `read_file` tool, not a `list_directory` tool.

## Considerations

**The client raises `ApiError` on failure.** A non-2xx response means something went wrong — bad API key, malformed payload, server error. BOUKENSHA surfaces this explicitly rather than returning a confusing `None` or partial response.

**SSL is handled automatically.** `urllib.request` uses `https` when the URL scheme calls for it, and Python's `ssl` module resolves system CA certificates without any manual configuration. Ollama running locally uses plain `http`, so no SSL is involved there either.

Ruby's version of this client hand-picks an OpenSSL certificate path, which turns out to be platform-specific (works on macOS, breaks on Linux/WSL2). Python's standard library sidesteps that rough edge entirely — `urllib.request` finds the right certificate store on its own, so there's no equivalent workaround to carry over here.

## Run Example

```bash
./week1_baseline/bin/python/04_api_client
```
