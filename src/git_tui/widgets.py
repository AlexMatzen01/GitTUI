"""Textual widgets for Git TUI.

Keyboard (arrow keys, Tab, Enter, Esc) and left-mouse-button (LMB) driven,
with rich markup styling and bold / underlined cues per the design mandates.
"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import MouseDown
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)

from .config_store import ReleaseSettings
from .gitignore_presets import ALL_PRESETS, merge_presets, preset_keys
from .release_uploader import (
    TARGETS,
    TargetConfigError,
    load_target_commands,
)
from .versioning import CHANNEL_ORDER, SemVer, channel_color


# --------------------------------------------------------------------------- #
# messages
# --------------------------------------------------------------------------- #
class StageFile(Message):
    def __init__(self, path: str):
        super().__init__()
        self.path = path


class UnstageFile(Message):
    def __init__(self, path: str):
        super().__init__()
        self.path = path


class DiscardFile(Message):
    def __init__(self, path: str):
        super().__init__()
        self.path = path


class StageAll(Message):
    pass


class CommitRequested(Message):
    def __init__(self, message: str):
        super().__init__()
        self.message = message


class TagRequested(Message):
    def __init__(self, tag: str):
        super().__init__()
        self.tag = tag


class BumpRequested(Message):
    def __init__(self, part: str):
        super().__init__()
        self.part = part  # major | minor | patch


class DecreaseRequested(Message):
    def __init__(self, part: str):
        super().__init__()
        self.part = part  # major | minor | patch


class ChannelRequested(Message):
    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel


class PresetsSelected(Message):
    def __init__(self, keys: list[str]):
        super().__init__()
        self.keys = keys


class GitignoreWriteRequested(Message):
    def __init__(self, content: str):
        super().__init__()
        self.content = content


class StashPushRequested(Message):
    def __init__(self, message: Optional[str]):
        super().__init__()
        self.message = message


class StashApplyRequested(Message):
    def __init__(self, ref: str):
        super().__init__()
        self.ref = ref


class StashPopRequested(Message):
    def __init__(self, ref: str):
        super().__init__()
        self.ref = ref


class StashDropRequested(Message):
    def __init__(self, ref: str):
        super().__init__()
        self.ref = ref


class BranchCheckoutRequested(Message):
    def __init__(self, name: str):
        super().__init__()
        self.name = name


class BranchCreateRequested(Message):
    def __init__(self, name: str):
        super().__init__()
        self.name = name


class BranchDeleteRequested(Message):
    def __init__(self, name: str):
        super().__init__()
        self.name = name


class ReleaseConfigureRequested(Message):
    def __init__(self, settings: ReleaseSettings):
        super().__init__()
        self.settings = settings


class ReleaseUploadRequested(Message):
    def __init__(self, tag: str, files: list[str], dry_run: bool):
        super().__init__()
        self.tag = tag
        self.files = files
        self.dry_run = dry_run


class WorkflowGenerateRequested(Message):
    pass


class TargetCommandsUpdated(Message):
    def __init__(self, commands: dict[str, str]):
        super().__init__()
        self.commands = commands


# --------------------------------------------------------------------------- #
# status badge helpers
# --------------------------------------------------------------------------- #
STATUS_BADGES = {
    "staged": ("[bold #22c55e]S[/]", "Staged"),
    "modified": ("[bold #f59e0b]M[/]", "Modified"),
    "untracked": ("[bold #38bdf8]?[/]", "Untracked"),
    "conflicted": ("[bold #ef4444]![/]", "Conflicted"),
    "ignored": ("[bold #64748b]I[/]", "Ignored"),
    "deleted": ("[bold #ef4444]D[/]", "Deleted"),
    "renamed": ("[bold #c084fc]R[/]", "Renamed"),
    "copied": ("[bold #c084fc]C[/]", "Copied"),
    "added": ("[bold #22c55e]A[/]", "Added"),
}


def badge_markup(kind: str) -> str:
    markup, _label = STATUS_BADGES.get(kind, ("[bold #94a3b8]?[/]", "Unknown"))
    return markup


# --------------------------------------------------------------------------- #
# GitHub status pill
# --------------------------------------------------------------------------- #
class GitHubPill(Static):
    """Live, color-coded GitHub connection status pill with underlined URL."""

    status = reactive("No remote")

    def compose(self) -> ComposeResult:
        yield Label("", id="github-label")

    def update_status(self, connected: bool, authenticated: bool, message: str, url: str | None, slug: str | None) -> None:
        if connected:
            self.status = "[bold #22c55e]\u25cf Connected[/]"
        elif authenticated:
            self.status = "[bold #f59e0b]\u25b2 Auth Missing[/]"
        else:
            self.status = "[bold #ef4444]\u2716 Offline[/]"
        label = self.query_one("#github-label", Label)
        link = f"[underline #38bdf8]{slug or url or ''}[/]" if (slug or url) else ""
        label.update(f"GitHub: {self.status}   {link}".strip())


# --------------------------------------------------------------------------- #
# file list (staging manager)
# --------------------------------------------------------------------------- #
class FileListItem(ListItem):
    def __init__(self, kind: str, path: str, xy: str = "  "):
        super().__init__()
        self.kind = kind
        self.path = path
        self.xy = xy

    def compose(self) -> ComposeResult:
        badge = badge_markup(self.kind)
        yield Static(f"{badge}  {self.path}", classes="file-row")


class FileList(ListView):
    """Staged / unstaged / untracked files with color badges; LMB + arrow keys."""

    selected_path = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries: list[tuple[str, str, str]] = []  # (kind, path, xy)

    def load(self, entries: list[tuple[str, str, str]]) -> None:
        self._entries = entries
        self.clear()
        for kind, path, xy in entries:
            self.append(FileListItem(kind, path, xy))

    def refresh_from(self, entries: list[tuple[str, str, str]]) -> None:
        self.load(entries)

    @on(ListView.Selected)
    def _on_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, FileListItem):
            self.selected_path = item.path
            self.post_message(StageFile(item.path)) if False else None
            self.post_message(_FileActivated(item.path, item.kind))


class _FileActivated(Message):
    def __init__(self, path: str, kind: str):
        super().__init__()
        self.path = path
        self.kind = kind


# --------------------------------------------------------------------------- #
# diff viewer
# --------------------------------------------------------------------------- #
class DiffViewer(Static):
    """Color-coded inline diff: + green, - red, @@ bold cyan."""

    def show_diff(self, diff_text: str) -> None:
        if not diff_text.strip():
            self.update("[bold #94a3b8]No diff available.[/]")
            return
        lines: list[str] = []
        for line in diff_text.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                lines.append(f"[bold #94a3b8]{line}[/]")
            elif line.startswith("@@"):
                lines.append(f"[bold #38bdf8]{line}[/]")
            elif line.startswith("+"):
                lines.append(f"[bold #22c55e]{line}[/]")
            elif line.startswith("-"):
                lines.append(f"[bold #ef4444]{line}[/]")
            else:
                lines.append(f"[#64748b]{line}[/]")
        self.update("\n".join(lines))

    def show_message(self, text: str, kind: str = "info") -> None:
        colors = {
            "info": "#38bdf8",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        color = colors.get(kind, "#94a3b8")
        self.update(f"[bold {color}]{text}[/]")


# --------------------------------------------------------------------------- #
# version panel
# --------------------------------------------------------------------------- #
class VersionPanel(Vertical):
    """Semantic version editor: bump major/minor/patch, channel, tag."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.version = SemVer(0, 1, 0, "alpha")

    def compose(self) -> ComposeResult:
        yield Label("Semantic Version", classes="panel-header")
        yield Label("MAJOR.MINOR.PATCH with release channel", classes="panel-subheader")
        self.version_label = Label("", classes="version-string")
        yield self.version_label
        yield Horizontal(
            Button("Major", id="bump-major", classes="button"),
            Button("Minor", id="bump-minor", classes="button"),
            Button("Patch", id="bump-patch", classes="button"),
            classes="button-row",
        )
        yield Label("Channel", classes="input-label")
        self.channel_select = Select(
            [(ch.title(), ch) for ch in CHANNEL_ORDER],
            value=self.version.channel or "alpha",
            id="channel-select",
        )
        yield self.channel_select
        yield Horizontal(
            Button("Promote \u2192", id="channel-promote", classes="button"),
            Button("Demote \u2190", id="channel-demote", classes="button"),
            classes="button-row",
        )
        yield Horizontal(
            Button("Create Tag v...", id="create-tag", classes="button--primary"),
            Button("Preview", id="preview-version", classes="button"),
            classes="button-row",
        )
        yield Label("", id="preview-text", classes="panel-subheader")

    def set_version(self, major: int, minor: int, patch: int, channel: str) -> None:
        self.version = SemVer(major, minor, patch, channel if channel else None)
        self.refresh_display()

    def refresh_display(self) -> None:
        color = channel_color(self.version.channel)
        self.version_label.update(f"[{color} bold]{self.version}[/]")
        try:
            self.channel_select.value = self.version.channel or "alpha"
        except Exception:
            pass
        try:
            self.query_one("#preview-text", Label).update(
                f"[bold]Tag:[/] [underline #38bdf8]{self.version.tag_name('v')}[/]"
            )
        except Exception:
            pass

    @on(Button.Pressed, "#bump-major")
    def _bump_major(self) -> None:
        self.version = self.version.bump_major()
        self.refresh_display()
        self.post_message(BumpRequested("major"))

    @on(Button.Pressed, "#bump-minor")
    def _bump_minor(self) -> None:
        self.version = self.version.bump_minor()
        self.refresh_display()
        self.post_message(BumpRequested("minor"))

    @on(Button.Pressed, "#bump-patch")
    def _bump_patch(self) -> None:
        self.version = self.version.bump_patch()
        self.refresh_display()
        self.post_message(BumpRequested("patch"))

    def on_mouse_down(self, event: MouseDown) -> None:
        """Right-click on bump buttons decreases; right-click channel buttons swaps."""
        if event.button != 3:
            return
        widget_id = event.widget.id if event.widget else None
        if widget_id == "bump-major":
            event.stop()
            self.post_message(DecreaseRequested("major"))
        elif widget_id == "bump-minor":
            event.stop()
            self.post_message(DecreaseRequested("minor"))
        elif widget_id == "bump-patch":
            event.stop()
            self.post_message(DecreaseRequested("patch"))
        elif widget_id == "channel-promote":
            event.stop()
            self.version = self.version.demote()
            self.refresh_display()
            self.post_message(ChannelRequested(self.version.channel or "alpha"))
        elif widget_id == "channel-demote":
            event.stop()
            self.version = self.version.promote()
            self.refresh_display()
            self.post_message(ChannelRequested(self.version.channel or "alpha"))

    @on(Select.Changed, "#channel-select")
    def _channel_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self.version = self.version.set_channel(str(event.value))
            self.refresh_display()
            self.post_message(ChannelRequested(str(event.value)))

    @on(Button.Pressed, "#channel-promote")
    def _promote(self) -> None:
        self.version = self.version.promote()
        self.refresh_display()
        self.post_message(ChannelRequested(self.version.channel or "alpha"))

    @on(Button.Pressed, "#channel-demote")
    def _demote(self) -> None:
        self.version = self.version.demote()
        self.refresh_display()
        self.post_message(ChannelRequested(self.version.channel or "alpha"))

    @on(Button.Pressed, "#create-tag")
    def _create_tag(self) -> None:
        self.post_message(TagRequested(self.version.tag_name("v")))

    @on(Button.Pressed, "#preview-version")
    def _preview(self) -> None:
        self.refresh_display()


