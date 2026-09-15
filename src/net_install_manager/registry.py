"""Registry for tracking installed applications and their installation metadata."""

from dataclasses import dataclass, asdict
import logging
from pathlib import Path
import yaml

from net_install_manager.config import Config
from net_install_manager.runtime_config import InstallOptions, RuntimeInfo
from net_install_manager.utilities.github_release_tools import GitHubReleaseInfo
from net_install_manager.utilities.git_tools import GitSourceInfo
from net_install_manager.utilities.install_tools import InstallSource
from net_install_manager.utilities.sys_platform import OperatingSystem, get_winpath

logger = logging.getLogger(__name__)


@dataclass
class TrackedApp:
    """Represents an application tracked by the registry."""

    # pylint: disable=too-many-instance-attributes

    binary_name: str
    app_directory: str
    source_binary_name: str
    source: InstallSource
    lib_path: str = ""
    self_contained: bool = False
    release: bool = True
    target_permissions: str | None = None
    installed_version: str | None = None

    @property
    def is_git(self) -> bool:
        """Return True if the app was installed from a Git source."""
        return self.source.is_git

    @property
    def source_path(self) -> str | None:
        """Return the local source path, if this is a local source."""
        return self.source.local_path

    @property
    def git_info(self):
        """Return Git metadata, if this is a Git source."""
        return self.source.git_info

    @property
    def prefer_opt(self) -> bool:
        """Infer whether prefer_opt was used based on lib_path."""
        return self.lib_path.startswith("/opt")

    def to_config(self) -> Config:
        """Convert the tracked app to a Config object."""
        return Config(
            app_directory=self.app_directory,
            binary_name=self.binary_name,
            source_binary_name=self.source_binary_name,
            target_permissions=self.target_permissions,
        )

    def to_install_options(
        self, force: bool = False, debug_override: bool | None = None
    ) -> InstallOptions:
        """Convert tracked app settings to InstallOptions."""
        release_mode = not debug_override if debug_override is not None else self.release
        return InstallOptions(
            self_contained=self.self_contained,
            release=release_mode,
            force=force,
        )

    def release_mode(self, debug_override: bool | None = None) -> bool:
        """Determine the release mode considering the debug override."""
        if debug_override is not None:
            return not debug_override
        return self.release


def get_registry_path(
    runtime: RuntimeInfo | None = None,
) -> Path:
    """Return the path to the ninman apps registry file."""
    runtime = runtime or RuntimeInfo.current()

    if runtime.os.is_posix:
        if runtime.system_wide:
            return Path("/etc/ninman/apps.yaml")
        xdg_config = runtime.env.get("XDG_CONFIG_HOME")
        base = Path(xdg_config) if xdg_config else runtime.home_dir / ".config"
        return base / "ninman" / "apps.yaml"

    if runtime.system_wide:
        program_data = get_winpath(runtime.env.get("PROGRAMDATA", r"C:\ProgramData"))
        return program_data / "ninman" / "apps.yaml"
    app_data = get_winpath(
        runtime.env.get("APPDATA", str(runtime.home_dir / "AppData" / "Roaming"))
    )
    return app_data / "ninman" / "apps.yaml"


class AppRegistry:
    """Manages the global tracking registry of installed .NET applications."""

    def __init__(
        self,
        registry_file: Path | None = None,
        runtime: RuntimeInfo | None = None,
    ):
        self.runtime = runtime or RuntimeInfo.current()
        self.registry_file = registry_file or get_registry_path(self.runtime)

    @property
    def target_os(self) -> OperatingSystem:
        """Return target operating system for backward compatibility."""
        return self.runtime.os

    def load(self) -> dict[str, TrackedApp]:
        """Load all tracked apps from the registry file."""
        if not self.registry_file.exists():
            return {}

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {}

            apps = {}
            for name, entry in data.items():
                if isinstance(entry, dict):
                    if isinstance(entry.get("source"), dict):
                        source_data = entry["source"]
                        if isinstance(source_data.get("git_info"), dict):
                            source_data["git_info"] = GitSourceInfo(**source_data["git_info"])
                        if isinstance(source_data.get("release_info"), dict):
                            source_data["release_info"] = GitHubReleaseInfo(
                                **source_data["release_info"]
                            )
                        entry["source"] = InstallSource(**source_data)
                    apps[name] = TrackedApp(**entry)
            return apps
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not read registry file %s: %s", self.registry_file, e)
            return {}

    def save(self, apps: dict[str, TrackedApp]) -> None:
        """Save tracked apps to the registry file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        data = {name: asdict(app) for name, app in apps.items()}
        with open(self.registry_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

    def register(self, app: TrackedApp) -> None:
        """Register or update an application in the registry."""
        apps = self.load()
        apps[app.binary_name] = app
        self.save(apps)

    def get(self, binary_name: str) -> TrackedApp | None:
        """Get a tracked app by binary name."""
        apps = self.load()
        return apps.get(binary_name)

    def remove(self, binary_name: str) -> bool:
        """Remove an application from the registry."""
        apps = self.load()
        if binary_name in apps:
            del apps[binary_name]
            self.save(apps)
            return True
        return False


__all__ = ["TrackedApp", "get_registry_path", "AppRegistry"]
