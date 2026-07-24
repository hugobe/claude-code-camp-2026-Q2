import json
from .base import Base


class LmStudio(Base):
    MODELS = {
        "google/gemma-4-12b-qat": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, model, host="http://localhost:1234/v1"):
        self.host = host
        self.configure_model(model)

    def to_messages(self, system, messages):
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content}
                )
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": str(msg.role), "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_tokens": max_output_tokens,
        }

    @property
    def headers(self):
        return {"Content-Type": "application/json"}

    @property
    def url(self):
        return f"{self.host}/chat/completions"

    def parse_response(self, response):
        choices = response.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id"),
                    "name": fn.get("name"),
                    "input": args,
                }
            )

        stop_reason = "end_turn" if not tool_calls else "tool_use"
        return {"stop_reason": stop_reason, "content": content}

    def _assistant_message(self, content):
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text_blocks = [b for b in blocks if b.get("type") == "text"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

        text_content = "".join(b.get("text", "") for b in text_blocks)
        msg = {"role": "assistant", "content": text_content}
        if tool_blocks:
            msg["tool_calls"] = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in tool_blocks
            ]
        return msg