# --------------------------------------------------------------------------- #
# gitignore panel
# --------------------------------------------------------------------------- #
class GitignorePanel(Vertical):
    """Multi-preset .gitignore generator with merge + preview diff."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label(".gitignore Generator", classes="panel-header")
        yield Label("Select and merge presets; .git-tui is always ignored", classes="panel-subheader")
        self.preset_list = ListView(id="preset-list")
        yield self.preset_list
        yield Horizontal(
            Button("Merge Selected", id="merge-presets", classes="button--primary"),
            Button("Clear", id="clear-presets", classes="button"),
            classes="button-row",
        )
        yield Label("Preview", classes="panel-subheader")
        self.preview = DiffViewer(id="gitignore-preview")
        yield self.preview
        yield Horizontal(
            Button("Write .gitignore", id="write-gitignore", classes="button--primary"),
            Button("Toggle Rule", id="toggle-rule", classes="button"),
            classes="button-row",
        )

    def on_mount(self) -> None:
        for key in preset_keys():
            preset = ALL_PRESETS[key]
            self.preset_list.append(
                ListItem(Label(f"[bold]{preset.name}[/]  [#94a3b8]{preset.description}[/]"), id=f"preset-{key}")
            )

    @on(ListView.Selected, "#preset-list")
    def _preset_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("preset-"):
            key = item_id[len("preset-"):]
            if key in self.selected_keys:
                self.selected_keys.remove(key)
            else:
                self.selected_keys.append(key)
            event.item.styles.background = "#38bdf8" if key in self.selected_keys else ""
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        merged = merge_presets(self.selected_keys)
        content = "\n".join(merged) if merged else "# (no presets selected)"
        self.preview.show_diff(content)

    @on(Button.Pressed, "#merge-presets")
    def _merge(self) -> None:
        self._refresh_preview()
        self.post_message(PresetsSelected(list(self.selected_keys)))

    @on(Button.Pressed, "#clear-presets")
    def _clear(self) -> None:
        self.selected_keys = []
        self.preview.show_message("Presets cleared", "info")

    @on(Button.Pressed, "#write-gitignore")
    def _write(self) -> None:
        content = "\n".join(merge_presets(self.selected_keys))
        self.post_message(GitignoreWriteRequested(content))

    @on(Button.Pressed, "#toggle-rule")
    def _toggle_rule(self) -> None:
        self.preview.show_message("Select a preset to toggle its rules", "info")


# --------------------------------------------------------------------------- #
# stash panel
# --------------------------------------------------------------------------- #
class StashPanel(Vertical):
    """Branch & stash quick-drawer."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stash_ids: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("Stashes", classes="panel-header")
        self.stash_list = ListView(id="stash-list")
        yield self.stash_list
        yield Horizontal(
            Input(placeholder="Stash message", id="stash-message", classes="input"),
            Button("Push", id="stash-push", classes="button--primary"),
            classes="button-row",
        )
        yield Horizontal(
            Button("Apply", id="stash-apply", classes="button"),
            Button("Pop", id="stash-pop", classes="button"),
            Button("Drop", id="stash-drop", classes="button--danger"),
            classes="button-row",
        )

    def load(self, stashes: list[dict[str, str]]) -> None:
        self.stash_list.clear()
        self._selected_ref = ""
        for stash in stashes:
            item = ListItem(
                Label(f"[bold #c084fc]{stash['ref']}[/]  [bold]{stash['subject']}[/]")
            )
            item.stash_ref = stash["ref"]
            self.stash_list.append(item)

    @on(ListView.Selected, "#stash-list")
    def _stash_selected(self, event: ListView.Selected) -> None:
        self._selected_ref = getattr(event.item, "stash_ref", "")

    def _get_ref(self) -> str:
        return getattr(self, "_selected_ref", "") or getattr(
            self.stash_list.highlighted_child, "stash_ref", ""
        )

    @on(Button.Pressed, "#stash-push")
    def _push(self) -> None:
        msg_input = self.query_one("#stash-message", Input)
        self.post_message(StashPushRequested(msg_input.value or None))
        msg_input.value = ""

    @on(Button.Pressed, "#stash-apply")
    def _apply(self) -> None:
        ref = self._get_ref()
        if ref:
            self.post_message(StashApplyRequested(ref))

    @on(Button.Pressed, "#stash-pop")
    def _pop(self) -> None:
        ref = self._get_ref()
        if ref:
            self.post_message(StashPopRequested(ref))

    @on(Button.Pressed, "#stash-drop")
    def _drop(self) -> None:
        ref = self._get_ref()
        if ref:
            self.post_message(StashDropRequested(ref))


