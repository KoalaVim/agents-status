#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys

from statusbar.common.types import WorkspaceInfo

CONFIG_LOC = os.path.expanduser("~/.config/hypr/UserConfigs/VirtualDesktopsNames.conf")


class HyprlandBar:
    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        names = {ws.id: ws.display_name for ws in workspaces}
        self._write_names(names)
        self._set_statuses(workspaces)

    def _write_names(self, names: dict[int, str]) -> None:
        """Write vdesk names to config file, only if changed."""
        names_str = ", ".join(f"{id}:{name}" for id, name in sorted(names.items()))
        content = (
            f"plugin {{\n"
            f"    virtual-desktops {{\n"
            f"        names = {names_str}\n"
            f"    }}\n"
            f"}}\n"
        )
        try:
            with open(CONFIG_LOC, "r") as f:
                if f.read() == content:
                    return
        except FileNotFoundError:
            pass

        try:
            with open(CONFIG_LOC, "w") as f:
                f.write(content)
        except OSError as e:
            print(f"Failed to write {CONFIG_LOC}: {e}", file=sys.stderr)
            return

        subprocess.run(["hyprctl", "dispatch", "vdeskreset"], capture_output=True)

    def _set_statuses(self, workspaces: list[WorkspaceInfo]) -> None:
        """Set vdesk status via hyprctl dispatch for each workspace."""
        for ws in workspaces:
            subprocess.run(
                ["hyprctl", "dispatch", "vdesksetstatus", f"{ws.id},{ws.agent_status}"],
                capture_output=True,
            )
