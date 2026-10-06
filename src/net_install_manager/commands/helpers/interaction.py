"""Helpers for user interaction."""

import argparse


def confirm(prompt: str) -> bool:
    """Prompt the user for confirmation."""

    try:
        answer = input(f"{prompt} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def register_autoconfirm_argument(parser: argparse.ArgumentParser) -> None:
    """Register the --assume-yes / -y argument for automatic confirmation."""
    parser.add_argument(
        "-y",
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Automatically answer yes to confirmation prompts.",
    )


__all__ = ["confirm", "register_autoconfirm_argument"]