# --------------------------------------------------------------------------- #
# branch panel
# --------------------------------------------------------------------------- #
class BranchPanel(Vertical):
    """Branch switch / create / delete with ahead/behind badges."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._branch_ids: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("Branches", classes="panel-header")
        self.branch_list = ListView(id="branch-list")
        yield self.branch_list
        yield Horizontal(
            Input(placeholder="New branch name", id="branch-name", classes="input"),
            Button("Create", id="branch-create", classes="button--primary"),
            classes="button-row",
        )
        yield Horizontal(
            Button("Checkout", id="branch-checkout", classes="button"),
            Button("Delete", id="branch-delete", classes="button--danger"),
            classes="button-row",
        )

    def load(self, branches: list[dict[str, str]]) -> None:
        self.branch_list.clear()
        self._selected_branch = ""
        for b in branches:
            marker = "[bold #38bdf8]*[/] " if b["current"] else "  "
            track = f" [#94a3b8]{b['track']}[/]" if b["track"] else ""
            item = ListItem(
                Label(f"{marker}[bold]{b['name']}[/]{track}  [#64748b]{b['commit']}[/]")
            )
            item.branch_name = b["name"]
            self.branch_list.append(item)

    @on(ListView.Selected, "#branch-list")
    def _branch_selected(self, event: ListView.Selected) -> None:
        self._selected_branch = getattr(event.item, "branch_name", "")

    def _get_name(self) -> str:
        return getattr(self, "_selected_branch", "") or getattr(
            self.branch_list.highlighted_child, "branch_name", ""
        )

    @on(Button.Pressed, "#branch-checkout")
    def _checkout(self) -> None:
        name = self._get_name()
        if name:
            self.post_message(BranchCheckoutRequested(name))

    @on(Button.Pressed, "#branch-create")
    def _create(self) -> None:
        name_input = self.query_one("#branch-name", Input)
        name = name_input.value.strip()
        if name:
            self.post_message(BranchCreateRequested(name))
            name_input.value = ""

    @on(Button.Pressed, "#branch-delete")
    def _delete(self) -> None:
        name = self._get_name()
        if name:
            self.post_message(BranchDeleteRequested(name))


# --------------------------------------------------------------------------- #
# history panel
# --------------------------------------------------------------------------- #
class HistoryPanel(Vertical):
    """Commit history with colored short hashes and bold subjects."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._commit_ids: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("Commit History", classes="panel-header")
        self.history_list = ListView(id="history-list")
        yield self.history_list
        yield Horizontal(
            Button("Revert", id="history-revert", classes="button--danger"),
            Button("Rollback", id="history-rollback", classes="button--danger"),
            classes="button-row",
        )

    def load(self, commits: list[dict[str, str]]) -> None:
        self.history_list.clear()
        self._selected_commit = ""
        for c in commits:
            tags = f" [underline #38bdf8]{c['tags']}[/]" if c.get("tags") else ""
            item = ListItem(
                Label(
                    f"[bold #c084fc]{c['hash']}[/]  [bold]{c['subject']}[/]{tags}  "
                    f"[#94a3b8 underline]{c['author']}[/]  [#64748b]{c['date']}[/]"
                )
            )
            item.commit_hash = c["hash"]
            self.history_list.append(item)

    @on(ListView.Selected, "#history-list")
    def _history_selected(self, event: ListView.Selected) -> None:
        self._selected_commit = getattr(event.item, "commit_hash", "")

    def _get_commit(self) -> str:
        return getattr(self, "_selected_commit", "") or getattr(
            self.history_list.highlighted_child, "commit_hash", ""
        )

    @on(Button.Pressed, "#history-revert")
    def _revert(self) -> None:
        commit = self._get_commit()
        if commit:
            self.post_message(_RevertRequested(commit))

    @on(Button.Pressed, "#history-rollback")
    def _rollback(self) -> None:
        commit = self._get_commit()
        if commit:
            self.post_message(_RollbackRequested(commit))


