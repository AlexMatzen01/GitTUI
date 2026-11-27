"""Semantic versioning and release channel engine."""

from __future__ import annotations

import re
from dataclasses import dataclass

CHANNEL_ORDER = ["alpha", "beta", "pre-release", "release"]
CHANNEL_COLORS = {
    "release": "#22c55e",        # emerald green
    "pre-release": "#f59e0b",    # amber / gold
    "beta": "#38bdf8",           # sky blue / cyan
    "alpha": "#c084fc",          # violet / magenta
}

SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<channel>[A-Za-z0-9.-]+))?(?:\+(?P<build>[A-Za-z0-9.-]+))?$")  # noqa: E501


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    channel: str | None = None
    build: str | None = None

    @property
    def is_prerelease(self) -> bool:
        return self.channel is not None

    def bump_major(self) -> "SemVer":
        return SemVer(major=self.major + 1, minor=0, patch=0, channel=self.channel)

    def bump_minor(self) -> "SemVer":
        return SemVer(major=self.major, minor=self.minor + 1, patch=0, channel=self.channel)

    def bump_patch(self) -> "SemVer":
        return SemVer(major=self.major, minor=self.minor, patch=self.patch + 1, channel=self.channel)

    def promote(self) -> "SemVer":
        if self.channel is None:
            return self
        try:
            idx = CHANNEL_ORDER.index(self.channel)
        except ValueError:
            return self
        if idx + 1 < len(CHANNEL_ORDER):
            return SemVer(major=self.major, minor=self.minor, patch=self.patch, channel=CHANNEL_ORDER[idx + 1])
        return self

    def demote(self) -> "SemVer":
        if self.channel is None:
            return self
        try:
            idx = CHANNEL_ORDER.index(self.channel)
        except ValueError:
            return self
        if idx - 1 >= 0:
            return SemVer(major=self.major, minor=self.minor, patch=self.patch, channel=CHANNEL_ORDER[idx - 1])
        return self

    def set_channel(self, channel: str) -> "SemVer":
        return SemVer(major=self.major, minor=self.minor, patch=self.patch, channel=channel)

    def strip_channel(self) -> "SemVer":
        return SemVer(major=self.major, minor=self.minor, patch=self.patch)

    def tag_name(self, prefix: str = "v") -> str:
        return f"{prefix}{self}"

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.channel:
            core = f"{core}-{self.channel}"
        if self.build:
            core = f"{core}+{self.build}"
        return core

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        value = value.strip()
        if value.startswith("v"):
            value = value[1:]
        match = SEMVER_RE.match(value)
        if not match:
            raise ValueError(f"invalid semantic version: {value!r}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            channel=match.group("channel"),
            build=match.group("build"),
        )


def format_version(major: int, minor: int, patch: int, channel: str | None = None) -> str:
    core = f"{major}.{minor}.{patch}"
    if channel:
        core = f"{core}-{channel}"
    return core


def channel_color(channel: str | None) -> str:
    if channel is None:
        return "#22c55e"
    return CHANNEL_COLORS.get(channel, "#94a3b8")


# module-level alias for convenience
parse = SemVer.parse
