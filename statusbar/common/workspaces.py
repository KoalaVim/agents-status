#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field

from statusbar.common.config import IconsConfig, StatusbarConfig
from statusbar.common.naming import clean_title, longest_common_prefix, strip_prefix_and_jira
from statusbar.common.tmux import get_tmux_session_statuses, highest_priority_status
from statusbar.common.types import WorkspaceInfo, WorkspacesProvider

BROWSER_CLASSES = frozenset({
    "firefox", "firefox_firefox", "chromium", "google-chrome",
    "brave-browser", "vivaldi", "zen", "zen-browser",
    # macOS app names (aerospace uses spaces, not hyphens)
    "google chrome", "brave browser", "arc",
})
SLACK_CLASSES = frozenset({"slack"})


@dataclass
class _TmuxEntry:
    agent_icon: str
    monitor_icons: str
    raw_name: str
    is_viewer: bool


@dataclass
class _WorkspaceAcc:
    id: int
    is_active: bool
    tmux_entries: list[_TmuxEntry] = field(default_factory=list)
    agent_statuses: list[str] = field(default_factory=list)
    has_browser: bool = False
    has_slack: bool = False
    all_windows_slack: bool = True
    fallback_title: str = ""


@dataclass
class IconMaps:
    agent_status: dict[str, str]
    monitor_status: dict[str, str]
    tmux: str
    browser: str
    slack: str


def build_icon_maps(icons: IconsConfig) -> IconMaps:
    return IconMaps(
        agent_status={
            "INPROGRESS": icons.agent_inprogress,
            "WAITING": icons.agent_waiting,
            "IDLE": icons.agent_idle,
            "DONE": icons.agent_done,
        },
        monitor_status={
            "INPROGRESS": icons.monitor_inprogress,
        },
        tmux=icons.tmux,
        browser=icons.browser,
        slack=icons.slack,
    )


def _format_tmux_entry(
    entry: _TmuxEntry, prefix: str, is_active: bool, max_len: int,
) -> str:
    if is_active or not entry.raw_name.startswith(prefix):
        name = entry.raw_name
    else:
        name = entry.raw_name[len(prefix):] or entry.raw_name
    prefix_icons = entry.agent_icon + (" " + entry.monitor_icons if entry.monitor_icons else "")
    display = f"{prefix_icons} {name}"
    if len(display) > max_len:
        display = display[:max_len] + "…"
    return display


@dataclass
class _WorkspaceParts:
    """Structured parts of a workspace label for template rendering."""
    display_name: str
    agent_icon: str = ""
    tmux_sessions: str = ""
    app_icons: str = ""


def _format_tmux_session_name(
    entry: _TmuxEntry, prefix: str, is_active: bool, max_len: int,
) -> str:
    """Format just the session name (no icons) with prefix dedup and truncation."""
    if is_active or not entry.raw_name.startswith(prefix):
        name = entry.raw_name
    else:
        name = entry.raw_name[len(prefix):] or entry.raw_name
    if len(name) > max_len:
        name = name[:max_len] + "…"
    return name


def _format_workspace(
    acc: _WorkspaceAcc, icons: IconMaps, config: StatusbarConfig, prefix: str,
) -> _WorkspaceParts:
    features = config.features
    max_len = config.naming.max_length

    main_entries = [e for e in acc.tmux_entries if not e.is_viewer]
    viewer_entries = [e for e in acc.tmux_entries if e.is_viewer]
    entries = main_entries or viewer_entries

    if entries:
        app_icon_list: list[str] = []
        if acc.has_slack and features.slack_icon:
            app_icon_list.append(icons.slack)
        if acc.has_browser and features.browser_icon:
            app_icon_list.append(icons.browser)
        app_icons_str = " ".join(app_icon_list)
        icons_prefix = app_icons_str + " " if app_icon_list else ""

        formatted = [
            _format_tmux_entry(e, prefix, acc.is_active, max_len)
            for e in entries
        ]
        display_name = f"{acc.id} {icons_prefix}{'|'.join(formatted)}"

        session_names = [
            _format_tmux_session_name(e, prefix, acc.is_active, max_len)
            for e in entries
        ]
        agent_icon = entries[0].agent_icon if len(entries) == 1 else ""
        if not agent_icon:
            status = highest_priority_status(acc.agent_statuses)
            agent_icon = icons.agent_status.get(status, icons.tmux) if status else ""

        return _WorkspaceParts(
            display_name=display_name,
            agent_icon=agent_icon,
            tmux_sessions="|".join(session_names),
            app_icons=app_icons_str,
        )

    if acc.has_slack and not acc.has_browser and acc.all_windows_slack:
        slack_icon = icons.slack if features.slack_icon else ""
        label = f"{acc.id} {slack_icon} Slack" if slack_icon else f"{acc.id} Slack"
        return _WorkspaceParts(display_name=label, app_icons=slack_icon)

    if not acc.fallback_title:
        return _WorkspaceParts(display_name=f"{acc.id}")

    app_icon_list = []
    if acc.has_slack and features.slack_icon:
        app_icon_list.append(icons.slack)
    if acc.has_browser and features.browser_icon:
        app_icon_list.append(icons.browser)
    app_icons_str = " ".join(app_icon_list)
    icons_prefix = app_icons_str + " " if app_icon_list else ""
    title = acc.fallback_title
    if len(title) > max_len:
        title = title[:max_len] + "…"
    return _WorkspaceParts(
        display_name=f"{acc.id} {icons_prefix}{title}",
        app_icons=app_icons_str,
    )


