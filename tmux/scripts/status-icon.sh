#!/usr/bin/env bash
# Outputs tmux-formatted colored icons based on @ai-agent-status and
# @monitor-status for a window.
# Usage: status-icon.sh <window-target>

target="${1:?Usage: status-icon.sh <window-target>}"

icon=""

status=$(tmux show-window-option -t "$target" -v @ai-agent-status 2>/dev/null)
case "$status" in
  WAITING)    icon='#[fg=#cf1313]W#[fg=default]' ;;
  INPROGRESS) icon='#[fg=#fa7900]●#[fg=default]' ;;
  DONE)       icon='#[fg=#1e88ff]✓#[fg=default]' ;;
  IDLE)       icon='#[fg=#15c70c]○#[fg=default]' ;;
esac

monitor=$(tmux show-window-option -t "$target" -v @monitor-status 2>/dev/null)
if [[ "$monitor" == "INPROGRESS" ]]; then
  sep=${icon:+ }
  icon="${icon}${sep}#[fg=#fa7900]󰦖#[fg=default]"
fi

printf '%s' "$icon"
