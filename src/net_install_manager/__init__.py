"""Net Install Manager (`ninman`) package."""

from net_install_manager.config import Config, load_config, parse_config, auto_discover_config
from net_install_manager.paths import Paths, get_paths
from net_install_manager.app_manager import AppManager, AppManagerError, VersionRegressionError

__all__ = [
    "Config",
    "load_config",
    "parse_config",
    "auto_discover_config",
    "Paths",
    "get_paths",
    "AppManager",
    "AppManagerError",
    "VersionRegressionError",
]
