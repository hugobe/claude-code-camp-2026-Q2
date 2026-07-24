# Step 8 — The REPL Loop

## What this step adds

| | Step 7 | Step 8 |
|---|---|---|
| Entry point | `boukensha.run(task=...)` | `boukensha.repl(...)` |
| Turns | one | many |
| History | discarded | accumulates across turns |
| User interaction | none | stdin prompt |

## New primitives

### `boukensha.Repl`

The interactive session loop. Built-in commands:

| Command | Effect |
|---|---|
| `/quiet` | Suppress logging output |
| `/loud` | Re-enable logging output |
| `/clear` | Wipe conversation history (tools stay registered) |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D | EOF — leave the REPL |
| Ctrl-C | Interrupt — leave the REPL gracefully |

### `boukensha.repl`

Same keyword arguments as `boukensha.run`, minus `task`. Register tools via a `configure` callback; then the REPL loop takes over.

```python
def configure(dsl):
    dsl.tool(
        "read_file",
        description="Read a file from disk",
        parameters={"path": {"type": "string", "description": "File path"}},
        block=lambda path: Path(path).read_text(),
    )

boukensha.repl(model="claude-haiku-4-5", configure=configure)
```

## Changes from step 7

### `Context.clear_messages()`
Wipes `.messages` while keeping tools registered. Used by the REPL `/clear` command.

### `Agent.run` — persists the final reply
Before step 8, the agent returned the final text without adding it to the context. That was fine for one-shot runs (context is thrown away anyway), but a REPL needs the full transcript so subsequent turns see the prior exchange.

```python
# step 7 — final text returned but NOT in context
return text

# step 8 — final text added to context, then returned
self.context.add_message("assistant", text)
return text
```

### `Client` — 401-specific error message
A failed request with HTTP status 401 now raises `ApiError("authentication failed (401) — check your API key")` instead of the generic "API request failed" message.

### `Config._resolve_dir` — a middle resolution tier
`BOUKENSHA_DIR` now resolves in three steps instead of two:

1. Explicit `BOUKENSHA_DIR` environment variable (unchanged)
2. **New:** `./.boukensha` in the current working directory, if it exists
3. `~/.boukensha` default (unchanged)

### `boukensha.VERSION`
`VERSION = "0.8.0"`, shown in the REPL banner.

`Logger.turn(n)` (added in step 7, unused there) gets its first caller here — the REPL logs a `{"phase": "turn", "n": n}` event at the start of every turn.

## Running it

```sh
./week1_baseline/bin/python/08_the_repl_loop
```

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.8.0)     ║
╚══════════════════════════════════════╝
  config:    /Users/you/.boukensha
  provider:  anthropic (claude-haiku-4-5)  ✓ API key set

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

boukensha> list the files in the boukensha directory
…
boukensha> now read boukensha/agent.py and explain the loop
…
boukensha> /quiet
(logging suppressed — type /loud to re-enable)
boukensha> what was the first file I asked you about?
…
boukensha> /exit
Goodbye.
```

The last question demonstrates persistent history: the agent answers from the accumulated transcript, not just the last message.
