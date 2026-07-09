#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys

from statusbar.common.config import SketchybarConfig
from statusbar.common.types import WorkspaceInfo

STATUS_COLORS = {
    "WAITING": "0xffcf1313",
    "INPROGRESS": "0xfffa7900",
    "DONE": "0xff1e88ff",
    "IDLE": "0xff15c70c",
}
DEFAULT_COLOR = "0xffffffff"


class SketchyBar:
    def __init__(self, config: SketchybarConfig) -> None:
        self._prefix = config.space_item_prefix

    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        if not workspaces:
            return

        cmd: list[str] = ["sketchybar"]
        for ws in workspaces:
            item = f"{self._prefix}.{ws.id}"
            color = STATUS_COLORS.get(ws.agent_status, DEFAULT_COLOR)
            label = ws.display_name
            id_prefix = f"{ws.id} "
            if label.startswith(id_prefix):
                label = label[len(id_prefix):]
            cmd.extend(["--set", item, f"label={label}", f"label.color={color}"])

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            print("sketchybar update timed out", file=sys.stderr)
        except FileNotFoundError:
            print("sketchybar not found", file=sys.stderr)
