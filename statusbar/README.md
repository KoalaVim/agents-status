# statusbar

Desktop statusbar integrations that display AI agent status on virtual desktop / workspace names.

The package follows a **provider + bar** split:

- **WorkspacesProvider** — queries the window manager for workspace and window information (Hyprland, AeroSpace)
- **StatusBar** — applies computed workspace names to the bar (Hyprland virtual desktops, sketchybar)

The shared pipeline in `common/` reads tmux agent status, processes window titles, and produces a list of `WorkspaceInfo` objects that any bar backend can render.

## Supported Combinations

| WorkspacesProvider | Bar | Platform |
|--------------------|-----|----------|
| `hyprland` | `hyprland` | Linux (Hyprland compositor) |
| `aerospace` | `sketchybar` | macOS (AeroSpace + sketchybar) |

Auto-detection selects the right combination based on available commands (`hyprctl`, `aerospace`, `sketchybar`).

## Usage

### As a post-event hook (recommended)

Add to `~/.config/agents-status/config.toml`:

```toml
[post-event]
commands = [
    "$AGENTS_STATUS_DIR/../statusbar/run.py",
]
```

This runs after every agent status change, keeping workspace names in sync.

### Standalone

```sh
./statusbar/run.py --debug
```

## Configuration

All statusbar configuration lives under `[statusbar]` in `~/.config/agents-status/config.toml`.

### Provider and bar selection

```toml
[statusbar]
workspaces_provider = "hyprland"   # "hyprland" | "aerospace" (auto-detected if omitted)
bar = "hyprland"                   # "hyprland" | "sketchybar" (auto-detected if omitted)
```

### Feature toggles

```toml
[statusbar.features]
agent_status = true           # Show agent status icons on workspaces
monitor_status = true         # Show monitor activity icon
browser_icon = true           # Replace browser window titles with a globe icon
slack_icon = true             # Replace Slack window titles with the Slack icon
jira_strip = true             # Strip JIRA project keys from window titles
prefix_dedup = true           # Remove shared prefixes across windows in a workspace
active_keeps_number = true    # Active workspace keeps its numeric ID in the name
```

### Naming

```toml
[statusbar.naming]
max_length = 20               # Max display name length (truncated with "…")
tmux_suffix = " - TMUX"       # Suffix stripped from tmux session names
```

### Icons

All icons can be overridden (Nerd Font glyphs by default):

```toml
[statusbar.icons]
agent_inprogress = ""        # Agent running
agent_waiting = ""            # Agent waiting for input
agent_idle = "󰚩"              # Agent idle
agent_done = ""              # Agent finished
monitor_inprogress = "󰙖"      # Monitor active
tmux = ""                    # tmux session
browser = ""                # Browser window
slack = ""                   # Slack window
```

### sketchybar-specific

```toml
[statusbar.sketchybar]
space_item_prefix = "space"                                        # Prefix for sketchybar space item names
label_template = "{id} {agent_icon} {tmux_sessions} [{window_count}]"  # Workspace label template
```

#### Template variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{id}` | aerospace.sh | Workspace number |
| `{agent_icon}` | agents-status | Agent status icon (from tmux) |
| `{tmux_sessions}` | agents-status | Tmux session names joined with `\|` |
| `{app_icons}` | agents-status | Browser/Slack icons |
| `{agent_label}` | agents-status | Full computed display name |
| `{window_count}` | aerospace.sh | Live window count from aerospace |

## Requirements

### Linux (Hyprland)

- [hyprland-virtual-desktops](https://github.com/levnikmyskin/hyprland-virtual-desktops) plugin
- `hyprctl`, `jq`, `tmux`, `python3`
- A [Nerd Font](https://www.nerdfonts.com/) for status icons

### macOS (AeroSpace + sketchybar)

- [AeroSpace](https://github.com/nikitabobko/AeroSpace) window manager
- [sketchybar](https://github.com/FelixKratz/SketchyBar)
- `tmux`, `python3`
- A [Nerd Font](https://www.nerdfonts.com/) for status icons

## Adding a New Provider

1. Create `statusbar/<provider>/workspaces.py` with a class implementing `WorkspacesProvider`:

```python
class MyProvider:
    def get_workspaces(self) -> list[WorkspaceData]: ...
    def get_pinned_classes(self) -> set[str]: ...
```

2. Register it in `run.py`'s `_create_provider()` function.
3. Export from `statusbar/<provider>/__init__.py`.

## Adding a New Bar

1. Create `statusbar/<bar>/bar.py` with a class implementing `StatusBar`:

```python
class MyBar:
    def apply(self, workspaces: list[WorkspaceInfo]) -> None: ...
```

2. Register it in `run.py`'s `_create_bar()` function.
3. Export from `statusbar/<bar>/__init__.py`.
