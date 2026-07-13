#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field, fields

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]  # Python < 3.11
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class FeaturesConfig:
    agent_status: bool = True
    monitor_status: bool = True
    browser_icon: bool = True
    slack_icon: bool = True
    jira_strip: bool = True
    prefix_dedup: bool = True
    active_keeps_number: bool = True


@dataclass
class NamingConfig:
    max_length: int = 20
    tmux_suffix: str = " - TMUX"


@dataclass
class IconsConfig:
    agent_inprogress: str = "\uead2"
    agent_waiting: str = "\uf421"
    agent_idle: str = "\U000f06a9"
    agent_done: str = "\ue63f"
    monitor_inprogress: str = "\U000f0996"
    tmux: str = "\ue240"
    browser: str = "\uf0ac"
    slack: str = "\ue8a4"


DEFAULT_STATUS_COLORS = {
    "idle": "#1e88ff",
    "inprogress": "#fa7900",
    "waiting": "#cf1313",
    "done": "#15c70c",
}

# Dimmed unfocused variants of the default bright colors
_DEFAULT_UNFOCUSED = {
    "idle": "#0c4583",
    "inprogress": "#61380a",
    "waiting": "#6f0c0c",
    "done": "#16610a",
}


def _hex_to_sketchybar(hex_color: str) -> str:
    """Convert #rrggbb to 0xffrrggbb."""
    return "0xff" + hex_color.lstrip("#")


def _dim_color(hex_color: str, factor: float = 0.4) -> str:
    """Produce a dimmed variant of a #rrggbb color."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class ColorsConfig:
    idle: str = ""
    inprogress: str = ""
    waiting: str = ""
    done: str = ""

    def resolved(self) -> dict[str, str]:
        """Return status->hex mapping with defaults filled in."""
        return {
            k: getattr(self, k) or DEFAULT_STATUS_COLORS[k]
            for k in DEFAULT_STATUS_COLORS
        }


@dataclass
class SketchybarColorsConfig:
    idle_focused: str = ""
    idle_unfocused: str = ""
    inprogress_focused: str = ""
    inprogress_unfocused: str = ""
    waiting_focused: str = ""
    waiting_unfocused: str = ""
    done_focused: str = ""
    done_unfocused: str = ""
    text_focused: str = "0xff1e1e1e"
    text_unfocused: str = "0xff000000"

    def apply_global_colors(self, colors: dict[str, str]) -> None:
        """Fill in empty slots from global [colors], converting to sketchybar format."""
        for status, hex_color in colors.items():
            focused_attr = f"{status}_focused"
            unfocused_attr = f"{status}_unfocused"
            if not getattr(self, focused_attr):
                setattr(self, focused_attr, _hex_to_sketchybar(hex_color))
            if not getattr(self, unfocused_attr):
                unfocused_hex = _DEFAULT_UNFOCUSED.get(status) or _dim_color(hex_color)
                setattr(self, unfocused_attr, _hex_to_sketchybar(unfocused_hex))


@dataclass
class SketchybarConfig:
    space_item_prefix: str = "space"
    label_template: str = "{app_icons} {agent_icon} {tmux_sessions} [{window_count}]"
    colors: SketchybarColorsConfig = field(default_factory=SketchybarColorsConfig)


@dataclass
class StatusbarConfig:
    workspaces_provider: str = ""
    bar: str = ""
    colors: ColorsConfig = field(default_factory=ColorsConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    icons: IconsConfig = field(default_factory=IconsConfig)
    sketchybar: SketchybarConfig = field(default_factory=SketchybarConfig)


def _auto_detect() -> tuple[str, str]:
    """Detect workspaces provider and bar from available system commands."""
    if shutil.which("hyprctl"):
        return "hyprland", "hyprland"
    if shutil.which("aerospace") and shutil.which("sketchybar"):
        return "aerospace", "sketchybar"
    return "", ""


def _build_dataclass(cls: type, raw: dict) -> object:
    """Instantiate a dataclass from a dict, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in raw.items() if k in known})


def load_statusbar_config() -> StatusbarConfig:
    """Load statusbar config from TOML file, with auto-detection fallback."""
    path = os.environ.get("AGENTS_STATUS_CONFIG") or os.path.expanduser(
        "~/.config/agents-status/config.toml"
    )
    full_config: dict = {}
    if os.path.isfile(path):
        if tomllib is None:
            print(
                f"statusbar: tomllib unavailable, skipping {path}",
                file=sys.stderr,
            )
        else:
            try:
                with open(path, "rb") as f:
                    full_config = tomllib.load(f)
            except Exception as e:
                print(f"statusbar: failed to load {path}: {e}", file=sys.stderr)

    global_colors = _build_dataclass(ColorsConfig, full_config.get("colors", {}))

    raw = full_config.get("statusbar", {})
    provider = raw.pop("workspaces_provider", "")
    bar = raw.pop("bar", "")

    features = _build_dataclass(FeaturesConfig, raw.pop("features", {}))
    naming = _build_dataclass(NamingConfig, raw.pop("naming", {}))
    icons = _build_dataclass(IconsConfig, raw.pop("icons", {}))
    sketchybar_raw = raw.pop("sketchybar", {})
    sketchybar_colors = _build_dataclass(
        SketchybarColorsConfig, sketchybar_raw.pop("colors", {}),
    )
    sketchybar_colors.apply_global_colors(global_colors.resolved())  # type: ignore[union-attr]
    sketchybar_obj = _build_dataclass(SketchybarConfig, sketchybar_raw)
    sketchybar_obj.colors = sketchybar_colors  # type: ignore[attr-defined]

    if not provider or not bar:
        detected_provider, detected_bar = _auto_detect()
        provider = provider or detected_provider
        bar = bar or detected_bar

    return StatusbarConfig(
        workspaces_provider=provider,
        bar=bar,
        colors=global_colors,  # type: ignore[arg-type]
        features=features,  # type: ignore[arg-type]
        naming=naming,  # type: ignore[arg-type]
        icons=icons,  # type: ignore[arg-type]
        sketchybar=sketchybar_obj,  # type: ignore[arg-type]
    )
