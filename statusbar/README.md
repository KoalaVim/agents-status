# statusbar

Desktop statusbar integrations that display agent status.

## Hyprland

`hyprland/RenameWorkspaces.py` renames Hyprland virtual desktops based on tmux session agent statuses. It reads `@ai-agent-status` from tmux windows, aggregates per-session, and uses `hyprctl` to rename virtual desktops with status icons.

### Requirements

- **Plugin:** [virtual-desktops](https://github.com/levnikmyskin/hyprland-virtual-desktops)
- **Dependencies:** python3, hyprctl, tmux, jq
- **Font:** A [Nerd Font](https://www.nerdfonts.com/) for status icons

### Usage

#### As a post-event hook

Add to agents-status core config:

```toml
[post-event]
commands = [
    "hyprctl dispatch exec $AGENTS_STATUS_DIR/../statusbar/hyprland/RenameWorkspaces.py",
]
```

#### Standalone

```sh
./statusbar/hyprland/RenameWorkspaces.py --debug
```