class _RevertRequested(Message):
    def __init__(self, commit: str):
        super().__init__()
        self.commit = commit


class _RollbackRequested(Message):
    def __init__(self, commit: str):
        super().__init__()
        self.commit = commit


# --------------------------------------------------------------------------- #
# release panel
# --------------------------------------------------------------------------- #
class ReleasePanel(Vertical):
    """Automated multi-arch release binary uploader."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.target_commands: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("Release Uploader", classes="panel-header")
        yield Label("Six targets: windows/linux x86_64 / arm64 / x86", classes="panel-subheader")
        self.dry_run_checkbox = Checkbox("Dry run", id="release-dry-run", value=True)
        yield self.dry_run_checkbox
        self.sums_checkbox = Checkbox("Generate SHA256SUMS.txt", id="release-sums", value=True)
        yield self.sums_checkbox
        yield Horizontal(
            Button("Generate Workflow", id="release-workflow", classes="button"),
            Button("Edit Targets", id="release-edit-targets", classes="button"),
            Button("Upload Artifacts", id="release-upload", classes="button--primary"),
            classes="button-row",
        )
        yield Label("Target build commands", classes="panel-subheader")
        self.targets_display = Static("", id="release-targets-display")
        yield self.targets_display
        self.tag_input = Input(placeholder="Tag (e.g. v1.4.2)", id="release-tag", classes="input")
        yield self.tag_input
        self.artifact_input = Input(placeholder="Artifact globs (comma separated)", id="release-artifacts", classes="input")
        yield self.artifact_input
        self.result = Label("", id="release-result")
        yield self.result

    def on_mount(self) -> None:
        self._load_targets_display()

    def _load_targets_display(self) -> None:
        repo_root = getattr(self.app, "repo_root", None) or ""
        try:
            self.target_commands = load_target_commands(repo_root)
        except TargetConfigError as exc:
            self.target_commands = {}
            self.show_result(str(exc), "error")
            return
        if not self.target_commands:
            self.targets_display.update(
                "[#94a3b8]No target commands configured. Click [bold underline]Edit Targets[/] to create .git-tui/git-tui-targets.json[/]"
            )
            return
        lines = [f"[bold]{t}[/]: [#94a3b8]{cmd}[/]" for t, cmd in self.target_commands.items()]
        self.targets_display.update("\n".join(lines))
        self.show_result(f"Loaded {len(self.target_commands)} target commands", "info")

    @on(Button.Pressed, "#release-workflow")
    def _workflow(self) -> None:
        self.post_message(WorkflowGenerateRequested())

    @on(Button.Pressed, "#release-edit-targets")
    def _edit_targets(self) -> None:
        self.post_message(TargetCommandsUpdated(self.target_commands))

    @on(Button.Pressed, "#release-upload")
    def _upload(self) -> None:
        tag = self.tag_input.value.strip() or "HEAD"
        globs = [g.strip() for g in self.artifact_input.value.split(",") if g.strip()]
        dry_run = self.dry_run_checkbox.value
        self.post_message(ReleaseUploadRequested(tag, globs, dry_run))

    def show_result(self, text: str, kind: str = "info") -> None:
        colors = {"info": "#38bdf8", "success": "#22c55e", "warning": "#f59e0b", "error": "#ef4444"}
        self.result.update(f"[bold {colors.get(kind, '#94a3b8')}]{text}[/]")


# --------------------------------------------------------------------------- #
# modals
# --------------------------------------------------------------------------- #
class ConfirmModal(ModalScreen[bool]):
    """Confirmation dialog with bold + underlined action cues."""

    def __init__(self, prompt: str, confirm_label: str = "[bold underline]Y[/]es", cancel_label: str = "[bold underline]N[/]o"):
        super().__init__()
        self.prompt = prompt
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        yield Container(
            Label(self.prompt, id="confirm-prompt"),
            Horizontal(
                Button(self.confirm_label, id="confirm-yes", classes="button--primary"),
                Button(self.cancel_label, id="confirm-no", classes="button--danger"),
                classes="button-row",
            ),
            classes="modal",
        )

    @on(Button.Pressed, "#confirm-yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-no")
    def _no(self) -> None:
        self.dismiss(False)


class CommitModal(ModalScreen[str | None]):
    """Commit message input with conventional commit prefix selector."""

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Commit Message", classes="modal-title"),
            Select(
                [
                    ("feat:  new feature", "feat"),
                    ("fix:   bug fix", "fix"),
                    ("docs:  documentation", "docs"),
                    ("style: formatting", "style"),
                    ("refactor: code refactor", "refactor"),
                    ("test:  tests", "test"),
                    ("chore: maintenance", "chore"),
                    ("(none)", ""),
                ],
                value="",
                id="commit-prefix",
            ),
            Input(placeholder="Description", id="commit-message", classes="input"),
            Horizontal(
                Button("[bold underline]C[/]ommit", id="commit-ok", classes="button--primary"),
                Button("[bold underline]C[/]ancel", id="commit-cancel", classes="button--danger"),
                classes="button-row",
            ),
            classes="modal",
        )

    @on(Button.Pressed, "#commit-ok")
    def _ok(self) -> None:
        prefix = self.query_one("#commit-prefix", Select).value or ""
        message_input = self.query_one("#commit-message", Input)
        message = message_input.value.strip()
        full = f"{prefix}: {message}" if prefix and message else message or prefix
        self.dismiss(full or None)

    @on(Button.Pressed, "#commit-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class CheatsheetModal(ModalScreen[None]):
    """Keybind & mouse cheat-sheet modal (? or [bold underline]? Help[/])."""

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Keybind & Mouse Cheat-Sheet", classes="modal-title"),
            Vertical(
                Label("[bold #38bdf8]Navigation[/]", classes="panel-subheader"),
                Label(
                    "[bold #c084fc]\u2191\u2193\u2190\u2192[/] move focus   [bold #c084fc]Tab[/] next   "
                    "[bold #c084fc]Shift+Tab[/] prev",
                    classes="cheatsheet-item",
                ),
                Label(
                    "[bold #c084fc]Enter[/] activate   [bold #c084fc]Esc[/] back/cancel   "
                    "[bold #c084fc]q[/] quit",
                    classes="cheatsheet-item",
                ),
                Label("[bold #38bdf8]LMB[/] click tabs, buttons, list items, checkboxes, links", classes="cheatsheet-item"),
                Label("", classes="cheatsheet-item"),
                Label("[bold #38bdf8]Staging[/]", classes="panel-subheader"),
                Label(
                    "[bold underline]S[/]tage   [bold underline]U[/]nstage   "
                    "[bold underline]C[/]ommit   [bold underline]P[/]ush",
                    classes="cheatsheet-item",
                ),
                Label("", classes="cheatsheet-item"),
                Label("[bold #38bdf8]Versioning[/]", classes="panel-subheader"),
                Label(
                    "[bold underline]V[/]ersion   bump Major / Minor / Patch   "
                    "promote / demote channel   create tag",
                    classes="cheatsheet-item",
                ),
                Label("", classes="cheatsheet-item"),
                Label("[bold #38bdf8]Gitignore / Branches / History[/]", classes="panel-subheader"),
                Label(
                    "[bold underline]G[/]itignore   [bold underline]B[/]ranch   "
                    "[bold underline]H[/]istory",
                    classes="cheatsheet-item",
                ),
                Label("", classes="cheatsheet-item"),
                Label("[bold #c084fc]?[/] this help   [bold #c084fc]q[/] quit", classes="cheatsheet-item"),
            ),
            Button("[bold underline]C[/]lose", id="cheat-close", classes="button--primary"),
            classes="modal",
        )

    @on(Button.Pressed, "#cheat-close")
    def _close(self) -> None:
        self.dismiss(None)


class TargetConfigModal(ModalScreen[dict[str, str] | None]):
    """Edit per-target build commands for .git-tui/git-tui-targets.json."""

    def __init__(self, current: dict[str, str]):
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Target Build Commands", classes="modal-title"),
            Label(
                "Edit the build command for each release target. These are written to "
                ".git-tui/git-tui-targets.json and used by the release workflow.",
                classes="panel-subheader",
            ),
            Vertical(
                *[
                    Horizontal(
                        Label(f"{target}", classes="panel-subheader"),
                        Input(
                            placeholder="build command",
                            id=f"target-{target}",
                            value=self.current.get(target, ""),
                            classes="input",
                        ),
                        classes="button-row",
                    )
                    for target in TARGETS
                ],
            ),
            Horizontal(
                Button("[bold underline]S[/]ave", id="target-save", classes="button--primary"),
                Button("[bold underline]C[/]ancel", id="target-cancel", classes="button--danger"),
                classes="button-row",
            ),
            classes="modal",
        )

    @on(Button.Pressed, "#target-save")
    def _save(self) -> None:
        commands: dict[str, str] = {}
        for target in TARGETS:
            value = self.query_one(f"#target-{target}", Input).value.strip()
            commands[target] = value
        self.dismiss(commands)

    @on(Button.Pressed, "#target-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)
