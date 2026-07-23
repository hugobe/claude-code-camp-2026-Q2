# Step 7 — The Run DSL

## What this step adds

A single top-level entry point: `boukensha.run`.

Every previous step required manually creating and wiring together a `Context`, `Registry`, backend, `PromptBuilder`, `Client`, `Logger`, and `Agent`. Step 7 hides all of that behind one function call and an optional `configure` callback.

## The new primitives

### `boukensha.RunDSL`

A tiny host object passed to the `configure` callback. It exposes exactly one method, `tool`, which delegates straight to `Registry.tool`:

```python
class RunDSL:
    def __init__(self, registry):
        self.registry = registry

    def tool(self, name, description, parameters=None, block=None):
        return self.registry.tool(name, description=description, parameters=parameters, block=block)
```

Ruby's `Boukensha.run(...) { instance_eval(&block) }` re-parents `self` inside the block so bare `tool "name", ...` calls resolve against the `RunDSL` instance. Python has no clean equivalent to `instance_eval` for a plain function passed by the caller, so the port makes the hand-off explicit: `run()` takes a `configure` callable and invokes it itself with the `RunDSL` instance as its one argument.

### `boukensha.run`

Accepts keyword arguments that describe *what* to do. All plumbing is handled internally.

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's system prompt | System prompt |
| `model` | task's configured model | Model name |
| `backend` | task's configured provider | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, `"ollama_cloud"`, or `"lm_studio"` |
| `api_key` | matching `*_API_KEY` env var | API key for the chosen backend (not needed for `"ollama"` or `"lm_studio"`) |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `lm_studio_host` | `"http://localhost:1234/v1"` | LM Studio base URL |
| `log` | `None` | Optional path override; by default logs go to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured cap | Max tokens per API response |
| `configure` | `None` | Callback receiving a `RunDSL` instance, used to register tools |

An unrecognized `backend` raises `ValueError`. The `Logger` is always closed via `finally`, even if the agent run raises.

## Before and after

**Step 6 — manual plumbing:**

```python
ctx = boukensha.Context(task=boukensha.Player, system=system_prompt)
registry = boukensha.Registry(ctx)
backend = boukensha.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-haiku-4-5")
builder = boukensha.PromptBuilder(ctx, backend)
client = boukensha.Client(builder)
logger = boukensha.Logger()
agent = boukensha.Agent(
    context=ctx, registry=registry, builder=builder, client=client, logger=logger,
)

def _read_file(path):
    return Path(path).read_text()

registry.tool(
    "read_file",
    description="Read a file",
    parameters={"path": {"type": "string"}},
    block=_read_file,
)

ctx.add_message("user", "Read lib/boukensha.rb")
agent.run()
```

**Step 7 — just describe what you want:**

```python
def _read_file(path):
    return Path(path).read_text()

def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read a file",
        parameters={"path": {"type": "string"}},
        block=_read_file,
    )

result = boukensha.run(task="Read lib/boukensha.rb", configure=configure)
```

## Logger additions

`Logger.turn(n)` logs a lightweight per-turn event (`{"phase": "turn", "n": n}`), distinct from the existing `turn_end`.

`Logger.subscribe(callback)` registers a callback that receives every event (the same dict written to disk, before the `session_id`/`at` fields are merged in) as it's logged:

```python
logger.subscribe(lambda event: print(event))
```

Nothing in this step's example uses `turn` or `subscribe` — they're ported for parity with the Ruby source, ready for a future step to wire up.

## Run Example

```sh
./week1_baseline/bin/python/07_the_run_dsl
```

The example registers two tools (`read_file`, `list_directory`) via `configure` and asks the agent to read `README.md` and summarize it. The logger writes a session JSONL file under `.boukensha/sessions`.
