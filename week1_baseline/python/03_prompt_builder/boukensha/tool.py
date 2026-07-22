from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    block: Callable[..., Any]

    def __str__(self) -> str:
        params_keys = list(self.parameters.keys())
        return f"#<Tool name={self.name} description={self.description[:41]} params={params_keys}>"

    def __repr__(self) -> str:
        return self.__str__()
