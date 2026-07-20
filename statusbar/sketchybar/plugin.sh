#!/bin/bash
# Sketchybar workspace plugin for agents-status.
# Reads the sentinel file written by statusbar/run.py and applies labels
# and colors to sketchybar workspace items.
#
# Usage (in sketchybarrc):
#   script="~/agents-status/statusbar/sketchybar/plugin.sh $sid"
#
# Requires: jq, sketchybar, aerospace

# Read pre-computed workspace state from cache
CACHE="/tmp/aerospace-ws-cache"
if [ -f "$CACHE" ]; then
    FOCUSED_GROUP=$(sed -n '1p' "$CACHE")
    CACHE_LINE=$(grep "^$1 " "$CACHE")
    HAS_WINDOWS=$( [ "$(echo "$CACHE_LINE" | cut -d' ' -f2)" = "1" ] && echo "true" || echo "false" )
    WIN_COUNT=$(echo "$CACHE_LINE" | cut -d' ' -f3)
else
    FOCUSED_GROUP=$(aerospace list-workspaces --focused 2>/dev/null)
    FOCUSED_GROUP="${FOCUSED_GROUP%%[bc]}"
    HAS_WINDOWS="false"
    WIN_COUNT=0
fi

IS_FOCUSED=$( [ "$1" = "$FOCUSED_GROUP" ] && echo "true" || echo "false" )
: "${WIN_COUNT:=0}"

SENTINEL="/tmp/agent-status-bg-$(id -u)"
TEMPLATE=""
AGENT_LABEL=""
AGENT_ICON=""
MONITOR_ICON=""
TMUX_SESSIONS=""
APP_ICONS=""
AGENT_BG=""
AGENT_TEXT=""
DEFAULT_BG_FOCUSED=""
DEFAULT_BG_UNFOCUSED=""
DEFAULT_TEXT_FOCUSED=""
DEFAULT_TEXT_UNFOCUSED=""

if [ -f "$SENTINEL" ]; then
    if [ "$IS_FOCUSED" = "true" ]; then
        BG_KEY="bg_focused"; TEXT_KEY="text_focused"
    else
        BG_KEY="bg_unfocused"; TEXT_KEY="text_unfocused"
    fi
    eval $(jq -r --arg id "$1" --arg bg_key "$BG_KEY" --arg text_key "$TEXT_KEY" '
        if .template then
            "TEMPLATE=\(.template | @sh)",
            "DEFAULT_BG_FOCUSED=\(.default_bg_focused // "" | @sh)",
            "DEFAULT_BG_UNFOCUSED=\(.default_bg_unfocused // "" | @sh)",
            "DEFAULT_TEXT_FOCUSED=\(.default_text_focused // "" | @sh)",
            "DEFAULT_TEXT_UNFOCUSED=\(.default_text_unfocused // "" | @sh)"
        elif .id == ($id | tonumber) then
            "AGENT_LABEL=\(.display_name // "" | @sh)",
            "AGENT_ICON=\(.agent_icon // "" | @sh)",
            "MONITOR_ICON=\(.monitor_icon // "" | @sh)",
            "TMUX_SESSIONS=\(.tmux_sessions // "" | @sh)",
            "APP_ICONS=\(.app_icons // "" | @sh)",
            "AGENT_BG=\(.[$bg_key] // "" | @sh)",
            "AGENT_TEXT=\(.[$text_key] // "" | @sh)"
        else empty end
    ' "$SENTINEL" 2>/dev/null)
fi

# Build label from template
LABEL=""
if [ -n "$TEMPLATE" ] && [ -n "$AGENT_LABEL" ]; then
    LABEL="$TEMPLATE"
    LABEL="${LABEL//\{id\}/$1}"
    LABEL="${LABEL//\{agent_label\}/$AGENT_LABEL}"
    LABEL="${LABEL//\{agent_icon\}/$AGENT_ICON}"
    LABEL="${LABEL//\{monitor_icon\}/$MONITOR_ICON}"
    LABEL="${LABEL//\{tmux_sessions\}/$TMUX_SESSIONS}"
    LABEL="${LABEL//\{app_icons\}/$APP_ICONS}"
    if [ "$IS_FOCUSED" = "true" ]; then
        LABEL=$(echo "$LABEL" | sed 's/\[{window_count}\]//g; s/{window_count}//g')
    else
        LABEL=$(echo "$LABEL" | sed "s/{window_count}/$WIN_COUNT/g")
    fi
    LABEL=$(echo "$LABEL" | sed 's/  */ /g;s/^[[:space:]]*//;s/[[:space:]]*$//')
elif [ "$WIN_COUNT" -gt 1 ] 2>/dev/null; then
    LABEL="$WIN_COUNT"
fi

set_workspace() {
    if [ -n "$LABEL" ]; then
        sketchybar --set "$NAME" "label=$LABEL" label.drawing=on "$@" drawing=on
    else
        sketchybar --set "$NAME" label.drawing=off "$@" drawing=on
    fi
}

# Resolve default colors (from sentinel header, or built-in fallback)
: "${DEFAULT_BG_FOCUSED:=0xff444444}"
: "${DEFAULT_BG_UNFOCUSED:=0xff222222}"
: "${DEFAULT_TEXT_FOCUSED:=0xffffffff}"
: "${DEFAULT_TEXT_UNFOCUSED:=0xffaaaaaa}"

if [ "$IS_FOCUSED" = "true" ]; then
    if [ -n "$AGENT_BG" ] && [ -n "$AGENT_TEXT" ]; then
        set_workspace background.color="$AGENT_BG" background.drawing=on icon.color="$AGENT_TEXT" label.color="$AGENT_TEXT"
    else
        set_workspace background.color="$DEFAULT_BG_FOCUSED" background.drawing=on icon.color="$DEFAULT_TEXT_FOCUSED" label.color="$DEFAULT_TEXT_FOCUSED"
    fi
elif [ "$HAS_WINDOWS" = "true" ]; then
    if [ -n "$AGENT_BG" ] && [ -n "$AGENT_TEXT" ]; then
        set_workspace background.color="$AGENT_BG" background.drawing=on icon.color="$AGENT_TEXT" label.color="$AGENT_TEXT"
    else
        set_workspace background.color="$DEFAULT_BG_UNFOCUSED" background.drawing=on icon.color="$DEFAULT_TEXT_UNFOCUSED" label.color="$DEFAULT_TEXT_UNFOCUSED"
    fi
else
    sketchybar --set "$NAME" label.drawing=off drawing=off
fi
