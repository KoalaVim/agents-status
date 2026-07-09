#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys

STATUS_PRIORITY = {
    "WAITING": 1,
    "INPROGRESS": 2,
    "DONE": 3,
    "IDLE": 4,
}

_debug_enabled = False


def set_debug(enabled: bool) -> None:
    global _debug_enabled
    _debug_enabled = enabled


def _debug(msg: str) -> None:
    if _debug_enabled:
        print(f"[debug] {msg}", file=sys.stderr)


def highest_priority_status(statuses: list[str]) -> str:
    """Return the highest priority status from a list (INPROGRESS > WAITING > DONE > IDLE)."""
    best = None
    best_priority = float("inf")
    for s in statuses:
        p = STATUS_PRIORITY.get(s)
        if p is not None and p < best_priority:
            best = s
            best_priority = p
    return best or ""


def get_tmux_session_statuses(session_name: str) -> tuple[str, list[str]]:
    """Get per-window @ai-agent-status and @monitor-status for a tmux session.

    Returns a tuple of:
      - the aggregated @ai-agent-status (highest priority across windows), and
      - the ordered list of per-window @monitor-status values (empties dropped).
    """
    try:
        list_result = subprocess.run(
            ["tmux", "list-windows", "-t", session_name, "-F",
             "#{@ai-agent-status}|#{@monitor-status}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        agent_statuses: list[str] = []
        monitor_statuses: list[str] = []
        for line in list_result.stdout.splitlines():
            agent, _, monitor = line.partition("|")
            agent = agent.strip()
            monitor = monitor.strip()
            if agent:
                agent_statuses.append(agent)
            if monitor:
                monitor_statuses.append(monitor)
        _debug(f"tmux session {session_name!r} agent={agent_statuses} monitor={monitor_statuses}")
        agent_winner = highest_priority_status(agent_statuses)
        _debug(f"tmux session {session_name!r} resolved agent status: {agent_winner!r}")
        return agent_winner, monitor_statuses
    except (subprocess.TimeoutExpired, Exception) as e:
        _debug(f"tmux session {session_name!r} status lookup failed: {e!r}")
        return "", []
