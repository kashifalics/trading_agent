class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class ProviderNotConfigured(AppError):
    status_code = 503
    code = "provider_not_configured"


class UnsupportedError(AppError):
    status_code = 422
    code = "unsupported"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"
