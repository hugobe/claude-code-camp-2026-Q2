from .errors import ApiError


class Agent:
    # Default iteration ceiling. Sourced from task_settings or falls back to this constant.
    MAX_ITERATIONS = 25

    # The wind-down call is deliberately short and cheap.
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools.\n"
        "Briefly summarize what you accomplished, what is still unfinished, and the\n"
        "single next action you would take."
    )

    def __init__(
        self,
        context,
        registry,
        builder,
        client,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self):
        while True:
            # Limits are trigger thresholds: once reached, stop starting new work
            # iterations and make exactly one terminal wind-down call instead of raising.
            if self._iteration_limit_reached():
                return self._wrap_up("max_iterations")

            self.iteration += 1
            print(f"[iteration {self.iteration}/{self.max_iterations}]")

            response = self.client.call(**self._call_opts())
            parsed = self.builder.parse_response(response)

            if parsed.get("stop_reason") == "tool_use":
                self._handle_tool_calls(parsed.get("content", []))
            else:
                return self._extract_text(parsed.get("content", []))

    def _resolve_max_iterations(self, task_settings, explicit):
        if explicit is not None:
            return int(explicit)
        if task_settings and hasattr(self.context.task, "max_iterations"):
            return self.context.task.max_iterations(task_settings)
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(self, task_settings, explicit):
        if explicit is not None:
            return explicit
        if task_settings and hasattr(self.context.task, "max_output_tokens"):
            return self.context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self):
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _call_opts(self):
        return {"max_output_tokens": self.max_output_tokens} if self.max_output_tokens else {}

    def _wrap_up(self, reason):
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(tools=[], max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS)
            parsed = self.builder.parse_response(response)
            text = self._extract_text(parsed.get("content", []))
            return text if text.strip() else self._fallback_message(reason)
        except ApiError:
            return self._fallback_message(reason)

    def _fallback_message(self, reason):
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        if isinstance(content, str):
            return content
        return "".join(b.get("text", "") for b in content if b.get("type") == "text")

    def _handle_tool_calls(self, content):
        self.context.add_message("assistant", content)

        for block in content:
            if block.get("type") != "tool_use":
                continue

            name = block.get("name")
            args = block.get("input", {})
            use_id = block.get("id")

            print(f"  tool call → {name}({args})")
            result = self.registry.dispatch(name, args)
            print(f"  tool result → {str(result)[:60]}")

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)
