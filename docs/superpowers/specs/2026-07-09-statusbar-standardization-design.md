# Statusbar Standardization + Sketchybar Support

## Goal

Standardize the statusbar interface so new statusbar integrations are easy to add. Support sketchybar (macOS) alongside the existing Hyprland integration (Linux). Keep relying on tmux window options for agent status and terminal window titles for session identification.

## Current State

`statusbar/hyprland/RenameWorkspaces.py` is a 426-line monolith that mixes:
- Reading tmux session/window statuses (`@ai-agent-status`, `@monitor-status`)
- Querying Hyprland for workspace/window data (`hyprctl clients`, `hyprctl printstate`)
- Name processing (JIRA stripping, prefix dedup, title cleaning, truncation)
- Icon mapping (agent status, monitor, browser, Slack)
- Rendering (writing `VirtualDesktopsNames.conf`, calling `hyprctl dispatch vdeskreset/vdesksetstatus`)

None of this is reusable by another statusbar.

## Architecture

Split into three layers:

1. **WorkspacesProvider** — reads workspace/window data from the window manager
2. **Shared logic** (`common/`) — reads tmux statuses, aggregates, applies naming rules, produces `WorkspaceInfo` objects
3. **StatusBar** — renders `WorkspaceInfo` to the native bar

```
WorkspacesProvider  -->  build_workspaces()  -->  StatusBar.apply()
(hyprland/aerospace)     (common, reads tmux)     (hyprland/sketchybar)
```

### Supported Combinations

| WorkspacesProvider | StatusBar | OS | Status |
|---|---|---|---|
| Hyprland | Hyprland | Linux | Existing (refactored) |
| AeroSpace | sketchybar | macOS | New |

## Directory Structure

```
statusbar/
  common/
    __init__.py          # exports public API
    types.py             # WorkspaceInfo, WorkspaceData, WindowInfo, protocols
    tmux.py              # read tmux session/window agent statuses
    workspaces.py        # build_workspaces() — aggregation, naming, icons
    naming.py            # JIRA stripping, prefix dedup, title cleaning
    icons.py             # icon maps (agent, monitor, browser, slack)
    config.py            # load [statusbar] config from config.toml
  hyprland/
    workspaces.py        # WorkspacesProvider via hyprctl
    bar.py               # StatusBar via hyprctl dispatch + config file
    hypr_enums.py        # kept as-is
  aerospace/
    workspaces.py        # WorkspacesProvider via aerospace CLI
  sketchybar/
    bar.py               # StatusBar via sketchybar CLI
  emojis.py              # emoji regex utility (existing, used by naming.py)
  README.md
```

## Data Model

### Input: WorkspacesProvider output

```python
@dataclass
class WindowInfo:
    title: str          # OS-level window title (e.g. "my-session - TMUX")
    app_class: str      # normalized lowercase (e.g. "firefox", "slack", "kitty")

@dataclass
class WorkspaceData:
    id: int
    windows: list[WindowInfo]
    is_active: bool
```

### Output: what StatusBar receives

```python
@dataclass
class WorkspaceInfo:
    id: int
    display_name: str        # fully formatted string ready to display
    agent_status: str        # raw status for bars that do their own coloring
    is_active: bool
```

## Protocol Contracts

### WorkspacesProvider

```python
class WorkspacesProvider(Protocol):
    def get_workspaces(self) -> list[WorkspaceData]:
        """Return all workspaces with their windows and active state."""
        ...

    def get_pinned_classes(self) -> set[str]:
        """Return window classes that are pinned/sticky (visible on all workspaces)."""
        ...
```

Implementations:
- **Hyprland:** calls `hyprctl clients -j`, `hyprctl printstate -j`, `hyprctl activeworkspace -j`
- **AeroSpace:** calls `aerospace list-workspaces --all`, `aerospace list-windows --all`

### StatusBar

```python
class StatusBar(Protocol):
    def apply(self, workspaces: list[WorkspaceInfo]) -> None:
        """Render workspace infos to the bar. Idempotent — only writes if changed."""
        ...
```

Implementations:
- **Hyprland:** writes `VirtualDesktopsNames.conf`, calls `hyprctl dispatch vdeskreset`, calls `hyprctl dispatch vdesksetstatus` per workspace
- **sketchybar:** calls `sketchybar --set space.<id> label="<display_name>" icon.color=<color>` per workspace

