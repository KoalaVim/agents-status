#!/usr/bin/env bash
# TPM-compatible plugin entry point for agents-status.

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$CURRENT_DIR/scripts"

# Register format interpolation: #{agents-status-icon}
tmux set-option -gq @agents-status-icon-cmd "$SCRIPTS_DIR/status-icon.sh"

# Create a named command tmux can use for format interpolation.
# We use a pipe-pane trick: define a custom format token via set-option.
# tmux doesn't support custom format variables natively, so we use
# #(script) syntax in the format string.
ICON_CMD="#($SCRIPTS_DIR/status-icon.sh #{window_id})"

# Auto-format: prepend icon to window-status-format if enabled.
auto_format=$(tmux show-option -gqv @agents-status-auto-format 2>/dev/null)
if [[ "$auto_format" == "on" ]]; then
  current_format=$(tmux show-option -gqv window-status-format)
  current_current_format=$(tmux show-option -gqv window-status-current-format)

  # Only prepend if not already present.
  if [[ "$current_format" != *"status-icon.sh"* ]]; then
    tmux set-option -gq window-status-format "${ICON_CMD} ${current_format}"
  fi
  if [[ "$current_current_format" != *"status-icon.sh"* ]]; then
    tmux set-option -gq window-status-current-format "${ICON_CMD} ${current_current_format}"
  fi
fi

# Periodic refresh of dim colors via hook (fires on window activity).
if [[ -x "$SCRIPTS_DIR/refresh_dim_colors.sh" ]]; then
  tmux set-hook -g window-activity "run-shell '$SCRIPTS_DIR/refresh_dim_colors.sh'"
fi

# Also set a periodic interval (every 5s) as a fallback.
# Uses the tmux status-interval to piggyback refresh.
if [[ -x "$SCRIPTS_DIR/refresh_dim_colors.sh" ]]; then
  tmux set-hook -g pane-focus-in "run-shell '$SCRIPTS_DIR/refresh_dim_colors.sh'"
fi
