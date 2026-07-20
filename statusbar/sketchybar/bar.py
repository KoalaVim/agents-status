#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys

from statusbar.common.config import (
    ColorsConfig,
    SketchybarColorsConfig,
    SketchybarConfig,
    _hex_to_sketchybar,
)
from statusbar.common.types import WorkspaceInfo

DEFAULT_COLOR = "0xffffffff"

SENTINEL_PATH = f"/tmp/agent-status-bg-{os.getuid()}"


def _bg_colors(
    colors: SketchybarColorsConfig,
) -> dict[str, tuple[str, str]]:
    """Map status -> (focused_bg, unfocused_bg)."""
    return {
        "IDLE": (colors.idle_focused, colors.idle_unfocused),
        "INPROGRESS": (colors.inprogress_focused, colors.inprogress_unfocused),
        "WAITING": (colors.waiting_focused, colors.waiting_unfocused),
        "DONE": (colors.done_focused, colors.done_unfocused),
    }


class SketchyBar:
    def __init__(self, config: SketchybarConfig, colors: ColorsConfig | None = None) -> None:
        self._prefix = config.space_item_prefix
        self._template = config.label_template
        self._bg_colors = _bg_colors(config.colors)
        self._text_focused = config.colors.text_focused
        self._text_unfocused = config.colors.text_unfocused
        self._default_bg_focused = config.colors.default_bg_focused
        self._default_bg_unfocused = config.colors.default_bg_unfocused
        self._default_text_focused = config.colors.default_text_focused
        self._default_text_unfocused = config.colors.default_text_unfocused
        resolved = (colors or ColorsConfig()).resolved()
        self._status_colors = {
            k.upper(): _hex_to_sketchybar(v) for k, v in resolved.items()
        }

    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        if not workspaces:
            return

        sentinel_entries: list[dict] = []

        for ws in workspaces:
            label = ws.display_name
            id_prefix = f"{ws.id} "
            if label.startswith(id_prefix):
                label = label[len(id_prefix):]

            bg_pair = self._bg_colors.get(ws.agent_status)
            entry = {
                "id": ws.id,
                "display_name": label,
                "agent_icon": ws.agent_icon,
                "monitor_icon": ws.monitor_icon,
                "tmux_sessions": ws.tmux_sessions,
                "app_icons": ws.app_icons,
                "agent_status": ws.agent_status,
            }

            if bg_pair:
                focused_bg, unfocused_bg = bg_pair
                entry.update({
                    "bg_focused": focused_bg,
                    "bg_unfocused": unfocused_bg,
                    "text_focused": self._text_focused,
                    "text_unfocused": self._text_unfocused,
                })
            else:
                entry.update({
                    "bg_focused": "",
                    "bg_unfocused": "",
                    "text_focused": "",
                    "text_unfocused": "",
                })

            sentinel_entries.append(entry)

        self._write_sentinel(sentinel_entries)
        self._trigger_workspace_events(workspaces)

    def _trigger_workspace_events(self, workspaces: list[WorkspaceInfo]) -> None:
        cmd: list[str] = ["sketchybar"]
        for ws in workspaces:
            cmd.extend(["--trigger", f"aerospace_workspace_change_{ws.id}"])
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _write_sentinel(self, entries: list[dict]) -> None:
        try:
            header = {
                "template": self._template,
                "default_bg_focused": self._default_bg_focused,
                "default_bg_unfocused": self._default_bg_unfocused,
                "default_text_focused": self._default_text_focused,
                "default_text_unfocused": self._default_text_unfocused,
            }
            with open(SENTINEL_PATH, "w") as f:
                f.write(json.dumps(header) + "\n")
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
        except OSError as e:
            print(f"Failed to write sentinel {SENTINEL_PATH}: {e}", file=sys.stderr)
