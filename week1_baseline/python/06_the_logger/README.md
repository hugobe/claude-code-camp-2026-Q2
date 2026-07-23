# Step 6 — The Logger

`boukensha.Logger` records each agent run as structured JSON Lines. 
It is a file logger, not user-facing display output.

## Session Logs

Each `boukensha.Logger` instance creates a session id and writes one log file for that session:

```text
.boukensha/sessions/<session-id>.jsonl
```

Every line is a complete JSON object with `session_id`, `at`, and `phase` fields, plus phase-specific data. This keeps logs grep/tail friendly and machine readable.

```json
{"phase":"session_start","session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
{"phase":"iteration","n":1,"session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
```

Model response lines include the active task, provider, model, normalized token counts, and estimated USD cost when the backend has token pricing data:

```json
{"phase":"response","task":"player","provider":"anthropic","model":"claude-haiku-4-5","input_tokens":1000,"output_tokens":100,"cost_usd":0.0015}
```

## Logger API

A plain object with one method per phase:

| Method | Phase | Logs |
|---|---|---|
| `iteration(n, max)` | `iteration` | loop counter |
| `prompt(messages, tools)` | `prompt` | messages and available tools |
| `tool_call(name, args)` | `tool_call` | tool name and arguments |
| `tool_result(name, result, ok, error)` | `tool_result` | tool execution result and status |
| `response(text, usage, stop_reason, task, backend)` | `response` | response text, token usage, task/provider/model, estimated cost |
| `raw(data)` | `raw` | raw provider response when debug is enabled |
| `limit_reached(kind, n, max)` | `limit_reached` | iteration ceiling reached |
| `turn_end(reason, iterations, tokens)` | `turn_end` | end of agent turn |

## Task Configuration

Step 6 uses task-based settings:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, the player task reads `.boukensha/prompts/player/system.md`. Otherwise it falls back to this step's shipped `prompts/system.md`.

Default usage:

```python
logger = boukensha.Logger()
agent = boukensha.Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
)
```

You can also provide a session id or override the destination directory:

```python
boukensha.Logger(session_id="manual-session")
boukensha.Logger(dir="/tmp/boukensha-sessions")
```

For compatibility, `log=` still accepts an explicit file path, but normal iteration usage should write under `.boukensha/sessions`.

## Debug Events

Call `boukensha.debug()` before running the agent to include raw provider responses:

```python
boukensha.debug()
```

## Run Example

```sh
./week1_baseline/bin/python/06_the_logger
```
