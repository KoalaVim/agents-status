# agents-status

Aggregates real-time status from AI coding agents (Claude Code, Cursor CLI, Codex CLI) into a single server, then surfaces that status through tmux window colors, desktop notifications, and statusbar integrations.

## Packages

| Package | Description |
|---------|-------------|
| [`core/`](core/) | Status aggregation server (Unix datagram socket), shared helpers, notification dispatch |
| [`hooks/`](hooks/) | Per-tool hook scripts that report lifecycle events to the server |
| [`simple-wrappers/`](simple-wrappers/) | Shell wrappers that add IDLE-on-launch and clear-on-exit for tools missing those hooks |
| [`advanced-wrappers/cursor-agent/`](advanced-wrappers/cursor-agent/) | Rust PTY wrapper that detects Cursor's AskQuestion interactive prompts |
| [`tmux/`](tmux/) | TPM-compatible tmux plugin for status-colored window names |
| [`statusbar/`](statusbar/) | Hyprland virtual desktop renaming by agent status |

## Supported Tools

| Tool | Hooks | Simple Wrapper | Advanced Wrapper |
|------|-------|----------------|------------------|
| Claude Code | Session start/stop, prompt, finish, permission, tool-done | -- | -- |
| Cursor CLI | Session start/end, prompt, finish, permission, shell exec, file read/edit, subagents | IDLE on launch, clear on exit | PTY wrapper detecting AskQuestion prompts |
| Codex CLI | Prompt start, finish, permission, tool-done | IDLE on launch, clear on exit | -- |

## Install

Each module installs independently. The installer patches your tool configs in place (with backups).

```sh
# 1. Core server (required)
./install.sh core

# 2. Hooks (pick tools you use)
./install.sh hooks claude
./install.sh hooks cursor
./install.sh hooks codex
./install.sh hooks all        # all of the above

# 3. Simple wrappers (optional, per tool)
./install.sh wrapper codex
./install.sh wrapper cursor

# 4. Cursor PTY wrapper (optional)
./install.sh cursor-cli-wrapper
```

## Configuration

### Core server

`~/.config/agents-status/config.toml` (or `$AGENTS_STATUS_CONFIG`):

```toml
[notification]
# Default: "notify-send". Set to your preferred notification command.
# macOS: "terminal-notifier" or a wrapper around osascript
command = "notify-send"

[post-event]
# Commands to run after every state change (async, non-blocking).
commands = [
    "$AGENTS_STATUS_DIR/../tmux/scripts/refresh_dim_colors.sh",
    "hyprctl dispatch exec $AGENTS_STATUS_DIR/../statusbar/hyprland/RenameWorkspaces.py",
]
```

### Cursor CLI wrapper

`~/.config/cursor-cli-wrapper/config.toml` -- see [`advanced-wrappers/cursor-agent/config.toml.example`](advanced-wrappers/cursor-agent/config.toml.example).

## Tmux Integration

Install as a TPM plugin or source directly:

```tmux
# TPM
set -g @plugin 'user/agents-status'

# Manual
run-shell ~/agents-status/tmux/agents-status.tmux
```

See [`tmux/README.md`](tmux/README.md) for configuration options.

## Statusbar

Wire the Hyprland integration as a post-event hook in your core config. See [`statusbar/README.md`](statusbar/README.md).

## How It Works

See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for architecture diagrams, event flow, and server internals.
