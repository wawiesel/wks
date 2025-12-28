"""Transform configuration error."""


class _TransformConfigError(Exception):
    """Raised when transform configuration is invalid."""

    def __init__(self, errors: list[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Transform configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)
