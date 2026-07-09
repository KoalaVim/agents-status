# Statusbar Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Hyprland-only statusbar into a standardized interface with pluggable workspace providers and statusbar backends, then add AeroSpace + sketchybar support for macOS.

**Architecture:** Extract shared logic (tmux reading, naming, icons, aggregation) into `statusbar/common/`. Define `WorkspacesProvider` and `StatusBar` protocols. Hyprland becomes one implementation; AeroSpace + sketchybar become another. A unified `run.py` entry point replaces `RenameWorkspaces.py`.

**Tech Stack:** Python 3.10+ (stdlib only — subprocess, json, dataclasses, typing). Same zero-dependency constraint as the rest of the repo. Uses `tomllib` (3.11+) with `tomli` fallback for config, matching `core/server.py`.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `statusbar/common/__init__.py` | Re-exports public API: `build_workspaces`, `load_statusbar_config`, types |
| `statusbar/common/types.py` | Dataclasses (`WindowInfo`, `WorkspaceData`, `WorkspaceInfo`) and protocols (`WorkspacesProvider`, `StatusBar`) |
| `statusbar/common/config.py` | Load `[statusbar]` from `config.toml` into `StatusbarConfig` dataclass |
| `statusbar/common/naming.py` | `clean_title()`, `strip_prefix_and_jira()`, `longest_common_prefix()` — extracted from `RenameWorkspaces.py` |
| `statusbar/common/icons.py` | `StatusIcons` dataclass built from config with defaults, `AGENT_STATUS_ICONS`/`MONITOR_STATUS_ICONS` maps |
| `statusbar/common/tmux.py` | `get_tmux_session_statuses()`, `highest_priority_status()` — extracted from `RenameWorkspaces.py` |
| `statusbar/common/workspaces.py` | `build_workspaces(provider, config)` — the core aggregation pipeline |
| `statusbar/hyprland/__init__.py` | Empty |
| `statusbar/hyprland/workspaces.py` | `HyprlandWorkspacesProvider` — calls hyprctl for workspace/window data |
| `statusbar/hyprland/bar.py` | `HyprlandBar` — writes config file, calls vdeskreset/vdesksetstatus |
| `statusbar/aerospace/__init__.py` | Empty |
| `statusbar/aerospace/workspaces.py` | `AerospaceWorkspacesProvider` — calls aerospace CLI for workspace/window data |
| `statusbar/sketchybar/__init__.py` | Empty |
| `statusbar/sketchybar/bar.py` | `SketchyBar` — calls sketchybar --set per workspace |
| `statusbar/run.py` | Entry point: load config, create provider + bar, build + apply |
| ~~`statusbar/emojis.py`~~ | Removed — emoji regex inlined in `common/naming.py` |
| `statusbar/README.md` | Rewritten documentation |
| `README.md` | Updated packages table and statusbar section |

Files removed after refactor:
- `statusbar/hyprland/RenameWorkspaces.py`
- `statusbar/hyprland/icons.py`
- `statusbar/hyprland/emojis.py`
- `statusbar/hyprland/hypr_enums.py` (merged into `common/types.py`)

---

### Task 1: Create `common/types.py` — data model and protocols

**Files:**
- Create: `statusbar/common/types.py`

- [ ] **Step 1: Create the types module**

```python
#!/usr/bin/env python3
"""Data types and protocols for the statusbar package."""

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
    """A window on a workspace, as reported by the window manager."""
    title: str
    app_class: str  # normalized lowercase


@dataclass
class WorkspaceData:
    """Raw workspace data from a WorkspacesProvider."""
    id: int
    windows: list[WindowInfo] = field(default_factory=list)
    is_active: bool = False


@dataclass
class WorkspaceInfo:
    """Fully processed workspace ready for a StatusBar to render."""
    id: int
    display_name: str
    agent_status: str
    is_active: bool = False


class WorkspacesProvider(Protocol):
    def get_workspaces(self) -> list[WorkspaceData]:
        """Return all workspaces with their windows and active state."""
        ...

    def get_pinned_classes(self) -> set[str]:
        """Return window classes that are pinned/sticky (visible on all workspaces)."""
        ...


class StatusBar(Protocol):
    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        """Render workspace infos to the bar. Idempotent — only writes if changed."""
        ...
```

- [ ] **Step 2: Create empty `__init__.py`**

Create `statusbar/common/__init__.py` with an empty body (will be populated in a later task).

```python
```

- [ ] **Step 3: Commit**

```bash
git add statusbar/common/types.py statusbar/common/__init__.py
git commit -m "statusbar: add common types and protocols"
```

---

### Task 2: Create `common/config.py` — configuration loading

**Files:**
- Create: `statusbar/common/config.py`

- [ ] **Step 1: Create the config module**

This reuses the same `tomllib` / `tomli` fallback pattern from `core/server.py`. The `StatusbarConfig` dataclass has nested dataclasses for each config section, with defaults matching the current hardcoded values.

