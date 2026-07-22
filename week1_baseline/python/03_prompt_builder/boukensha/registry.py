from typing import Any, Callable

from .errors import UnknownToolError
from .tool import Tool


class Registry:
    def __init__(self, context):
        self.context = context

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        block: Callable | None = None,
    ) -> Tool:
        if parameters is None:
            parameters = {}
        tool_obj = Tool(
            name=str(name),
            description=description,
            parameters=parameters,
            block=block,
        )
        self.context.register_tool(tool_obj)
        return tool_obj

    def dispatch(self, name: str, args: dict | None = None) -> Any:
        tool = self.context.tools.get(str(name))
        if not tool:
            raise UnknownToolError(f"No tool registered as '{name}'")
        kwargs = args if args is not None else {}
        return tool.block(**kwargs)
