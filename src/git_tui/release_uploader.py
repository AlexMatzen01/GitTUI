"""Automated multi-arch release binary uploader.

Generates a GitHub Actions workflow for the six target combinations and can
upload local build artifacts to a GitHub Release via ``gh release upload`` or
the GitHub API, with SHA256SUMS generation, dry-run mode, and progress bars.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass

from .github_client import detect_github, gh_auth_token, gh_available
from .versioning import SemVer

TARGETS = [
    "windows-x86_64",
    "linux-x86_64",
    "windows-arm64",
    "linux-arm64",
    "windows-x86",
    "linux-x86",
]

TARGETS_JSON_FILENAME = "git-tui-targets.json"


class TargetConfigError(Exception):
    """Raised when the per-target build command config is invalid."""

    pass


DEFAULT_TARGET_COMMAND = {
    "windows-x86_64": "GOOS=windows GOARCH=amd64 go build -o dist/app.exe .",
    "linux-x86_64": "GOOS=linux GOARCH=amd64 go build -o dist/app .",
    "windows-arm64": "GOOS=windows GOARCH=arm64 go build -o dist/app.exe .",
    "linux-arm64": "GOOS=linux GOARCH=arm64 go build -o dist/app .",
    "windows-x86": "GOOS=windows GOARCH=386 go build -o dist/app.exe .",
    "linux-x86": "GOOS=linux GOARCH=386 go build -o dist/app .",
}

_TARGET_CONFIG_DOCS = (
    "Invalid or missing per-target build command config.\n"
    "Create a file at: .git-tui/git-tui-targets.json\n"
    "It must be a single JSON object mapping each of the six targets to a build command.\n"
    "Example:\n"
    "{\n"
    '  "windows-x86_64": "GOOS=windows GOARCH=amd64 go build -o dist/app.exe .",\n'
    '  "linux-x86_64": "GOOS=linux GOARCH=amd64 go build -o dist/app .",\n'
    '  "windows-arm64": "GOOS=windows GOARCH=arm64 go build -o dist/app.exe .",\n'
    '  "linux-arm64": "GOOS=linux GOARCH=arm64 go build -o dist/app .",\n'
    '  "windows-x86": "GOOS=windows GOARCH=386 go build -o dist/app.exe .",\n'
    '  "linux-x86": "GOOS=linux GOARCH=386 go build -o dist/app ."\n'
    "}\n"
    "Keys must match the target names exactly: windows-x86_64, linux-x86_64,\n"
    "windows-arm64, linux-arm64, windows-x86, linux-x86.\n"
    "Values are shell commands run for that target in the release workflow."
)


def load_target_commands(repo_root: str) -> dict[str, str]:
    """Load per-target build commands from ``.git-tui/git-tui-targets.json``.

    Returns an empty dict if the file does not exist (callers fall back to
    defaults). Raises :class:`TargetConfigError` (with usage docs) if the file
    exists but contains invalid JSON or the wrong shape.
    """
    path = os.path.join(repo_root, ".git-tui", TARGETS_JSON_FILENAME)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise TargetConfigError(f"{_TARGET_CONFIG_DOCS}\n\nJSON parse error: {exc}") from None
    if not isinstance(data, dict):
        raise TargetConfigError(
            f"{_TARGET_CONFIG_DOCS}\n\nTop level must be a JSON object, not {type(data).__name__}."
        )
    result: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TargetConfigError(
                f"{_TARGET_CONFIG_DOCS}\n\nAll keys and values must be strings "
                f'(got key {key!r} -> value {value!r}).'
            )
        result[key] = value
    return result


def write_target_commands(repo_root: str, commands: dict[str, str]) -> str:
    """Write per-target build commands to ``.git-tui/git-tui-targets.json``.

    Validates that keys match the six known targets and values are non-empty
    strings. Returns the path written.
    """
    path = os.path.join(repo_root, ".git-tui", TARGETS_JSON_FILENAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    unknown = [k for k in commands if k not in TARGETS]
    if unknown:
        raise TargetConfigError(
            f"Unknown target(s): {', '.join(unknown)}. "
            f"Valid targets: {', '.join(TARGETS)}."
        )
    missing = [t for t in TARGETS if t not in commands]
    if missing:
        raise TargetConfigError(
            f"Missing target(s): {', '.join(missing)}. All six targets are required."
        )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(commands, fh, indent=2)
        fh.write("\n")
    return path


@dataclass
class UploadResult:
    ok: bool
    message: str
    uploaded: list[str] = None  # type: ignore[assignment]
    sha256: str | None = None

    def __post_init__(self):
        if self.uploaded is None:
            self.uploaded = []


def release_tag(version: SemVer) -> str:
    return version.tag_name("v")


def workflow_yaml(
    repo_slug: str | None,
    tag_prefix: str = "v",
    target_commands: dict[str, str] | None = None,
) -> str:
    targets_matrix = "\n        - ".join(f'"{t}"' for t in TARGETS)
    commands = target_commands or {}
    case_arms: list[str] = []
    for target in TARGETS:
        command = commands.get(target)
        if not command:
            command = DEFAULT_TARGET_COMMAND[target]
        command = command.replace("{target}", target)
        case_arms.append(f'            {target}) {command} ;;')
    case_block = "\n".join(case_arms)
    return f"""name: Release Binaries

