#!/usr/bin/env python3
"""Unified statusbar entry point.

Reads config, creates the appropriate workspace provider and statusbar backend,
builds workspace info, and applies it to the bar.

Usage (as post-event hook in config.toml):
    "$AGENTS_STATUS_DIR/../statusbar/run.py"

    # With debug logging:
    "$AGENTS_STATUS_DIR/../statusbar/run.py --debug"
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from statusbar.common.config import load_statusbar_config
from statusbar.common.tmux import set_debug
from statusbar.common.workspaces import build_workspaces


def _create_provider(name: str):
    if name == "hyprland":
        from statusbar.hyprland.workspaces import HyprlandWorkspacesProvider
        return HyprlandWorkspacesProvider()
    if name == "aerospace":
        from statusbar.aerospace.workspaces import AerospaceWorkspacesProvider
        return AerospaceWorkspacesProvider()
    print(f"Unknown workspaces_provider: {name!r}. Supported: hyprland, aerospace",
          file=sys.stderr)
    sys.exit(1)


def _create_bar(name: str, config):
    if name == "hyprland":
        from statusbar.hyprland.bar import HyprlandBar
        return HyprlandBar()
    if name == "sketchybar":
        from statusbar.sketchybar.bar import SketchyBar
        return SketchyBar(config.sketchybar)
    print(f"Unknown bar: {name!r}. Supported: hyprland, sketchybar",
          file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug logs")
    args = parser.parse_args()

    set_debug(args.debug)

    config = load_statusbar_config()

    if not config.workspaces_provider:
        print("No workspaces_provider configured and auto-detection failed.\n"
              "Set [statusbar] workspaces_provider in config.toml.", file=sys.stderr)
        sys.exit(1)
    if not config.bar:
        print("No bar configured and auto-detection failed.\n"
              "Set [statusbar] bar in config.toml.", file=sys.stderr)
        sys.exit(1)

    provider = _create_provider(config.workspaces_provider)
    bar = _create_bar(config.bar, config)
    workspaces = build_workspaces(provider, config)
    bar.apply(workspaces)


if __name__ == "__main__":
    main()
