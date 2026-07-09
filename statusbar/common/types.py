#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class AgentStatus(StrEnum):
    INPROGRESS = "INPROGRESS"
    WAITING = "WAITING"
    DONE = "DONE"
    IDLE = "IDLE"


@dataclass
class WindowInfo:
    title: str
    app_class: str  # normalized lowercase


@dataclass
class WorkspaceData:
    id: int
    windows: list[WindowInfo] = field(default_factory=list)
    is_active: bool = False


@dataclass
class WorkspaceInfo:
    id: int
    display_name: str
    agent_status: str
    is_active: bool = False
    agent_icon: str = ""
    tmux_sessions: str = ""
    app_icons: str = ""


class WorkspacesProvider(Protocol):
    def get_workspaces(self) -> list[WorkspaceData]: ...
    def get_pinned_classes(self) -> set[str]: ...


class StatusBar(Protocol):
    def apply(self, workspaces: list[WorkspaceInfo]) -> None: ...
