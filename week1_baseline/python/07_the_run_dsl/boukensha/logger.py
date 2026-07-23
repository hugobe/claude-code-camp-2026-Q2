from datetime import datetime, timezone
import json
import os
import secrets

import boukensha


class Logger:
    DEFAULT_SESSION_DIR = "sessions"

    def __init__(self, session_id=None, dir=None, log=None, snapshot=None):
        self.session_id = session_id or self._generate_session_id()
        if log:
            self.path = log
        else:
            base_dir = dir or self._default_dir()
            self.path = os.path.join(base_dir, f"{self.session_id}.jsonl")

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._log_file = open(self.path, "a", encoding="utf-8")

        self._subscribers = []

        start_event = {"phase": "session_start"}
        if snapshot:
            start_event.update(snapshot)
        self._write_log(start_event)

    def turn(self, n):
        self._write_log({"phase": "turn", "n": n})

    def iteration(self, n, max):
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason, iterations, tokens=None):
        self._write_log({
            "phase": "turn_end",
            "reason": reason,
            "iterations": iterations,
            "tokens": tokens,
        })

    def prompt(self, messages, tools):
        serialized_messages = [self._serialize_message(m) for m in messages]
        tool_names = list(tools.keys()) if isinstance(tools, dict) else []
        self._write_log({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": serialized_messages,
            "tool_count": len(tool_names),
            "tools": tool_names,
        })

    def tool_call(self, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, name, result, ok=True, error=None):
        self._write_log({
            "phase": "tool_result",
            "name": name,
            "result": str(result),
            "ok": ok,
            "error": error,
        })

    def response(self, text, usage=None, stop_reason=None, task=None, backend=None):
        event = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, data):
        if not boukensha.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def close(self):
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    def _default_dir(self):
        return os.path.join(boukensha.config().dir, self.DEFAULT_SESSION_DIR)

    def _write_log(self, event):
        log_entry = dict(event)
        log_entry["session_id"] = self.session_id
        log_entry["at"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(log_entry) + "\n"
        self._log_file.write(line)
        self._log_file.flush()
        for subscriber in self._subscribers:
            subscriber(event)

    def _generate_session_id(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        hex_suffix = secrets.token_hex(4)
        return f"{timestamp}-{hex_suffix}"

    def _serialize_message(self, msg):
        if isinstance(msg, dict):
            return {"role": msg.get("role"), "content": msg.get("content")}
        return {"role": getattr(msg, "role", None), "content": getattr(msg, "content", None)}

    def _execution_metadata(self, task, backend, usage):
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        task_name = None
        if task:
            if hasattr(task, "task_name") and callable(getattr(task, "task_name")):
                task_name = task.task_name()
            elif hasattr(task, "task_name") and not callable(getattr(task, "task_name")):
                task_name = task.task_name
            else:
                task_name = str(task)

        provider = None
        if backend:
            cls_name = backend.__class__.__name__
            if cls_name.endswith("Backend"):
                cls_name = cls_name[:-7]
            # Convert CamelCase to snake_case
            provider = "".join(["_" + c.lower() if c.isupper() else c for c in cls_name]).lstrip("_")

        metadata = {
            "task": task_name,
            "provider": provider,
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None) if not callable(getattr(backend, "usage_unit", None)) else backend.usage_unit(),
            "usage_level": getattr(backend, "usage_level", None) if not callable(getattr(backend, "usage_level", None)) else backend.usage_level(),
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    def _usage_tokens(self, usage):
        if not isinstance(usage, dict):
            usage = {}
        return {
            "input": self._first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"),
            "output": self._first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"),
        }

    def _first_integer(self, hash_dict, *keys):
        for k in keys:
            val = hash_dict.get(k)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
        return None

    def _estimate_cost(self, backend, tokens):
        if not backend or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