```python
#!/usr/bin/env python3
"""Load [statusbar] configuration from agents-status config.toml."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


@dataclass
class FeaturesConfig:
    agent_status: bool = True
    monitor_status: bool = True
    browser_icon: bool = True
    slack_icon: bool = True
    jira_strip: bool = True
    prefix_dedup: bool = True
    active_keeps_number: bool = True


@dataclass
class NamingConfig:
    max_length: int = 20
    tmux_suffix: str = " - TMUX"


@dataclass
class IconsConfig:
    agent_inprogress: str = "\uf111"   # 
    agent_waiting: str = "\uf28b"      # 
    agent_idle: str = "\udb81\ude29"   # 󰚩
    agent_done: str = "\uf00c"         # 
    monitor_inprogress: str = "\udb81\udd96"  # 󰦖
    tmux: str = "\ue795"               # 
    browser: str = "\udb80\udd9b"      # 󰎛
    slack: str = "\udb81\udecb"        # 󰻋


@dataclass
class SketchybarConfig:
    space_item_prefix: str = "space"


@dataclass
class StatusbarConfig:
    workspaces_provider: str = ""
    bar: str = ""
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    icons: IconsConfig = field(default_factory=IconsConfig)
    sketchybar: SketchybarConfig = field(default_factory=SketchybarConfig)


def _auto_detect() -> tuple[str, str]:
    """Auto-detect workspaces_provider and bar from available CLIs."""
    if shutil.which("hyprctl"):
        return "hyprland", "hyprland"
    if shutil.which("aerospace"):
        bar = "sketchybar" if shutil.which("sketchybar") else ""
        return "aerospace", bar
    return "", ""


def _build_dataclass(cls, raw: dict):
    """Build a dataclass from a dict, ignoring unknown keys."""
    valid = {f.name for f in cls.__dataclass_fields__.values()}
    return cls(**{k: v for k, v in raw.items() if k in valid})


def load_statusbar_config() -> StatusbarConfig:
    """Load [statusbar] config from config.toml, with defaults and auto-detection."""
    path = os.environ.get("AGENTS_STATUS_CONFIG") or os.path.expanduser(
        "~/.config/agents-status/config.toml"
    )
    raw: dict = {}
    if os.path.isfile(path) and tomllib is not None:
        try:
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
            raw = cfg.get("statusbar", {})
        except Exception:
            pass

    config = StatusbarConfig(
        workspaces_provider=raw.get("workspaces_provider", ""),
        bar=raw.get("bar", ""),
    )

    if raw.get("features"):
        config.features = _build_dataclass(FeaturesConfig, raw["features"])
    if raw.get("naming"):
        config.naming = _build_dataclass(NamingConfig, raw["naming"])
    if raw.get("icons"):
        config.icons = _build_dataclass(IconsConfig, raw["icons"])
    if raw.get("sketchybar"):
        config.sketchybar = _build_dataclass(SketchybarConfig, raw["sketchybar"])

    if not config.workspaces_provider or not config.bar:
        auto_provider, auto_bar = _auto_detect()
        if not config.workspaces_provider:
            config.workspaces_provider = auto_provider
        if not config.bar:
            config.bar = auto_bar

    return config
```

- [ ] **Step 2: Commit**

```bash
git add statusbar/common/config.py
git commit -m "statusbar: add config loading with defaults and auto-detection"
```

---

### Task 3: Create `common/naming.py` — name processing

**Files:**
- Create: `statusbar/common/naming.py`
- Reference: `statusbar/hyprland/RenameWorkspaces.py:97-151` (functions being extracted)

- [ ] **Step 1: Create the naming module**

