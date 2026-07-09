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


@dataclass
class SketchybarColorsConfig:
    idle_focused: str = "0xff0be600"
    idle_unfocused: str = "0xff16610a"
    inprogress_focused: str = "0xfffa7900"
    inprogress_unfocused: str = "0xff61380a"
    waiting_focused: str = "0xffc80000"
    waiting_unfocused: str = "0xff6f0c0c"
    done_focused: str = "0xff1e88ff"
    done_unfocused: str = "0xff0c4583"
    text_focused: str = "0xff1e1e1e"
    text_unfocused: str = "0xff000000"


@dataclass
class SketchybarConfig:
    space_item_prefix: str = "space"
    label_template: str = "{agent_icon} {tmux_sessions} [{window_count}]"
    colors: SketchybarColorsConfig = field(default_factory=SketchybarColorsConfig)


@dataclass
class StatusbarConfig:
    workspaces_provider: str = ""
    bar: str = ""
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
    raw: dict = {}
    if os.path.isfile(path):
        if tomllib is None:
            print(
                f"statusbar: tomllib unavailable, skipping {path}",
                file=sys.stderr,
            )
        else:
            try:
                with open(path, "rb") as f:
                    raw = tomllib.load(f).get("statusbar", {})
            except Exception as e:
                print(f"statusbar: failed to load {path}: {e}", file=sys.stderr)

    provider = raw.pop("workspaces_provider", "")
    bar = raw.pop("bar", "")

    features = _build_dataclass(FeaturesConfig, raw.pop("features", {}))
    naming = _build_dataclass(NamingConfig, raw.pop("naming", {}))
    icons = _build_dataclass(IconsConfig, raw.pop("icons", {}))
    sketchybar_raw = raw.pop("sketchybar", {})
    sketchybar_colors = _build_dataclass(
        SketchybarColorsConfig, sketchybar_raw.pop("colors", {}),
    )
    sketchybar_obj = _build_dataclass(SketchybarConfig, sketchybar_raw)
    sketchybar_obj.colors = sketchybar_colors  # type: ignore[attr-defined]

    if not provider or not bar:
        detected_provider, detected_bar = _auto_detect()
        provider = provider or detected_provider
        bar = bar or detected_bar

    return StatusbarConfig(
        workspaces_provider=provider,
        bar=bar,
        features=features,  # type: ignore[arg-type]
        naming=naming,  # type: ignore[arg-type]
        icons=icons,  # type: ignore[arg-type]
        sketchybar=sketchybar_obj,  # type: ignore[arg-type]
    )
