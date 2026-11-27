"""Global application configuration (``~/.config/git-tui``).

Separate from the per-repository ``.git-tui/config.json``. Stores user-level
preferences such as theme, default repository, GitHub token, release targets,
and wizard completion state.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class GlobalConfig:
    version: int = 1
    wizard_completed: bool = False
    theme: str = "dark"  # dark | light
    default_repo: str = ""
    github_token: str = ""
    github_auth_method: str = "none"  # none | gh | token
    release_dry_run: bool = True
    release_generate_sums: bool = True
    window_width: int = 1200
    window_height: int = 800
    font_size: int = 13


DEFAULT_TARGETS = {
    "windows-x86_64": "GOOS=windows GOARCH=amd64 go build -o dist/app.exe .",
    "linux-x86_64": "GOOS=linux GOARCH=amd64 go build -o dist/app .",
    "windows-arm64": "GOOS=windows GOARCH=arm64 go build -o dist/app.exe .",
    "linux-arm64": "GOOS=linux GOARCH=arm64 go build -o dist/app .",
    "windows-x86": "GOOS=windows GOARCH=386 go build -o dist/app.exe .",
    "linux-x86": "GOOS=linux GOARCH=386 go build -o dist/app .",
}


class GlobalConfigStore:
    """User-level configuration for Git TUI."""

    def __init__(self):
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        self.dir_path = os.path.join(xdg, "git-tui")
        self.config_path = os.path.join(self.dir_path, "config.json")
        self.targets_path = os.path.join(self.dir_path, "git-tui-targets.json")
        self._config = GlobalConfig()

    def exists(self) -> bool:
        return os.path.isfile(self.config_path)

    def ensure_dir(self) -> None:
        os.makedirs(self.dir_path, exist_ok=True)

    def load(self) -> GlobalConfig:
        if not self.exists():
            self._config = GlobalConfig()
            return self._config
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("config root is not an object")  # noqa: TRY004
            self._config = self._coerce(data)
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            self._config = GlobalConfig()
        return self._config

    def save(self) -> None:
        self.ensure_dir()
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self._config), fh, indent=2, sort_keys=True)
        os.replace(tmp, self.config_path)

    def _coerce(self, data: dict[str, Any]) -> GlobalConfig:
        return GlobalConfig(
            version=int(data.get("version", 1)),
            wizard_completed=bool(data.get("wizard_completed", False)),
            theme=str(data.get("theme", "dark") or "dark"),
            default_repo=str(data.get("default_repo", "") or ""),
            github_token=str(data.get("github_token", "") or ""),
            github_auth_method=str(data.get("github_auth_method", "none") or "none"),
            release_dry_run=bool(data.get("release_dry_run", True)),
            release_generate_sums=bool(data.get("release_generate_sums", True)),
            window_width=int(data.get("window_width", 1200) or 1200),
            window_height=int(data.get("window_height", 800) or 800),
            font_size=int(data.get("font_size", 13) or 13),
        )

    # ------------------------------------------------------------------ #
    # targets
    # ------------------------------------------------------------------ #
    def load_targets(self) -> dict[str, str]:
        if not os.path.isfile(self.targets_path):
            return dict(DEFAULT_TARGETS)
        try:
            with open(self.targets_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return dict(DEFAULT_TARGETS)
            return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_TARGETS)

    def save_targets(self, targets: dict[str, str]) -> None:
        self.ensure_dir()
        tmp = self.targets_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(targets, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, self.targets_path)

    # ------------------------------------------------------------------ #
    # accessors
    # ------------------------------------------------------------------ #
    @property
    def config(self) -> GlobalConfig:
        return self._config

    def set_wizard_completed(self) -> None:
        self._config.wizard_completed = True
        self.save()

    def set_default_repo(self, path: str) -> None:
        self._config.default_repo = os.path.abspath(path)
        self.save()

    def set_github_token(self, token: str, method: str = "token") -> None:
        self._config.github_token = token
        self._config.github_auth_method = method
        self.save()

    def set_window_size(self, width: int, height: int) -> None:
        self._config.window_width = int(width)
        self._config.window_height = int(height)
        self.save()
