"""GitHub connection detection & status."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from .git_ops import GitOps


@dataclass
class GitHubStatus:
    connected: bool
    authenticated: bool
    remote_name: str
    remote_url: str | None
    repo_slug: str | None
    message: str
    auth_method: str = "none"  # none | gh | token | config


def _parse_slug(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    # https://github.com/owner/repo.git  or  git@github.com:owner/repo.git
    if url.startswith("git@"):
        url = url.replace(":", "/").replace("git@", "https://")
    if url.endswith(".git"):
        url = url[:-4]
    if "github.com/" in url:
        return url.split("github.com/", 1)[1].strip("/")
    return None


def detect_github(repo_root: str) -> GitHubStatus:
    """Detect remote, auth (gh CLI / env token / config), and repo slug."""
    git = GitOps(repo_root)
    remotes = git.remotes()
    origin = next((r for r in remotes if r["name"] == "origin"), remotes[0] if remotes else None)

    if origin is None:
        return GitHubStatus(
            connected=False, authenticated=False, remote_name="", remote_url=None,
            repo_slug=None, message="No GitHub remote configured", auth_method="none",
        )

    url = origin["url"]
    slug = _parse_slug(url)
    if not slug:
        return GitHubStatus(
            connected=False, authenticated=False, remote_name=origin["name"], remote_url=url,
            repo_slug=None, message=f"Unparsable remote URL: {url}", auth_method="none",
        )

    # Auth detection: gh CLI auth status
    auth_method = "none"
    authenticated = False
    if shutil.which("gh"):
        try:
            proc = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                authenticated = True
                auth_method = "gh"
            else:
                auth_method = "gh"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            auth_method = "gh"
    elif os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        authenticated = True
        auth_method = "token"
    else:
        # config reference only
        auth_method = "config"

    connected = authenticated
    message = "Connected" if connected else "Auth missing"
    return GitHubStatus(
        connected=connected, authenticated=authenticated, remote_name=origin["name"],
        remote_url=url, repo_slug=slug, message=message, auth_method=auth_method,
    )


def gh_available() -> bool:
    return shutil.which("gh") is not None


def gh_auth_token() -> Optional[str]:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
