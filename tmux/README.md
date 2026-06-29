# agents-status tmux plugin

Shows AI agent status icons in tmux window labels.

## Install

### Via TPM

```tmux
set -g @plugin 'user/agents-status'
```

Then `prefix + I` to install.

### Manual

```tmux
run-shell ~/agents-status/tmux/agents-status.tmux
```

## Window options (set by the server)

| Option | Values | Description |
|--------|--------|-------------|
| `@ai-agent-status` | `WAITING` \| `INPROGRESS` \| `DONE` \| `IDLE` | Current agent state |
| `@ai-agent` | `claude` \| `cursor` \| `codex` | Which agent owns the window |
| `@window_color` | Hex color (e.g. `#fa7900`) | Window accent color |
| `@window_color_dim` | Hex color (auto-computed) | Dimmed variant (58% brightness) |

## Status color mapping

| Status | Color | Icon |
|--------|-------|------|
| WAITING | `#cf1313` | W |
| INPROGRESS | `#fa7900` | ● |
| DONE | `#1e88ff` | ✓ |
| IDLE | `#15c70c` | ○ |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `@agents-status-auto-format` | `off` | When `on`, prepends status icon to `window-status-format` automatically |

Set before loading the plugin:

```tmux
set -g @agents-status-auto-format on
```

## Custom format

Use the icon command directly in your format string:

```tmux
set -g window-status-format "#(~/.tmux/plugins/agents-status/tmux/scripts/status-icon.sh #{window_id}) #I:#W"
```
