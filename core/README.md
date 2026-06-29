# agents-status core

Status aggregation server and shared helpers.

## Server

Listens on a Unix datagram socket at `/tmp/agent-status-$UID.sock`. Hook scripts send JSON events; the server applies state side-effects and dispatches notifications.

### Event shape

```json
{
  "agent": "claude | cursor | codex",
  "instance_id": "tmux:<session>:<window_id> | tty:<tty>",
  "status": "IDLE | INPROGRESS | WAITING | DONE",
  "notify": "Done | Requires Permission | ...",
  "clear": true,
  "unset_status": true,
  "subagent_delta": 1
}
```

All fields except `agent` and `instance_id` are optional.

### Side effects

- Sets tmux window-local options (`@ai-agent-status`, `@ai-agent`, `@window_color`)
- Sends desktop notifications (via `notify-send` or configured command)
- Runs post-event hook commands

### Server features

- **Debounced notifications** — 1.5 s window; a superseding event cancels the pending notification
- **Deferred events** — 30 s hold (for auto-run suppression); dropped if a non-deferred event arrives first
- **Subagent tracking** — holds DONE until all subagents finish (5 min safety timeout)

## Files

| File | Purpose |
|---|---|
| `server.py` | The server |
| `helpers.sh` | Sourced by hook scripts — `send_event`, `get_instance_id`, `ensure_server` |
| `send` | Sends a JSON event to the socket |
| `ensure-running` | Starts the server if not already running |
| `restart` | Kills and restarts the server |
| `focus` | Switches to a tmux window + Hyprland focus |

## Configuration

`~/.config/agents-status/config.toml` (or `$AGENTS_STATUS_CONFIG`):

```toml
[notification]
command = "notify-send"

[post-event]
commands = [
    "$AGENTS_STATUS_DIR/../tmux/scripts/refresh_dim_colors.sh",
]
```