### Main entry point

```python
def build_workspaces(
    provider: WorkspacesProvider,
    config: StatusbarConfig,
) -> list[WorkspaceInfo]:
    """Read workspace data from provider, read tmux statuses,
    aggregate, apply naming rules, return ready-to-render WorkspaceInfos."""
    ...

def main():
    config = load_config()
    provider = create_provider(config.workspaces_provider)
    bar = create_bar(config.bar)
    workspaces = build_workspaces(provider, config)
    bar.apply(workspaces)
```

## Configuration

All under `~/.config/agents-status/config.toml`:

```toml
[statusbar]
workspaces_provider = "hyprland"   # "hyprland" | "aerospace"
bar = "hyprland"                   # "hyprland" | "sketchybar"

[statusbar.features]
agent_status = true                # show agent status icons per workspace
monitor_status = true              # show monitor status icons
browser_icon = true                # show browser icon when browser present
slack_icon = true                  # show slack icon when slack present
jira_strip = true                  # strip JIRA ticket prefix from session names
prefix_dedup = true                # deduplicate common prefix across session names
active_keeps_number = true         # keep JIRA ticket number on active workspace

[statusbar.naming]
max_length = 20                    # max display name length before truncation
tmux_suffix = " - TMUX"           # suffix to identify tmux terminal windows

[statusbar.icons]
agent_inprogress = ""
agent_waiting = ""
agent_idle = "󰚩"
agent_done = ""
tmux = ""
browser = ""
slack = ""

[statusbar.sketchybar]
space_item_prefix = "space"        # items named space.1, space.2, etc.
```

If `[statusbar]` is omitted entirely, auto-detect from available CLIs (check `hyprctl` then `aerospace`/`sketchybar`). All `[statusbar.features]` default to `true`. All icons have built-in defaults (current Nerd Font glyphs).

## Error Handling

- **tmux not running:** return workspaces with empty agent status, no crash
- **Provider CLI missing:** fail fast with a clear message (e.g. "hyprctl not found")
- **Bar CLI missing:** fail fast with a clear message (e.g. "sketchybar not found, is it running?")
- **Mixed sessions:** multiple tmux terminals on one workspace use existing priority (WAITING > INPROGRESS > DONE > IDLE)
- **Viewer sessions:** tmux sessions ending in `-viewer` are displayed separately (lower priority than main sessions), matching current behavior
- **Pinned windows:** if the provider doesn't support pinned/sticky windows (e.g. AeroSpace), `get_pinned_classes()` returns an empty set
- **Malformed data:** log and skip, never crash (consistent with server.py pattern)

## Documentation

### statusbar/README.md (rewritten)

1. Overview — what statusbar does, the provider/bar split
2. Supported combinations — table of provider x bar
3. Configuration — full `[statusbar]` config reference
4. Adding a new provider — implement `WorkspacesProvider`, drop in `statusbar/<name>/workspaces.py`
5. Adding a new bar — implement `StatusBar`, drop in `statusbar/<name>/bar.py`

### Root README.md (updated)

- Packages table: "Desktop statusbar integration (Hyprland, sketchybar)"
- Statusbar section: link to `statusbar/README.md` config reference, mention both platforms

## Migration

The new entry point replaces the current Hyprland-specific post-event hook. In `config.toml`, the post-event command changes from:

```toml
"hyprctl dispatch exec $AGENTS_STATUS_DIR/../statusbar/hyprland/RenameWorkspaces.py"
```

to a unified script that auto-detects or reads config:

```toml
"$AGENTS_STATUS_DIR/../statusbar/run.py"
```

`statusbar/run.py` is the new top-level entry point that calls `main()`. It replaces `RenameWorkspaces.py` as the post-event hook target. The old `RenameWorkspaces.py` is removed after the refactor.

## Out of Scope

- Waybar, eww, AGS integrations (remain in `statusbar/TODO.md` for future)
- Configurable icons per-bar (all bars share the same icon config for now)
- The server (`core/server.py`) is unchanged — it still sets tmux window options, which is the stable interface statusbar reads from
