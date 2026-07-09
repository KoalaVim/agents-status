# Agent Map

Entry point for coding agents working in this repo.

## Start Here

- User-facing usage: `README.md`
- System design and diagrams: `SYSTEM_DESIGN.md`
- Per-package docs: `core/README.md`, `hooks/*/README.md`, `simple-wrappers/README.md`, `advanced-wrappers/cursor-agent/README.md`, `tmux/README.md`, `statusbar/README.md`
- Future work: `statusbar/TODO.md`

## What This Repo Is

A monorepo that aggregates real-time status from AI coding agents (Claude Code, Cursor CLI, Codex CLI) into a central server, then surfaces that status through tmux window colors, desktop notifications, and Hyprland statusbar integrations.

## Repo Layout

```
core/              Python server + shell helpers (the heart)
hooks/             Per-tool hook scripts (claude/, cursor/, codex/)
simple-wrappers/   Shell wrappers for idle/stop lifecycle
advanced-wrappers/ Rust PTY wrapper for Cursor AskQuestion detection
tmux/              TPM-compatible tmux plugin
statusbar/         Desktop statusbar integrations (Hyprland, sketchybar)
install.sh         Modular installer
```

## Working Rules

- The server (`core/server.py`) is plain Python 3 with zero required dependencies. Keep it that way. `tomllib` (3.11+) is used with a fallback; do not add pip dependencies.
- Hook scripts are POSIX sh. They must be fast and non-blocking (background subshell pattern). Do not add bash-isms to hooks.
- `helpers.sh` is the shared library sourced by all hooks and wrappers. Changes here affect every tool integration.
- `install.sh` is bash (needs `python3 -c` for JSON merging). It must be idempotent and always back up before patching config files.
- The advanced wrapper (`advanced-wrappers/cursor-agent/`) is Rust. It has its own `Cargo.toml` and builds independently.
- Every script self-resolves `core/` from its own filesystem location (relative to `$0`). No env vars needed. Never hard-code absolute paths.
- The server communicates via Unix datagram socket at `/tmp/agent-status-$UID.sock`. This is the only IPC boundary.

## Key Invariants

- Hooks must never block the AI tool. Always run in a background subshell: `( ... ) </dev/null >/dev/null 2>&1 &`
- The server must handle malformed JSON gracefully (log and continue, never crash).
- Notification debouncing (1.5s) and deferred events (30s) are correctness features, not optimizations. Do not remove them without understanding the auto-run suppression flow in `SYSTEM_DESIGN.md`.
- Subagent tracking (held DONE) prevents premature notifications. The 5-minute safety timeout is a last resort, not the happy path.

## Adding a New Tool

1. Create `hooks/<tool>/` with hook scripts following the existing pattern (resolve `core/` from `$0`, source `helpers.sh`, call `send_event`).
2. Add a `hooks/<tool>/README.md` with the hook responsibility table.
3. Add a `hooks_<tool>()` function in `install.sh` matching the tool's hook config format.
4. Update the dispatcher in `cmd_hooks()`.
5. If the tool lacks session start/end hooks, add a simple wrapper in `simple-wrappers/`.
6. Update `README.md` tables.

## Common Commands

```sh
# Start/restart server manually
core/restart

# Send a test event
core/send '{"agent":"test","instance_id":"test:1","status":"IDLE"}'

# Install hooks for a specific tool
./install.sh hooks cursor

# Build cursor-cli-wrapper
cd advanced-wrappers/cursor-agent && cargo build --release
```

## Verification

- After changing `server.py`: restart with `core/restart`, send test events with `core/send`, verify tmux options are set.
- After changing hooks: test by running the actual AI tool and checking status transitions.
- After changing `install.sh`: test with a dry run on a fresh config (backup and restore).
- After changing `helpers.sh`: test that all three tool integrations still work (changes here are cross-cutting).

## Files Not to Commit

- `personal.md` is gitignored -- it documents dotfiles migration leftovers for the author.
- `advanced-wrappers/cursor-agent/target/` is gitignored (Rust build output).
