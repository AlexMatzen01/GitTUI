"""Git operations wrapper.

All git invocations use ``subprocess.run`` with argument lists (``shell=False``)
and timeouts. Results are returned as structured :class:`GitResult` instances.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class GitResult:
    """Outcome of a single git invocation."""

    returncode: int
    stdout: str
    stderr: str
    ok: bool

    @property
    def lines(self) -> List[str]:
        return [line for line in self.stdout.splitlines() if line]


class GitError(RuntimeError):
    """Raised when a git command fails and the caller did not expect it."""

    def __init__(self, message: str, result: GitResult):
        super().__init__(message)
        self.result = result


def _run(
    args: List[str],
    cwd: Optional[str] = None,
    timeout: int = 30,
    env: Optional[dict] = None,
    input: Optional[str] = None,
) -> GitResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
            input=input,
        )
    except FileNotFoundError as exc:
        return GitResult(returncode=127, stdout="", stderr=str(exc), ok=False)
    except subprocess.TimeoutExpired as exc:
        return GitResult(
            returncode=124,
            stdout=exc.stdout.decode("utf-8", "replace") if exc.stdout else "",
            stderr=exc.stderr.decode("utf-8", "replace") if exc.stderr else "command timed out",
            ok=False,
        )
    return GitResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        ok=proc.returncode == 0,
    )


class GitOps:
    """Thin, structured wrapper around the ``git`` CLI."""

    def __init__(self, repo_root: str):
        self.repo_root = repo_root

    # ------------------------------------------------------------------ #
    # primitives
    # ------------------------------------------------------------------ #
    def run(self, args: List[str], timeout: int = 30, env: Optional[dict] = None, input: Optional[str] = None) -> GitResult:
        return _run(["git"] + args, cwd=self.repo_root, timeout=timeout, env=env, input=input)

    def is_repo(self) -> bool:
        result = self.run(["rev-parse", "--is-inside-work-tree"], timeout=10)
        return result.ok and result.stdout.strip() == "true"

    def repo_root_abs(self) -> str:
        result = self.run(["rev-parse", "--show-toplevel"], timeout=10)
        return result.stdout.strip() if result.ok else self.repo_root

    def current_branch(self) -> str:
        result = self.run(["rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
        return result.stdout.strip() if result.ok else "HEAD"

    # ------------------------------------------------------------------ #
    # status
    # ------------------------------------------------------------------ #
    def status_porcelain(self) -> List[tuple[str, str, str]]:
        """Return ``[(xy, index_worktree, path), ...]`` from ``git status --porcelain=v2``.

        Falls back to ``git status --porcelain`` parsing if v2 is unavailable.
        """
        result = self.run(["status", "--porcelain=v2", "--ignored"], timeout=20)
        if not result.ok:
            result = self.run(["status", "--porcelain", "--ignored"], timeout=20)
            if not result.ok:
                return []
            entries: List[tuple[str, str, str]] = []
            for line in result.lines:
                if len(line) < 3:
                    continue
                xy = line[:2]
                path = line[3:]
                entries.append((xy, xy, path))
            return entries
        entries = []
        for line in result.lines:
            parts = line.split(" ")
            if not parts:
                continue
            code = parts[0]
            if code == "!":
                # ! <path> - ignored file
                if len(parts) < 2:
                    continue
                entries.append(("!!", "!!", parts[1]))
                continue
            if code == "1":
                # 1 <xy> <sub> <mH> <mI> <mW> [<hH> <hI>] <path>
                if len(parts) < 7:
                    continue
                xy = parts[1]
                path = parts[-1]
                entries.append((xy, xy, path))
            elif code == "2":
                # 2 <xy> <mH> <mI> <mW> <path> [<orig>]
                if len(parts) < 6:
                    continue
                xy = parts[1]
                path = parts[5]
                entries.append((xy, xy, path))
        return entries

    def status_categories(self) -> dict[str, List[tuple[str, str]]]:
        """Group porcelain entries into semantic categories.

        Returns keys: staged, unstaged, untracked, conflicted, ignored.
        Each value is a list of ``(status_code, path)`` tuples.
        """
        entries = self.status_porcelain()
        staged: List[tuple[str, str]] = []
        unstaged: List[tuple[str, str]] = []
        untracked: List[tuple[str, str]] = []
        conflicted: List[tuple[str, str]] = []
        ignored: List[tuple[str, str]] = []

        for xy, _, path in entries:
            index_status = xy[0] if len(xy) > 0 else " "
            work_status = xy[1] if len(xy) > 1 else " "

            if xy.strip() in ("AA", "AU", "UA", "UD", "DU", "DD"):
                conflicted.append((xy, path))
                continue

            if index_status in ("A", "C", "M", "R", "D"):
                staged.append((xy, path))
            if work_status in ("A", "C", "M", "R", "D"):
                unstaged.append((xy, path))
            if index_status == "?" or work_status == "?":
                untracked.append((xy, path))
            if xy.strip() == "!!":
                ignored.append((xy, path))

        return {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "conflicted": conflicted,
            "ignored": ignored,
        }

    # ------------------------------------------------------------------ #
    # staging / unstaging / discarding
    # ------------------------------------------------------------------ #
    def stage(self, paths: List[str]) -> GitResult:
        if not paths:
            return GitResult(returncode=0, stdout="", stderr="", ok=True)
        return self.run(["add", "--"] + paths, timeout=60)

    def stage_all(self) -> GitResult:
        return self.run(["add", "--all"], timeout=120)

    def unstage(self, paths: List[str]) -> GitResult:
        if not paths:
            return GitResult(returncode=0, stdout="", stderr="", ok=True)
        return self.run(["restore", "--staged", "--"] + paths, timeout=60)

    def discard(self, paths: List[str]) -> GitResult:
        if not paths:
            return GitResult(returncode=0, stdout="", stderr="", ok=True)
        return self.run(["restore", "--"] + paths, timeout=60)

    # ------------------------------------------------------------------ #
    # diff
    # ------------------------------------------------------------------ #
    def diff(self, path: Optional[str] = None, staged: bool = False) -> str:
        args: List[str] = ["diff", "--color=never"]
        if staged:
            args.append("--cached")
        if path:
            args.append("--")
            args.append(path)
        result = self.run(args, timeout=30)
        return result.stdout

    def diff_stat(self) -> str:
        result = self.run(["diff", "--stat", "--color=never"], timeout=30)
        return result.stdout

    # ------------------------------------------------------------------ #
    # commits
    # ------------------------------------------------------------------ #
    def commit(self, message: str) -> GitResult:
        return self.run(["commit", "-m", message], timeout=60)

    def push(self, branch: str | None = None, remote: str = "origin") -> GitResult:
        args: List[str] = ["push"]
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        return self.run(args, timeout=120)

    def log(self, limit: int = 20) -> List[dict[str, str]]:
        fmt = "%h%x09%s%x09%an%x09%ae%x09%ad%x09%d"
        result = self.run(["log", f"-n{limit}", f"--pretty=format:{fmt}", "--date=short"], timeout=30)
        commits: List[dict[str, str]] = []
        for line in result.lines:
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            commits.append(
                {
                    "hash": parts[0],
                    "subject": parts[1],
                    "author": parts[2],
                    "email": parts[3] if len(parts) > 3 else "",
                    "date": parts[4],
                    "tags": parts[5] if len(parts) > 5 else "",
                }
            )
        return commits

    # ------------------------------------------------------------------ #
    # branches / stash
    # ------------------------------------------------------------------ #
    def branches(self) -> List[dict[str, str]]:
        result = self.run(["branch", "--format=%(refname:short)%09%(upstream:track)%09%(objectname:short)"], timeout=20)
        out: List[dict[str, str]] = []
        current = self.current_branch()
        for line in result.lines:
            parts = line.split("\t")
            name = parts[0] if parts else ""
            track = parts[1] if len(parts) > 1 else ""
            commit = parts[2] if len(parts) > 2 else ""
            out.append({"name": name, "track": track, "commit": commit, "current": name == current})
        return out

    def create_branch(self, name: str, checkout: bool = True) -> GitResult:
        args = ["checkout", "-b", name] if checkout else ["branch", name]
        return self.run(args, timeout=30)

    def checkout_branch(self, name: str) -> GitResult:
        return self.run(["checkout", name], timeout=30)

    def delete_branch(self, name: str, force: bool = False) -> GitResult:
        flag = "-D" if force else "-d"
        return self.run(["branch", flag, name], timeout=30)

    def stash_list(self) -> List[dict[str, str]]:
        result = self.run(["stash", "list", "--format=%gd%x09%s"], timeout=20)
        out: List[dict[str, str]] = []
        for line in result.lines:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                out.append({"ref": parts[0], "subject": parts[1]})
        return out

    def stash_push(self, message: Optional[str] = None) -> GitResult:
        args = ["stash", "push"]
        if message:
            args += ["-m", message]
        return self.run(args, timeout=30)

    def stash_apply(self, ref: str) -> GitResult:
        return self.run(["stash", "apply", ref], timeout=30)

    def stash_pop(self, ref: str) -> GitResult:
        return self.run(["stash", "pop", ref], timeout=30)

    def stash_drop(self, ref: str) -> GitResult:
        return self.run(["stash", "drop", ref], timeout=30)

    # ------------------------------------------------------------------ #
    # tags / remotes
    # ------------------------------------------------------------------ #
    def tags(self) -> List[str]:
        result = self.run(["tag", "--sort=-version:refname"], timeout=20)
        return result.lines

    def create_tag(self, name: str, message: Optional[str] = None) -> GitResult:
        args = ["tag"]
        if message:
            args += ["-a", name, "-m", message]
        else:
            args += [name]
        return self.run(args, timeout=30)

    def delete_tag(self, name: str) -> GitResult:
        return self.run(["tag", "-d", name], timeout=30)

    def remotes(self) -> List[dict[str, str]]:
        result = self.run(["remote", "-v"], timeout=15)
        out: List[dict[str, str]] = []
        seen = set()
        for line in result.lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            if name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "url": url})
        return out

    def remote_url(self, name: str = "origin") -> Optional[str]:
        for remote in self.remotes():
            if remote["name"] == name:
                return remote["url"]
        return None

    # ------------------------------------------------------------------ #
    # version-ish helpers
    # ------------------------------------------------------------------ #
    def describe(self) -> Optional[str]:
        result = self.run(["describe", "--tags", "--always"], timeout=15)
        return result.stdout.strip() or None

    def is_clean(self) -> bool:
        return len(self.status_porcelain()) == 0
