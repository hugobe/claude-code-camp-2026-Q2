# Plan doc template

Extracted from the four existing plans (`docs/plans/python_port/00_config.md`,
`01_struct_skeleton.md`, `02_the_registry.md`, `03_prompt_builder.md`) — they
all follow this shape. Read at least the most recent one of those before
writing a new plan; matching its tone/detail level matters more than matching
this skeleton exactly.

```markdown
# Python Port Plan — Step NN (<Step Title>)

## Context

Source: `week1_baseline/ruby/NN_name` (Ruby gem `boukensha`, step NN of the
00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/NN_name` (state it plainly: a fresh copy of
`python/<prev>`, already made / to be made as step one of implementation).

This plan covers **only step NN**. Say one sentence on what it builds on top
of (the previous step's structures) and one sentence on what's new.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/NN_name/README.md` | Design doc, ... |
| `week1_baseline/ruby/NN_name/lib/boukensha.rb` | Top-level require, what it now pulls in |
| `week1_baseline/ruby/NN_name/lib/boukensha/<new_file>.rb` | one row per new/changed Ruby file |
| `week1_baseline/ruby/NN_name/examples/example.rb` | Smoke test / reference for output ordering |
| `week1_baseline/ruby/NN_name/Gemfile` + `Gemfile.lock` | Only if a dependency changed |
| `week1_baseline/bin/ruby/NN_name` | Bash wrapper — model for the Python equivalent |

Do not modify anything under `week1_baseline/ruby/**` — it stays a
read-only reference.

## Confirmed current state of the Python target

State what `diff -rq week1_baseline/python/<prev> week1_baseline/python/NN_name`
actually shows (should be "no differences" if the copy was just made — call
that out explicitly), then a short table of what's missing/needs updating:

| File | Status |
|---|---|
| `boukensha/<x>.py` | Present, unchanged — no change needed. / Missing entirely. Must be created. |
| `examples/example.py` | Still the step <prev> example. **Needs rewrite.** |
| `README.md` | Still the step <prev> README. **Needs rewrite.** |
| `requirements.txt` | Unchanged from step <prev> (list current deps) — call out explicitly whether this step's Gemfile added anything. |
| `bin/python/NN_name` | Missing. Must be created. |

## Decisions & architectural mapping

One `###`-headed subsection per new/changed Ruby file or concept. Include an
actual Python code sketch for anything non-trivial (class shape, method
signatures) — not just prose. Call out explicitly:
- Any Ruby idiom translation choice made (see the skill's SKILL.md
  "Standing translation conventions" table) and *why*, if it's not obvious.
- Any deliberate Ruby quirk/inconsistency being preserved rather than fixed,
  and why (cite the reason — "faithful port, not a fix").
- Exact method signatures / constructor keyword args, matching Ruby's
  argument order and naming as closely as Python idiom allows.

## Target structure

```
week1_baseline/python/NN_name/
  requirements.txt               (copied from step <prev> / UPDATED — new dep)
  boukensha/
    __init__.py                  (UPDATE - add re-exports for ...)
    <existing files>              (no change)
    <new_file>.py                (NEW - ...)
  prompts/
    system.md                    (no change, unless the Ruby step changed it)
  examples/
    example.py                   (REWRITE - port step NN example.rb)
  README.md                      (REWRITE - document step NN Python usage)
```

## File-by-file mapping

| Ruby source | Python target | Action | Notes |
|---|---|---|---|
| ... | ... | Create / Update / Copied / None | ... |

## Bin Script Runner (`week1_baseline/bin/python/NN_name`)

Copy verbatim from the most recent existing `bin/python/<prev>` script, only
changing the `cd` target directory name. Do not introduce new logic here
unless the Ruby step's own bin script does something structurally different
(rare — check `week1_baseline/bin/ruby/NN_name` first).

## Acceptance criteria

- `python examples/example.py` produces matching structure/ordering of
  output lines as `bundle exec ruby examples/example.rb`.
- `from boukensha import ...` (full symbol list for this step) imports
  cleanly.
- One assertion per new piece of behavior the step introduces (specific
  inputs → specific outputs/errors), not just "it works."
- Executing `./week1_baseline/bin/python/NN_name` runs cleanly end-to-end.
- No code under `week1_baseline/ruby/NN_name` is modified.

## Not part of this plan

- All later steps in the 00–12 roadmap.
- Anything explicitly out of scope for this step per `ITERATIONS.md` (e.g.
  "no HTTP calls yet," "no tool execution wiring yet").
```
