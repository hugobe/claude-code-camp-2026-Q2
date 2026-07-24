import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


class Config:
    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (set before loading .env)
    #   2. ~/.boukensha  (default)
    DEFAULT_DIR = str(Path.home() / ".boukensha")

    # Default prompts shipped alongside this step.
    PROMPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "prompts")

    def __init__(self):
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name=None):
        """With no argument: returns the full tasks dict from settings.yaml.
        With a name: returns that task's settings dict, e.g. tasks("player")."""
        all_tasks = self.dig("tasks") or {}
        return all_tasks.get(name) if name else all_tasks

    @property
    def user_prompts_dir(self):
        return str(Path(self.dir) / "prompts")

    # ---------- MUD connection --------------------------------------------

    @property
    def mud_host(self):
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self):
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self):
        return self.dig("mud", "username")

    @property
    def mud_password(self):
        return self.dig("mud", "password")

    # ---------- low-level helpers -----------------------------------------

    def dig(self, *keys):
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def __repr__(self):
        return f"<Boukensha.Config dir={self.dir} tasks={','.join(self.tasks().keys())}>"

    def _resolve_dir(self):
        # 1. Explicit override
        if os.environ.get("BOUKENSHA_DIR"):
            return str(Path(os.environ["BOUKENSHA_DIR"]).expanduser().absolute())

        # 2. .boukensha in the current working directory
        cwd_dir = Path.cwd() / ".boukensha"
        if cwd_dir.is_dir():
            return str(cwd_dir)

        # 3. ~/.boukensha default
        return str(Path(self.DEFAULT_DIR).expanduser().absolute())

    def _load_env(self):
        env_file = Path(self.dir) / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self):
        settings_file = Path(self.dir) / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
