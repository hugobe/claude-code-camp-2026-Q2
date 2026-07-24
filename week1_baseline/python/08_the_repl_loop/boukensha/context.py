from typing import Any, Optional
from .message import Message
from .tool import Tool


class Context:
    def __init__(self, task: Any, system: Optional[str] = None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, tool_use_id: Optional[str] = None) -> None:
        self.messages.append(Message(role=role, content=content, tool_use_id=tool_use_id))

    def clear_messages(self) -> None:
        self.messages = []

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = None
        if self.task is not None:
            if hasattr(self.task, "task_name") and callable(self.task.task_name):
                task_name = self.task.task_name()
            elif hasattr(self.task, "task_name"):
                task_name = self.task.task_name
            else:
                task_name = str(self.task)
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"

    def __repr__(self) -> str:
        return self.__str__()
