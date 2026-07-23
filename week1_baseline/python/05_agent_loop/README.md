# The Agent Loop

The Agent Loop is the heart of BOUKENSHA. Everything built before this — the structs, the registry, the prompt builder, the client — was setup. The loop is where the agent actually does work.

## New Files

| File | Description |
|---|---|
| `boukensha/agent.py` | The agent loop — sends requests, dispatches tools, and knows when to stop |

## Updated Files

| File | Change |
|---|---|
| `boukensha/errors.py` | Added `LoopError` for runaway agents |
| `boukensha/tasks/base.py` | Added `max_iterations` and `max_output_tokens` task helpers |
| `boukensha/prompt_builder.py` | Added `parse_response`, delegating to the backend; updated `to_api_payload` for `tools=None` |
| `boukensha/client.py` | Updated `call` to accept `tools=None` |
| `boukensha/backends/*.py` | Added `parse_response` and assistant message reconstruction across backends |

## How It Works

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls
        → dispatch each tool via Registry
        → inject results as tool_result messages
        → go back to top
    no  → return final text response
```

## boukensha.Agent

| Method | Description |
|---|---|
| `run()` | Starts the loop and returns the final text response when the agent is done |

## Every Backend Speaks the Same Normalized Shape

Different providers use different response formats — Anthropic nests tool calls inside `content`, Ollama puts them in `message.tool_calls`, OpenAI nests them under `choices[0].message.tool_calls`, and Gemini calls them `functionCall` parts. Rather than teach the Agent loop about each of these, every backend implements `parse_response`, converting its raw response into one common shape:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    ]
}
```

`Agent` only ever sees this shape — it calls `self.builder.parse_response(response)`, which delegates to the backend, and never inspects a raw provider response.

The conversion also runs in reverse. When the conversation history is replayed on the next request, backends rebuild a provider-specific assistant message from the normalized `content` blocks via a private `_assistant_message` (or `_assistant_parts`) method — the inverse of `parse_response`. Anthropic's `content` array doubles as both the normalized shape and the wire format, so it needs no extra conversion.

**Tool call IDs aren't universal.** Anthropic and OpenAI assign every tool call a unique `id`, echoed back in the `tool_result`. Ollama, OllamaCloud, and Gemini don't assign call ids at all — those backends reuse the tool's `name` as its `id` and match the `tool_result` back to the call by name.

## Task Configuration

This step uses the task-based configuration introduced in the earlier baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
    max_iterations: 25
    max_output_tokens: 1024
```

When `prompt_override.system` is true, Boukensha reads `.boukensha/prompts/player/system.md`.
Otherwise it falls back to this step's shipped `prompts/system.md`.
`max_iterations` controls model round-trips per turn before wind-down, and `max_output_tokens` is passed to each model reply.

## What the Loop Looks Like

Running the example produces output like this:

```
=== BOUKENSHA Step 5: Agent Loop ===

[iteration 1]
  tool call → list_directory({'path': '.'})
  tool result → README.md, examples, boukensha

[iteration 2]
  tool call → read_file({'path': 'README.md'})
  tool result → # The Agent Loop...

=== FINAL RESPONSE ===
Here are the files in the current directory: README.md, examples, boukensha.
The contents of README.md are...
```

## Considerations

**The assistant message must be stored before the tool result.** The Anthropic API requires the assistant's tool_use block to appear in the message history before its corresponding tool_result. BOUKENSHA handles this in `_handle_tool_calls` — get the order wrong and the API rejects the request.

**The model can call multiple tools in one turn.** The loop handles this by iterating over all tool_use blocks in a single response before making the next API call.

**`MAX_ITERATIONS` is a turn ceiling.** A poorly prompted agent can loop forever if the model keeps calling tools. BOUKENSHA stops starting new work after 25 iterations by default and makes one short wrap-up call with tools disabled. This keeps the turn bounded while still returning a useful final response.

**The agent has no way to stop itself.** The model signals it is done via `stop_reason: "end_turn"`. BOUKENSHA watches for that signal and exits the loop. The agent never decides unilaterally to stop.

## Run Example

```bash
./week1_baseline/bin/python/05_agent_loop
```
