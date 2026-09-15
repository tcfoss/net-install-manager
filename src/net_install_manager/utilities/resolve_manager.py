"""Tool to resolve an AppManager instance."""

import argparse

from net_install_manager.app_manager import AppManager
from net_install_manager.registry import AppRegistry
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.errors import AppNotRegisteredError, CannotResolveManagerError

def resolve_manager(
    args: argparse.Namespace,
    runtime: RuntimeInfo,
    manager: AppManager | None = None,
    registry: AppRegistry | None = None,
    app_manager_cls: type[AppManager] = AppManager,
) -> AppManager:
    """Resolve AppManager from args or registry."""
    if manager is not None:
        return manager

    if getattr(args, "app_name", None):
        registry = registry or AppRegistry(runtime=runtime)
        tracked = registry.get(args.app_name)
        if not tracked:
            raise AppNotRegisteredError(args.app_name)
        config = tracked.to_config()
        return app_manager_cls(
            config=config,
            runtime=runtime,
            prefer_opt=getattr(args, "prefer_opt", False) or tracked.prefer_opt,
        )

    raise CannotResolveManagerError()
