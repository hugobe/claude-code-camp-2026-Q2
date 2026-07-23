from .agent import Agent
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.lm_studio import LmStudio
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tasks.player import Player
from .tool import Tool

_quiet = False
_debug = False
_config = None


def config():
    global _config
    if _config is None:
        _config = Config()
    return _config


def quiet():
    global _quiet
    _quiet = True


def loud():
    global _quiet
    _quiet = False


def is_quiet():
    return _quiet


def debug():
    global _debug
    _debug = True


def is_debug():
    return _debug


__all__ = [
    "Config",
    "Player",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Anthropic",
    "OpenAI",
    "Gemini",
    "Ollama",
    "OllamaCloud",
    "LmStudio",
    "Client",
    "Agent",
    "Logger",
    "config",
    "quiet",
    "loud",
    "is_quiet",
    "debug",
    "is_debug",
]


