# Claude Code Hooks

Hook scripts for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) integration.

| Hook Script | Trigger Event | Status Sent | Notification | Notes |
|---|---|---|---|---|
| hook-session-start | SessionStart | IDLE | -- | Also calls ensure_server |
| hook-session-stop | SessionEnd | (clear) | -- | Clears all state for instance |
| hook-prompt-start | UserPromptSubmit | INPROGRESS | -- | |
| hook-finish | Stop | DONE | Done | |
| hook-perm-req | PermissionRequest | WAITING | Requires Permission | |
| hook-tool-done | PostToolUse / PostToolUseFailure | INPROGRESS | -- | |

These hooks are injected into `~/.claude/settings.json` by `install.sh hooks claude`.
