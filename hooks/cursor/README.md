# Cursor Hooks

Hook scripts for [Cursor CLI](https://cursor.com) agent integration.

| Hook Script | Trigger Event | Status Sent | Notification | Notes |
|---|---|---|---|---|
| hook-session-start | sessionStart | IDLE | -- | Also calls ensure_server |
| hook-session-end | sessionEnd | (clear) | -- | Clears all state for instance |
| hook-prompt-start | beforeSubmitPrompt | INPROGRESS | -- | |
| hook-finish | stop | DONE | Done | |
| hook-perm-req | beforeShellExecution | WAITING | Requires Permission | Deferred; dropped if auto-run fires |
| hook-after-shell | afterShellExecution | INPROGRESS | -- | Cancels deferred perm-req |
| hook-agent-activity | beforeReadFile, afterFileEdit | INPROGRESS | -- | Workaround: no plan-approved hook |
| hook-subagent-start | subagentStart | (subagent_delta +1) | -- | |
| hook-subagent-stop | subagentStop | (subagent_delta -1) | -- | Releases held DONE when count=0 |

These hooks are injected into `~/.cursor/hooks.json` by `install.sh hooks cursor`.
