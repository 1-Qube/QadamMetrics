"""Application errors mapped to consistent API responses."""


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("not_found", message, 404, details)


class InfeasibleError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__("infeasible_constraints", message, 422, details)
