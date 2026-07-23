---
name: python-port
description: Port the next (or a named) Ruby "boukensha" step from week1_baseline/ruby/ to a matching Python step under week1_baseline/python/, following this repo's copy-forward-then-apply-the-delta porting workflow. Use whenever the user asks to port a ruby step to python, continue/resume the python port, work on docs/plans/python_port, or mentions boukensha python, week1_baseline python, or a step by number or name ("port step 4", "04_api_client to python", "do the next python step"). Always load this skill before hand-writing or scaffolding a new week1_baseline/python/<step> directory from scratch — the established workflow requires literally copying the previous python step's directory first and porting only that step's delta on top, not writing a fresh implementation.
---

# Port a Ruby boukensha step to Python

## Why this workflow, not a fresh rewrite

Every Python step folder under `week1_baseline/python/` is a **copy of the
previous step plus that one step's delta** — never an independent
reimplementation. This is deliberate: it keeps each step's Python code
diffable against the step before it, the same way the Ruby steps are, and it
means a step that changes nothing (e.g. `config.py` in step 03) simply isn't
touched. Departing from this — writing a step from scratch, "cleaning up" a
copied file that didn't need changing, or fixing a Ruby quirk instead of
porting it as-is — breaks that diffability and the tutorial's pedagogy. See
`week1_baseline/ruby/ITERATIONS.md` for the full 00–12 roadmap this all
tracks.

`week1_baseline/ruby/**` is read-only reference for this whole workflow.
Never edit it.

## Step 1 — Identify the target step

List both trees to see where things stand:

```bash
ls week1_baseline/ruby/ week1_baseline/python/
```

A Ruby step only counts as portable if it actually has content (a
`lib/boukensha.rb`, `README.md`, etc.) — some numbered Ruby directories are
still empty placeholders waiting to be recorded (check with `ls`; an empty
one has nothing but the bare directory). **If the user names a step whose
Ruby source is empty, stop and say so** — this skill ports existing Ruby
code, it doesn't invent the Ruby side.

- If the user names a step (by number or folder name), target that one.
- Otherwise, the target is the lowest-numbered Ruby step with content that
  doesn't yet have a same-named Python counterpart directory.
- The **previous step** is the Python directory with the next-lower number
  — it must already exist; it's the copy source. If it doesn't exist, an
  earlier step is missing and needs to be done first.

Also check `docs/plans/python_port/<NN_name>.md`. Several of these already
exist as empty placeholder files — that's expected, this skill fills them
in. If one already has real content, treat it as an already-approved plan:
skim it, confirm it still matches the current Ruby source (`diff -rq`
against the previous Ruby step — see Step 2), and skip straight to Step 4
rather than overwriting a plan a human already signed off on.

## Step 2 — Research the delta

Don't guess at what changed — read it:

```bash
diff -rq week1_baseline/ruby/<prev_name> week1_baseline/ruby/<target_name>
```

Then, for every file the diff flags as new or changed:
- Read the full Ruby source file.
- Read `week1_baseline/ruby/<target_name>/README.md` (design rationale,
  expected example output) and `examples/example.rb` (exact input/output
  ordering the Python port must match).
- Diff `Gemfile`/`Gemfile.lock` against the previous step — only add a pip
  dependency if a gem was genuinely added.
- Check `week1_baseline/bin/ruby/<target_name>` for how the smoke test is
  invoked.
- Grep the relevant step's write-up in `week1_baseline/ruby/ITERATIONS.md`
  — the author left behind narrative notes and gotchas there (e.g. a known
  arity inconsistency in step 3's backends, token-accounting semantics in
  step 12) that aren't always obvious from the code alone.

## Step 3 — Write the plan doc

Write (or fill in, if it exists but is empty/stale) `docs/plans/python_port/<NN_name>.md`.
Read `references/plan-template.md` in this skill directory for the exact
shape to follow — it's extracted from the four existing plans
(`00_config.md`, `01_struct_skeleton.md`, `02_the_registry.md`,
`03_prompt_builder.md`), which are the authoritative style examples. Skim at
least the most recent one directly before writing, since matching its level
of detail matters more than matching a rigid skeleton.

