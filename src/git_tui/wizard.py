"""First-run setup wizard for Git TUI.

Walks the user through selecting a default repository, configuring GitHub
authentication, and setting release build targets. Results are stored in the
global config store (~/.config/git-tui).
"""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .global_config import DEFAULT_TARGETS, GlobalConfigStore
from .styles import SKY, SLATE_PANEL, TEXT, VIOLET, style_button, style_input, style_label


class WizardPage(QWidget):
    """Base wizard page with a title and subtitle."""

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle


class WelcomePage(WizardPage):
    def __init__(self, parent=None):
        super().__init__("Welcome to Git TUI", "Set up your desktop Git interface", parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(16)
        t = QLabel(self.title)
        t.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 20px;")
        s = QLabel(self.subtitle)
        style_label(s, "muted")
        desc = QLabel(
            "Git TUI is a richly styled desktop interface for Git. "
            "This wizard will help you choose a default repository, connect "
            "GitHub, and configure release build targets."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addWidget(desc)
        lay.addStretch()

    def validate(self) -> Optional[str]:
        return None


class RepoPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__("Default Repository", "Choose the repository Git TUI opens by default", parent)
        self.repo_path = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(16)
        t = QLabel(self.title)
        t.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 20px;")
        s = QLabel(self.subtitle)
        style_label(s, "muted")
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path to a Git repository (or leave blank for current dir)")
        style_input(self.path_edit)
        browse = QPushButton("Browse…")
        style_button(browse, "ghost")
        browse.clicked.connect(self._browse)
        row.addWidget(self.path_edit)
        row.addWidget(browse)
        hint = QLabel("Tip: You can change this later from Settings.")
        style_label(hint, "muted")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addLayout(row)
        lay.addWidget(hint)
        lay.addStretch()

    def _browse(self):
        d = QFileDialog(self, "Select Repository")
        d.setFileMode(QFileDialog.FileMode.Directory)
        if d.exec():
            sel = d.selectedFiles()
            if sel:
                self.path_edit.setText(sel[0])
                self.repo_path = sel[0]

    def validate(self) -> Optional[str]:
        path = self.path_edit.text().strip() or os.getcwd()
        if not os.path.isdir(os.path.join(path, ".git")):
            return f"Not a Git repository: {path}"
        self.repo_path = path
        return None


class GithubPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__("GitHub Connection", "Connect Git TUI to GitHub", parent)
        self.token = ""
        self.method = "none"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(16)
        t = QLabel(self.title)
        t.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 20px;")
        s = QLabel(self.subtitle)
        style_label(s, "muted")
        self.gh_cb = QCheckBox("I have the `gh` CLI installed and authenticated")
        self.gh_cb.setStyleSheet(f"color: {TEXT};")
        self.token_cb = QCheckBox("I want to use a GitHub personal access token")
        self.token_cb.setStyleSheet(f"color: {TEXT};")
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("ghp_…")
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        style_input(self.token_edit)
        self.token_edit.setEnabled(False)
        self.token_cb.toggled.connect(self.token_edit.setEnabled)
        hint = QLabel(
            "Git TUI detects your GitHub remote and auth automatically. "
            "Providing a token enables release uploads without the `gh` CLI."
        )
        hint.setWordWrap(True)
        style_label(hint, "muted")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addWidget(self.gh_cb)
        lay.addWidget(self.token_cb)
        lay.addWidget(self.token_edit)
        lay.addWidget(hint)
        lay.addStretch()

    def validate(self) -> Optional[str]:
        if self.gh_cb.isChecked():
            self.method = "gh"
        elif self.token_cb.isChecked():
            self.method = "token"
            self.token = self.token_edit.text().strip()
            if not self.token:
                return "Please enter a GitHub token."
        return None


class TargetsPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__("Release Build Targets", "Set the build command for each release target", parent)
        self.targets = dict(DEFAULT_TARGETS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(12)
        t = QLabel(self.title)
        t.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 20px;")
        s = QLabel(self.subtitle)
        style_label(s, "muted")
        self.inputs = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for i, target in enumerate(
            ["windows-x86_64", "linux-x86_64", "windows-arm64", "linux-arm64", "windows-x86", "linux-x86"]
        ):
            lbl = QLabel(target)
            lbl.setStyleSheet(f"color: {VIOLET}; font-weight: bold;")
            le = QLineEdit()
            le.setText(DEFAULT_TARGETS[target])
            style_input(le)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(le, i, 1)
            self.inputs[target] = le
        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        scroll_content = QVBoxLayout()
        scroll_content.addWidget(QLabel("Edit each target's build command:"))
        style_label(scroll_content.itemAt(0).widget(), "muted")
        scroll_content.addWidget(grid_widget)
        scroll_content.addStretch()
        scroll = QWidget()
        scroll.setLayout(scroll_content)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addWidget(scroll)
        hint = QLabel("These are written to ~/.config/git-tui/git-tui-targets.json.")
        style_label(hint, "muted")
        lay.addWidget(hint)

    def validate(self) -> Optional[str]:
        self.targets = {t: le.text().strip() for t, le in self.inputs.items()}
        return None


class FinishPage(WizardPage):
    def __init__(self, parent=None):
        super().__init__("All Set", "Git TUI is ready to use", parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(16)
        t = QLabel(self.title)
        t.setStyleSheet(f"color: {SKY}; font-weight: bold; font-size: 20px;")
        s = QLabel(self.subtitle)
        style_label(s, "muted")
        desc = QLabel(
            "Your default repository, GitHub auth, and release targets are saved. "
            "Launch Git TUI from your app menu or run `git-tui-qt`."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addWidget(desc)
        lay.addStretch()

    def validate(self) -> Optional[str]:
        return None


class WizardDialog(QDialog):
    """Multi-page setup wizard."""

    def __init__(self, store: GlobalConfigStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Git TUI Setup Wizard")
        self.setMinimumSize(700, 520)
        self.setStyleSheet(f"background: {SLATE_PANEL};")

        self.pages = [
            WelcomePage(),
            RepoPage(),
            GithubPage(),
            TargetsPage(),
            FinishPage(),
        ]
        self.current = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.stack_area = QVBoxLayout()
        self.stack_area.setContentsMargins(0, 0, 0, 0)
        self.stack_area.setSpacing(0)
        for p in self.pages:
            self.stack_area.addWidget(p)
        lay.addLayout(self.stack_area)

        self.nav = QHBoxLayout()
        self.nav.setContentsMargins(24, 16, 24, 16)
        self.nav.setSpacing(12)
        self.back_btn = QPushButton("Back")
        style_button(self.back_btn, "ghost")
        self.back_btn.clicked.connect(self._prev)
        self.back_btn.setEnabled(False)
        self.next_btn = QPushButton("Next")
        style_button(self.next_btn, "primary")
        self.next_btn.clicked.connect(self._next)
        self.finish_btn = QPushButton("Finish")
        style_button(self.finish_btn, "success")
        self.finish_btn.clicked.connect(self._finish)
        self.finish_btn.setVisible(False)
        self.nav.addWidget(self.back_btn)
        self.nav.addStretch()
        self.nav.addWidget(self.next_btn)
        self.nav.addWidget(self.finish_btn)
        lay.addLayout(self.nav)

        self._show_page(0)

    def _show_page(self, idx: int):
        self.current = idx
        for i, p in enumerate(self.pages):
            p.setVisible(i == idx)
        self.back_btn.setEnabled(idx > 0)
        is_last = idx == len(self.pages) - 1
        self.next_btn.setVisible(not is_last)
        self.finish_btn.setVisible(is_last)
        self.setWindowTitle(f"Git TUI Setup — {self.pages[idx].title}")

    def _next(self):
        page = self.pages[self.current]
        err = page.validate()
        if err:

            QMessageBox.warning(self, "Validation error", err)
            return
        if self.current < len(self.pages) - 1:
            self._show_page(self.current + 1)

    def _prev(self):
        if self.current > 0:
            self._show_page(self.current - 1)

    def _finish(self):
        page = self.pages[self.current]
        err = page.validate()
        if err:

            QMessageBox.warning(self, "Validation error", err)
            return
        repo_page = self.pages[1]
        gh_page = self.pages[2]
        targets_page = self.pages[3]

        if repo_page.repo_path:
            self.store.set_default_repo(repo_page.repo_path)
        if gh_page.method != "none":
            self.store.set_github_token(gh_page.token, gh_page.method)
        self.store.save_targets(targets_page.targets)
        self.store.set_wizard_completed()
        self.accept()
