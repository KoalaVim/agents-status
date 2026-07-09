#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

from statusbar.common.types import WindowInfo, WorkspaceData


def _run_hyprctl(args: list[str]) -> str:
    """Run hyprctl with timeout, return stdout."""
    try:
        result = subprocess.run(
            ["hyprctl"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"hyprctl {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"hyprctl {' '.join(args)} timed out", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("hyprctl not found", file=sys.stderr)
        return ""


def _parse_json(output: str, label: str) -> list | dict:
    """Parse JSON output, return [] on failure."""
    try:
        return json.loads(output)
    except (json.JSONDecodeError, ValueError):
        if output.strip():
            print(f"Error parsing {label} JSON: {output[:200]}", file=sys.stderr)
        return []


class HyprlandWorkspacesProvider:
    def get_workspaces(self) -> list[WorkspaceData]:
        vdesks = _parse_json(_run_hyprctl(["printstate", "-j"]), "vdesks")
        if not isinstance(vdesks, list):
            return []

        clients = _parse_json(_run_hyprctl(["clients", "-j"]), "clients")
        if not isinstance(clients, list):
            clients = []

        active_ws = _parse_json(_run_hyprctl(["activeworkspace", "-j"]), "activeworkspace")
        active_ws_id = active_ws.get("id") if isinstance(active_ws, dict) else None

        # Map hyprland workspace IDs -> vdesk
        ws_to_vdesk: dict[int, dict] = {}
        for vdesk in vdesks:
            for ws_id in vdesk.get("workspaces", []):
                ws_to_vdesk[ws_id] = vdesk

        active_vdesk_id = None
        if active_ws_id is not None:
            active_vdesk = ws_to_vdesk.get(active_ws_id)
            if active_vdesk:
                active_vdesk_id = active_vdesk.get("id")

        # Group clients by vdesk ID
        vdesk_windows: dict[int, list[WindowInfo]] = {}
        for client in clients:
            ws_id = client.get("workspace", {}).get("id")
            if ws_id is None:
                continue
            vdesk = ws_to_vdesk.get(ws_id)
            if vdesk is None:
                continue
            vdesk_id = vdesk.get("id")
            vdesk_windows.setdefault(vdesk_id, []).append(
                WindowInfo(
                    title=client.get("title", ""),
                    app_class=client.get("class", "").lower(),
                )
            )

        results: list[WorkspaceData] = []
        for vdesk in vdesks:
            vdesk_id = vdesk.get("id")
            results.append(WorkspaceData(
                id=vdesk_id,
                windows=vdesk_windows.get(vdesk_id, []),
                is_active=vdesk_id == active_vdesk_id,
            ))
        return results

    def get_pinned_classes(self) -> set[str]:
        windows = _parse_json(
            _run_hyprctl(["printpinnedwindows", "-j"]), "pinnedwindows",
        )
        if not isinstance(windows, list):
            return set()
        return {w.get("class", "").lower() for w in windows}
