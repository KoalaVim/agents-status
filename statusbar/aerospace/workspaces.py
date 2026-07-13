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
    @staticmethod
    def _ws_group(ws_id: str) -> int | None:
        """Extract group number from a workspace ID (e.g. '2b' -> 2, '1' -> 1)."""
        group_str = ws_id.rstrip("bc")
        try:
            return int(group_str)
        except ValueError:
            return None

    def get_workspaces(self) -> list[WorkspaceData]:
        all_ws = _run_aerospace(["list-workspaces", "--all"]).strip()
        if not all_ws:
            return []
        ws_ids = [line.strip() for line in all_ws.splitlines() if line.strip()]

        focused = _run_aerospace(["list-workspaces", "--focused"]).strip()
        focused_group = self._ws_group(focused)

        windows_output = _run_aerospace([
            "list-windows", "--all",
            "--format", "%{workspace}|%{app-name}|%{window-title}",
        ]).strip()

        # Group windows by workspace group number (aggregate sub-workspaces)
        group_windows: dict[int, list[WindowInfo]] = {}
        for line in windows_output.splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            ws_id, app_name, title = parts
            group = self._ws_group(ws_id.strip())
            if group is None:
                continue
            group_windows.setdefault(group, []).append(
                WindowInfo(title=title.strip(), app_class=app_name.strip().lower())
            )

        # Collect unique groups
        seen_groups: set[int] = set()
        for ws_id in ws_ids:
            group = self._ws_group(ws_id)
            if group is not None:
                seen_groups.add(group)

        results: list[WorkspaceData] = []
        for group in sorted(seen_groups):
            results.append(WorkspaceData(
                id=group,
                windows=group_windows.get(group, []),
                is_active=group == focused_group,
            ))
        return results

    def get_pinned_classes(self) -> set[str]:
        return set()
