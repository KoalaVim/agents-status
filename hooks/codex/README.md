# Codex CLI Hooks

Hook scripts for [Codex CLI](https://github.com/openai/codex) integration.

| Hook Script | Trigger Event | Status Sent | Notification | Notes |
|---|---|---|---|---|
| hook-prompt-start | UserPromptSubmit | INPROGRESS | -- | |
| hook-finish | Stop | DONE | Done | |
| hook-perm-req | PermissionRequest | (disabled) | -- | `exit 0` at top; reserved for future use |
| hook-tool-done | PostToolUse | INPROGRESS | -- | |

These hooks are injected into `~/.codex/hooks.json` by `install.sh hooks codex`. Codex has no SessionStart/SessionEnd hooks — use the simple wrapper (`simple-wrappers/codex`) for idle/clear lifecycle.
