"""Application-level typed errors for stable API contracts."""


class AppError(Exception):
    """Base application error with stable code and HTTP status."""

    code = 'APP_ERROR'
    http_status = 400

    def __init__(self, message=None):
        super().__init__(message or self.code)
        self.message = message or self.code


class InvalidModeError(AppError):
    code = 'INVALID_MODE'
    http_status = 400


class InvalidActionError(AppError):
    code = 'INVALID_ACTION'
    http_status = 400


class ValidationError(AppError):
    code = 'VALIDATION_ERROR'
    http_status = 400


class UnauthorizedError(AppError):
    code = 'UNAUTHORIZED'
    http_status = 401


class ResourceNotFoundError(AppError):
    code = 'RESOURCE_NOT_FOUND'
    http_status = 404


class InternalServerError(AppError):
    code = 'INTERNAL_ERROR'
    http_status = 500
