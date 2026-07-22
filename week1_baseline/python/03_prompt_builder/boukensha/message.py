from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    role: str
    content: str
    tool_use_id: Optional[str] = None

    def __str__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={self.content[:61]}...>"

    def __repr__(self) -> str:
        return self.__str__()
