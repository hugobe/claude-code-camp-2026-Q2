# Python Port Plan — Step 00 (Configuration)

## Context

Source: `week1_baseline/ruby/00_config` (Ruby gem `boukensha`, step 0 of the
00–12 roadmap described in `week1_baseline/ruby/ITERATIONS.md`).
Target: `week1_baseline/python/00_config` (currently an empty directory).

This plan covers **only step 00**. Every later Ruby step (01 Struct
Skeleton, 02 Tool Registry, … 12 Context Management) gets its own plan file
following the same naming scheme (`docs/plans/python_port/01_...`, `02_...`,
…) if/when needed — not part of this plan.

## Source files to reference (Ruby)

| File | Purpose |
|---|---|
| `week1_baseline/ruby/00_config/README.md` | Design doc, config resolution order, YAML schema, expected example output |
| `week1_baseline/ruby/00_config/lib/boukensha.rb` | Top-level require (= package entry point) |
| `week1_baseline/ruby/00_config/lib/boukensha/config.rb` | `Boukensha::Config` — directory resolution, `.env` loading, `settings.yaml` loading, `dig`, MUD accessor methods |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/base.rb` | Abstract `Tasks::Base` — class methods for `provider`, `model`, `prompt_override?`, `system_prompt` |
| `week1_baseline/ruby/00_config/lib/boukensha/tasks/player.rb` | Concrete `Tasks::Player` (only `task_name`) |
| `week1_baseline/ruby/00_config/prompts/system.md` | Default system prompt (plain text, language-agnostic — copy as-is) |
| `week1_baseline/ruby/00_config/examples/example.rb` | Smoke test / reference for input/output ordering |
| `week1_baseline/ruby/00_config/Gemfile` + `Gemfile.lock` | Shows the one deliberate dependency (`dotenv`) — model for the Python requirements |
| `week1_baseline/bin/00_config` | Bash wrapper that runs the Ruby smoke test — model for a Python equivalent |

Do not modify anything under `week1_baseline/ruby/**` — it stays a
read-only reference.

## Decisions already made

1. **Project layout:** no `uv`/`pyproject.toml` like
   `week0_explore/circlemud-world-parser`. Instead **pip + `requirements.txt`**,
   as a **snapshot per step** (`python/00_config`, `python/01_...`, … each
   self-contained) — mirrors the Ruby pattern of "one Gemfile per step
   folder", just with pip instead of Bundler.
2. **Settings format:** `settings.yaml` stays YAML (no switch to TOML).
   `PyYAML` is added as a dependency — analogous to Ruby's one deliberate
   exception (the `dotenv` gem) to the stdlib-only principle. `python-dotenv`
   is added as a second, equally deliberate exception.
3. **Tasks design:** `Tasks::Base` is translated closely 1:1 — a class with
   `@classmethod`s, no instances, `Player(Base)` as a subclass. No switch to
   free module functions, so later steps stay easy to diff against the Ruby
   original.
4. **`dig()`:** becomes a simple dict-walk (a chain of `dict.get`), **without**
   Ruby's symbol/string duality — `yaml.safe_load` only ever produces string
   keys in Python, so the double check (`node[key.to_s] || node[key.to_sym]`)
   is dropped entirely.

## Target structure

```
week1_baseline/python/00_config/
  requirements.txt
  boukensha/
    __init__.py
    config.py
    tasks/
      __init__.py
      base.py
      player.py
  prompts/
    system.md
  examples/
    example.py
  README.md
```

## File-by-file mapping

| Ruby source | Python target | Notes |
|---|---|---|
| `lib/boukensha/config.rb` | `boukensha/config.py` | `Config` class. `DEFAULT_DIR = Path.home() / ".boukensha"`. `PROMPTS_DIR` points, relative to the package, at the sibling `prompts/` directory (`Path(__file__).resolve().parent.parent / "prompts"`). `tasks(name=None)`, `user_prompts_dir`, `mud_host`/`mud_port`/`mud_username`/`mud_password` as properties, `dig(*keys)` as a simple dict-walk (see above), `__repr__` instead of `to_s`/`inspect`. `resolve_dir`/`load_env`/`load_settings` become `_`-prefixed "private" methods. `.env` loading via `python-dotenv`'s `load_dotenv(...)`, YAML loading via `yaml.safe_load(...)`. |
| `lib/boukensha/tasks/base.rb` | `boukensha/tasks/base.py` | `Base` class with `@classmethod task_name` (raises `NotImplementedError`), `provider(settings)`, `model(settings)` (both raise `ValueError` instead of Ruby's `ArgumentError` when a required field is missing), `prompt_override(settings, prompt="system")`, `prompt(...)`, `system_prompt(...)`. Private helpers (`_fetch`, `_read_user_prompt`, `_read_default_prompt`, `_read_file`) as `_`-prefixed `@staticmethod`/`@classmethod`. |
| `lib/boukensha/tasks/player.rb` | `boukensha/tasks/player.py` | `class Player(Base)`, `task_name` returns `"player"`. |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Re-exports `Config`, `Player` (`from .config import Config`, `from .tasks.player import Player`). |
| `prompts/system.md` | `prompts/system.md` | 1:1 copy, plain text, no porting needed. |
| `examples/example.rb` | `examples/example.py` | Same output ordering/format as the Ruby original (see "Run Example" in the Ruby README), so both implementations can be diffed directly. `os.environ.setdefault("BOUKENSHA_DIR", ...)` instead of `ENV["BOUKENSHA_DIR"] ||=`. |
| `Gemfile` / `Gemfile.lock` | `requirements.txt` | `pyyaml`, `python-dotenv`. |
| `README.md` | `README.md` | Carry content over 1:1; the YAML schema/example stays unchanged (format doesn't change); replace Ruby code blocks with the Python equivalents; adjust the "Run Example" section to the Python invocation. |
| `../../bin/00_config` (bash wrapper) | still open, see below | currently only calls the Ruby path. |

## Open detail questions (please confirm)

1. **Bin wrapper:** should `week1_baseline/bin/00_config` (currently pure
   Ruby) stay untouched and Python get its **own** script (suggestion:
   `week1_baseline/bin/00_config_python`), or should the existing script be
   extended to choose between Ruby/Python (e.g. via an argument or env var)?
2. **Virtual environment:** plain `python -m venv .venv` +
   `pip install -r requirements.txt` locally inside the step folder, or
   should the wrapper script run against a venv the user already activated
   (no venv creation inside the script)? Reminder: `.venv` would sit on the
   iCloud-synced Desktop — the known `hidden`-flag issue mainly affects
   editable installs (`uv`), plain `pip install` without `-e` should be
   unaffected, but sporadic EPERM write locks on many files remain a residual
   risk.
3. **Python version:** `circlemud-world-parser` (the only other Python
   project in the repo) requires `.python-version` = `3.14`. Should
   `00_config` assume the same minimum version, or should the baseline port
   stay deliberately broader-compatible (e.g. 3.11+ for `tomllib`, even
   though TOML isn't used here)?
4. **Tests:** Ruby step 0 has no formal tests, only `examples/example.rb` as
   a smoke test. Should the Python port additionally get a
   `tests/test_config.py` (pytest), or stay deliberately 1:1 (just
   `example.py`, no pytest, to avoid scope creep in step 0)?


1. I created subfolders in bin, so we have bin/python and bin/ruby, Please fix the pathing for Ruby and create a new bin script for running the Python. 
2. Create a python environment and add that to the pythons README at the top, we should expect the user to create the environment Based on our instructions and assumed environment will be there, maybe venv should loaded at the root of the project because we wil be creating iterations in future folders and having a single python env in a single place will make things easier
3. continue using 3.14
4.  just example.py

## Acceptance criteria

- `python examples/example.py` produces the same structure/ordering of
  output lines as `bundle exec ruby examples/example.rb` (reference: "Run
  Example" section in `week1_baseline/ruby/00_config/README.md`), when both
  run against the same `.boukensha/` directory (or the same `BOUKENSHA_DIR`).
- `from boukensha import Config, Player` works analogous to
  `require_relative "boukensha"` in the Ruby original.
- No code under `week1_baseline/ruby/00_config` is modified.

## Not part of this plan

- All later steps (01–12) from `week1_baseline/ruby/ITERATIONS.md`.
- The MCP server part / `mud_manager` integration (only relevant starting at
  Ruby step 10).
