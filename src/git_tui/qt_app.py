"""Git TUI — PyQt6 GUI application.

A richly styled, animated desktop Git interface. Shares the core logic
modules (git_ops, config_store, versioning, gitignore_presets,
github_client, release_uploader) with the Textual TUI.
"""

from __future__ import annotations

import glob as glob_mod
import os
import subprocess as subprocess_mod
import sys

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt6.QtGui import QFont, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .config_store import ConfigStore
from .git_ops import GitOps
from .github_client import detect_github
from .gitignore_presets import ALL_PRESETS, merge_presets, preset_keys
from .global_config import GlobalConfigStore
from .release_uploader import (
    TargetConfigError,
    load_target_commands,
    upload_assets,
    write_target_commands,
    write_workflow,
)

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #
from .styles import (
    AMBER,
    CRIMSON,
    EMERALD,
    FOCUS,
    MUTED,
    SKY,
    SLATE_BG,
    SLATE_BORDER,
    SLATE_PANEL,
    TEXT,
    VIOLET,
    rgb,
    style_button,
    style_input,
    style_label,
)
from .versioning import SemVer, channel_color
from .wizard import WizardDialog


# --------------------------------------------------------------------------- #
# worker thread for long-running git / github operations
# --------------------------------------------------------------------------- #
class GitWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# --------------------------------------------------------------------------- #
# animated panel
# --------------------------------------------------------------------------- #
class AnimatedPanel(QWidget):
    """A panel that fades in/out when shown/hidden."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def fade_in(self):
        self.show()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def fade_out(self, callback=None):
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(lambda: self._on_fade_done(callback))
        self._anim.start()

    def _on_fade_done(self, callback):
        self.hide()
        if callback:
            callback()


# --------------------------------------------------------------------------- #
# styled helpers (imported from .styles)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# main window
# --------------------------------------------------------------------------- #
class GitTuiQtApp(QMainWindow):
    """PyQt6 Git TUI application."""

    def __init__(self, repo_root: str | None = None, global_store: GlobalConfigStore | None = None):
        super().__init__()
        self.global_store = global_store or GlobalConfigStore()
        self.global_config = self.global_store.load()

        # First-run wizard
        if not self.global_config.wizard_completed:

            wizard = WizardDialog(self.global_store, self)
            if wizard.exec() == QDialog.DialogCode.Accepted:
                self.global_config = self.global_store.load()
            else:
                # User closed wizard; still allow running but mark incomplete
                pass

        # Resolve repo root: CLI arg > global default > cwd
        resolved = repo_root or self.global_config.default_repo or os.getcwd()
        self.repo_root = os.path.abspath(resolved)
        self.git = GitOps(self.repo_root)
        self.store = ConfigStore(self.repo_root)
        self.config = self.store.load()
        self.github_status = None
        self._is_repo = self.git.is_repo()
        self._programmatic_change = False

        self.setWindowTitle("Git TUI")
        self.resize(self.global_config.window_width, self.global_config.window_height)
        self._apply_palette()
        self._build_ui()
        self._refresh_github()
        if self._is_repo:
            self._refresh_status()
            self._refresh_versioning()
        else:
            self.status_label.setText("Not a Git repository")
            self.status_label.setStyleSheet(f"color: {CRIMSON}; font-weight: bold;")

    def closeEvent(self, event):
        self.global_store.set_window_size(self.width(), self.height())
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # palette / theme
    # ------------------------------------------------------------------ #
    def _apply_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, rgb(SLATE_BG))
        palette.setColor(QPalette.ColorRole.WindowText, rgb(TEXT))
        palette.setColor(QPalette.ColorRole.Base, rgb(SLATE_PANEL))
        palette.setColor(QPalette.ColorRole.AlternateBase, rgb(SLATE_PANEL))
        palette.setColor(QPalette.ColorRole.Text, rgb(TEXT))
        palette.setColor(QPalette.ColorRole.Button, rgb(SLATE_PANEL))
        palette.setColor(QPalette.ColorRole.ButtonText, rgb(TEXT))
        self.setPalette(palette)
        self.setStyleSheet(
            f"""
            QMainWindow {{ background: {SLATE_BG}; }}
            QSplitter::handle {{ background: {SLATE_BORDER}; }}
            QTableWidget {{ background: {SLATE_PANEL}; color: {TEXT}; gridline-color: {SLATE_BORDER}; border: none; }}
            QTableWidget::item {{ padding: 4px; border: none; }}
            QTableWidget::item:selected {{ background: {FOCUS}; color: {SLATE_BG}; }}
            QHeaderView::section {{ background: {SLATE_PANEL}; color: {MUTED}; border: none; padding: 6px; font-weight: bold; }}
            QListWidget {{ background: {SLATE_PANEL}; color: {TEXT}; border: 1px solid {SLATE_BORDER}; border-radius: 6px; }}
            QListWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {SLATE_BORDER}; }}
            QListWidget::item:selected {{ background: {FOCUS}; color: {SLATE_BG}; }}
            QTextEdit {{ background: #0f172a; color: {TEXT}; border: 1px solid {SLATE_BORDER}; border-radius: 6px; }}
            QScrollBar:vertical {{ background: {SLATE_BG}; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {SLATE_BORDER}; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
            """
        )

    # ------------------------------------------------------------------ #
    # ui build
    # ------------------------------------------------------------------ #
    def _build_ui(self):  # noqa: PLR0915
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background: {SLATE_BG}; border-bottom: 1px solid {SLATE_BORDER};")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Git TUI")
        title.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 18px;")
        sub = QLabel("interactive git desktop UI")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        vtitle = QVBoxLayout()
        vtitle.setContentsMargins(0, 0, 0, 0)
        vtitle.setSpacing(0)
        vtitle.addWidget(title)
        vtitle.addWidget(sub)
        hlay.addLayout(vtitle)
        hlay.addStretch()
        self.github_label = QLabel("GitHub: detecting…")
        style_label(self.github_label, "muted")
        hlay.addWidget(self.github_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet(f"background: {SLATE_PANEL}; border-right: 1px solid {SLATE_BORDER};")
        slay = QVBoxLayout(sidebar)
        slay.setContentsMargins(12, 16, 12, 16)
        slay.setSpacing(8)
        slay.addWidget(QLabel("NAVIGATION"))
        slay.itemAt(0).widget().setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")

        self.nav_btns = {}
        for label, panel_id, kind in [
            ("Status", "status", "primary"),
            ("Versioning", "versioning", "ghost"),
            (".gitignore", "gitignore", "ghost"),
            ("Stash", "stash", "ghost"),
            ("Branches", "branches", "ghost"),
            ("History", "history", "ghost"),
            ("Release", "release", "ghost"),
        ]:
            btn = QPushButton(label)
            style_button(btn, kind)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=None, pid=panel_id: self.show_panel(pid))
            self.nav_btns[panel_id] = btn
            slay.addWidget(btn)
        slay.addStretch()

        quit_btn = QPushButton("Quit")
        style_button(quit_btn, "danger")
        quit_btn.clicked.connect(self.close)
        slay.addWidget(quit_btn)

        # content
        self.stack = QStackedWidget()
        self.status_panel = self._build_status_panel()
        self.version_panel = self._build_version_panel()
        self.gitignore_panel = self._build_gitignore_panel()
        self.stash_panel = self._build_stash_panel()
        self.branch_panel = self._build_branch_panel()
        self.history_panel = self._build_history_panel()
        self.release_panel = self._build_release_panel()
        for p in (
            self.status_panel,
            self.version_panel,
            self.gitignore_panel,
            self.stash_panel,
            self.branch_panel,
            self.history_panel,
            self.release_panel,
        ):
            self.stack.addWidget(p)

        splitter.addWidget(sidebar)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(header)
        root.addWidget(splitter)

        self.show_panel("status")

    # ------------------------------------------------------------------ #
    # panels
    # ------------------------------------------------------------------ #
    def _panel_scroll(self) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setStyleSheet("background: transparent;")
        return area

    def _build_status_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        h = QLabel("Repository Status")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)

        btn_row = QHBoxLayout()
        stage_all = QPushButton("Stage All")
        style_button(stage_all, "success")
        stage_all.clicked.connect(self._stage_all)
        stage_selected = QPushButton("Stage Selected")
        style_button(stage_selected, "success")
        stage_selected.clicked.connect(self._stage_selected)
        unstage_all = QPushButton("Unstage All")
        style_button(unstage_all, "ghost")
        unstage_all.clicked.connect(self._unstage_all)
        unstage_selected = QPushButton("Unstage Selected")
        style_button(unstage_selected, "ghost")
        unstage_selected.clicked.connect(self._unstage_selected)
        discard_all = QPushButton("Discard All")
        style_button(discard_all, "danger")
        discard_all.clicked.connect(self._discard_all)
        commit_btn = QPushButton("Commit")
        style_button(commit_btn, "primary")
        commit_btn.clicked.connect(self._commit)
        push_btn = QPushButton("Push")
        style_button(push_btn, "primary")
        push_btn.clicked.connect(self._push)
        refresh = QPushButton("Refresh")
        style_button(refresh, "ghost")
        refresh.clicked.connect(self._refresh_status)
        for b in (stage_all, stage_selected, unstage_all, unstage_selected, discard_all, commit_btn, push_btn, refresh):
            btn_row.addWidget(b)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderLabels(["", "File", "Status"])
        self.status_tree.setColumnWidth(0, 30)
        self.status_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.status_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.status_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.status_tree.itemChanged.connect(self._on_item_checked)
        self.status_tree.setAlternatingRowColors(True)
        self.status_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.status_tree)

        self.status_hint = QLabel("")
        style_label(self.status_hint, "muted")
        lay.addWidget(self.status_hint)

        lay.addStretch()
        return panel

    def _build_version_panel(self) -> QWidget:  # noqa: PLR0915
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        h = QLabel("Semantic Versioning")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)

        sub = QLabel("MAJOR.MINOR.PATCH with release channel — type values directly")
        style_label(sub, "muted")
        lay.addWidget(sub)

        # version input row
        ver_row = QHBoxLayout()
        self.ver_major = QLineEdit("0")
        self.ver_minor = QLineEdit("1")
        self.ver_patch = QLineEdit("0")
        for le in (self.ver_major, self.ver_minor, self.ver_patch):
            style_input(le)
            le.setFixedWidth(80)
            le.setMaxLength(6)
            le.textEdited.connect(self._on_version_edited)
        lbl_major = QLabel("Major")
        style_label(lbl_major, "muted")
        ver_row.addWidget(lbl_major)
        ver_row.addWidget(self.ver_major)
        lbl_minor = QLabel("Minor")
        style_label(lbl_minor, "muted")
        ver_row.addWidget(lbl_minor)
        ver_row.addWidget(self.ver_minor)
        lbl_patch = QLabel("Patch")
        style_label(lbl_patch, "muted")
        ver_row.addWidget(lbl_patch)
        ver_row.addWidget(self.ver_patch)
        ver_row.addStretch()
        lay.addLayout(ver_row)

        # channel
        ch_row = QHBoxLayout()
        lbl_channel = QLabel("Channel")
        style_label(lbl_channel, "muted")
        ch_row.addWidget(lbl_channel)
        self.ver_channel = QLineEdit()
        style_input(self.ver_channel)
        self.ver_channel.setFixedWidth(140)
        self.ver_channel.textEdited.connect(self._on_version_edited)
        ch_row.addWidget(self.ver_channel)
        ch_row.addStretch()
        lay.addLayout(ch_row)

        # preview
        self.ver_preview = QLabel("v0.1.0-alpha")
        self.ver_preview.setStyleSheet(f"color: {VIOLET}; font-weight: bold; font-size: 18px;")
        lay.addWidget(self.ver_preview)

        # tag button
        tag_btn = QPushButton("Create Tag v...")
        style_button(tag_btn, "success")
        tag_btn.clicked.connect(self._create_tag)
        lay.addWidget(tag_btn)

        # push tag button
        push_tag_btn = QPushButton("Push Tag v...")
        style_button(push_tag_btn, "primary")
        push_tag_btn.clicked.connect(self._push_tag)
        lay.addWidget(push_tag_btn)

        lay.addStretch()
        return panel

    def _build_gitignore_panel(self) -> QWidget:  # noqa: PLR0915
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        h = QLabel(".gitignore Generator")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)
        sub = QLabel("Select and merge presets. .git-tui is always ignored.")
        style_label(sub, "muted")
        lay.addWidget(sub)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.addWidget(QLabel("Presets"))
        self.preset_list = QListWidget()
        self.preset_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for key in preset_keys():
            p = ALL_PRESETS[key]
            item = QListWidgetItem(f"{p.name}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(p.description)
            self.preset_list.addItem(item)
        self.preset_list.itemSelectionChanged.connect(self._on_preset_select)
        llay.addWidget(self.preset_list)
        presets_btn_row = QHBoxLayout()
        merge_btn = QPushButton("Merge Selected")
        style_button(merge_btn, "primary")
        merge_btn.clicked.connect(self._merge_presets)
        clear_btn = QPushButton("Clear")
        style_button(clear_btn, "ghost")
        clear_btn.clicked.connect(self._clear_presets)
        presets_btn_row.addWidget(merge_btn)
        presets_btn_row.addWidget(clear_btn)
        llay.addLayout(presets_btn_row)

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(QLabel("Preview"))
        self.gitignore_preview = QTextEdit()
        self.gitignore_preview.setReadOnly(True)
        self.gitignore_preview.setFixedHeight(260)
        rlay.addWidget(self.gitignore_preview)
        write_row = QHBoxLayout()
        write_btn = QPushButton("Write .gitignore")
        style_button(write_btn, "success")
        write_btn.clicked.connect(self._write_gitignore)
        write_row.addWidget(write_btn)
        write_row.addStretch()
        rlay.addLayout(write_row)
        rlay.addStretch()

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split)
        lay.addStretch()
        return panel

    def _build_stash_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        h = QLabel("Stash Drawer")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)
        self.stash_list = QListWidget()
        lay.addWidget(self.stash_list)
        row = QHBoxLayout()
        self.stash_msg = QLineEdit()
        self.stash_msg.setPlaceholderText("Stash message")
        style_input(self.stash_msg)
        push_btn = QPushButton("Push")
        style_button(push_btn, "success")
        push_btn.clicked.connect(self._stash_push)
        row.addWidget(self.stash_msg)
        row.addWidget(push_btn)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        pop_btn = QPushButton("Pop")
        drop_btn = QPushButton("Drop")
        for b in (apply_btn, pop_btn, drop_btn):
            style_button(b, "ghost")
        apply_btn.clicked.connect(self._stash_apply)
        pop_btn.clicked.connect(self._stash_pop)
        drop_btn.clicked.connect(self._stash_drop)
        row2.addWidget(apply_btn)
        row2.addWidget(pop_btn)
        row2.addWidget(drop_btn)
        row2.addStretch()
        lay.addLayout(row2)
        lay.addStretch()
        return panel

    def _build_branch_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        h = QLabel("Branches")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)
        self.branch_list = QListWidget()
        lay.addWidget(self.branch_list)
        row = QHBoxLayout()
        self.branch_name = QLineEdit()
        self.branch_name.setPlaceholderText("New branch name")
        style_input(self.branch_name)
        create_btn = QPushButton("Create")
        style_button(create_btn, "success")
        create_btn.clicked.connect(self._branch_create)
        row.addWidget(self.branch_name)
        row.addWidget(create_btn)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        checkout_btn = QPushButton("Checkout")
        delete_btn = QPushButton("Delete")
        style_button(checkout_btn, "ghost")
        style_button(delete_btn, "danger")
        checkout_btn.clicked.connect(self._branch_checkout)
        delete_btn.clicked.connect(self._branch_delete)
        row2.addWidget(checkout_btn)
        row2.addWidget(delete_btn)
        row2.addStretch()
        lay.addLayout(row2)
        lay.addStretch()
        return panel

    def _build_history_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        h = QLabel("Commit History")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)
        self.history_list = QListWidget()
        lay.addWidget(self.history_list)
        row = QHBoxLayout()
        revert_btn = QPushButton("Revert")
        rollback_btn = QPushButton("Rollback")
        style_button(revert_btn, "danger")
        style_button(rollback_btn, "danger")
        revert_btn.clicked.connect(self._history_revert)
        rollback_btn.clicked.connect(self._history_rollback)
        row.addWidget(revert_btn)
        row.addWidget(rollback_btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        return panel

    def _build_release_panel(self) -> QWidget:  # noqa: PLR0915
        panel = QWidget()
        panel.setStyleSheet(f"background: {SLATE_PANEL};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        h = QLabel("Release Uploader")
        h.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 16px;")
        lay.addWidget(h)
        sub = QLabel("Six targets: windows/linux x86_64 / arm64 / x86")
        style_label(sub, "muted")
        lay.addWidget(sub)

        row = QHBoxLayout()
        self.dry_run_cb = QCheckBox("Dry run")
        self.dry_run_cb.setChecked(True)
        self.dry_run_cb.setStyleSheet(f"color: {TEXT};")
        self.sums_cb = QCheckBox("Generate SHA256SUMS.txt")
        self.sums_cb.setChecked(True)
        self.sums_cb.setStyleSheet(f"color: {TEXT};")
        wf_btn = QPushButton("Generate Workflow")
        style_button(wf_btn, "ghost")
        wf_btn.clicked.connect(self._release_workflow)
        edit_btn = QPushButton("Edit Targets")
        style_button(edit_btn, "ghost")
        edit_btn.clicked.connect(self._edit_targets)
        row.addWidget(self.dry_run_cb)
        row.addWidget(self.sums_cb)
        row.addStretch()
        row.addWidget(wf_btn)
        row.addWidget(edit_btn)
        lay.addLayout(row)

        self.targets_display = QTextEdit()
        self.targets_display.setReadOnly(True)
        self.targets_display.setFixedHeight(150)
        self.targets_display.setStyleSheet(
            f"background: #0f172a; color: {MUTED}; border: 1px solid {SLATE_BORDER}; border-radius: 6px; font-size: 12px;"
        )
        lay.addWidget(self.targets_display)

        row2 = QHBoxLayout()
        lbl_tag = QLabel("Tag")
        style_label(lbl_tag, "muted")
        row2.addWidget(lbl_tag)
        self.release_tag_input = QLineEdit()
        self.release_tag_input.setPlaceholderText("e.g. v1.4.2")
        style_input(self.release_tag_input)
        row2.addWidget(self.release_tag_input)
        lbl_art = QLabel("Artifact globs")
        style_label(lbl_art, "muted")
        row2.addWidget(lbl_art)
        self.release_art_input = QLineEdit()
        self.release_art_input.setPlaceholderText("dist/*, build/*.zip")
        style_input(self.release_art_input)
        row2.addWidget(self.release_art_input)
        upload_btn = QPushButton("Upload Artifacts")
        style_button(upload_btn, "success")
        upload_btn.clicked.connect(self._release_upload)
        row2.addWidget(upload_btn)
        lay.addLayout(row2)

        self.release_result = QLabel("")
        style_label(self.release_result, "muted")
        lay.addWidget(self.release_result)
        lay.addStretch()
        return panel

    # ------------------------------------------------------------------ #
    # navigation
    # ------------------------------------------------------------------ #
    def show_panel(self, panel_id: str):
        for pid, btn in self.nav_btns.items():
            btn.setChecked(pid == panel_id)
        index = {
            "status": 0,
            "versioning": 1,
            "gitignore": 2,
            "stash": 3,
            "branches": 4,
            "history": 5,
            "release": 6,
        }[panel_id]
        self.stack.setCurrentIndex(index)
        if panel_id == "status" and self._is_repo:
            self._refresh_status()
        elif panel_id == "versioning" and self._is_repo:
            self._refresh_versioning()
        elif panel_id == "stash" and self._is_repo:
            self._refresh_stash()
        elif panel_id == "branches" and self._is_repo:
            self._refresh_branches()
        elif panel_id == "history" and self._is_repo:
            self._refresh_history()
        elif panel_id == "release":
            self._load_targets_display()

    # ------------------------------------------------------------------ #
    # refresh helpers
    # ------------------------------------------------------------------ #
    def _refresh_github(self):
        status = detect_github(self.repo_root)
        self.github_status = status
        if status.connected:
            self.github_label.setText(
                f"GitHub: ● Connected  {status.repo_slug or status.remote_url or ''}"
            )
            self.github_label.setStyleSheet(f"color: {EMERALD}; font-weight: bold;")
        elif status.authenticated:
            self.github_label.setText(f"GitHub: ▲ Auth Missing  {status.remote_url or ''}")
            self.github_label.setStyleSheet(f"color: {AMBER}; font-weight: bold;")
        else:
            self.github_label.setText(f"GitHub: ✖ Offline  {status.remote_url or ''}")
            self.github_label.setStyleSheet(f"color: {CRIMSON}; font-weight: bold;")

    def _refresh_status(self):  # noqa: PLR0915
        # Build status map from git
        cats = self.git.status_categories()
        status_info = {
            "staged": (EMERALD, "S"),
            "unstaged": (AMBER, "M"),
            "untracked": (SKY, "?"),
            "conflicted": (CRIMSON, "!"),
            "ignored": (MUTED, "I"),
        }
        status_map: dict[str, tuple[str, str, str, str]] = {}  # path -> (xy, cat, color, badge)
        for cat, items in cats.items():
            color, badge = status_info[cat]
            for xy, path in items:
                status_map[path] = (xy, cat, color, badge)

        # Batch check-ignore to catch files inside ignored directories
        all_paths: list[str] = []

        def collect_paths(dir_path: str):
            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                return
            for entry in entries:
                if entry == ".git":
                    continue
                full_path = os.path.join(dir_path, entry)
                rel_path = os.path.relpath(full_path, self.repo_root)
                if os.path.isdir(full_path):
                    all_paths.append(rel_path)
                    collect_paths(full_path)
                else:
                    all_paths.append(rel_path)

        collect_paths(self.repo_root)

        ignored_paths: set[str] = set()
        if all_paths:
            proc = self.git.run(
                ["check-ignore", "--stdin"],
                input="\n".join(all_paths) + "\n",
                timeout=30,
            )
            if proc.ok and proc.stdout:
                ignored_paths = set(proc.stdout.splitlines())

        # Mark ignored paths in status_map
        for p in ignored_paths:
            if p not in status_map:
                status_map[p] = ("!!", "ignored", MUTED, "I")

        self._programmatic_change = True
        self.status_tree.clear()
        root = self.status_tree.invisibleRootItem()

        counts = {k: 0 for k in status_info}

        def add_file(parent, name: str, rel_path: str):
            nonlocal counts
            _xy, cat, color, badge = status_map.get(rel_path, (None, None, MUTED, "?"))
            if cat:
                counts[cat] += 1

            item = QTreeWidgetItem([badge if badge else "?", rel_path, cat.title() if cat else "unknown"])
            item.setData(0, Qt.ItemDataRole.UserRole, rel_path)

            if cat == "ignored":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(0, rgb("#475569"))
                item.setForeground(1, rgb("#475569"))
                item.setForeground(2, rgb("#475569"))
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                checked = cat == "staged"
                item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                item.setForeground(0, rgb(color))
                item.setForeground(1, rgb(TEXT))
                item.setForeground(2, rgb(color))

            item.setFont(0, QFont("monospace", 10, QFont.Weight.Bold))
            item.setFont(2, QFont("monospace", 10, QFont.Weight.Bold))
            parent.addChild(item)
            return item

        def add_folder(parent, name: str, rel_path: str):
            is_ignored = rel_path in ignored_paths
            item = QTreeWidgetItem(["", name, "folder"])
            # Store rel_path so we can identify folders by path
            item.setData(0, Qt.ItemDataRole.UserRole, rel_path)
            # Make folders checkable so users can stage/unstage entire directories
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setExpanded(True)
            if is_ignored:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setForeground(1, rgb("#475569"))
                item.setFont(1, QFont("", 10, QFont.Weight.Bold))
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setForeground(1, rgb(MUTED))
                item.setFont(1, QFont("", 10, QFont.Weight.Bold))
            parent.addChild(item)
            return item

        def walk_dir(dir_path: str, parent_item):
            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                return

            dirs = []
            files = []
            for entry in entries:
                if entry == ".git":
                    continue
                full_path = os.path.join(dir_path, entry)
                rel_path = os.path.relpath(full_path, self.repo_root)
                if os.path.isdir(full_path):
                    dirs.append((entry, full_path, rel_path))
                else:
                    files.append((entry, full_path, rel_path))

            for entry, full_path, rel_path in dirs:
                folder_item = add_folder(parent_item, entry, rel_path)
                if rel_path not in ignored_paths:
                    walk_dir(full_path, folder_item)

            for entry, _full_path, rel_path in files:
                add_file(parent_item, entry, rel_path)

        walk_dir(self.repo_root, root)

        # Bottom-up: set folder check states based on children
        def set_folder_states(item: QTreeWidgetItem):
            for i in range(item.childCount()):
                child = item.child(i)
                set_folder_states(child)
            # Only compute for folder items (items with checkable children)
            if item.data(0, Qt.ItemDataRole.UserRole) and item.childCount() > 0:
                checked = 0
                unchecked = 0
                for j in range(item.childCount()):
                    c = item.child(j)
                    if c.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        if c.checkState(0) == Qt.CheckState.Checked:
                            checked += 1
                        else:
                            unchecked += 1
                if checked > 0 and unchecked == 0:
                    item.setCheckState(0, Qt.CheckState.Checked)
                elif unchecked > 0 and checked == 0:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(0, Qt.CheckState.PartiallyChecked)

        set_folder_states(root)
        self._programmatic_change = False

        self.status_hint.setText(
            f"<span style='color:{EMERALD}'>{counts['staged']} staged</span>  "
            f"<span style='color:{AMBER}'>{counts['unstaged']} modified</span>  "
            f"<span style='color:{SKY}'>{counts['untracked']} untracked</span>  "
            f"<span style='color:{CRIMSON}'>{counts['conflicted']} conflicted</span>  "
            f"<span style='color:#475569'>{counts['ignored']} ignored</span>"
        )

    def _stage_all(self):
        result = self.git.run(["add", "."], timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Stage All failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _stage_selected(self):
        paths = []
        self._collect_checked_paths(self.status_tree.invisibleRootItem(), paths)
        if not paths:
            QMessageBox.information(self, "Stage Selected", "No files selected.")
            return
        result = self.git.run(["add", "--"] + paths, timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Stage Selected failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _unstage_all(self):
        result = self.git.run(["restore", "--staged", "."], timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Unstage All failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _unstage_selected(self):
        paths = []
        self._collect_checked_paths(self.status_tree.invisibleRootItem(), paths)
        if not paths:
            QMessageBox.information(self, "Unstage Selected", "No files selected.")
            return
        result = self.git.run(["restore", "--staged", "--"] + paths, timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Unstage Selected failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _collect_checked_paths(self, item, paths):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable and child.checkState(0) == Qt.CheckState.Checked:
                path = child.data(0, Qt.ItemDataRole.UserRole)
                if path:
                    paths.append(path)
            self._collect_checked_paths(child, paths)


    def _discard_all(self):
        result = self.git.run(["restore", "."], timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Discard All failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _unstage_all(self):
        paths = [p for xy, p in self.git.status_categories()["staged"]]
        if paths:
            self.git.unstage(paths)
        self._refresh_status()

    def _discard_all(self):
        paths = [p for xy, p in self.git.status_categories()["unstaged"]]
        if paths:
            self.git.discard(paths)
        self._refresh_status()

    def _on_item_checked(self, item: QTreeWidgetItem):
        if self._programmatic_change:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        state = item.checkState(0)

        # If clicking a folder (has children), propagate to all descendants
        if item.childCount() > 0:
            self._programmatic_change = True
            for i in range(item.childCount()):
                child = item.child(i)
                if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    child.setCheckState(0, state)
                    child_path = child.data(0, Qt.ItemDataRole.UserRole)
                    if child_path:
                        if state == Qt.CheckState.Checked:
                            self.git.stage([child_path])
                        else:
                            self.git.unstage([child_path])
                        # Recurse into subfolders
                        if child.childCount() > 0:
                            self._propagate_to_children(child, state)
            self._programmatic_change = False
        elif path:
            if state == Qt.CheckState.Checked:
                self.git.stage([path])
            else:
                self.git.unstage([path])

        # Update parent folder check state
        parent = item.parent()
        if parent is not None:
            self._update_folder_check_state(parent)
        # Note: we don't call _refresh_status() here because it would delete
        # all tree items (including the one that triggered this event).
        # Use the Refresh button to update badges from git status.

    def _propagate_to_children(self, item: QTreeWidgetItem, state: Qt.CheckState):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)
                child_path = child.data(0, Qt.ItemDataRole.UserRole)
                if child_path:
                    if state == Qt.CheckState.Checked:
                        self.git.stage([child_path])
                    else:
                        self.git.unstage([child_path])
                if child.childCount() > 0:
                    self._propagate_to_children(child, state)

    def _update_folder_check_state(self, folder_item: QTreeWidgetItem):
        self._programmatic_change = True
        checked = 0
        unchecked = 0
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                if child.checkState(0) == Qt.CheckState.Checked:
                    checked += 1
                else:
                    unchecked += 1
        if checked > 0 and unchecked == 0:
            folder_item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked > 0 and checked == 0:
            folder_item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            folder_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self._programmatic_change = False
        # Recurse up
        parent = folder_item.parent()
        if parent is not None:
            self._update_folder_check_state(parent)

    def _refresh_versioning(self):
        vs = self.config.version_state
        self.ver_major.blockSignals(True)
        self.ver_minor.blockSignals(True)
        self.ver_patch.blockSignals(True)
        self.ver_channel.blockSignals(True)
        self.ver_major.setText(str(vs.major))
        self.ver_minor.setText(str(vs.minor))
        self.ver_patch.setText(str(vs.patch))
        self.ver_channel.setText(vs.channel or "alpha")
        self.ver_major.blockSignals(False)
        self.ver_minor.blockSignals(False)
        self.ver_patch.blockSignals(False)
        self.ver_channel.blockSignals(False)
        self._render_version_preview()

    def _render_version_preview(self):
        try:
            major = int(self.ver_major.text() or 0)
            minor = int(self.ver_minor.text() or 0)
            patch = int(self.ver_patch.text() or 0)
        except ValueError:
            self.ver_preview.setText("invalid")
            return
        channel = self.ver_channel.text().strip() or "alpha"
        v = SemVer(major, minor, patch, channel)
        color = channel_color(channel)
        self.ver_preview.setText(f"v{v}")
        self.ver_preview.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 18px;")

    def _on_version_edited(self):
        self._render_version_preview()

    # ------------------------------------------------------------------ #
    # actions: staging
    # ------------------------------------------------------------------ #
    def _stage_all(self):
        result = self.git.run(["add", "."], timeout=120)
        if not result.ok:
            QMessageBox.critical(self, "Stage All failed", result.stderr.strip() or str(result))
        self._refresh_status()

    def _unstage_all(self):
        paths = [p for _, p in self.git.status_categories()["staged"]]
        if paths:
            self.git.unstage(paths)
        self._refresh_status()

    def _discard_all(self):
        paths = [p for _, p in self.git.status_categories()["unstaged"]]
        if paths:
            self.git.discard(paths)
        self._refresh_status()

    def _commit(self):
        dlg = CommitDialog(self)
        if dlg.exec():
            message = dlg.message
            result = self.git.commit(message)
            if result.ok:
                self._refresh_status()
                QMessageBox.information(self, "Committed", message)
            else:
                QMessageBox.critical(self, "Commit failed", result.stderr.strip() or str(result))

    def _push(self):
        branch = self.git.current_branch()
        result = self.git.push(branch)
        if result.ok:
            QMessageBox.information(self, "Pushed", f"Pushed branch {branch}")
            self._refresh_github()
        else:
            QMessageBox.critical(self, "Push failed", result.stderr.strip() or str(result))

    # ------------------------------------------------------------------ #
    # actions: versioning
    # ------------------------------------------------------------------ #
    def _create_tag(self):
        try:
            major = int(self.ver_major.text() or 0)
            minor = int(self.ver_minor.text() or 0)
            patch = int(self.ver_patch.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Invalid version", "Enter valid integers for Major/Minor/Patch.")
            return
        channel = self.ver_channel.text().strip() or "alpha"
        v = SemVer(major, minor, patch, channel)
        tag = v.tag_name("v")
        result = self.git.create_tag(tag)
        if result.ok:
            self.config.version_state.major = major
            self.config.version_state.minor = minor
            self.config.version_state.patch = patch
            self.config.version_state.channel = channel
            self.config.version_state.last_tag = tag
            self.store.save()
            QMessageBox.information(self, "Tag created", f"Created tag {tag}")
        else:
            QMessageBox.critical(self, "Tag failed", result.stderr.strip() or str(result))

    def _push_tag(self):
        try:
            major = int(self.ver_major.text() or 0)
            minor = int(self.ver_minor.text() or 0)
            patch = int(self.ver_patch.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Invalid version", "Enter valid integers for Major/Minor/Patch.")
            return
        channel = self.ver_channel.text().strip() or "alpha"
        v = SemVer(major, minor, patch, channel)
        tag = v.tag_name("v")
        result = self.git.run(["push", "origin", tag], timeout=120)
        if result.ok:
            QMessageBox.information(self, "Tag pushed", f"Pushed tag {tag} to origin")
        else:
            QMessageBox.critical(self, "Push failed", result.stderr.strip() or str(result))

    # ------------------------------------------------------------------ #
    # actions: gitignore
    # ------------------------------------------------------------------ #
    def _on_preset_select(self):
        self._refresh_gitignore_preview()

    def _refresh_gitignore_preview(self):
        keys = [it.data(Qt.ItemDataRole.UserRole) for it in self.preset_list.selectedItems()]
        merged = merge_presets(keys)
        self.gitignore_preview.setPlainText("\n".join(merged))

    def _merge_presets(self):
        self._refresh_gitignore_preview()
        self.config.selected_presets = [
            it.data(Qt.ItemDataRole.UserRole) for it in self.preset_list.selectedItems()
        ]
        self.store.set_selected_presets(self.config.selected_presets)
        self.store.save()

    def _clear_presets(self):
        self.preset_list.clearSelection()
        self.gitignore_preview.clear()

    def _write_gitignore(self):
        keys = [it.data(Qt.ItemDataRole.UserRole) for it in self.preset_list.selectedItems()]
        content = "\n".join(merge_presets(keys))
        path = os.path.join(self.repo_root, ".gitignore")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        QMessageBox.information(self, ".gitignore", f"Wrote {path}")

    # ------------------------------------------------------------------ #
    # actions: stash
    # ------------------------------------------------------------------ #
    def _refresh_stash(self):
        self.stash_list.clear()
        for s in self.git.stash_list():
            self.stash_list.addItem(f"{s['ref']}  {s['subject']}")

    def _stash_push(self):
        result = self.git.stash_push(self.stash_msg.text().strip() or None)
        if result.ok:
            self.stash_msg.clear()
            self._refresh_stash()
        else:
            QMessageBox.critical(self, "Stash failed", result.stderr.strip() or str(result))

    def _stash_apply(self):
        item = self.stash_list.currentItem()
        if not item:
            return
        ref = item.text().split()[0]
        result = self.git.stash_apply(ref)
        if result.ok:
            self._refresh_stash()
        else:
            QMessageBox.critical(self, "Stash apply failed", result.stderr.strip() or str(result))

    def _stash_pop(self):
        item = self.stash_list.currentItem()
        if not item:
            return
        ref = item.text().split()[0]
        result = self.git.stash_pop(ref)
        if result.ok:
            self._refresh_stash()
        else:
            QMessageBox.critical(self, "Stash pop failed", result.stderr.strip() or str(result))

    def _stash_drop(self):
        item = self.stash_list.currentItem()
        if not item:
            return
        ref = item.text().split()[0]
        result = self.git.stash_drop(ref)
        if result.ok:
            self._refresh_stash()
        else:
            QMessageBox.critical(self, "Stash drop failed", result.stderr.strip() or str(result))

    # ------------------------------------------------------------------ #
    # actions: branches
    # ------------------------------------------------------------------ #
    def _refresh_branches(self):
        self.branch_list.clear()
        for b in self.git.branches():
            mark = "* " if b["current"] else "  "
            self.branch_list.addItem(f"{mark}{b['name']}  {b['track']}".strip())

    def _branch_create(self):
        name = self.branch_name.text().strip()
        if not name:
            return
        result = self.git.create_branch(name)
        if result.ok:
            self.branch_name.clear()
            self._refresh_branches()
        else:
            QMessageBox.critical(self, "Create failed", result.stderr.strip() or str(result))

    def _branch_checkout(self):
        item = self.branch_list.currentItem()
        if not item:
            return
        name = item.text().split()[0].lstrip("*")
        result = self.git.checkout_branch(name)
        if result.ok:
            self._refresh_branches()
            self._refresh_status()
        else:
            QMessageBox.critical(self, "Checkout failed", result.stderr.strip() or str(result))

    def _branch_delete(self):
        item = self.branch_list.currentItem()
        if not item:
            return
        name = item.text().split()[0].lstrip("*")
        result = self.git.delete_branch(name)
        if result.ok:
            self._refresh_branches()
        else:
            QMessageBox.critical(self, "Delete failed", result.stderr.strip() or str(result))

    # ------------------------------------------------------------------ #
    # actions: history
    # ------------------------------------------------------------------ #
    def _refresh_history(self):
        self.history_list.clear()
        for c in self.git.log(30):
            self.history_list.addItem(f"{c['hash']}  {c['subject']}  [{c['author']}]  {c['date']}")

    def _history_revert(self):
        item = self.history_list.currentItem()
        if not item:
            return
        commit = item.text().split()[0]
        result = self.git.run(["revert", "--no-edit", commit])
        if result.ok:
            self._refresh_history()
            self._refresh_status()
        else:
            QMessageBox.critical(self, "Revert failed", result.stderr.strip() or str(result))

    def _history_rollback(self):
        item = self.history_list.currentItem()
        if not item:
            return
        commit = item.text().split()[0]
        result = self.git.run(["reset", "--hard", commit])
        if result.ok:
            self._refresh_history()
            self._refresh_status()
        else:
            QMessageBox.critical(self, "Rollback failed", result.stderr.strip() or str(result))

    # ------------------------------------------------------------------ #
    # actions: release
    # ------------------------------------------------------------------ #
    def _load_targets_display(self):
        try:
            cmds = load_target_commands(self.repo_root)
        except TargetConfigError as exc:
            self.targets_display.setPlainText(str(exc))
            self.release_result.setText(str(exc))
            self.release_result.setStyleSheet(f"color: {CRIMSON};")
            return
        if not cmds:
            self.targets_display.setPlainText(
                "No target commands configured.\n"
                "Click 'Edit Targets' to create .git-tui/git-tui-targets.json\n"
                "with a command for each of the six targets."
            )
            self.release_result.setText("")
            return
        lines = [f"{t}: {c}" for t, c in cmds.items()]
        self.targets_display.setPlainText("\n".join(lines))
        self.release_result.setText(f"Loaded {len(cmds)} target commands")
        self.release_result.setStyleSheet(f"color: {EMERALD};")

    def _edit_targets(self):
        try:
            current = load_target_commands(self.repo_root)
        except TargetConfigError:
            current = {}
        dlg = TargetConfigDialog(current, self)
        if dlg.exec():
            try:
                path = write_target_commands(self.repo_root, dlg.commands)
                self._load_targets_display()
                self.release_result.setText(f"Written: {path}")
                self.release_result.setStyleSheet(f"color: {EMERALD};")
            except TargetConfigError as exc:
                QMessageBox.critical(self, "Invalid targets", str(exc))

    def _release_workflow(self):
        try:
            cmds = load_target_commands(self.repo_root)
        except TargetConfigError as exc:
            QMessageBox.critical(self, "Invalid target config", str(exc))
            return
        wf_dir = os.path.join(self.repo_root, ".github", "workflows")
        path = write_workflow(wf_dir, self.github_status.repo_slug if self.github_status else None, target_commands=cmds)
        QMessageBox.information(self, "Workflow", f"Written: {path}")

    def _release_upload(self):
        tag = self.release_tag_input.text().strip() or "HEAD"
        dry_run = self.dry_run_cb.isChecked()
        generate_sums = self.sums_cb.isChecked()

        # Load per-target build commands and run them to produce artifacts.
        try:
            target_commands = load_target_commands(self.repo_root)
        except TargetConfigError as exc:
            self.release_result.setText(str(exc))
            self.release_result.setStyleSheet(f"color: {CRIMSON};")
            return

        files: list[str] = []

        for target, command in target_commands.items():
            cmd = command.replace("{target}", target)
            if dry_run:
                self.release_result.setText(f"[dry-run] would run: {cmd}")
                self.release_result.setStyleSheet(f"color: {SKY};")
                continue
            try:
                proc = subprocess_mod.run(
                    cmd, cwd=self.repo_root, shell=True,
                    capture_output=True, text=True, timeout=300,
                )
                if proc.returncode != 0:
                    self.release_result.setText(f"Build failed for {target}: {proc.stderr.strip()}")
                    self.release_result.setStyleSheet(f"color: {CRIMSON};")
                    return
            except (subprocess_mod.TimeoutExpired, OSError) as exc:
                self.release_result.setText(f"Build error for {target}: {exc}")
                self.release_result.setStyleSheet(f"color: {CRIMSON};")
                return

        # Collect artifact globs.
        globs = [g.strip() for g in self.release_art_input.text().split(",") if g.strip()]
        for pat in globs:
            files.extend(glob_mod.glob(os.path.join(self.repo_root, pat)))

        if dry_run:
            self.release_result.setText(
                f"[dry-run] would upload {len(files)} file(s) to GitHub release {tag}"
            )
            self.release_result.setStyleSheet(f"color: {SKY};")
            return

        result = upload_assets(
            self.repo_root,
            tag,
            files,
            dry_run=False,
            generate_sums=generate_sums,
        )
        self.release_result.setText(result.message)
        self.release_result.setStyleSheet(f"color: {'green' if result.ok else CRIMSON};"        )


class CommitDialog(QDialog):
    """Commit message dialog with conventional commit prefix selector."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Commit")
        self.setMinimumWidth(450)
        self.message = ""
        self.setStyleSheet(f"background: {SLATE_PANEL};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        prefix_lbl = QLabel("Conventional commit prefix")
        style_label(prefix_lbl, "muted")
        lay.addWidget(prefix_lbl)

        self.prefix_select = QComboBox()
        self.prefix_select.addItems(
            ["feat:  new feature", "fix:   bug fix", "docs:  documentation",
             "style: formatting", "refactor: code refactor", "test:  tests",
             "chore: maintenance", "(none)"]
        )
        self.prefix_select.setStyleSheet(
            f"""
            QComboBox {{
                background: #0f172a;
                color: {TEXT};
                border: 1px solid {SLATE_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border: 1px solid {FOCUS};
            }}
            """
        )
        lay.addWidget(self.prefix_select)

        msg_lbl = QLabel("Commit message")
        style_label(msg_lbl, "muted")
        lay.addWidget(msg_lbl)

        self.msg_edit = QLineEdit()
        self.msg_edit.setPlaceholderText("Description of changes")
        style_input(self.msg_edit)
        lay.addWidget(self.msg_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        style_button(cancel_btn, "danger")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Commit")
        style_button(ok_btn, "success")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

    def accept(self):
        prefix = self.prefix_select.currentText()
        msg = self.msg_edit.text().strip()
        if prefix == "(none)":
            self.message = msg
        else:
            self.message = f"{prefix}: {msg}" if msg else prefix
        super().accept()


class TargetConfigDialog(QMessageBox):
    """Modal dialog to edit per-target build commands."""

    def __init__(self, current: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Target Build Commands")
        self.setText(
            "Edit the build command for each release target. "
            "Written to .git-tui/git-tui-targets.json."
        )
        self.commands = {}
        self.inputs = {}
        layout = self.layout()
        # Build a custom widget area
        container = QWidget()
        gl = QGridLayout(container)
        gl.setContentsMargins(16, 16, 16, 16)
        gl.setSpacing(10)
        for i, target in enumerate(
            ["windows-x86_64", "linux-x86_64", "windows-arm64", "linux-arm64", "windows-x86", "linux-x86"]
        ):
            lbl = QLabel(target)
            lbl.setStyleSheet("color: #c084fc; font-weight: bold;")
            le = QLineEdit()
            le.setText(current.get(target, ""))
            style_input(le)
            gl.addWidget(lbl, i, 0)
            gl.addWidget(le, i, 1)
            self.inputs[target] = le
        # insert container into message box layout
        layout.addWidget(container, 1, 0, 1, layout.columnCount())

        btn_save = QPushButton("Save")
        style_button(btn_save, "success")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancel")
        style_button(btn_cancel, "danger")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_save, 2, 0)
        layout.addWidget(btn_cancel, 2, 1)

    def _save(self):
        self.commands = {t: le.text().strip() for t, le in self.inputs.items()}
        self.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    repo = sys.argv[1] if len(sys.argv) > 1 else None
    global_store = GlobalConfigStore()
    window = GitTuiQtApp(repo, global_store=global_store)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
