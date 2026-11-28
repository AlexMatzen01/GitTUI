# Git TUI

Interactive, richly styled Git terminal & desktop user interface in Python 3.11+
built with [Textual](https://textual.textualize.io/) and [PyQt6](https://pypi.org/project/PyQt6/).
Native mouse support (`LMB`), arrow-key navigation, truecolor styling, bold
typography, and underlined visual cues.

## Features

- **Navigation** — arrow keys, `Tab`/`Shift+Tab`, `Enter` to activate, `Esc` to
  back/cancel, plus full left-mouse-button (`LMB`) support for tabs, buttons,
  list items, checkboxes, and scrollable panes.
- **Tracking & Staging Manager** — color-coded status badges
  (`[S]` staged, `[M]` modified, `[?]` untracked, `[!]` conflicted), stage /
  unstage individual files (per-file buttons in the Qt GUI; `s`/`u` keys in the
  terminal UI), stage all, discard unstaged changes (with confirmation),
  inline color-coded diffs (`+` green, `-` red, `@@` bold cyan),
  and commit with conventional-commit prefix selector.
- **Semantic Versioning & Release Channels** — `MAJOR.MINOR.PATCH` with
  `alpha`/`beta`/`pre-release`/`release` channels, bump major/minor/patch,
  channel promotion/demotion, bold preview of the formatted version, and Git
  tag creation (`v...`).
- **Multi-Preset `.gitignore` Generator** — 19 built-in presets (Python, C/C++
  + CMake/Qt6, Rust, Go, Node/TypeScript, Java/Maven/Gradle, C#/.NET,
  Swift/iOS, Kotlin/Android, PHP/Laravel, Ruby/Rails, Unity/Unreal, Docker,
  Terraform, macOS/Windows/Linux, VS Code, IntelliJ). Merge multiple presets,
  preview colorized diffs before writing, toggle rules. Every generated
  `.gitignore` mandatorily includes `.git-tui` / `.git-tui/`.
- **Local Config Persistence** — `.git-tui/config.json` with schema validation
  and safe defaults for missing/corrupted config.
- **GitHub Connection Status** — remote detection, auth check (`gh` CLI, env
  token, config), color-coded status pill in the header, underlined clickable
  repo URL/slug.
- **Multi-Arch Release Binary Uploader** — all six targets
  (`windows-x86_64`, `linux-x86_64`, `windows-arm64`, `linux-arm64`,
  `windows-x86`, `linux-x86`), GitHub Actions workflow generation, direct
  upload via `gh release upload` or GitHub REST API, `SHA256SUMS.txt`,
  dry-run mode, colorized progress/reporting.

  Per-target build commands are stored in `~/.config/git-tui/git-tui-targets.json`
  (a single JSON object mapping each target name to a shell command). These
  commands are run before uploading, with `{target}` substituted by the target
  name:

  ```json
  {
    "windows-x86_64": "GOOS=windows GOARCH=amd64 go build -o dist/app.exe .",
    "linux-x86_64": "GOOS=linux GOARCH=amd64 go build -o dist/app .",
    "windows-arm64": "GOOS=windows GOARCH=arm64 go build -o dist/app.exe .",
    "linux-arm64": "GOOS=linux GOARCH=arm64 go build -o dist/app .",
    "windows-x86": "GOOS=windows GOARCH=386 go build -o dist/app.exe .",
    "linux-x86": "GOOS=linux GOARCH=386 go build -o dist/app ."
  }
  ```

  Edit them from the Release panel via the **Edit Targets** button, or during
  the first-run wizard. Invalid JSON shows a documented error in the app.
- **Branch & Stash Quick-Drawer** — switch/create/delete branches with
  ahead/behind badges, create/apply/pop/drop stashes.
- **Commit History & Rollback** — colored short hashes, bold subjects,
  underlined author/tag badges, revert and hard-reset rollback with
  confirmation.
- **Keybind & Mouse Cheat-Sheet** — `?` or click `[bold underline]? Help[/]`.

## Two frontends

Git TUI ships two frontends sharing the same core logic:

| Command | Frontend | Best for |
|---------|----------|----------|
| `git-tui` | Textual TUI (terminal) | SSH sessions, keyboard-driven workflows |
| `git-tui-qt` | PyQt6 desktop GUI | Linux desktop, mouse-driven, animations |

Both use the same `git_ops.py`, `versioning.py`, `gitignore_presets.py`,
`github_client.py`, `release_uploader.py`, and `config_store.py` modules.

## Installation

```bash
pip install .
```

or, for development:

```bash
pip install -e .
```

Run the terminal UI:

```bash
git-tui
# or
git-tui /path/to/repo
```

Run the desktop GUI:

```bash
git-tui-qt
# or
git-tui-qt /path/to/repo
```

### First-run wizard (desktop GUI)

The first time you launch `git-tui-qt`, a setup wizard opens and guides you
through:

1. **Welcome** — overview of Git TUI.
2. **Default Repository** — choose the repo Git TUI opens by default.
3. **GitHub Connection** — connect via `gh` CLI or a personal access token.
4. **Release Build Targets** — set the build command for each of the six
   release targets (written to `~/.config/git-tui/git-tui-targets.json`).
5. **Finish** — saves everything to `~/.config/git-tui/config.json`.

Re-run the wizard anytime by deleting `~/.config/git-tui/config.json`.

## Keybindings (terminal UI)

| Key | Action |
|-----|--------|
| `↑ ↓ ← →` | Move focus |
| `Tab` / `Shift+Tab` | Next / previous focus |
| `Enter` | Activate / select |
| `Esc` | Back / cancel |
| `s` | Stage selected file |
| `u` | Unstage selected file |
| `S` | Stage all |
| `c` | Commit |
| `p` | Push |
| `b` | Branches panel |
| `v` | Versioning panel |
| `g` | Gitignore panel |
| `h` | History panel |
| `t` | Stash panel |
| `r` | Release panel |
| `?` | Cheat-sheet modal |
| `q` | Quit |

All actions are also available via left-mouse-button clicks and on-screen
buttons with `[bold underline]` mnemonics (`[bold underline]S[/]tage`,
`[bold underline]C[/]ommit`, `[bold underline]P[/]ush`, etc.).

## Color scheme

| Semantic | Color | Use |
|----------|-------|-----|
| Staged / success / connected | `#22c55e` emerald | badges, tags, connected pill |
| Modified / warning / pre-release | `#f59e0b` amber | modified files, pre-release channel |
| Untracked / info / beta | `#38bdf8` sky | untracked files, beta channel, links |
| Deleted / error / conflict / offline | `#ef4444` crimson | errors, conflicts, offline pill |
| Alpha / experimental / accent | `#c084fc` violet | alpha channel, commit hashes |

Panels use deep slate (`#0f172a` / `#1e293b`) with crisp `#38bdf8` focus
borders and `#94a3b8` muted labels. Bold and underlined attributes are
preserved on terminals with limited color depth (ANSI / 256-color).

## Project layout

```
pyproject.toml          # packaging, ruff config, entry points
README.md
src/git_tui/__init__.py
src/git_tui/app.py          # Textual app, bindings, navigation, action wiring
src/git_tui/qt_app.py       # PyQt6 desktop GUI (dark theme, animations)
src/git_tui/wizard.py       # First-run setup wizard
src/git_tui/global_config.py # User-level config (~/.config/git-tui)
src/git_tui/styles.py       # Shared Qt styles & palette
src/git_tui/styles.tcss     # Textual CSS styling (colors, bold, underline)
src/git_tui/git_ops.py      # git/gh subprocess wrapper (shell=False, timeouts)
src/git_tui/config_store.py # Per-repo .git-tui/config.json + schema validation
src/git_tui/versioning.py   # semantic version + release channel engine
src/git_tui/gitignore_presets.py  # 19 presets, merge, mandatory .git-tui rule
src/git_tui/github_client.py      # GitHub remote/auth detection
src/git_tui/release_uploader.py   # multi-arch release uploads + workflow generation
src/git_tui/widgets.py    # Textual widgets, panels, modals, messages
src/git_tui/resources/git-tui.svg          # app icon
src/git_tui/resources/git-tui.desktop     # Linux desktop entry
src/git_tui/resources/org.gittui.desktop.metainfo.xml  # AppStream metadata
```

## Config (`
.git-tui/config.json`)

Stored per repository in `.git-tui/config.json`: version state, selected
presets, release settings (dry-run, artifact globs, six targets), UI
preferences (theme, color depth), GitHub token env name, and auto-fetch. Missing
or corrupted config is rebuilt from validated defaults.

## Global config (`~/.config/git-tui/config.json`)

Stored per user: wizard completion, theme, default repository, GitHub token,
release dry-run/SHA256SUMS preferences, window size, font size, and per-target
build commands (`git-tui-targets.json`).

## Linux desktop integration

The package installs:

- `share/applications/git-tui.desktop` — app menu entry (`git-tui-qt`).
- `share/metainfo/org.gittui.desktop.metainfo.xml` — AppStream metadata.
- `share/icons/hicolor/scalable/apps/git-tui.svg` — app icon.

Launch from your application menu as **Git TUI**, or run `git-tui-qt`.

## License

MIT — see LICENSE.
