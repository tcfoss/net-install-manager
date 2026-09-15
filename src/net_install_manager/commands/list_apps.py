"""List apps command to show all tracked applications managed by ninman."""

import argparse
from net_install_manager.cli_output import write
from net_install_manager.registry import AppRegistry
from net_install_manager.runtime_config import RuntimeInfo


def execute(
    args: argparse.Namespace,
    registry: AppRegistry | None = None,
    runtime: RuntimeInfo | None = None,
) -> int:
    """Execute the list-apps command."""
    runtime = runtime or RuntimeInfo.current(system_wide=getattr(args, "system", False))
    registry = registry or AppRegistry(runtime=runtime)
    apps = registry.load()

    if not apps:
        write("No applications currently tracked by ninman.")
        return 0

    write(f"Tracked applications ({'system-wide' if args.system else 'user'}):")
    for name, app in sorted(apps.items()):
        ver_str = f" (v{app.installed_version})" if app.installed_version else ""
        write(f"  - {name}{ver_str}: {app.source_path}")

    return 0


def register_list_apps_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the list-apps command arguments."""
    parser = subparsers.add_parser("list-apps", help="List all applications tracked by ninman")
    return parser


__all__ = ["execute", "register_list_apps_command"]
