# cursor-cli-wrapper

Rust PTY wrapper around Cursor's CLI agent that detects interactive prompts.

## What

Wraps `cursor-agent` in a PTY, intercepts output to detect Cursor's AskQuestion prompt (the `↑/↓ option · ←/→ question` bar).

## Why

Cursor has no hook for when it asks the user a question. This wrapper detects it by scanning PTY output for the prompt marker.

## Hooks

| Hook | Description |
|---|---|
| `on-question` | Command to run when a question prompt appears |
| `on-question-submit` | Command to run when the user presses Enter to answer |
| `on-question-cooldown-ms` | Minimum milliseconds between `on-question` firings (default: 500) |

## Config

`~/.config/cursor-cli-wrapper/config.toml`:

```toml
[hooks]
on-question = "notify-send 'Cursor' 'Question waiting'"
on-question-submit = "notify-send 'Cursor' 'Question submitted'"
on-question-cooldown-ms = 500
```

## Build

```sh
cargo build --release
```

Binary at `target/release/cursor-cli-wrapper`.

## Install

```sh
./install.sh cursor-cli-wrapper
```

Builds and copies the binary to `~/.local/bin/`.

## Integration

Set `CURSOR_CLI_WRAPPER_BIN=cursor-cli-wrapper` so `simple-wrappers/cursor-agent` uses it instead of the raw `cursor-agent` binary.
