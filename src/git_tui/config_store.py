"""Local project configuration persistence (``.git-tui/config.json``).

Handles missing or corrupted ``.git-tui/`` safely with defaults and JSON schema
validation. All reads/writes are atomic-ish (write temp + replace).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_THEME = "dark"
DEFAULT_COLOR_DEPTH = "truecolor"  # truecolor | 256 | ansi


@dataclass
class ReleaseSettings:
    enabled: bool = False
    dry_run: bool = True
    artifact_globs: list[str] = field(default_factory=lambda: ["dist/*", "build/*.zip", "build/*.tar.gz"])
    targets: list[str] = field(
        default_factory=lambda: [
            "windows-x86_64",
            "linux-x86_64",
            "windows-arm64",
            "linux-arm64",
            "windows-x86",
            "linux-x86",
        ]
    )
    upload_on_tag: bool = True
    generate_sha256: bool = True


@dataclass
class UIState:
    theme: str = DEFAULT_THEME
    color_depth: str = DEFAULT_COLOR_DEPTH
    last_tab: str = "status"
    window_width: int = 120
    window_height: int = 40


@dataclass
class VersionState:
    major: int = 0
    minor: int = 1
    patch: int = 0
    channel: str = "alpha"  # alpha | beta | pre-release | release
    last_tag: str = ""


@dataclass
class Config:
    version: int = 1
    repo: str = ""
    version_state: VersionState = field(default_factory=VersionState)
    selected_presets: list[str] = field(default_factory=list)
    release: ReleaseSettings = field(default_factory=ReleaseSettings)
    ui: UIState = field(default_factory=UIState)
    github_token_env: str = "GITHUB_TOKEN"
    auto_fetch: bool = False


SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "integer"},
        "repo": {"type": "string"},
        "version_state": {
            "type": "object",
            "properties": {
                "major": {"type": "integer"},
                "minor": {"type": "integer"},
                "patch": {"type": "integer"},
                "channel": {"type": "string", "enum": ["alpha", "beta", "pre-release", "release"]},
                "last_tag": {"type": "string"},
            },
            "required": ["major", "minor", "patch", "channel"],
        },
        "selected_presets": {"type": "array", "items": {"type": "string"}},
        "release": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "dry_run": {"type": "boolean"},
                "artifact_globs": {"type": "array", "items": {"type": "string"}},
                "targets": {"type": "array", "items": {"type": "string"}},
                "upload_on_tag": {"type": "boolean"},
                "generate_sha256": {"type": "boolean"},
            },
            "required": ["enabled", "dry_run", "artifact_globs", "targets"],
        },
        "ui": {
            "type": "object",
            "properties": {
                "theme": {"type": "string"},
                "color_depth": {"type": "string", "enum": ["truecolor", "256", "ansi"]},
                "last_tab": {"type": "string"},
                "window_width": {"type": "integer"},
                "window_height": {"type": "integer"},
            },
            "required": ["theme", "color_depth"],
        },
        "github_token_env": {"type": "string"},
        "auto_fetch": {"type": "boolean"},
    },
    "required": ["version", "repo", "version_state", "selected_presets", "release", "ui"],
}


class ConfigStore:
    """Persisted configuration for a single repository."""

    GIT_TUI_DIR = ".git-tui"
    CONFIG_FILE = "config.json"

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.dir_path = os.path.join(repo_root, self.GIT_TUI_DIR)
        self.config_path = os.path.join(self.dir_path, self.CONFIG_FILE)
        self._config = Config(repo=repo_root)

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def exists(self) -> bool:
        return os.path.isfile(self.config_path)

    def ensure_dir(self) -> None:
        os.makedirs(self.dir_path, exist_ok=True)

    def load(self) -> Config:
        """Load config, falling back to defaults on any corruption/missing file."""
        if not self.exists():
            self._config = Config(repo=self.repo_root)
            return self._config
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise TypeError("config root is not an object")
            self._config = self._validate_and_coerce(data)
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            # Corrupted or unreadable: reset to defaults but keep repo.
            self._config = Config(repo=self.repo_root)
        return self._config

    def save(self) -> None:
        self.ensure_dir()
        tmp_path = self.config_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self._config), fh, indent=2, sort_keys=True)
        os.replace(tmp_path, self.config_path)

    # ------------------------------------------------------------------ #
    # validation / coercion
    # ------------------------------------------------------------------ #
    def _validate_and_coerce(self, data: dict[str, Any]) -> Config:
        version = data.get("version", 1)
        repo = str(data.get("repo", self.repo_root))

        vs = data.get("version_state", {})
        version_state = VersionState(
            major=int(vs.get("major", 0) or 0),
            minor=int(vs.get("minor", 1) or 1),
            patch=int(vs.get("patch", 0) or 0),
            channel=self._coerce_channel(vs.get("channel", "alpha")),
            last_tag=str(vs.get("last_tag", "") or ""),
        )

        rel = data.get("release", {})
        release = ReleaseSettings(
            enabled=bool(rel.get("enabled", False)),
            dry_run=bool(rel.get("dry_run", True)),
            artifact_globs=[
                str(g) for g in (rel.get("artifact_globs") or [])
            ] or ["dist/*", "build/*.zip", "build/*.tar.gz"],
            targets=[str(t) for t in (rel.get("targets") or [])] or [
                "windows-x86_64", "linux-x86_64", "windows-arm64", "linux-arm64", "windows-x86", "linux-x86",
            ],
            upload_on_tag=bool(rel.get("upload_on_tag", True)),
            generate_sha256=bool(rel.get("generate_sha256", True)),
        )

        ui = data.get("ui", {})
        ui_state = UIState(
            theme=str(ui.get("theme", DEFAULT_THEME) or DEFAULT_THEME),
            color_depth=self._coerce_depth(ui.get("color_depth", DEFAULT_COLOR_DEPTH)),
            last_tab=str(ui.get("last_tab", "status") or "status"),
            window_width=int(ui.get("window_width", 120) or 120),
            window_height=int(ui.get("window_height", 40) or 40),
        )

        return Config(
            version=int(version) if isinstance(version, int) else 1,
            repo=repo,
            version_state=version_state,
            selected_presets=[str(p) for p in (data.get("selected_presets") or [])],
            release=release,
            ui=ui_state,
            github_token_env=str(data.get("github_token_env", "GITHUB_TOKEN") or "GITHUB_TOKEN"),
            auto_fetch=bool(data.get("auto_fetch", False)),
        )

    @staticmethod
    def _coerce_channel(value: Any) -> str:
        channel = str(value or "alpha")
        if channel not in ("alpha", "beta", "pre-release", "release"):
            return "alpha"
        return channel

    @staticmethod
    def _coerce_depth(value: Any) -> str:
        depth = str(value or DEFAULT_COLOR_DEPTH)
        if depth not in ("truecolor", "256", "ansi"):
            return DEFAULT_COLOR_DEPTH
        return depth

    # ------------------------------------------------------------------ #
    # accessors
    # ------------------------------------------------------------------ #
    @property
    def config(self) -> Config:
        return self._config

    def set_version(self, major: int, minor: int, patch: int, channel: str) -> None:
        self._config.version_state.major = int(major)
        self._config.version_state.minor = int(minor)
        self._config.version_state.patch = int(patch)
        self._config.version_state.channel = self._coerce_channel(channel)

    def set_last_tag(self, tag: str) -> None:
        self._config.version_state.last_tag = str(tag)

    def set_selected_presets(self, presets: list[str]) -> None:
        self._config.selected_presets = list(presets)

    def set_ui_state(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self._config.ui, key):
                setattr(self._config.ui, key, value)
