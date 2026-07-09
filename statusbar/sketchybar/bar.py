#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import asdict

from statusbar.common.config import SketchybarColorsConfig, SketchybarConfig
from statusbar.common.types import WorkspaceInfo

STATUS_COLORS = {
    "WAITING": "0xffcf1313",
    "INPROGRESS": "0xfffa7900",
    "DONE": "0xff1e88ff",
    "IDLE": "0xff15c70c",
}
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
    def __init__(self, config: SketchybarConfig) -> None:
        self._prefix = config.space_item_prefix
        self._bg_colors = _bg_colors(config.colors)
        self._text_focused = config.colors.text_focused
        self._text_unfocused = config.colors.text_unfocused

    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        if not workspaces:
            return

        cmd: list[str] = ["sketchybar"]
        sentinel_lines: list[str] = []

        for ws in workspaces:
            item = f"{self._prefix}.{ws.id}"
            color = STATUS_COLORS.get(ws.agent_status, DEFAULT_COLOR)

            label = ws.display_name
            id_prefix = f"{ws.id} "
            if label.startswith(id_prefix):
                label = label[len(id_prefix):]

            bg_pair = self._bg_colors.get(ws.agent_status)
            if bg_pair:
                focused_bg, unfocused_bg = bg_pair
                bg_color = focused_bg if ws.is_active else unfocused_bg
                text_color = self._text_focused if ws.is_active else self._text_unfocused
                cmd.extend([
                    "--set", item, f"label={label}",
                    f"label.color={text_color}",
                    f"icon.color={text_color}",
                    f"background.color={bg_color}",
                    "background.drawing=on",
                ])
                sentinel_lines.append(
                    f"{ws.id}:{unfocused_bg}:{focused_bg}"
                    f":{self._text_unfocused}:{self._text_focused}"
                )
            else:
                cmd.extend([
                    "--set", item, f"label={label}",
                    f"label.color={color}",
                    "background.drawing=off",
                ])

        self._write_sentinel(sentinel_lines)

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            print("sketchybar update timed out", file=sys.stderr)
        except FileNotFoundError:
            print("sketchybar not found", file=sys.stderr)

    @staticmethod
    def _write_sentinel(lines: list[str]) -> None:
        try:
            with open(SENTINEL_PATH, "w") as f:
                f.write("\n".join(lines) + "\n" if lines else "")
        except OSError as e:
            print(f"Failed to write sentinel {SENTINEL_PATH}: {e}", file=sys.stderr)
