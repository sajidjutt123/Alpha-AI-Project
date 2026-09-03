"""Domain exceptions and the API error envelope.

Handlers (registered in `app.main`) render every domain error as:

    {"error": {"code": "<machine-readable>", "message": "<human-readable>"}}

HTTPException (auth, 404s raised by FastAPI) is rendered the same way so
clients can rely on one error shape.
"""

from typing import Any


class DomainError(Exception):
    """Base for business-rule failures rendered as API errors."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class BusinessRuleError(DomainError):
    status_code = 422
    code = "business_rule_violation"
