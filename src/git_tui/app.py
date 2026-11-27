"""Git TUI application — interactive Git terminal user interface."""

from __future__ import annotations

import glob as glob_mod
import os

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label

from .config_store import ConfigStore
from .git_ops import GitOps
from .github_client import detect_github
from .release_uploader import TargetConfigError, load_target_commands, upload_assets, write_target_commands, write_workflow
from .widgets import (
    BranchCheckoutRequested,
    BranchCreateRequested,
    BranchDeleteRequested,
    BranchPanel,
    BumpRequested,
    ChannelRequested,
    CheatsheetModal,
    CommitModal,
    ConfirmModal,
    DecreaseRequested,
    DiffViewer,
    FileList,
    GitHubPill,
    GitignorePanel,
    GitignoreWriteRequested,
    HistoryPanel,
    PresetsSelected,
    ReleasePanel,
    ReleaseUploadRequested,
    StashApplyRequested,
    StashDropRequested,
    StashPanel,
    StashPopRequested,
    StashPushRequested,
    TagRequested,
    TargetCommandsUpdated,
    TargetConfigModal,
    VersionPanel,
    WorkflowGenerateRequested,
    _FileActivated,
    _RevertRequested,
    _RollbackRequested,
)


class GitTuiApp(App[None]):
    """Main Git TUI application."""

    CSS_PATH = "styles.tcss"

    active_panel = reactive("status")

    BINDINGS = [
        ("up", "cursor_up", "Move Up"),
        ("down", "cursor_down", "Move Down"),
        ("left", "cursor_left", "Move Left"),
        ("right", "cursor_right", "Move Right"),
        ("tab", "focus_next", "Next Focus"),
        ("shift+tab", "focus_previous", "Previous Focus"),
        ("enter", "activate", "Activate"),
        ("esc", "back", "Back / Cancel"),
        ("s", "stage_selected", "Stage File"),
        ("u", "unstage_selected", "Unstage File"),
        ("S", "stage_all", "Stage All"),
        ("c", "commit_action", "Commit"),
        ("p", "push_action", "Push"),
        ("b", "show_branches", "Branches"),
        ("v", "show_versioning", "Versioning"),
        ("g", "show_gitignore", "Gitignore"),
        ("h", "show_history", "History"),
        ("t", "show_stash", "Stash"),
        ("r", "show_release", "Release"),
        ("?", "show_cheatsheet", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, repo_root: str | None = None):
        super().__init__()
        self.repo_root = os.path.abspath(repo_root or os.getcwd())
        self.git = GitOps(self.repo_root)
        self.store = ConfigStore(self.repo_root)
        self.config = self.store.load()
        self.github_status = None
        self._is_repo = self.git.is_repo()

    # ------------------------------------------------------------------ #
    # composition
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        self.github_pill = GitHubPill(id="github-pill", classes="github-pill")
        yield self.github_pill
        with Horizontal(id="title-dock", classes="header-dock"):
            yield Label("Git TUI", id="app-title", classes="header-title")
            yield Label("interactive git terminal UI", id="app-sub", classes="header-sub")

        with Horizontal(id="tab-bar", classes="tab-bar"):
            yield Button("Status", id="tab-status", classes="tab tab--active")
            yield Button("Versioning", id="tab-versioning", classes="tab")
            yield Button("Gitignore", id="tab-gitignore", classes="tab")
            yield Button("Stash", id="tab-stash", classes="tab")
            yield Button("Branches", id="tab-branches", classes="tab")
            yield Button("History", id="tab-history", classes="tab")
            yield Button("Release", id="tab-release", classes="tab")
            yield Button("Help", id="tab-help", classes="tab")

        with Horizontal(id="body"):
            with Vertical(id="sidebar", classes="slate-panel"):
                yield Label("Quick Actions", classes="panel-header")
                yield Button("[bold underline]S[/]tage", id="qa-stage", classes="button--primary")
                yield Button("[bold underline]U[/]nstage", id="qa-unstage", classes="button")
                yield Button("[bold underline]A[/]ll", id="qa-stage-all", classes="button")
                yield Button("[bold underline]D[/]iscard", id="qa-discard", classes="button--danger")
                yield Button("[bold underline]C[/]ommit", id="qa-commit", classes="button--primary")
                yield Button("[bold underline]P[/]ush", id="qa-push", classes="button")
                yield Label("", classes="panel-subheader")
                yield Label("Panels", classes="panel-subheader")
                yield Button("Versioning", id="qa-versioning", classes="button")
                yield Button("Gitignore", id="qa-gitignore", classes="button")
                yield Button("Stash", id="qa-stash", classes="button")
                yield Button("Branches", id="qa-branches", classes="button")
                yield Button("History", id="qa-history", classes="button")
                yield Button("Release", id="qa-release", classes="button")

            with VerticalScroll(id="main-content"):
                with Vertical(id="panel-status", classes="panel"):
                    yield Label("Repository Status", classes="panel-header")
                    yield Horizontal(
                        Button("[bold underline]S[/]tage All", id="btn-stage-all", classes="button--primary"),
                        Button("[bold underline]R[/]efresh", id="btn-refresh", classes="button"),
                        classes="button-row",
                    )
                    self.file_list = FileList(id="status-file-list")
                    yield self.file_list
                    yield Label("", id="status-hint")

                yield VersionPanel(id="panel-versioning")
                yield GitignorePanel(id="panel-gitignore")
                yield StashPanel(id="panel-stash")
                yield BranchPanel(id="panel-branches")
                yield HistoryPanel(id="panel-history")
                yield ReleasePanel(id="panel-release")

                yield Label("Diff Preview", classes="panel-header")
                self.diff_viewer = DiffViewer(id="diff-viewer")
                yield self.diff_viewer

        yield Footer()

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def on_mount(self) -> None:
        self.title = "Git TUI"
        self._hide_all_panels()
        self.query_one("#panel-status").display = True
        self._update_title()
        self._refresh_github()
        self._refresh_status()
        if not self._is_repo:
            self.diff_viewer.show_message("Not a Git repository", "error")

    def watch_active_panel(self, old_value: str, new_value: str) -> None:
        self._hide_all_panels()
        try:
            self.query_one(f"#panel-{new_value}").display = True
        except Exception:
            pass
        self._set_active_tab(new_value)
        self._refresh_for_panel(new_value)
        self._update_title()

    def _hide_all_panels(self) -> None:
        for panel_id in (
            "status", "versioning", "gitignore", "stash", "branches", "history", "release",
        ):
            try:
                self.query_one(f"#panel-{panel_id}").display = False
            except Exception:
                pass

    def _set_active_tab(self, panel: str) -> None:
        tab_map = {
            "status": "tab-status",
            "versioning": "tab-versioning",
            "gitignore": "tab-gitignore",
            "stash": "tab-stash",
            "branches": "tab-branches",
            "history": "tab-history",
            "release": "tab-release",
        }
        for button_id in tab_map.values():
            button = self.query_one(f"#{button_id}", Button)
            button.remove_class("tab--active")
        active_id = tab_map.get(panel)
        if active_id:
            self.query_one(f"#{active_id}", Button).add_class("tab--active")

    def _update_title(self) -> None:
        title = self.query_one("#app-title", Label)
        sub = self.query_one("#app-sub", Label)
        titles = {
            "status": ("Repository Status", "staged / unstaged / untracked files"),
            "versioning": ("Semantic Versioning", "major.minor.patch + release channel"),
            "gitignore": (".gitignore Generator", "merge presets, preview, write"),
            "stash": ("Stash Drawer", "create / apply / pop / drop stashes"),
            "branches": ("Branches", "switch / create / delete branches"),
            "history": ("Commit History", "browse / revert / rollback"),
            "release": ("Release Uploader", "multi-arch binary uploads"),
        }
        t, s = titles.get(self.active_panel, ("Git TUI", ""))
        title.update(t)
        sub.update(s)

    def _refresh_for_panel(self, panel: str) -> None:
        if not self._is_repo:
            return
        if panel == "status":
            self._refresh_status()
        elif panel == "versioning":
            self._refresh_versioning()
        elif panel == "gitignore":
            self._refresh_gitignore()
        elif panel == "stash":
            self._refresh_stash()
        elif panel == "branches":
            self._refresh_branches()
        elif panel == "history":
            self._refresh_history()
        elif panel == "release":
            try:
                self.query_one("#panel-release", ReleasePanel)._load_targets_display()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # refresh helpers
    # ------------------------------------------------------------------ #
    def _refresh_status(self) -> None:
        categories = self.git.status_categories()
        entries: list[tuple[str, str, str]] = []
        for kind, items in (
            ("staged", categories["staged"]),
            ("modified", categories["unstaged"]),
            ("untracked", categories["untracked"]),
            ("conflicted", categories["conflicted"]),
            ("ignored", categories["ignored"]),
        ):
            for xy, path in items:
                entries.append((kind, path, xy))
        self.file_list.refresh_from(entries)
        total = sum(len(v) for v in categories.values())
        hint = self.query_one("#status-hint", Label)
        hint.update(
            f"[bold]{total}[/] changed  "
            f"[#22c55e]{len(categories['staged'])} staged[/]  "
            f"[#f59e0b]{len(categories['unstaged'])} modified[/]  "
            f"[#38bdf8]{len(categories['untracked'])} untracked[/]  "
            f"[#ef4444]{len(categories['conflicted'])} conflicted[/]"
        )

    def _refresh_versioning(self) -> None:
        vs = self.config.version_state
        panel = self.query_one("#panel-versioning", VersionPanel)
        panel.set_version(vs.major, vs.minor, vs.patch, vs.channel)

    def _refresh_gitignore(self) -> None:
        panel = self.query_one("#panel-gitignore", GitignorePanel)
        panel.selected_keys = list(self.config.selected_presets)
        panel._refresh_preview()

    def _refresh_stash(self) -> None:
        panel = self.query_one("#panel-stash", StashPanel)
        panel.load(self.git.stash_list())

    def _refresh_branches(self) -> None:
        panel = self.query_one("#panel-branches", BranchPanel)
        panel.load(self.git.branches())

    def _refresh_history(self) -> None:
        panel = self.query_one("#panel-history", HistoryPanel)
        panel.load(self.git.log(30))

    def _refresh_github(self) -> None:
        status = detect_github(self.repo_root)
        self.github_status = status
        self.github_pill.update_status(
            status.connected, status.authenticated, status.message,
            status.remote_url, status.repo_slug,
        )

    # ------------------------------------------------------------------ #
    # navigation actions
    # ------------------------------------------------------------------ #
    def action_show_branches(self) -> None:
        self.active_panel = "branches"

    def action_show_versioning(self) -> None:
        self.active_panel = "versioning"

    def action_show_gitignore(self) -> None:
        self.active_panel = "gitignore"

    def action_show_stash(self) -> None:
        self.active_panel = "stash"

    def action_show_history(self) -> None:
        self.active_panel = "history"

    def action_show_release(self) -> None:
        self.active_panel = "release"

    def action_show_cheatsheet(self) -> None:
        self.push_screen(CheatsheetModal())

    def action_back(self) -> None:
        self.active_panel = "status"

    # ------------------------------------------------------------------ #
    # staging / commit
    # ------------------------------------------------------------------ #
    def action_stage_selected(self) -> None:
        path = self.file_list.selected_path
        if path:
            self.git.stage([path])
            self._refresh_status()

    def action_unstage_selected(self) -> None:
        path = self.file_list.selected_path
        if path:
            self.git.unstage([path])
            self._refresh_status()

    def action_stage_all(self) -> None:
        self.git.stage_all()
        self._refresh_status()

    @on(Button.Pressed, "#btn-stage-all")
    def _btn_stage_all(self) -> None:
        self.action_stage_all()

    @on(Button.Pressed, "#btn-refresh")
    def _btn_refresh(self) -> None:
        self._refresh_status()
        self._refresh_github()

    @on(Button.Pressed, "#qa-stage")
    def _qa_stage(self) -> None:
        self.action_stage_selected()

    @on(Button.Pressed, "#qa-unstage")
    def _qa_unstage(self) -> None:
        self.action_unstage_selected()

    @on(Button.Pressed, "#qa-stage-all")
    def _qa_stage_all(self) -> None:
        self.action_stage_all()

    @on(Button.Pressed, "#qa-discard")
    def _qa_discard(self) -> None:
        path = self.file_list.selected_path
        if path:
            self.push_screen(ConfirmModal(f"Discard unstaged changes to {path}?"), self._on_discard_confirm)

    def _on_discard_confirm(self, confirmed: bool | None) -> None:
        if confirmed:
            path = self.file_list.selected_path
            if path:
                self.git.discard([path])
                self._refresh_status()

    @on(Button.Pressed, "#qa-commit")
    def _qa_commit(self) -> None:
        self.action_commit()

    def action_commit(self) -> None:
        self.push_screen(CommitModal(), self._on_commit_result)

    def _on_commit_result(self, message: str | None) -> None:
        if message:
            result = self.git.commit(message)
            if result.ok:
                self.diff_viewer.show_message(f"Committed: {message}", "success")
            else:
                self.diff_viewer.show_message(f"Commit failed: {result.stderr.strip()}", "error")
            self._refresh_status()

    @on(Button.Pressed, "#qa-push")
    def _qa_push(self) -> None:
        self.action_push()

    def action_push(self) -> None:
        branch = self.git.current_branch()
        result = self.git.run(["push", "-u", "origin", branch], timeout=120)
        if result.ok:
            self.diff_viewer.show_message(f"Pushed branch {branch}", "success")
        else:
            self.diff_viewer.show_message(f"Push failed: {result.stderr.strip()}", "error")
        self._refresh_github()

    # ------------------------------------------------------------------ #
    # file list activation
    # ------------------------------------------------------------------ #
    @on(_FileActivated)
    def _on_file_activated(self, message: _FileActivated) -> None:
        kind = message.kind
        path = message.path
        if kind in ("staged", "added"):
            self.git.unstage([path])
        elif kind in ("modified", "deleted", "renamed", "copied", "untracked"):
            self.git.stage([path])
        elif kind in ("conflicted", "ignored"):
            self.diff_viewer.show_message(f"Cannot stage {kind} file directly", "warning")
        self._refresh_status()

    # ------------------------------------------------------------------ #
    # versioning
    # ------------------------------------------------------------------ #
    @on(BumpRequested)
    def _on_bump(self, message: BumpRequested) -> None:
        vs = self.config.version_state
        part = message.part
        if part == "major":
            vs.major += 1
            vs.minor = 0
            vs.patch = 0
        elif part == "minor":
            vs.minor += 1
            vs.patch = 0
        else:
            vs.patch += 1
        self.store.set_version(vs.major, vs.minor, vs.patch, vs.channel)
        self.store.save()
        self._refresh_versioning()

    @on(DecreaseRequested)
    def _on_decrease(self, message: DecreaseRequested) -> None:
        vs = self.config.version_state
        part = message.part
        if part == "major":
            vs.major = max(0, vs.major - 1)
            vs.minor = 0
            vs.patch = 0
        elif part == "minor":
            vs.minor = max(0, vs.minor - 1)
            vs.patch = 0
        else:
            vs.patch = max(0, vs.patch - 1)
        self.store.set_version(vs.major, vs.minor, vs.patch, vs.channel)
        self.store.save()
        self._refresh_versioning()

    @on(ChannelRequested)
    def _on_channel(self, message: ChannelRequested) -> None:
        vs = self.config.version_state
        self.store.set_version(vs.major, vs.minor, vs.patch, message.channel)
        self.store.save()
        self._refresh_versioning()

    @on(TagRequested)
    def _on_tag(self, message: TagRequested) -> None:
        result = self.git.create_tag(message.tag)
        if result.ok:
            self.store.set_last_tag(message.tag)
            self.store.save()
            self.diff_viewer.show_message(f"Tag {message.tag} created", "success")
        else:
            self.diff_viewer.show_message(f"Tag failed: {result.stderr.strip()}", "error")
        self._refresh_versioning()

    # ------------------------------------------------------------------ #
    # gitignore
    # ------------------------------------------------------------------ #
    @on(PresetsSelected)
    def _on_presets_selected(self, message: PresetsSelected) -> None:
        self.config.selected_presets = list(message.keys)
        self.store.set_selected_presets(self.config.selected_presets)
        self.store.save()

    @on(GitignoreWriteRequested)
    def _on_gitignore_write(self, message: GitignoreWriteRequested) -> None:
        path = os.path.join(self.repo_root, ".gitignore")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(message.content)
        self.diff_viewer.show_message(".gitignore written", "success")
        self._refresh_status()

    # ------------------------------------------------------------------ #
    # stash
    # ------------------------------------------------------------------ #
    @on(StashPushRequested)
    def _on_stash_push(self, message: StashPushRequested) -> None:
        result = self.git.stash_push(message.message)
        if result.ok:
            self.diff_viewer.show_message("Stash pushed", "success")
        else:
            self.diff_viewer.show_message(f"Stash failed: {result.stderr.strip()}", "error")
        self._refresh_stash()

    @on(StashApplyRequested)
    def _on_stash_apply(self, message: StashApplyRequested) -> None:
        result = self.git.stash_apply(message.ref)
        if result.ok:
            self.diff_viewer.show_message(f"Stash {message.ref} applied", "success")
        else:
            self.diff_viewer.show_message(f"Stash apply failed: {result.stderr.strip()}", "error")
        self._refresh_stash()

    @on(StashPopRequested)
    def _on_stash_pop(self, message: StashPopRequested) -> None:
        result = self.git.stash_pop(message.ref)
        if result.ok:
            self.diff_viewer.show_message(f"Stash {message.ref} popped", "success")
        else:
            self.diff_viewer.show_message(f"Stash pop failed: {result.stderr.strip()}", "error")
        self._refresh_stash()

    @on(StashDropRequested)
    def _on_stash_drop(self, message: StashDropRequested) -> None:
        result = self.git.stash_drop(message.ref)
        if result.ok:
            self.diff_viewer.show_message(f"Stash {message.ref} dropped", "success")
        else:
            self.diff_viewer.show_message(f"Stash drop failed: {result.stderr.strip()}", "error")
        self._refresh_stash()

    # ------------------------------------------------------------------ #
    # branches
    # ------------------------------------------------------------------ #
    @on(BranchCheckoutRequested)
    def _on_branch_checkout(self, message: BranchCheckoutRequested) -> None:
        result = self.git.checkout_branch(message.name)
        if result.ok:
            self.diff_viewer.show_message(f"Switched to {message.name}", "success")
        else:
            self.diff_viewer.show_message(f"Checkout failed: {result.stderr.strip()}", "error")
        self._refresh_branches()
        self._refresh_status()

    @on(BranchCreateRequested)
    def _on_branch_create(self, message: BranchCreateRequested) -> None:
        result = self.git.create_branch(message.name)
        if result.ok:
            self.diff_viewer.show_message(f"Branch {message.name} created", "success")
        else:
            self.diff_viewer.show_message(f"Create failed: {result.stderr.strip()}", "error")
        self._refresh_branches()

    @on(BranchDeleteRequested)
    def _on_branch_delete(self, message: BranchDeleteRequested) -> None:
        self.push_screen(
            ConfirmModal(f"Delete branch {message.name}?"),
            lambda confirmed: self._do_delete_branch(message.name, confirmed),
        )

    def _do_delete_branch(self, name: str, confirmed: bool | None) -> None:
        if confirmed:
            result = self.git.delete_branch(name)
            if result.ok:
                self.diff_viewer.show_message(f"Branch {name} deleted", "success")
            else:
                self.diff_viewer.show_message(f"Delete failed: {result.stderr.strip()}", "error")
            self._refresh_branches()

    # ------------------------------------------------------------------ #
    # history
    # ------------------------------------------------------------------ #
    @on(_RevertRequested)
    def _on_revert(self, message: _RevertRequested) -> None:
        self.push_screen(
            ConfirmModal(f"Revert commit {message.commit}?"),
            lambda confirmed: self._do_revert(message.commit, confirmed),
        )

    def _do_revert(self, commit: str, confirmed: bool | None) -> None:
        if confirmed:
            result = self.git.run(["revert", "--no-edit", commit], timeout=120)
            if result.ok:
                self.diff_viewer.show_message(f"Reverted {commit}", "success")
            else:
                self.diff_viewer.show_message(f"Revert failed: {result.stderr.strip()}", "error")
            self._refresh_history()
            self._refresh_status()

    @on(_RollbackRequested)
    def _on_rollback(self, message: _RollbackRequested) -> None:
        self.push_screen(
            ConfirmModal(f"Reset hard to {message.commit}? (discards changes)"),
            lambda confirmed: self._do_rollback(message.commit, confirmed),
        )

    def _do_rollback(self, commit: str, confirmed: bool | None) -> None:
        if confirmed:
            result = self.git.run(["reset", "--hard", commit], timeout=120)
            if result.ok:
                self.diff_viewer.show_message(f"Rolled back to {commit}", "success")
            else:
                self.diff_viewer.show_message(f"Rollback failed: {result.stderr.strip()}", "error")
            self._refresh_history()
            self._refresh_status()

    # ------------------------------------------------------------------ #
    # release
    # ------------------------------------------------------------------ #
    @on(WorkflowGenerateRequested)
    def _on_workflow(self) -> None:
        workflow_dir = os.path.join(self.repo_root, ".github", "workflows")
        try:
            target_commands = load_target_commands(self.repo_root)
        except TargetConfigError as exc:
            self.diff_viewer.show_message(str(exc), "error")
            return
        path = write_workflow(
            workflow_dir,
            self.github_status.repo_slug if self.github_status else None,
            target_commands=target_commands,
        )
        self.diff_viewer.show_message(f"Workflow written: {path}", "success")

    @on(TargetCommandsUpdated)
    def _on_target_commands_updated(self, message: TargetCommandsUpdated) -> None:
        self.push_screen(TargetConfigModal(message.commands), self._on_target_config_result)

    def _on_target_config_result(self, commands: dict[str, str] | None) -> None:
        if commands is None:
            return
        try:
            path = write_target_commands(self.repo_root, commands)
        except TargetConfigError as exc:
            self.diff_viewer.show_message(str(exc), "error")
            return
        self.diff_viewer.show_message(f"Target commands written: {path}", "success")
        # Refresh the release panel display
        try:
            panel = self.query_one("#panel-release", ReleasePanel)
            panel._load_targets_display()
        except Exception:
            pass

    @on(ReleaseUploadRequested)
    def _on_release_upload(self, message: ReleaseUploadRequested) -> None:
        files: list[str] = []
        for pattern in message.files:
            if "*" in pattern or "?" in pattern:
                files.extend(glob_mod.glob(os.path.join(self.repo_root, pattern)))
            elif os.path.exists(os.path.join(self.repo_root, pattern)):
                files.append(os.path.join(self.repo_root, pattern))
        result = upload_assets(self.repo_root, message.tag, files, dry_run=message.dry_run, generate_sums=True)
        self.query_one("#panel-release", ReleasePanel).show_result(
            result.message, "success" if result.ok else "error"
        )

    # ------------------------------------------------------------------ #
    # tab bar
    # ------------------------------------------------------------------ #
    @on(Button.Pressed, "#tab-status")
    def _tab_status(self) -> None:
        self.active_panel = "status"

    @on(Button.Pressed, "#tab-versioning")
    def _tab_versioning(self) -> None:
        self.active_panel = "versioning"

    @on(Button.Pressed, "#tab-gitignore")
    def _tab_gitignore(self) -> None:
        self.active_panel = "gitignore"

    @on(Button.Pressed, "#tab-stash")
    def _tab_stash(self) -> None:
        self.active_panel = "stash"

    @on(Button.Pressed, "#tab-branches")
    def _tab_branches(self) -> None:
        self.active_panel = "branches"

    @on(Button.Pressed, "#tab-history")
    def _tab_history(self) -> None:
        self.active_panel = "history"

    @on(Button.Pressed, "#tab-release")
    def _tab_release(self) -> None:
        self.active_panel = "release"

    @on(Button.Pressed, "#tab-help")
    def _tab_help(self) -> None:
        self.action_show_cheatsheet()

    @on(Button.Pressed, "#qa-versioning")
    def _qa_versioning(self) -> None:
        self.active_panel = "versioning"

    @on(Button.Pressed, "#qa-gitignore")
    def _qa_gitignore(self) -> None:
        self.active_panel = "gitignore"

    @on(Button.Pressed, "#qa-stash")
    def _qa_stash(self) -> None:
        self.active_panel = "stash"

    @on(Button.Pressed, "#qa-branches")
    def _qa_branches(self) -> None:
        self.active_panel = "branches"

    @on(Button.Pressed, "#qa-history")
    def _qa_history(self) -> None:
        self.active_panel = "history"

    @on(Button.Pressed, "#qa-release")
    def _qa_release(self) -> None:
        self.active_panel = "release"


def main() -> None:
    app = GitTuiApp()
    app.run()


if __name__ == "__main__":
    main()
