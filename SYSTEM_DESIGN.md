# agents-status System Design

## Architecture Overview

```mermaid
graph TB
    subgraph aiTools["AI Tools"]
        cursor["Cursor CLI"]
        claude["Claude Code"]
        codex["Codex CLI"]
    end

    subgraph packages["Packages"]
        hooks["hooks/\n(per-tool hook scripts)"]
        simpleWrappers["simple-wrappers/\n(shell wrappers)"]
        advancedWrappers["advanced-wrappers/cursor-agent/\n(Rust PTY wrapper)"]
        core["core/\n(status server)"]
        tmuxPlugin["tmux/\n(tmux plugin)"]
        statusbar["statusbar/\n(desktop statusbar integration)"]
    end

    subgraph sideEffects["Side Effects"]
        tmuxOpts["tmux window options"]
        notifications["Desktop notifications"]
        postHooks["Post-event hooks"]
    end

    subgraph display["Display Layers"]
        tmuxBar["tmux status bar\n(colored window names)"]
        desktopBar["Desktop statusbar\n(virtual desktop names)"]
        notifPopup["Notification popups"]
    end

    cursor -->|"triggers"| hooks
    claude -->|"triggers"| hooks
    codex -->|"wrapped by"| simpleWrappers
    cursor -->|"wrapped by"| advancedWrappers

    simpleWrappers -->|"triggers"| hooks
    advancedWrappers -->|"triggers"| hooks

    hooks -->|"sources helpers.sh,\nsends JSON via\nUnix datagram socket"| core

    core --> tmuxOpts
    core --> notifications
    core --> postHooks

    tmuxOpts --> tmuxPlugin
    tmuxPlugin --> tmuxBar
    tmuxBar --> statusbar
    statusbar --> desktopBar
    notifications --> notifPopup
```

## Event Flow

```mermaid
sequenceDiagram
    participant Tool as AI Tool
    participant Hook as Hook Script
    participant Helpers as helpers.sh
    participant Send as send
    participant Server as server.py
    participant Tmux as tmux
    participant Notif as Notification Cmd
    participant PostHook as Post-Event Hooks

    Tool->>Hook: Triggers hook (e.g. beforeSubmitPrompt)
    Hook->>Helpers: source helpers.sh
    Helpers->>Helpers: Build JSON event
    Note right of Helpers: instance_id, agent,<br/>status, repo, branch,<br/>tmux session/window

    Helpers->>Send: Pass JSON payload
    Send->>Server: Transmit via Unix datagram socket

    Server->>Server: Process event
    Note right of Server: Debounce (1.5s)<br/>Defer check (30s)<br/>Subagent tracking

    Server->>Tmux: Set window options
    Note right of Tmux: @ai-agent-status<br/>@window_color

    Server->>Notif: Send notification (configurable cmd)
    Server->>PostHook: Run post-event hooks (configurable cmds)
```

## Server Internals

### Processing Pipeline

```mermaid
flowchart TD
    receive["Receive JSON event\nvia datagram socket"] --> parse["Parse event fields:\ninstance_id, status,\ndefer, subagent_delta"]

    parse --> checkDefer{defer:true?}

    checkDefer -->|Yes| storeDefer["Hold event for 30s\n(deferred timer)"]
    storeDefer --> deferWait["Wait for non-defer\nevent on same instance"]
    deferWait -->|"Non-defer arrives"| dropDefer["Drop deferred event\n(auto-run suppression)"]
    deferWait -->|"30s elapsed, no cancel"| processEvent

    checkDefer -->|No| cancelDefer["Cancel any pending\ndeferred event for instance"]
    cancelDefer --> checkSubagent

    checkSubagent{subagent_delta\npresent?}
    checkSubagent -->|Yes| adjustCounter["Adjust per-instance\nsubagent counter (+1/-1)"]
    adjustCounter --> checkHeldDone{Held DONE exists\nand counter == 0?}
    checkHeldDone -->|Yes| releaseDone["Release held DONE event"]
    releaseDone --> processEvent
    checkHeldDone -->|No| done["Done"]

    checkSubagent -->|No| checkDone{status == DONE\nand counter > 0?}
    checkDone -->|Yes| holdDone["Hold DONE event\n+ start 5min safety timer"]
    holdDone --> safetyTimeout["On timeout: fire notification\nwith timeout annotation"]
    checkDone -->|No| processEvent

    processEvent["Apply state:\n1. Set tmux window options\n2. Schedule notification (debounced)\n3. Run post-event hooks"]

    processEvent --> debounce["Debounce notification\nper-instance (1.5s)"]
    debounce -->|"New event within 1.5s"| cancelNotif["Cancel pending notification"]
    debounce -->|"1.5s elapsed"| fireNotif["Fire notification"]
```

### Debouncing

Notifications are debounced per-instance with a 1.5-second window. Each new event for a given `instance_id` cancels any pending notification timer and starts a new one. This prevents notification spam during rapid state transitions (e.g. multiple file edits in quick succession).

### Deferred Events

Events marked `defer:true` are held for 30 seconds. If any non-deferred event arrives for the same instance during that window, the deferred event is silently dropped. This handles Cursor's `beforeShellExecution` hook, which fires for both real permission prompts (user must act) and auto-approved commands (no user action needed). By deferring, we only notify when the prompt genuinely requires attention.

