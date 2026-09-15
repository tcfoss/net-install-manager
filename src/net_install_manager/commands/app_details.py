"""Retrieve and display details about a .NET application."""

import argparse

from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.registry import AppRegistry
from net_install_manager.cli_output import write, error


def execute(
    args: argparse.Namespace,
    registry: AppRegistry | None = None,
    runtime: RuntimeInfo | None = None,
) -> int:
    """Retrieve and display details about a ninman-managed application."""
    runtime = runtime or RuntimeInfo.current(system_wide=getattr(args, "system", False))
    registry = registry or AppRegistry(runtime=runtime)
    app_name = args.app_name

    details = registry.get(app_name)
    if not details:
        error(f"No details found for application '{app_name}'.")
        return 1

    write(f"Details for application '{app_name}':")

    write(f"    Lib path:      {details.lib_path}")
    write(f"    Version:       {details.installed_version}")
    write(f"    Binary:        {details.binary_name}")
    write(f"    Source binary: {details.source_binary_name}")

    write("    Source:")
    if details.source.git_info:
        write("        Source type: Git Repository Source")
        write(f"        Clone URL: {details.source.git_info.clone_url}")
        write(f"        Subpath:   {details.source.git_info.subpath}")
        write(f"        Ref:       {details.source.git_info.ref}")
    elif details.source.release_info:
        write("        Source type: GitHub Release Artifact")
        write(f"        Owner:         {details.source.release_info.owner}")
        write(f"        Repo:          {details.source.release_info.repo}")
        write(f"        Asset pattern: {details.source.release_info.asset_pattern}")
        write(f"        Tag:           {details.source.release_info.tag}")
    elif details.source.local_path:
        write("        Source type: Local Path")
        write(f"        Path:          {details.source.local_path}")

    return 0


def register_app_details_command(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the command to display application details."""
    parser = subparsers.add_parser(
        "app-details", help="Display details about a ninman-managed application"
    )
    parser.add_argument("app_name", help="Name of the ninman-managed application")
    return parser
