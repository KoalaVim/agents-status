#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_STATUS_DIR="$REPO_DIR/core"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${GREEN}[✓]${NC} %s\n" "$*"; }
warn()    { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()     { printf "${RED}[✗]${NC} %s\n" "$*" >&2; }
heading() { printf "\n${BOLD}%s${NC}\n" "$*"; }

# ─────────────────────────────────────────────
#  core
# ─────────────────────────────────────────────
cmd_core() {
    heading "Installing agents-status core"

    if ! command -v python3 &>/dev/null; then
        err "python3 is required but not found on PATH"
        exit 1
    fi
    info "python3 found: $(command -v python3)"

    mkdir -p "$HOME/.config/agents-status"
    info "Created ~/.config/agents-status/"

    if [ ! -f "$HOME/.config/agents-status/config.toml" ]; then
        cp "$REPO_DIR/core/config.example.toml" "$HOME/.config/agents-status/config.toml"
        info "Copied default config to ~/.config/agents-status/config.toml"
    else
        warn "~/.config/agents-status/config.toml already exists — skipping"
    fi

    info "Core installation complete"
}

# ─────────────────────────────────────────────
#  hooks helpers
# ─────────────────────────────────────────────

merge_json_hooks() {
    local target_file="$1"
    local new_hooks_json="$2"
    local hook_format="$3"  # "claude", "cursor", or "codex"

    local dir
    dir="$(dirname "$target_file")"
    mkdir -p "$dir"

    if [ ! -f "$target_file" ]; then
        echo '{}' > "$target_file"
        info "Created $target_file"
    fi

    cp "$target_file" "${target_file}.bak"
    info "Backed up to ${target_file}.bak"

    python3 -c "
import json, sys

target_path = sys.argv[1]
new_hooks_raw = sys.argv[2]
hook_format = sys.argv[3]

with open(target_path) as f:
    data = json.load(f)

new_hooks = json.loads(new_hooks_raw)

if hook_format == 'cursor':
    if 'version' not in data:
        data['version'] = 1
    existing = data.setdefault('hooks', {})
    for event_type, new_entries in new_hooks.items():
        if event_type not in existing:
            existing[event_type] = new_entries
        else:
            existing_cmds = {e.get('command') for e in existing[event_type]}
            for entry in new_entries:
                if entry.get('command') not in existing_cmds:
                    existing[event_type].append(entry)

elif hook_format in ('claude', 'codex'):
    existing = data.setdefault('hooks', {})

    for event_type, new_entries in new_hooks.items():
        if event_type not in existing:
            existing[event_type] = new_entries
        else:
            existing_cmds = set()
            for group in existing[event_type]:
                for h in group.get('hooks', []):
                    existing_cmds.add(h.get('command'))
            for group in new_entries:
                for h in group.get('hooks', []):
                    if h.get('command') not in existing_cmds:
                        existing[event_type].append(group)
                        break

with open(target_path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$target_file" "$new_hooks_json" "$hook_format"

    info "Merged hooks into $target_file"
}

# ─────────────────────────────────────────────
#  hooks claude
# ─────────────────────────────────────────────
hooks_claude() {
    heading "Installing Claude hooks"
    local hdir="$REPO_DIR/hooks/claude"
    local hooks_json
    hooks_json=$(cat <<EOF
{
  "SessionStart": [{"hooks": [{"type": "command", "command": "$hdir/hook-session-start"}]}],
  "SessionEnd": [{"hooks": [{"type": "command", "command": "$hdir/hook-session-stop"}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "$hdir/hook-prompt-start"}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "$hdir/hook-finish"}]}],
  "PermissionRequest": [{"hooks": [{"type": "command", "command": "$hdir/hook-perm-req"}]}],
  "PostToolUse": [{"hooks": [{"type": "command", "command": "$hdir/hook-tool-done"}]}],
  "PostToolUseFailure": [{"hooks": [{"type": "command", "command": "$hdir/hook-tool-done"}]}]
}
EOF
)
    merge_json_hooks "$HOME/.claude/settings.json" "$hooks_json" "claude"
    info "Claude hooks installed"
}

# ─────────────────────────────────────────────
#  hooks cursor
# ─────────────────────────────────────────────
hooks_cursor() {
    heading "Installing Cursor hooks"
    local hdir="$REPO_DIR/hooks/cursor"
    local hooks_json
    hooks_json=$(cat <<EOF
{
  "sessionStart": [{"command": "$hdir/hook-session-start"}],
  "sessionEnd": [{"command": "$hdir/hook-session-end"}],
  "beforeSubmitPrompt": [{"command": "$hdir/hook-prompt-start"}],
  "stop": [{"command": "$hdir/hook-finish"}],
  "beforeShellExecution": [{"command": "$hdir/hook-perm-req"}],
  "afterShellExecution": [{"command": "$hdir/hook-after-shell"}],
  "beforeReadFile": [{"command": "$hdir/hook-agent-activity"}],
  "afterFileEdit": [{"command": "$hdir/hook-agent-activity"}],
  "subagentStart": [{"command": "$hdir/hook-subagent-start"}],
  "subagentStop": [{"command": "$hdir/hook-subagent-stop"}]
}
EOF
)
    merge_json_hooks "$HOME/.cursor/hooks.json" "$hooks_json" "cursor"
    info "Cursor hooks installed"
}

