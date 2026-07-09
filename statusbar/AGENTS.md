# statusbar — Agent Guide

Entry point for agents modifying the statusbar package. For user-facing docs, config reference, and file structure see `README.md`.

## What This Package Does

Surfaces AI agent status onto desktop statusbar workspace indicators. Runs as a post-event hook — fast, stateless, no daemon.

## Design Principles

- **Multi-platform.** Must support multiple window managers (providers) and multiple statusbars (bars). Every feature that works on one platform should work on all, or be cleanly togglable.
- **Provider + Bar separation.** Providers fetch workspace/window data. Bars render it. Shared logic lives in `common/`. Providers and bars never import each other. `common/` never imports a specific provider or bar.
- **Configuration over code.** Every visual behavior (icons, colors, naming rules) should be configurable via `[statusbar]` in `config.toml`. Defaults should be sensible. Auto-detection fills in provider/bar when not explicitly set, but never overrides explicit config.
- **Zero dependencies.** Plain Python 3 stdlib only. `tomllib` with `tomli` fallback. No pip installs.
- **Fast and stateless.** Invoked on every agent status change via post-event hook. Must complete in under a second. No persistent state beyond the sentinel file.

## Key Rules

- The sentinel file (`/tmp/agent-status-bg-$UID`) is the IPC boundary between this package and external bar plugins (e.g. `aerospace.sh` in dotfiles). Changes to its format are cross-repo breaking changes.
- Feature parity matters: when adding a visual feature (e.g. background colors), implement it for all supported bars or make it cleanly degrade.
- Each new feature should be behind a toggle in `[statusbar.features]` or the bar-specific config section.

## Adding a New Platform

- New provider: create `statusbar/<provider>/workspaces.py` implementing the `WorkspacesProvider` protocol.
- New bar: create `statusbar/<bar>/bar.py` implementing the `StatusBar` protocol.
- Register in `run.py`, document in `README.md`.
- See `README.md` for the full checklist.

## Verification

- Test with `PYTHONPATH=. python3 statusbar/run.py --debug` from the repo root.
- After bar changes: trigger with `core/send` and visually confirm updates.
- Cross-repo changes (sentinel format): test both `bar.py` AND the external plugin script.

## Related Docs

- User-facing docs and config reference: `README.md`
- Future work: `TODO.md`
- System-wide architecture: `SYSTEM_DESIGN.md`