### Subagent Tracking

The `subagent_delta` field (+1 or -1) adjusts a per-instance counter tracking active background subagents. When a DONE event arrives while the counter is above zero, the event is held rather than processed -- this prevents premature "Done" notifications while subagents are still running. The held DONE is released once the counter drops to zero. A 5-minute safety timeout ensures held events are eventually fired even if a subagent stop event is lost.

## Per-Tool Lifecycle

### Cursor CLI

```mermaid
flowchart LR
    sessionStart["sessionStart"] --> idle["IDLE"]
    idle --> beforeSubmit["beforeSubmitPrompt"]
    beforeSubmit --> inprog1["INPROGRESS"]

    inprog1 --> shellPath["beforeShellExecution"]
    shellPath --> waiting["WAITING\n(deferred)"]
    waiting --> afterShell["afterShellExecution"]
    afterShell --> inprog2["INPROGRESS\n(cancels defer)"]
    inprog2 --> inprog1

    inprog1 --> filePath["beforeReadFile /\nafterFileEdit"]
    filePath --> inprog3["INPROGRESS"]
    inprog3 --> inprog1

    inprog1 --> subStart["subagentStart\n(delta +1)"]
    subStart --> inprog1
    inprog1 --> subStop["subagentStop\n(delta -1)"]
    subStop --> inprog1

    inprog1 --> stop["stop"]
    stop --> doneState["DONE"]
    doneState --> sessionEnd["sessionEnd"]
    sessionEnd --> clear["clear"]
```

### Claude Code

```mermaid
flowchart LR
    ccSessionStart["SessionStart"] --> ccIdle["IDLE"]
    ccIdle --> userPrompt["UserPromptSubmit"]
    userPrompt --> ccInprog["INPROGRESS"]

    ccInprog --> postTool["PostToolUse"]
    postTool --> ccInprog2["INPROGRESS"]
    ccInprog2 --> ccInprog

    ccInprog --> permReq["PermissionRequest"]
    permReq --> ccWaiting["WAITING"]
    ccWaiting --> ccInprog

    ccInprog --> ccStop["Stop"]
    ccStop --> ccDone["DONE"]
    ccDone --> ccSessionEnd["SessionEnd"]
    ccSessionEnd --> ccClear["clear"]
```

### Codex CLI (with simple wrapper)

```mermaid
flowchart LR
    wrapperStart["wrapper start"] --> cxIdle["IDLE"]
    cxIdle --> cxPrompt["UserPromptSubmit"]
    cxPrompt --> cxInprog["INPROGRESS"]

    cxInprog --> cxPostTool["PostToolUse"]
    cxPostTool --> cxInprog2["INPROGRESS"]
    cxInprog2 --> cxInprog

    cxInprog --> cxStop["Stop"]
    cxStop --> cxDone["DONE"]
    cxDone --> wrapperExit["wrapper exit"]
    wrapperExit --> cxClear["clear"]
```

## Display Chain

```mermaid
flowchart LR
    subgraph server["core/server.py"]
        setOpts["Set tmux window options:\n@ai-agent-status\n@window_color"]
        sendNotif["Send notification\n(configurable command)"]
    end

    subgraph tmuxLayer["tmux/plugin"]
        readOpts["Read @ai-agent-status\nand @window_color"]
        renderWindow["Render colored\nwindow names"]
    end

    subgraph desktopLayer["statusbar/"]
        readTmux["Read tmux session\nwindow states"]
        aggregate["Aggregate statuses\nacross windows"]
        renameDesktop["Rename virtual desktops\nwith status icons"]
    end

    subgraph notifLayer["Notifications"]
        notifPopup["Desktop notification\npopup"]
    end

    setOpts --> readOpts
    readOpts --> renderWindow
    renderWindow --> readTmux
    readTmux --> aggregate
    aggregate --> renameDesktop

    sendNotif --> notifPopup
```

The display chain has two independent paths:

- **tmux path**: `server.py` sets per-window tmux user options. The tmux plugin reads these options during status bar rendering, applying color and label formatting to window names. The statusbar package then reads tmux session state, aggregates the statuses of all windows, and renames Hyprland virtual desktops accordingly.
- **notification path**: `server.py` fires a configurable notification command directly, producing desktop notification popups independent of the tmux display pipeline.

## Instance Identity

Each concurrent agent session is identified by a unique `instance_id`, constructed using a priority-based scheme:

| Priority | Format | When Used |
|----------|--------|-----------|
| 1 (highest) | `tmux:SESSION:WINDOW_ID` | Inside a tmux session |
| 2 | `tty:/dev/pts/N` | Terminal without tmux |
| 3 (fallback) | `pid:PPID` | No tmux, no TTY |

```mermaid
flowchart TD
    start["Determine instance_id"] --> checkTmux{Inside tmux?}
    checkTmux -->|Yes| tmuxId["tmux:SESSION:WINDOW_ID"]
    checkTmux -->|No| checkTty{TTY available?}
    checkTty -->|Yes| ttyId["tty:/dev/pts/N"]
    checkTty -->|No| pidId["pid:PPID"]
```

The tmux-based identity is preferred because it maps directly to the visual unit the user sees -- a tmux window. This ensures multiple concurrent agent sessions running in different tmux windows each track their status independently, with state correctly bound to the right window for both color rendering and notification context.
