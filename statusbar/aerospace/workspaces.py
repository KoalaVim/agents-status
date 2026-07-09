#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys

from statusbar.common.types import WindowInfo, WorkspaceData


def _run_aerospace(args: list[str]) -> str:
    """Run aerospace with timeout, return stdout."""
    try:
        result = subprocess.run(
            ["aerospace"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"aerospace {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"aerospace {' '.join(args)} timed out", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("aerospace not found", file=sys.stderr)
        return ""


class AerospaceWorkspacesProvider:
    def get_workspaces(self) -> list[WorkspaceData]:
        all_ws = _run_aerospace(["list-workspaces", "--all"]).strip()
        if not all_ws:
            return []
        ws_ids = [line.strip() for line in all_ws.splitlines() if line.strip()]

        focused = _run_aerospace(["list-workspaces", "--focused"]).strip()

        windows_output = _run_aerospace([
            "list-windows", "--all",
            "--format", "%{workspace}|%{app-name}|%{window-title}",
        ]).strip()

        # Group windows by workspace
        ws_windows: dict[str, list[WindowInfo]] = {}
        for line in windows_output.splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            ws_id, app_name, title = parts
            ws_id = ws_id.strip()
            ws_windows.setdefault(ws_id, []).append(
                WindowInfo(title=title.strip(), app_class=app_name.strip().lower())
            )

        results: list[WorkspaceData] = []
        for ws_id in ws_ids:
            try:
                numeric_id = int(ws_id)
            except ValueError:
                print(f"Skipping non-numeric workspace ID: {ws_id!r}", file=sys.stderr)
                continue
            results.append(WorkspaceData(
                id=numeric_id,
                windows=ws_windows.get(ws_id, []),
                is_active=ws_id == focused,
            ))
        return results

    def get_pinned_classes(self) -> set[str]:
        return set()