on:
  push:
    tags:
      - "{tag_prefix}*"

jobs:
  build-upload:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target:
          - {targets_matrix}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: stable

      - name: Build for ${{{{ matrix.target }}}}
        run: |
          case "${{{{ matrix.target }}}}" in
{case_block}
          esac

      - name: Upload release asset
        uses: softprops/action-gh-release@v2
        with:
          files: dist/*
"""


def write_workflow(
    workflow_dir: str,
    repo_slug: str | None = None,
    target_commands: dict[str, str] | None = None,
) -> str:
    os.makedirs(workflow_dir, exist_ok=True)
    path = os.path.join(workflow_dir, "release-binaries.yml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(workflow_yaml(repo_slug, target_commands=target_commands))
    return path


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_sha256sums(files: list[str], output: str = "SHA256SUMS.txt") -> str:
    lines = []
    for path in files:
        if not os.path.isfile(path):
            continue
        digest = _sha256_file(path)
        lines.append(f"{digest}  {os.path.basename(path)}")
    with open(output, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return output


def upload_assets(
    repo_root: str,
    tag: str,
    files: list[str],
    dry_run: bool = True,
    generate_sums: bool = True,
) -> UploadResult:
    """Upload artifacts to a GitHub Release.

    Uses ``gh release upload`` when available, otherwise falls back to the
    GitHub REST API with a token from the environment/config.
    """
    status = detect_github(repo_root)
    if not status.repo_slug:
        return UploadResult(ok=False, message="No GitHub repo slug detected")

    existing = [f for f in files if os.path.isfile(f)]
    if generate_sums and existing:
        sums_path = os.path.join(repo_root, "SHA256SUMS.txt")
        generate_sha256sums(existing, sums_path)
        files_to_upload = existing + [sums_path]
    else:
        files_to_upload = existing

    if dry_run:
        return UploadResult(
            ok=True,
            message=f"[dry-run] would upload {len(files_to_upload)} file(s) to {status.repo_slug}@{tag}",
            uploaded=files_to_upload,
        )

    if not existing:
        return UploadResult(ok=False, message="No valid artifact files to upload")

    # Ensure the release exists (create empty if missing via gh).
    if gh_available():
        cmd = ["gh", "release", "upload", tag] + files_to_upload
        try:
            proc = subprocess.run(
                cmd, cwd=repo_root, capture_output=True, text=True, timeout=300
            )
            if proc.returncode == 0:
                msg = f"Uploaded {len(files_to_upload)} file(s) via gh"
                return UploadResult(ok=True, message=msg, uploaded=files_to_upload)
            return UploadResult(ok=False, message=proc.stderr.strip() or "gh release upload failed", uploaded=files_to_upload)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return UploadResult(ok=False, message=str(exc), uploaded=files_to_upload)

    token = gh_auth_token()
    if not token:
        return UploadResult(ok=False, message="gh CLI unavailable and no GITHUB_TOKEN/GH_TOKEN set")

    # REST API fallback: create release then upload assets.
    api = f"https://api.github.com/repos/{status.repo_slug}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        req = urllib.request.Request(f"{api}/releases/tags/{tag}", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read().decode())
    except Exception:
        # create release
        data = json.dumps({"tag_name": tag, "name": tag, "draft": False, "prerelease": True}).encode()
        req = urllib.request.Request(
            f"{api}/releases",
            data=data,
            headers={**headers, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                release = json.loads(resp.read().decode())
        except Exception as exc:
            return UploadResult(ok=False, message=f"failed to locate/create release: {exc}", uploaded=files_to_upload)

    upload_url = release["upload_url"].replace("{?name,label}", "")
    for path in files_to_upload:
        name = os.path.basename(path)
        with open(path, "rb") as fh:
            body = fh.read()
        req = urllib.request.Request(
            f"{upload_url}?name={name}",
            data=body,
            headers={**headers, "Content-Type": "application/octet-stream", "Content-Length": str(len(body))},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as _:
                pass
        except Exception as exc:
            return UploadResult(ok=False, message=f"failed to upload {name}: {exc}", uploaded=files_to_upload)

    return UploadResult(ok=True, message=f"Uploaded {len(files_to_upload)} file(s) via REST API", uploaded=files_to_upload)
