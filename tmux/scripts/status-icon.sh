#!/usr/bin/env bash
# Outputs a tmux-formatted colored icon based on @ai-agent-status for a window.
# Usage: status-icon.sh <window-target>

target="${1:?Usage: status-icon.sh <window-target>}"

status=$(tmux show-window-option -t "$target" -v @ai-agent-status 2>/dev/null)

case "$status" in
  WAITING)    printf '#[fg=#cf1313]W#[fg=default]' ;;
  INPROGRESS) printf '#[fg=#fa7900]●#[fg=default]' ;;
  DONE)       printf '#[fg=#1e88ff]✓#[fg=default]' ;;
  IDLE)       printf '#[fg=#15c70c]○#[fg=default]' ;;
  *)          printf '' ;;
esac