Extract `strip_prefix_and_jira()`, `longest_common_prefix()`, and `clean_title()` from `RenameWorkspaces.py`. The `clean_title` function needs access to the emoji regex, so import from the top-level `emojis.py` (which we'll move in a later task — for now use a relative import path).

```python
#!/usr/bin/env python3
"""Name processing utilities for statusbar workspace names."""

from __future__ import annotations

import re

JIRA_TICKET_RE = re.compile(r"[A-Z]+-\d+")
SEPARATORS = set("-_/. ")

# Inline the emoji regex to avoid cross-package import issues.
# Copied from statusbar/emojis.py (canonical source for the full pattern).
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "\U000020E3"
    "\U00002600-\U000026FF"
    "\U0000231A-\U0000231B"
    "\U00002934-\U00002935"
    "\U000025AA-\U000025AB"
    "\U000025FB-\U000025FE"
    "\U00002B05-\U00002B07"
    "\U00002B1B-\U00002B1C"
    "\U00002B50"
    "\U00002B55"
    "\U00003030"
    "\U0000303D"
    "\U00003297"
    "\U00003299"
    "]+",
    flags=re.UNICODE,
)


def clean_title(title: str) -> str:
    """Remove emojis, CJK brackets, collapse whitespace, strip."""
    title = EMOJI_RE.sub("", title)
    title = title.replace("\u300c", "").replace("\u300d", "")
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def strip_prefix_and_jira(name: str, keep_number: bool = False) -> str:
    """Strip username prefix and JIRA project key from a branch/session name.

    With keep_number=True, retains the ticket number
    (e.g. 'ofirg-DR-1299-fix-bug' -> '1299-fix-bug').
    Otherwise drops it (e.g. 'ofirg-DR-1299-fix-bug' -> 'fix-bug').
    """
    m = JIRA_TICKET_RE.search(name)
    if m:
        ticket = m.group()
        number = ticket.split("-", 1)[1]
        rest = name[m.end():].lstrip("-_ ")
        if keep_number:
            return f"{number}-{rest}" if rest else number
        return rest or name
    return name


def longest_common_prefix(names: list[str]) -> str:
    """Find the longest separator-terminated prefix shared by at least 2 names."""
    if len(names) < 2:
        return ""
    prefix_counts: dict[str, int] = {}
    for name in names:
        seen: set[str] = set()
        for i, ch in enumerate(name):
            if ch in SEPARATORS:
                prefix = name[: i + 1]
                if prefix not in seen:
                    seen.add(prefix)
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    best = ""
    for prefix, count in prefix_counts.items():
        if count >= 2 and len(prefix) > len(best):
            best = prefix
    return best
```

- [ ] **Step 2: Commit**

```bash
git add statusbar/common/naming.py
git commit -m "statusbar: extract naming utilities from RenameWorkspaces"
```

---

### Task 4: Create `common/icons.py` — configurable icon maps

**Files:**
- Create: `statusbar/common/icons.py`
- Reference: `statusbar/hyprland/icons.py` (current hardcoded icons)

- [ ] **Step 1: Create the icons module**

Build icon maps from `StatusbarConfig.icons`. The maps are keyed by `AgentStatus` string values.

```python
#!/usr/bin/env python3
"""Icon maps for statusbar, built from configuration."""

from __future__ import annotations

from dataclasses import dataclass

from statusbar.common.config import IconsConfig


BROWSER_CLASSES = frozenset({
    "firefox", "firefox_firefox", "chromium", "google-chrome",
    "brave-browser", "vivaldi", "zen", "zen-browser",
})
SLACK_CLASSES = frozenset({"slack"})


@dataclass
class IconMaps:
    """Pre-built icon lookup tables from config."""
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
```

- [ ] **Step 2: Commit**

```bash
git add statusbar/common/icons.py
git commit -m "statusbar: add configurable icon maps"
```

---

### Task 5: Create `common/tmux.py` — tmux status reading

**Files:**
- Create: `statusbar/common/tmux.py`
- Reference: `statusbar/hyprland/RenameWorkspaces.py:39-82` (functions being extracted)

- [ ] **Step 1: Create the tmux module**

Extract `get_tmux_session_statuses()` and `highest_priority_status()`. These are used by `build_workspaces()` to look up agent status for tmux sessions found on workspaces.

```python
#!/usr/bin/env python3
"""Read agent status from tmux session window options."""

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
    """Return the highest priority status from a list (WAITING > INPROGRESS > DONE > IDLE)."""
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
        result = subprocess.run(
            ["tmux", "list-windows", "-t", session_name, "-F",
             "#{@ai-agent-status}|#{@monitor-status}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        agent_statuses: list[str] = []
        monitor_statuses: list[str] = []
        for line in result.stdout.splitlines():
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
```

- [ ] **Step 2: Commit**

```bash
git add statusbar/common/tmux.py
git commit -m "statusbar: extract tmux status reading into common module"
```

---

### Task 6: Create `common/workspaces.py` — the core aggregation pipeline

**Files:**
- Create: `statusbar/common/workspaces.py`
- Reference: `statusbar/hyprland/RenameWorkspaces.py:231-423` (the main() logic being extracted)

This is the largest task. It takes `WorkspacesProvider` output and config, reads tmux statuses, applies naming rules, and produces `WorkspaceInfo` objects.

- [ ] **Step 1: Create the workspaces module**

```python
#!/usr/bin/env python3
"""Core aggregation pipeline: provider data + tmux statuses -> WorkspaceInfo list."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from statusbar.common.config import StatusbarConfig
from statusbar.common.icons import IconMaps, build_icon_maps, BROWSER_CLASSES, SLACK_CLASSES
from statusbar.common.naming import clean_title, strip_prefix_and_jira, longest_common_prefix
from statusbar.common.tmux import get_tmux_session_statuses, highest_priority_status, set_debug, _debug
from statusbar.common.types import WorkspaceData, WorkspaceInfo, WorkspacesProvider


@dataclass
class _TmuxEntry:
    """Intermediate: a tmux session found on a workspace."""
    agent_icon: str
    monitor_icons: str
    raw_name: str
    is_viewer: bool


@dataclass
class _WorkspaceAcc:
    """Accumulator for per-workspace data during the aggregation pass."""
    id: int
    is_active: bool
    tmux_entries: list[_TmuxEntry] = field(default_factory=list)
    agent_statuses: list[str] = field(default_factory=list)
    has_browser: bool = False
    has_slack: bool = False
    all_windows_slack: bool = True
    fallback_title: str = ""


def build_workspaces(
    provider: WorkspacesProvider,
    config: StatusbarConfig,
) -> list[WorkspaceInfo]:
    """Read workspace data from provider, read tmux statuses,
    aggregate, apply naming rules, return ready-to-render WorkspaceInfos."""

    icons = build_icon_maps(config.icons)
    pinned = provider.get_pinned_classes()
    workspace_datas = provider.get_workspaces()

    if not workspace_datas:
        print("No workspaces found", file=sys.stderr)
        return []

    accs: dict[int, _WorkspaceAcc] = {}
    for ws in workspace_datas:
        acc = _WorkspaceAcc(id=ws.id, is_active=ws.is_active)

        browser_candidate_title = ""
        for win in ws.windows:
            cls = win.app_class
            if cls in BROWSER_CLASSES:
                acc.has_browser = True
                if not browser_candidate_title:
                    browser_candidate_title = clean_title(win.title)
            if cls in SLACK_CLASSES and cls not in pinned:
                acc.has_slack = True
            if cls not in SLACK_CLASSES:
                acc.all_windows_slack = False

            if win.title.endswith(config.naming.tmux_suffix):
                name = clean_title(win.title[:-len(config.naming.tmux_suffix)])
                agent_status, monitor_statuses = get_tmux_session_statuses(name)

                if config.features.agent_status and agent_status:
                    acc.agent_statuses.append(agent_status)
                for ms in monitor_statuses:
                    if config.features.monitor_status:
                        acc.agent_statuses.append(ms)

                agent_icon = icons.agent_status.get(agent_status, icons.tmux) if config.features.agent_status else icons.tmux
                monitor_icons_str = ""
                if config.features.monitor_status:
                    monitor_icons_str = "".join(
                        icons.monitor_status[s] for s in monitor_statuses if s in icons.monitor_status
                    )

                session_name = name
                if config.features.jira_strip:
                    session_name = strip_prefix_and_jira(
                        name,
                        keep_number=config.features.active_keeps_number and ws.is_active,
                    )

                acc.tmux_entries.append(_TmuxEntry(
                    agent_icon=agent_icon,
                    monitor_icons=monitor_icons_str,
                    raw_name=session_name,
                    is_viewer=session_name.endswith("-viewer"),
                ))
            elif not acc.fallback_title:
                acc.fallback_title = clean_title(win.title)

        if not acc.fallback_title and browser_candidate_title:
            acc.fallback_title = browser_candidate_title

        accs[ws.id] = acc

    # Compute common prefix for shortening
    prefix = ""
    if config.features.prefix_dedup:
        all_names = [e.raw_name for acc in accs.values() for e in acc.tmux_entries]
        prefix = longest_common_prefix(all_names)

    results: list[WorkspaceInfo] = []
    for acc in accs.values():
        agent_status = highest_priority_status(acc.agent_statuses)
        display = _format_workspace(acc, icons, config, prefix)
        results.append(WorkspaceInfo(
            id=acc.id,
            display_name=display,
            agent_status=agent_status,
            is_active=acc.is_active,
        ))

    results.sort(key=lambda w: w.id)
    return results


def _format_workspace(
    acc: _WorkspaceAcc,
    icons: IconMaps,
    config: StatusbarConfig,
    prefix: str,
) -> str:
    """Format a single workspace's display name."""
    max_len = config.naming.max_length

    main_entries = [e for e in acc.tmux_entries if not e.is_viewer]
    viewer_entries = [e for e in acc.tmux_entries if e.is_viewer]
    entries = main_entries or viewer_entries

    if entries:
        app_icons: list[str] = []
        if config.features.slack_icon and acc.has_slack:
            app_icons.append(icons.slack)
        if config.features.browser_icon and acc.has_browser:
            app_icons.append(icons.browser)
        icons_prefix = " ".join(app_icons) + " " if app_icons else ""

        formatted = [_format_tmux_entry(e, prefix, acc.is_active, max_len) for e in entries]
        return f"{acc.id} {icons_prefix}{'|'.join(formatted)}"

    # No tmux sessions — fall back to window title
    if not acc.fallback_title:
        return f"{acc.id}"

    only_slack = (
        acc.has_slack
        and not acc.has_browser
        and config.features.slack_icon
        and acc.all_windows_slack
    )
    if only_slack:
        return f"{acc.id} {icons.slack} Slack"

    app_icons = []
    if config.features.slack_icon and acc.has_slack:
        app_icons.append(icons.slack)
    if config.features.browser_icon and acc.has_browser:
        app_icons.append(icons.browser)
    icons_prefix = " ".join(app_icons) + " " if app_icons else ""

    title = acc.fallback_title
    if len(title) > max_len:
        title = title[:max_len] + "\u2026"
    return f"{acc.id} {icons_prefix}{title}"


def _format_tmux_entry(
    entry: _TmuxEntry,
    prefix: str,
    is_active: bool,
    max_len: int,
) -> str:
    """Format a single tmux session entry within a workspace."""
    name = entry.raw_name
    if not is_active and prefix and name.startswith(prefix):
        shortened = name[len(prefix):]
        if shortened:
            name = shortened

    prefix_icons = entry.agent_icon
    if entry.monitor_icons:
        prefix_icons += " " + entry.monitor_icons
    display = f"{prefix_icons} {name}"
    if len(display) > max_len:
        display = display[:max_len] + "\u2026"
    return display
```

- [ ] **Step 2: Commit**

```bash
git add statusbar/common/workspaces.py
git commit -m "statusbar: add core workspace aggregation pipeline"
```

---

### Task 7: Create Hyprland provider and bar

**Files:**
- Create: `statusbar/hyprland/__init__.py`
- Create: `statusbar/hyprland/workspaces.py` (new — the provider)
- Create: `statusbar/hyprland/bar.py` (new — the bar backend)

- [ ] **Step 1: Create `hyprland/__init__.py`**

```python
```

- [ ] **Step 2: Create the Hyprland WorkspacesProvider**

Extract the `hyprctl` calls from `RenameWorkspaces.py` into a provider that returns `WorkspaceData` objects.

`statusbar/hyprland/workspaces.py`:

```python
#!/usr/bin/env python3
"""WorkspacesProvider for Hyprland — reads workspace/window data via hyprctl."""

from __future__ import annotations

import json
import subprocess
import sys


from statusbar.common.types import WindowInfo, WorkspaceData


def _run_hyprctl(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["hyprctl"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"hyprctl {args[0]} failed: {e}", file=sys.stderr)
        return ""


def _parse_json(output: str, label: str) -> list | dict:
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print(f"Error parsing {label} JSON", file=sys.stderr)
        return []


class HyprlandWorkspacesProvider:
    def get_workspaces(self) -> list[WorkspaceData]:
        vdesks = _parse_json(_run_hyprctl(["printstate", "-j"]), "vdesks")
        if not isinstance(vdesks, list):
            return []

        clients = _parse_json(_run_hyprctl(["clients", "-j"]), "clients")
        if not isinstance(clients, list):
            clients = []

        # Map hyprland workspace id -> vdesk
        ws_to_vdesk: dict[int, dict] = {}
        for vdesk in vdesks:
            for ws_id in vdesk.get("workspaces", []):
                ws_to_vdesk[ws_id] = vdesk

        # Find active vdesk
        active_vdesk_id: int | None = None
        active_ws = _parse_json(_run_hyprctl(["activeworkspace", "-j"]), "activeworkspace")
        if isinstance(active_ws, dict):
            active_ws_id = active_ws.get("id")
            vdesk = ws_to_vdesk.get(active_ws_id)
            if vdesk:
                active_vdesk_id = vdesk.get("id")

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
            win = WindowInfo(
                title=client.get("title", ""),
                app_class=client.get("class", "").lower(),
            )
            vdesk_windows.setdefault(vdesk_id, []).append(win)

        # Build WorkspaceData per vdesk
        results: list[WorkspaceData] = []
        for vdesk in vdesks:
            vdesk_id = vdesk.get("id")
            results.append(WorkspaceData(
                id=vdesk_id,
                windows=vdesk_windows.get(vdesk_id, []),
                is_active=(vdesk_id == active_vdesk_id),
            ))
        return results

    def get_pinned_classes(self) -> set[str]:
        output = _run_hyprctl(["printpinnedwindows", "-j"])
        data = _parse_json(output, "pinned")
        if isinstance(data, list):
            return {w.get("class", "").lower() for w in data}
        return set()
```

- [ ] **Step 3: Create the Hyprland StatusBar**

Extract `write_names()` and `set_vdesk_statuses()` from `RenameWorkspaces.py`.

`statusbar/hyprland/bar.py`:

```python
#!/usr/bin/env python3
"""StatusBar for Hyprland — writes VirtualDesktopsNames.conf and sets vdesk statuses."""

from __future__ import annotations

import os
import subprocess

from statusbar.common.tmux import highest_priority_status
from statusbar.common.types import WorkspaceInfo


CONFIG_LOC = os.path.expanduser("~/.config/hypr/UserConfigs/VirtualDesktopsNames.conf")


class HyprlandBar:
    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        names: dict[int, str] = {}
        for ws in workspaces:
            names[ws.id] = ws.display_name

        self._write_names(names)
        self._set_statuses(workspaces)

    def _write_names(self, names: dict[int, str]) -> None:
        names_str = ", ".join(f"{id}:{name}" for id, name in sorted(names.items()))
        content = f"""plugin {{
    virtual-desktops {{
        names = {names_str}
    }}
}}
"""
        try:
            with open(CONFIG_LOC, "r") as f:
                if f.read() == content:
                    return
        except FileNotFoundError:
            pass

        with open(CONFIG_LOC, "w") as f:
            f.write(content)

        subprocess.run(["hyprctl", "dispatch", "vdeskreset"], capture_output=True)

    def _set_statuses(self, workspaces: list[WorkspaceInfo]) -> None:
        for ws in workspaces:
            subprocess.run(
                ["hyprctl", "dispatch", "vdesksetstatus", f"{ws.id},{ws.agent_status}"],
                capture_output=True,
            )
```

- [ ] **Step 4: Commit**

```bash
git add statusbar/hyprland/__init__.py statusbar/hyprland/workspaces.py statusbar/hyprland/bar.py
git commit -m "statusbar: add Hyprland provider and bar backend"
```

---

### Task 8: Create AeroSpace provider

**Files:**
- Create: `statusbar/aerospace/__init__.py`
- Create: `statusbar/aerospace/workspaces.py`

- [ ] **Step 1: Create `aerospace/__init__.py`**

```python
```

- [ ] **Step 2: Create the AeroSpace WorkspacesProvider**

AeroSpace uses `aerospace list-workspaces` and `aerospace list-windows` CLI commands.

`statusbar/aerospace/workspaces.py`:

```python
#!/usr/bin/env python3
"""WorkspacesProvider for AeroSpace — reads workspace/window data via aerospace CLI."""

from __future__ import annotations

import json
import subprocess
import sys

from statusbar.common.types import WindowInfo, WorkspaceData


def _run_aerospace(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["aerospace"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"aerospace {args[0]} failed: {e}", file=sys.stderr)
        return ""


class AerospaceWorkspacesProvider:
    def get_workspaces(self) -> list[WorkspaceData]:
        # Get all workspace IDs
        ws_output = _run_aerospace(["list-workspaces", "--all"])
        if not ws_output.strip():
            return []

        # Get focused workspace
        focused_output = _run_aerospace(["list-workspaces", "--focused"]).strip()

        # Get all windows as JSON
        win_output = _run_aerospace([
            "list-windows", "--all",
            "--format", "%{workspace}|%{app-name}|%{window-title}",
        ])

        # Group windows by workspace
        ws_windows: dict[str, list[WindowInfo]] = {}
        for line in win_output.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            ws_id, app_name, title = parts
            ws_id = ws_id.strip()
            win = WindowInfo(
                title=title.strip(),
                app_class=app_name.strip().lower(),
            )
            ws_windows.setdefault(ws_id, []).append(win)

        results: list[WorkspaceData] = []
        for ws_id_str in ws_output.strip().splitlines():
            ws_id_str = ws_id_str.strip()
            if not ws_id_str:
                continue
            try:
                ws_id = int(ws_id_str)
            except ValueError:
                continue
            results.append(WorkspaceData(
                id=ws_id,
                windows=ws_windows.get(ws_id_str, []),
                is_active=(ws_id_str == focused_output),
            ))
        return results

    def get_pinned_classes(self) -> set[str]:
        return set()
```

- [ ] **Step 3: Commit**

```bash
git add statusbar/aerospace/__init__.py statusbar/aerospace/workspaces.py
git commit -m "statusbar: add AeroSpace workspace provider"
```

---

### Task 9: Create sketchybar backend

**Files:**
- Create: `statusbar/sketchybar/__init__.py`
- Create: `statusbar/sketchybar/bar.py`

- [ ] **Step 1: Create `sketchybar/__init__.py`**

```python
```

- [ ] **Step 2: Create the sketchybar StatusBar**

Sketchybar is configured via `sketchybar --set` commands. Each workspace item is named `<prefix>.<id>`.

`statusbar/sketchybar/bar.py`:

```python
#!/usr/bin/env python3
"""StatusBar for sketchybar — updates space items via sketchybar CLI."""

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
        args = ["sketchybar"]
        for ws in workspaces:
            item = f"{self._prefix}.{ws.id}"
            color = STATUS_COLORS.get(ws.agent_status, DEFAULT_COLOR)
            args += ["--set", item, f"label={ws.display_name}", f"icon.color={color}"]

        if len(args) <= 1:
            return

        try:
            subprocess.run(args, capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"sketchybar update failed: {e}", file=sys.stderr)
```

- [ ] **Step 3: Commit**

```bash
git add statusbar/sketchybar/__init__.py statusbar/sketchybar/bar.py
git commit -m "statusbar: add sketchybar backend"
```

---

### Task 10: Create `run.py` entry point and wire up `__init__.py`

**Files:**
- Create: `statusbar/run.py`
- Modify: `statusbar/common/__init__.py`

- [ ] **Step 1: Populate `common/__init__.py` with re-exports**

```python
from statusbar.common.config import load_statusbar_config, StatusbarConfig
from statusbar.common.types import (
    AgentStatus, WindowInfo, WorkspaceData, WorkspaceInfo,
    WorkspacesProvider, StatusBar,
)
from statusbar.common.workspaces import build_workspaces

__all__ = [
    "load_statusbar_config", "StatusbarConfig",
    "AgentStatus", "WindowInfo", "WorkspaceData", "WorkspaceInfo",
    "WorkspacesProvider", "StatusBar",
    "build_workspaces",
]
```

- [ ] **Step 2: Create `run.py`**

This is the unified entry point that replaces `RenameWorkspaces.py` in post-event hooks.

`statusbar/run.py`:

```python
#!/usr/bin/env python3
"""Unified statusbar entry point.

Reads config, creates the appropriate workspace provider and statusbar backend,
builds workspace info, and applies it to the bar.

Usage (as post-event hook in config.toml):
    "$AGENTS_STATUS_DIR/../statusbar/run.py"

    # With debug logging:
    "$AGENTS_STATUS_DIR/../statusbar/run.py --debug"
"""

import argparse
import sys

from statusbar.common.config import load_statusbar_config
from statusbar.common.tmux import set_debug
from statusbar.common.workspaces import build_workspaces


def _create_provider(name: str):
    if name == "hyprland":
        from statusbar.hyprland.workspaces import HyprlandWorkspacesProvider
        return HyprlandWorkspacesProvider()
    elif name == "aerospace":
        from statusbar.aerospace.workspaces import AerospaceWorkspacesProvider
        return AerospaceWorkspacesProvider()
    else:
        print(f"Unknown workspaces_provider: {name!r}. Supported: hyprland, aerospace", file=sys.stderr)
        sys.exit(1)


def _create_bar(name: str, config):
    if name == "hyprland":
        from statusbar.hyprland.bar import HyprlandBar
        return HyprlandBar()
    elif name == "sketchybar":
        from statusbar.sketchybar.bar import SketchyBar
        return SketchyBar(config.sketchybar)
    else:
        print(f"Unknown bar: {name!r}. Supported: hyprland, sketchybar", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Print debug logs")
    args = parser.parse_args()

    set_debug(args.debug)

    config = load_statusbar_config()

    if not config.workspaces_provider:
        print("No workspaces_provider configured and auto-detection failed.\n"
              "Set [statusbar] workspaces_provider in config.toml.", file=sys.stderr)
        sys.exit(1)
    if not config.bar:
        print("No bar configured and auto-detection failed.\n"
              "Set [statusbar] bar in config.toml.", file=sys.stderr)
        sys.exit(1)

    provider = _create_provider(config.workspaces_provider)
    bar = _create_bar(config.bar, config)
    workspaces = build_workspaces(provider, config)
    bar.apply(workspaces)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Make `run.py` executable**

```bash
chmod +x statusbar/run.py
```

- [ ] **Step 4: Commit**

```bash
git add statusbar/common/__init__.py statusbar/run.py
git commit -m "statusbar: add unified run.py entry point"
```

---

### Task 11: Clean up old files

**Files:**
- Delete: `statusbar/hyprland/RenameWorkspaces.py`
- Delete: `statusbar/hyprland/icons.py`
- Delete: `statusbar/hyprland/emojis.py`
- Delete: `statusbar/hyprland/hypr_enums.py`

- [ ] **Step 1: Remove old Hyprland-only files**

These are now replaced by the common modules and the Hyprland provider/bar.

```bash
git rm statusbar/hyprland/RenameWorkspaces.py
git rm statusbar/hyprland/icons.py
git rm statusbar/hyprland/emojis.py
git rm statusbar/hyprland/hypr_enums.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "statusbar: remove old monolithic Hyprland files"
```

---

### Task 12: Verify the refactor works

- [ ] **Step 1: Test import chain**

Run from the repo root to verify all modules import cleanly:

```bash
PYTHONPATH=. python3 -c "from statusbar.common import build_workspaces, load_statusbar_config, WorkspaceInfo; print('common OK')"
PYTHONPATH=. python3 -c "from statusbar.hyprland.workspaces import HyprlandWorkspacesProvider; print('hyprland provider OK')"
PYTHONPATH=. python3 -c "from statusbar.hyprland.bar import HyprlandBar; print('hyprland bar OK')"
PYTHONPATH=. python3 -c "from statusbar.aerospace.workspaces import AerospaceWorkspacesProvider; print('aerospace provider OK')"
PYTHONPATH=. python3 -c "from statusbar.sketchybar.bar import SketchyBar; print('sketchybar bar OK')"
```

Expected: all print "OK".

- [ ] **Step 2: Test `run.py --help`**

```bash
PYTHONPATH=. python3 statusbar/run.py --help
```

Expected: prints usage with `--debug` option.

- [ ] **Step 3: Fix any import errors**

If any imports fail, fix them and re-run.

---

### Task 13: Update documentation

**Files:**
- Rewrite: `statusbar/README.md`
- Modify: `README.md`
- Modify: `statusbar/TODO.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Rewrite `statusbar/README.md`**

Replace the current Hyprland-only README with documentation covering the standardized interface:

```markdown
# statusbar

Desktop statusbar integrations that display agent status on workspace/desktop indicators.

## How It Works

The statusbar package reads agent status from tmux window options (`@ai-agent-status`) and workspace/window data from your window manager, then renders status icons and session names to your statusbar.

Two pluggable layers:
- **WorkspacesProvider** — reads workspace and window data from the window manager
- **StatusBar** — renders the formatted output to the bar

## Supported Combinations

| Provider | Bar | OS |
|----------|-----|----|
| Hyprland | Hyprland | Linux |
| AeroSpace | sketchybar | macOS |

## Usage

### As a post-event hook (recommended)

Add to `~/.config/agents-status/config.toml`:

\```toml
[post-event]
commands = [
    "$AGENTS_STATUS_DIR/../statusbar/run.py",
]
\```

### Standalone

\```sh
PYTHONPATH=/path/to/agents-status python3 statusbar/run.py --debug
\```

## Configuration

All configuration lives in `~/.config/agents-status/config.toml` under the `[statusbar]` section.

### Provider and bar selection

\```toml
[statusbar]
workspaces_provider = "hyprland"   # "hyprland" | "aerospace"
bar = "hyprland"                   # "hyprland" | "sketchybar"
\```

If omitted, auto-detected from available CLIs.

### Feature toggles

\```toml
[statusbar.features]
agent_status = true                # show agent status icons per workspace
monitor_status = true              # show monitor status icons
browser_icon = true                # show browser icon when browser present
slack_icon = true                  # show slack icon when slack present
jira_strip = true                  # strip JIRA ticket prefix from session names
prefix_dedup = true                # deduplicate common prefix across session names
active_keeps_number = true         # keep JIRA ticket number on active workspace
\```

### Naming

\```toml
[statusbar.naming]
max_length = 20                    # max display name length before truncation
tmux_suffix = " - TMUX"           # suffix to identify tmux terminal windows
\```

### Custom icons

\```toml
[statusbar.icons]
agent_inprogress = ""
agent_waiting = ""
agent_idle = "󰚩"
agent_done = ""
tmux = ""
browser = ""
slack = ""
\```

### Sketchybar-specific

\```toml
[statusbar.sketchybar]
space_item_prefix = "space"        # items named space.1, space.2, etc.
\```

## Requirements

- **Python 3.10+**
- **tmux** (for reading agent statuses)
- **A Nerd Font** for status icons
- **Hyprland:** hyprctl, [virtual-desktops plugin](https://github.com/levnikmyskin/hyprland-virtual-desktops)
- **macOS:** AeroSpace, sketchybar

## Adding a New Provider

Implement `WorkspacesProvider` protocol in `statusbar/<name>/workspaces.py`:

\```python
class MyProvider:
    def get_workspaces(self) -> list[WorkspaceData]:
        ...

    def get_pinned_classes(self) -> set[str]:
        ...
\```

Then register it in `statusbar/run.py:_create_provider()`.

## Adding a New Bar

Implement `StatusBar` protocol in `statusbar/<name>/bar.py`:

\```python
class MyBar:
    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        ...
\```

Then register it in `statusbar/run.py:_create_bar()`.
```

Note: the `\``` ` above should be plain triple backticks in the actual file (escaped here for plan readability).

- [ ] **Step 2: Update root `README.md`**

In the packages table, change the statusbar row from:

```
| [`statusbar/`](statusbar/) | Hyprland virtual desktop renaming by agent status |
```

to:

```
| [`statusbar/`](statusbar/) | Desktop statusbar integration (Hyprland, sketchybar) |
```

In the Statusbar section near the bottom, replace:

```
Wire the Hyprland integration as a post-event hook in your core config. See [`statusbar/README.md`](statusbar/README.md).
```

with:

```
Add the statusbar integration as a post-event hook. Supports Hyprland (Linux) and AeroSpace + sketchybar (macOS). See [`statusbar/README.md`](statusbar/README.md) for configuration.
```

- [ ] **Step 3: Update `statusbar/TODO.md`**

Remove items that are now done or no longer applicable. Keep Waybar, eww, AGS as future work. Add any new items that surfaced.

Replace current contents with:

```markdown
# statusbar TODO

- [ ] Waybar custom module (JSON output for waybar's custom module protocol)
- [ ] eww widget integration
- [ ] AGS module integration
- [ ] Install script for required system packages
- [ ] Tests for common/naming.py and common/tmux.py
```

- [ ] **Step 4: Update `AGENTS.md`**

In the `## Repo Layout` section, update the statusbar line from:

```
statusbar/ Hyprland virtual desktop renaming
```

to:

```
statusbar/ Desktop statusbar integrations (Hyprland, sketchybar)
```

- [ ] **Step 5: Commit**

```bash
git add statusbar/README.md README.md statusbar/TODO.md AGENTS.md
git commit -m "docs: update statusbar documentation for standardized interface"
```

---

### Task 14: Final verification

- [ ] **Step 1: Run full import test again**

```bash
PYTHONPATH=. python3 -c "
from statusbar.common import build_workspaces, load_statusbar_config
from statusbar.hyprland.workspaces import HyprlandWorkspacesProvider
from statusbar.hyprland.bar import HyprlandBar
from statusbar.aerospace.workspaces import AerospaceWorkspacesProvider
from statusbar.sketchybar.bar import SketchyBar
print('All imports OK')
"
```

- [ ] **Step 2: Verify `run.py` auto-detection works on macOS**

```bash
PYTHONPATH=. python3 statusbar/run.py --debug
```

On macOS with AeroSpace + sketchybar installed, this should auto-detect and run. Without either, it should print a clear error message about missing provider/bar.

- [ ] **Step 3: Verify no old files remain**

```bash
ls statusbar/hyprland/
```

Expected: only `__init__.py`, `workspaces.py`, `bar.py`.