Apply the standing translation conventions below wherever relevant, and cite
them in the plan's "Decisions" section instead of re-deriving them each
time.

**Standing translation conventions** (apply unless the target step's Ruby
source calls for something else):

| Ruby | Python | Notes |
|---|---|---|
| `Struct.new(...)` | `@dataclass` | Same field names/order. |
| Symbols (`:foo`) | Strings (`"foo"`) | `yaml.safe_load` only ever produces string keys, so drop Ruby's symbol/string dual-lookup entirely rather than porting it. |
| `raise ArgumentError` | `raise ValueError` | Nearest Python equivalent for "bad argument." |
| Abstract base + `NotImplementedError` | Same shape, `@classmethod`/`@staticmethod` as needed | Keep the class-based `Tasks::Base`-style design 1:1, even where a free function would be more idiomatic Python — later steps stay easy to diff against Ruby. |
| Class-level data tables (`MODELS`, pricing, etc.) | Transcribed verbatim | Static tutorial data — port the values, don't "improve," re-derive, or re-sort them. |
| A Ruby method's own quirk or inconsistency (e.g. mismatched arity across sibling classes) | Preserved as-is | The task is a faithful port of that step, not a fix. Note it in the plan explicitly so it isn't "corrected" by accident later. |

Show the plan to the user and pause for confirmation before implementing —
every existing plan doc ends with either explicit "Open detail questions"
or an implicit expectation of review before code gets written. Skip the
pause only if the user has explicitly said to go ahead without stopping.

## Step 4 — Implement

Only after the plan is agreed:

1. **Copy forward first, unconditionally:**
   ```bash
   mkdir -p week1_baseline/python/<NN_name>
   rsync -a --exclude='.venv' --exclude='__pycache__' \
     week1_baseline/python/<prev_name>/ week1_baseline/python/<NN_name>/
   ```
   (`.venv` is excluded on purpose: the bin script recreates it from
   `requirements.txt` on first run, and copying it verbatim both carries a
   stale absolute path in `pyvenv.cfg` and risks the repo's known
   iCloud-Desktop-sync issue — hidden-flagged dotfiles / sporadic EPERM
   write locks on this machine. Plain `pip install` without `-e` is
   otherwise unaffected, but there's no reason to copy a venv at all when
   the bin script rebuilds it for free.)

   Never hand-write a file this step doesn't actually change — if the plan
   says a file needs zero changes, leave the copied version untouched.

2. **Apply only the delta** identified in Step 2: new/changed modules,
   updated `boukensha/__init__.py` re-exports, a rewritten
   `examples/example.py` (port of the new `example.rb`, same output
   ordering so the two can be diffed side by side), a rewritten
   `README.md`, and `requirements.txt` only if the plan says a dependency
   was actually added.

3. **Add the bin script** `week1_baseline/bin/python/<NN_name>`, copied
   from the most recent existing `bin/python/<prev_name>` script with only
   the `cd` target changed (all existing ones are identical apart from
   that), then `chmod +x` it.

## Step 5 — Verify

- Run the bin script (or `python examples/example.py` inside a venv with
  `requirements.txt` installed) and confirm it completes without error.
- Compare its output's structure/ordering against
  `bundle exec ruby examples/example.rb` in the matching Ruby step
  directory (manually, if Ruby/bundler isn't set up in this environment —
  note that instead of skipping the check).
- Confirm every symbol the plan says this step should export actually
  imports: `from boukensha import ...`.
- `git status` / `git diff` — confirm nothing under `week1_baseline/ruby/**`
  changed.

## Step 6 — Report

Tell the user which step got ported, which files were created/changed, and
how to run it (`./week1_baseline/bin/python/<NN_name>`). If any acceptance
criterion from the plan couldn't be verified in this environment (e.g. no
API key for a live backend call), say so plainly rather than claiming it
passed.
