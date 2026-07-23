class UnknownToolError(Exception):
    """Raised when attempting to dispatch an unregistered tool."""

    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is asked to use a model it doesn't recognize."""

    pass


class ApiError(Exception):
    """Raised when an API request fails after exhausting retries."""

    pass


class LoopError(Exception):
    """Raised when an agent loop encounters an unrecoverable condition."""

    pass

