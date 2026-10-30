"""Domain errors raised by services and translated to HTTP at the edge.

Services should raise these instead of importing FastAPI's HTTPException, so
business logic stays testable and reusable outside a request cycle.
"""


class AppError(Exception):
    """Base class for expected, client-safe application errors."""

    status_code = 500
    default_detail = "Something went wrong"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """The requested resource does not exist or is not owned by the caller."""

    status_code = 404
    default_detail = "Resource not found"


class ForbiddenError(AppError):
    """The caller is authenticated but not allowed to perform the action."""

    status_code = 403
    default_detail = "You do not have access to this resource"


class ConflictError(AppError):
    """The request conflicts with the resource's current state."""

    status_code = 409
    default_detail = "This action is no longer available"


class InvalidRequestError(AppError):
    """The request is well-formed but violates a business rule."""

    status_code = 400
    default_detail = "Invalid request"


class AIUnavailableError(AppError):
    """The AI provider could not be reached or returned its fallback text."""

    status_code = 503
    default_detail = (
        "The AI assistant is temporarily unavailable. Please try again in a moment."
    )


class AIResponseError(AppError):
    """The AI provider responded, but not with usable structured data."""

    status_code = 502
    default_detail = "Request could not be completed"
