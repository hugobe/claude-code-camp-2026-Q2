class UnknownToolError(Exception):
    """Raised when attempting to dispatch an unregistered tool."""

    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is asked to use a model it doesn't recognize."""

    pass
