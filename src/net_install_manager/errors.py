"""Errors module for the Net Install Manager application."""


class AppManagerError(Exception):
    """Base exception for AppManager errors."""


class VersionRegressionError(AppManagerError):
    """Raised when attempting to install an older or equal version without --force."""


class AppNotRegisteredError(AppManagerError):
    """Raised when attempting to access an application that is not registered."""

    def __init__(self, app_name: str):
        self.app_name = app_name
        super().__init__(f"Application '{app_name}' is not registered.")


class CannotResolveManagerError(AppManagerError):
    """Raised when the application manager cannot be resolved from the given context."""

    def __init__(self):
        super().__init__(
            "Please specify an application name, run inside an"
            " application directory, or provide --config."
        )


__all__ = [
    "AppManagerError",
    "VersionRegressionError",
    "AppNotRegisteredError",
    "CannotResolveManagerError",
]
