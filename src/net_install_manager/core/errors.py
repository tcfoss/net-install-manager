"""Custom error classes for the Net Install Manager."""

from pathlib import Path


class BaseNinmanError(Exception):
    """Base class for all Net Install Manager errors."""


class SelfMigrationError(BaseNinmanError):
    """Raised when the self-migration command cannot complete."""

    def __init__(self, status: int):
        super().__init__(f"Self-migration failed with status {status}.")
        self.status = status


class AppNotRegisteredError(BaseNinmanError):
    """Raised when an application is not found in the registry."""

    def __init__(self, app_name: str, registry_path: str | Path):
        super().__init__(f"Application '{app_name}' not found in registry at '{registry_path}'.")
        self.app_name = app_name
        self.registry_path = registry_path


class AppAlreadyInstalledError(BaseNinmanError):
    """Raised when an application is already installed."""

    def __init__(self, app_name: str, installation_path: str | Path):
        super().__init__(
            f"Application '{app_name}' is already installed at '{installation_path}'."
            "Supply the --force flag to install anyway."
        )
        self.app_name = app_name
        self.installation_path = installation_path


class VersionAlreadyInstalledError(BaseNinmanError):
    """Raised when a specific version of an application is already installed."""

    def __init__(self, app_name: str, version: str, installation_path: str | Path):
        super().__init__(
            f"Version '{version}' of application '{app_name}' is already installed "
            f"at '{installation_path}'. Supply the --force flag to install anyway."
        )
        self.app_name = app_name
        self.version = version
        self.installation_path = installation_path


class NoVersionsInstalledError(BaseNinmanError):
    """Raised when no versions of an application are installed."""

    def __init__(self, app_name: str):
        super().__init__(f"No versions of application '{app_name}' are installed.")
        self.app_name = app_name


class VersionNotInstalledError(BaseNinmanError):
    """Raised when a requested application version is not installed."""

    def __init__(self, app_name: str, version: str):
        super().__init__(f"Version '{version}' of application '{app_name}' is not installed.")
        self.app_name = app_name
        self.version = version


class InstallationDirectoryNotFoundError(BaseNinmanError):
    """Raised when the installation directory for an application is not found."""

    def __init__(self, app_name: str, installation_path: str | Path):
        super().__init__(
            f"Installation directory for application '{app_name}' "
            f"not found at '{installation_path}'."
        )
        self.app_name = app_name
        self.installation_path = installation_path


class MultipleCsprojFilesError(BaseNinmanError):
    """Raised when multiple .csproj files are found in a directory."""

    def __init__(self, directory: str | Path, csproj_files: list[Path]):
        super().__init__(
            f"Multiple .csproj files found in directory '{directory}': "
            + ", ".join(str(f) for f in csproj_files)
        )

        self.directory = directory
        self.csproj_files = csproj_files


class InvalidSourceError(BaseNinmanError):
    """Raised when the provided source is invalid."""

    def __init__(self, source: str | Path):
        super().__init__(
            f"Invalid source: '{source}'. Must be a .csproj file, "
            "a directory containing a single .csproj file, "
            "a directory containing compiled sources, or a Git URL."
        )
        self.source = source


class UnresolvedTargetError(BaseNinmanError):
    """Raised when a target cannot be resolved."""

    def __init__(self, target_name: str):
        super().__init__(f"Unresolved target: '{target_name}'.")
        self.target_name = target_name


class UnresolvedVersionError(BaseNinmanError):
    """Raised when the version of an application cannot be resolved."""

    def __init__(self, app_name: str):
        super().__init__(
            f"Unresolved version for application '{app_name}'."
            " Use the --version-override option to specify the version manually."
        )
        self.app_name = app_name


class AmbiguousSourceError(BaseNinmanError):
    """Raised when the provided source is ambiguous."""

    def __init__(self, source: str | Path):
        super().__init__(f"Ambiguous source: '{source}'. Cannot determine the correct source.")
        self.source = source


class GitBranchError(BaseNinmanError):
    """Raised when a Git repository's default branch cannot be checked out."""

    def __init__(self, clone_url: str, ref: str | None = None):
        branch_str = f"branch '{ref}'" if ref is not None else "the default branch"
        super().__init__(f"Unable to check out {branch_str} for Git repository '{clone_url}'.")
        self.clone_url = clone_url
        self.ref = ref


class PruneAllError(BaseNinmanError):
    """Raised when an attempt is made to prune all versions of an application."""

    def __init__(self, app_name: str):
        super().__init__(
            f"Cannot prune all versions of application '{app_name}'. "
            "If you want to remove all versions, use uninstall instead."
        )
        self.app_name = app_name