def build_workspaces(
    provider: WorkspacesProvider, config: StatusbarConfig,
) -> list[WorkspaceInfo]:
    """Core aggregation pipeline: workspace data -> WorkspaceInfo list."""
    workspaces = provider.get_workspaces()
    if not workspaces:
        return []

    pinned_classes = provider.get_pinned_classes()
    icons = build_icon_maps(config.icons)
    features = config.features
    naming = config.naming

    accumulators: list[_WorkspaceAcc] = []

    for ws in workspaces:
        acc = _WorkspaceAcc(id=ws.id, is_active=ws.is_active)
        browser_fallback_set = False

        for win in ws.windows:
            if win.app_class in BROWSER_CLASSES:
                acc.has_browser = True
            if win.app_class in SLACK_CLASSES and win.app_class not in pinned_classes:
                acc.has_slack = True
            if win.app_class not in SLACK_CLASSES:
                acc.all_windows_slack = False

            if win.title.endswith(naming.tmux_suffix):
                session_name = clean_title(win.title[: -len(naming.tmux_suffix)])
                agent_status, monitor_statuses = get_tmux_session_statuses(session_name)

                if agent_status:
                    acc.agent_statuses.append(agent_status)
                acc.agent_statuses.extend(monitor_statuses)

                if features.agent_status:
                    agent_icon = icons.agent_status.get(agent_status, icons.tmux)
                else:
                    agent_icon = icons.tmux

                if features.monitor_status:
                    monitor_icons_str = "".join(
                        icons.monitor_status[s]
                        for s in monitor_statuses
                        if s in icons.monitor_status
                    )
                else:
                    monitor_icons_str = ""

                if features.jira_strip:
                    display_name = strip_prefix_and_jira(
                        session_name,
                        keep_number=features.active_keeps_number and ws.is_active,
                    )
                else:
                    display_name = session_name

                acc.tmux_entries.append(_TmuxEntry(
                    agent_icon=agent_icon,
                    monitor_icons=monitor_icons_str,
                    raw_name=display_name,
                    is_viewer=display_name.endswith("-viewer"),
                ))
            else:
                cleaned = clean_title(win.title)
                if cleaned:
                    if win.app_class in BROWSER_CLASSES and not browser_fallback_set:
                        acc.fallback_title = cleaned
                        browser_fallback_set = True
                    elif not acc.fallback_title and not browser_fallback_set:
                        acc.fallback_title = cleaned

        accumulators.append(acc)

    if features.prefix_dedup:
        all_raw_names = [
            e.raw_name for acc in accumulators for e in acc.tmux_entries
        ]
        prefix = longest_common_prefix(all_raw_names)
    else:
        prefix = ""

    results: list[WorkspaceInfo] = []
    for acc in sorted(accumulators, key=lambda a: a.id):
        parts = _format_workspace(acc, icons, config, prefix)
        status = highest_priority_status(acc.agent_statuses)
        results.append(WorkspaceInfo(
            id=acc.id,
            display_name=parts.display_name,
            agent_status=status,
            is_active=acc.is_active,
            agent_icon=parts.agent_icon,
            tmux_sessions=parts.tmux_sessions,
            app_icons=parts.app_icons,
        ))

    return results
