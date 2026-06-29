# Simple Wrappers

Shell wrappers that add IDLE-on-launch and clear-on-exit lifecycle.

## Wrappers

### `codex`

Wraps the real `codex` binary. Sends IDLE on launch, clears status on exit. Needed because Codex has no SessionEnd hook — without this, the pane's status would stick at DONE after the session ends.

### `cursor-agent`

Wraps `cursor-cli-wrapper` (or the real `cursor-agent`). Sends IDLE on launch. Uses the `CURSOR_CLI_WRAPPER_BIN` env var to locate the binary (defaults to `cursor-cli-wrapper`).

## PATH ordering

These wrappers must appear on PATH before the real binaries. The installer symlinks them into `~/.local/bin/`.

## Server startup

Both call `ensure_server` on startup so the server is guaranteed running before the first hook fires.