# ─────────────────────────────────────────────
#  hooks codex
# ─────────────────────────────────────────────
hooks_codex() {
    heading "Installing Codex hooks"
    local hdir="$REPO_DIR/hooks/codex"
    local hooks_json
    hooks_json=$(cat <<EOF
{
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "$hdir/hook-prompt-start"}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "$hdir/hook-finish"}]}],
  "PermissionRequest": [{"hooks": [{"type": "command", "command": "$hdir/hook-perm-req"}]}],
  "PostToolUse": [{"hooks": [{"type": "command", "command": "$hdir/hook-tool-done"}]}]
}
EOF
)
    merge_json_hooks "$HOME/.codex/hooks.json" "$hooks_json" "codex"
    info "Codex hooks installed"
}

# ─────────────────────────────────────────────
#  hooks (dispatcher)
# ─────────────────────────────────────────────
cmd_hooks() {
    local target="${1:-}"
    case "$target" in
        claude) hooks_claude ;;
        cursor) hooks_cursor ;;
        codex)  hooks_codex ;;
        all)
            hooks_claude
            hooks_cursor
            hooks_codex
            ;;
        *)
            err "Usage: $0 hooks claude|cursor|codex|all"
            exit 1
            ;;
    esac
}

# ─────────────────────────────────────────────
#  wrapper
# ─────────────────────────────────────────────
ensure_local_bin() {
    mkdir -p "$HOME/.local/bin"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        warn "$HOME/.local/bin is not on your PATH"
        warn "Add to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

cmd_wrapper() {
    local target="${1:-}"
    case "$target" in
        codex)
            heading "Installing codex wrapper"
            ensure_local_bin
            ln -sf "$REPO_DIR/simple-wrappers/codex" "$HOME/.local/bin/codex"
            info "Symlinked simple-wrappers/codex -> ~/.local/bin/codex"
            ;;
        cursor)
            heading "Installing cursor-agent wrapper"
            ensure_local_bin
            ln -sf "$REPO_DIR/simple-wrappers/cursor-agent" "$HOME/.local/bin/cursor-agent"
            info "Symlinked simple-wrappers/cursor-agent -> ~/.local/bin/cursor-agent"
            ;;
        *)
            err "Usage: $0 wrapper codex|cursor"
            exit 1
            ;;
    esac
}

# ─────────────────────────────────────────────
#  cursor-cli-wrapper (advanced, Rust)
# ─────────────────────────────────────────────
cmd_cursor_cli_wrapper() {
    heading "Building cursor-cli-wrapper (Rust)"

    if ! command -v cargo &>/dev/null; then
        err "cargo is required but not found on PATH"
        exit 1
    fi
    info "cargo found: $(command -v cargo)"

    local project_dir="$REPO_DIR/advanced-wrappers/cursor-agent"
    (cd "$project_dir" && cargo build --release)
    info "Build complete"

    ensure_local_bin
    cp "$project_dir/target/release/cursor-cli-wrapper" "$HOME/.local/bin/cursor-cli-wrapper"
    info "Copied binary to ~/.local/bin/cursor-cli-wrapper"

    mkdir -p "$HOME/.config/cursor-cli-wrapper"
    if [ ! -f "$HOME/.config/cursor-cli-wrapper/config.toml" ]; then
        cp "$project_dir/config.toml.example" "$HOME/.config/cursor-cli-wrapper/config.toml"
        info "Copied default config to ~/.config/cursor-cli-wrapper/config.toml"
    else
        warn "~/.config/cursor-cli-wrapper/config.toml already exists — skipping"
    fi

    echo ""
    echo "To use cursor-cli-wrapper as the Cursor CLI backend, set:"
    echo ""
    echo "  export CURSOR_CLI_WRAPPER_BIN=\"$HOME/.local/bin/cursor-cli-wrapper\""
    echo ""
}

# ─────────────────────────────────────────────
#  usage
# ─────────────────────────────────────────────
usage() {
    printf "%b\n" "${BOLD}agents-status installer${NC}"
    echo ""
    printf "%b\n" "${BOLD}Usage:${NC}"
    echo "  $0 core                            Set up core (env var, config)"
    echo "  $0 hooks claude|cursor|codex|all   Install agent hooks"
    echo "  $0 wrapper codex|cursor            Symlink simple wrapper to ~/.local/bin"
    echo "  $0 cursor-cli-wrapper              Build & install Rust cursor-cli-wrapper"
    echo ""
    printf "%b\n" "${BOLD}Examples:${NC}"
    echo "  $0 core"
    echo "  $0 hooks all"
    echo "  $0 wrapper codex"
    echo "  $0 cursor-cli-wrapper"
}

# ─────────────────────────────────────────────
#  main
# ─────────────────────────────────────────────
main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        core)               cmd_core ;;
        hooks)              cmd_hooks "$@" ;;
        wrapper)            cmd_wrapper "$@" ;;
        cursor-cli-wrapper) cmd_cursor_cli_wrapper ;;
        -h|--help|help|"")  usage ;;
        *)
            err "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
