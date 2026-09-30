"""Command-line interface: wallmotion --set file.mp4 --stop --mute.

Scriptable control of the app. When another instance is already running,
commands are forwarded to it (see wallmotion/instance.py); otherwise they
apply to the freshly started instance.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallmotion",
        description="Live wallpaper: images and video behind desktop icons.",
    )
    parser.add_argument("--set", metavar="FILE",
                        help="set image/video as wallpaper and keep running")
    parser.add_argument("--stop", action="store_true",
                        help="stop video wallpaper, restore original")
    mute = parser.add_mutually_exclusive_group()
    mute.add_argument("--mute", action="store_true",
                      help="mute video sound")
    mute.add_argument("--unmute", action="store_true",
                      help="unmute video sound")
    parser.add_argument("--volume", metavar="0-100", type=int, default=None,
                        help="set video volume (0-100)")
    parser.add_argument("--version", action="store_true",
                        help="print version tag if known, else 'unknown'")
    return parser


def parse_args(argv: list | None = None) -> argparse.Namespace:
    """Parse CLI args. Pure function, unit-tested."""
    return build_parser().parse_args(argv if argv is not None else [])


def args_to_command(args: argparse.Namespace) -> dict:
    """Convert parsed args to a remote-command dict (JSON-serializable).

    Only actions that make sense for a running instance are included;
    --set with a value included, flags only when set.
    """
    cmd: dict = {}
    if getattr(args, "set", None):
        cmd["set"] = args.set
    if getattr(args, "stop", False):
        cmd["stop"] = True
    if getattr(args, "mute", False):
        cmd["muted"] = True
    if getattr(args, "unmute", False):
        cmd["muted"] = False
    volume = getattr(args, "volume", None)
    if volume is not None:
        try:
            cmd["volume"] = max(0, min(100, int(volume)))
        except Exception:
            pass
    return cmd


def has_action(args: argparse.Namespace) -> bool:
    """True when any actionable flag was given (ignores --version)."""
    return bool(args_to_command(args))
