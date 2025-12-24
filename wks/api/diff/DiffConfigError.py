"""Diff configuration error."""


class DiffConfigError(Exception):
    """Raised when diff configuration is invalid."""

    def __init__(self, errors: list[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Diff configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)
