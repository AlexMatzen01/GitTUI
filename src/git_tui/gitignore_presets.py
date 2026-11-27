"""Multi-preset ``.gitignore`` generator & manager.

Every preset (and every merged result) mandatorily includes ``.git-tui`` /
``.git-tui/`` so Git TUI's local config directory is always ignored.
"""

from __future__ import annotations

from dataclasses import dataclass

MANDATORY_RULES = [
    "# Git TUI local config directory (always ignored)",
    ".git-tui",
    ".git-tui/",
]


@dataclass(frozen=True)
class GitIgnorePreset:
    key: str
    name: str
    description: str
    rules: list[str]

    def merged_rules(self) -> list[str]:
        rules = list(self.rules)
        for rule in MANDATORY_RULES:
            if rule not in rules:
                rules.append(rule)
        return rules


# ---------------------------------------------------------------------- #
# preset library
# ---------------------------------------------------------------------- #
def _preset(key: str, name: str, description: str, rules: list[str]) -> GitIgnorePreset:
    return GitIgnorePreset(key=key, name=name, description=description, rules=list(rules))


PYTHON_RULES = [
    "# Byte-compiled / optimized / DLL files",
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    "# C extensions",
    "*.so",
    "# Distribution / packaging",
    ".Python",
    "build/",
    "develop-eggs/",
    "dist/",
    "downloads/",
    "eggs/",
    ".eggs/",
    "lib/",
    "lib64/",
    "parts/",
    "sdist/",
    "var/",
    "wheels/",
    "share/python-wheels/",
    "*.egg-info/",
    ".installed.cfg",
    "*.egg",
    "# PyInstaller",
    "*.manifest",
    "*.spec",
    "# Installer logs",
    "pip-log.txt",
    "pip-delete-this-directory.txt",
    "# Unit test / coverage reports",
    ".tox/",
    "tox.ini",
    ".coverage",
    ".coverage.*",
    ".cache",
    "nosetests.xml",
    "coverage.xml",
    "*.cover",
    "*.py,cover",
    ".hypothesis/",
    ".pytest_cache/",
    "# Translations",
    "*.mo",
    "*.pot",
    "# Django stuff:",
    "*.log",
    "local_settings.py",
    "db.sqlite3",
    "db.sqlite3-journal",
    "# Flask stuff:",
    "instance/",
    ".webassets-cache",
    "# Scrapy stuff:",
    ".scrapy",
    "# Sphinx documentation",
    "docs/_build/",
    "# PyBuilder",
    "target/",
    "# Jupyter Notebook",
    ".ipynb_checkpoints",
    "ipynb",
    ".ipynb",
    "# pyenv",
    ".python-version",
    "# pipenv",
    "Pipfile.lock",
    "# Poetry",
    "poetry.lock",
]


def python_preset() -> GitIgnorePreset:
    return _preset("python", "Python", "CPython, Django, Flask, Poetry, pipenv, pytest, Jupyter", PYTHON_RULES)


CPLUSPLUS_RULES = [
    "# Compiled Object files",
    "*.slo",
    "*.lo",
    "*.o",
    "*.obj",
    "# Precompiled Headers",
    "*.gch",
    "*.pch",
    "# Compiled Dynamic libraries",
    "*.so",
    "*.dylib",
    "*.dll",
    "# Fortran module files",
    "*.mod",
    "*.smod",
    "# Compiled Static libraries",
    "*.lai",
    "*.la",
    "*.a",
    "*.lib",
    "# Executables",
    "*.exe",
    "*.out",
    "*.app",
    "*.i*86",
    "*.x86_64",
    "*.x64",
    "build/",
    "cmake-build-debug/",
    "cmake-build-release/",
    "CMakeFiles/",
    "CMakeCache.txt",
    "CTestTestfile.cmake",
    "install_manifest.txt",
    "compile_commands.json",
    "# Qt6",
    "*.moc",
    "moc_*.cpp",
    "qrc_*.cpp",
    "ui_*.h",
    ".qmake.stash",
    ".qmake.",
    "*.pro.user",
    "*.qmlproject.user",
]


def cpp_preset() -> GitIgnorePreset:
    return _preset("cpp", "C/C++", "GCC/Clang, CMake, Qt6 build artifacts", CPLUSPLUS_RULES)


RUST_RULES = [
    "/target/",
    "Cargo.lock",
    "*.rs.bak",
    "*.rs.bk",
    "Cargo.lock.*",
]


def rust_preset() -> GitIgnorePreset:
    return _preset("rust", "Rust", "Cargo build artifacts and target directory", RUST_RULES)


GO_RULES = [
    "*.exe",
    "*.exe~",
    "*.dll",
    "*.so",
    "*.dylib",
    "bin/",
    ".bin/",
    "/vendor/",
    ".go.buildcache",
]


def go_preset() -> GitIgnorePreset:
    return _preset("go", "Go", "Go build binaries and vendor directory", GO_RULES)


NODE_RULES = [
    "node_modules/",
    "*.log",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    "pnpm-debug.log*",
    "lerna-debug.log*",
    ".node_repl_history",
    "*.npm",
    "dist/",
    "build/",
    ".next/",
    "out/",
    "tsconfig.tsbuildinfo",
    ".npmrc",
    ".yarn-integrity",
    ".yarn/cache",
    ".yarn/install-state.gz",
    ".pnp",
    ".pnp.js",
    "coverage/",
    ".nyc_output",
]


def node_preset() -> GitIgnorePreset:
    return _preset("node", "Node / TypeScript", "npm, yarn, pnpm, Next.js, Nuxt, tsbuildinfo", NODE_RULES)


JAVA_RULES = [
    "*.class",
    "*.jar",
    "*.war",
    "*.ear",
    "*.zip",
    "*.tar.gz",
    "*.rar",
    "hs_err_pid*",
    "replacer.log",
    "*.orig",
    "*.rej",
    "target/",
    ".gradle/",
    "build/",
    "out/",
    "*.iml",
    ".idea/",
    "*.ipr",
    "*.iws",
]


def java_preset() -> GitIgnorePreset:
    return _preset("java", "Java / Maven / Gradle", "Maven target, Gradle cache, IntelliJ artifacts", JAVA_RULES)


CSHARP_RULES = [
    "*.dll",
    "*.exe",
    "*.app",
    "*.user",
    "*.userprefs",
    "*.suo",
    "*.cache",
    "*.log",
    "obj/",
    "bin/",
    ".vs/",
    "publish/",
    "*.nupkg",
    "*.snk",
    "Project.lock.json",
]


def csharp_preset() -> GitIgnorePreset:
    return _preset("csharp", "C# / .NET", "MSBuild, NuGet, Visual Studio artifacts", CSHARP_RULES)


SWIFT_RULES = [
    "build/",
    "DerivedData/",
    "*.xcodeproj/project.xcuserdata/",
    "*.xcworkspace/xcuserdata/",
    "Package.resolved",
    "*.swpmproj",
    ".build/",
]


def swift_preset() -> GitIgnorePreset:
    return _preset("swift", "Swift / iOS", "Xcode, SPM, derived data", SWIFT_RULES)


KOTLIN_RULES = [
    "*.class",
    "*.apk",
    "*.aab",
    "build/",
    ".gradle/",
    "local.properties",
    ".idea/",
    "*.iml",
    ".cxx/",
    "externalNativeBuild/",
]


def kotlin_preset() -> GitIgnorePreset:
    return _preset("kotlin", "Kotlin / Android", "Gradle, APK/AAB, local.properties", KOTLIN_RULES)


PHP_RULES = [
    "vendor/",
    "composer.lock",
    ".env",
    ".env.*",
    "*.php",
    "bootstrap/cache/",
    "storage/*.key",
    "storage/logs/*.log",
    "storage/framework/cache/*.php",
    "storage/framework/sessions/*",
    "storage/framework/views/*",
    "node_modules/",
    "public/hot",
    "public/storage",
    "public/*.css",
    "public/*.js",
    ".vscode/",
    ".idea/",
]


def php_preset() -> GitIgnorePreset:
    return _preset("php", "PHP / Laravel", "Composer, .env, bootstrap/cache, storage", PHP_RULES)


RUBY_RULES = [
    "*.gem",
    "*.rbc",
    "/.config/",
    "coverage/",
    "InstalledFiles",
    "lib/bundler/man",
    "tmp/",
    "vendor/",
    "Gemfile.lock",
    ".ruby-version",
    ".ruby-gemset",
    "*.bundle",
    ".bundle/",
    "*.o",
    "*.so",
    "*.o.bak",
    "*.orig",
    "*.rej",
    ".DS_Store",
]


def ruby_preset() -> GitIgnorePreset:
    return _preset("ruby", "Ruby / Rails", "Bundler, gems, tmp, vendor", RUBY_RULES)


GAME_RULES = [
    "# Unity",
    "[Ll]ibrary/",
    "[Tt]emp/",
    "[Oo]bj/",
    "[Bb]uild/",
    "[Bb]uilds/",
    "[Aa]ssets/AssetStoreTools*",
    "# Unreal",
    "*.sdf",
    "*.opendb",
    "*.opensdf",
    "Intermediate/",
    "Saved/",
    "Binaries/",
    "Build/",
    ".vs/",
    "*.vcxproj",
    "*.vcxproj.filters",
    "*.uproject",
]


def game_preset() -> GitIgnorePreset:
    return _preset("games", "Unity / Unreal", "Library, Temp, Binaries, Intermediate, Saved", GAME_RULES)


DOCKER_RULES = [
    "Dockerfile.*",
    "docker-compose.override.yml",
    ".dockerignore",
    "volumes/",
    "data/",
]


def docker_preset() -> GitIgnorePreset:
    return _preset("docker", "Docker", "override compose, volumes, data", DOCKER_RULES)


TERRAFORM_RULES = [
    ".terraform/",
    "*.tfstate",
    "*.tfstate.backup",
    "*.tfvars",
    "crash.log",
    "crash.*.log",
    ".terraform.lock.hcl",
    "override.tf",
    "override.tf.json",
    "_override.tf",
    "_override.tf.json",
    ".terraform.tfplan",
]


def terraform_preset() -> GitIgnorePreset:
    return _preset("terraform", "Terraform", ".terraform, tfstate, tfvars", TERRAFORM_RULES)


OS_WINDOWS_RULES = [
    "Thumbs.db",
    "ehthumbs.db",
    "Desktop.ini",
    "$RECYCLE.BIN/",
    "*.lnk",
]


def windows_preset() -> GitIgnorePreset:
    return _preset("windows", "Windows", "Thumbs.db, Desktop.ini, Recycle Bin", OS_WINDOWS_RULES)


OS_MACOS_RULES = [
    ".DS_Store",
    ".AppleDouble",
    ".LSOverride",
    "Icon",
    "._*",
    ".Spotlight-V100",
    ".Trashes",
    "ehthumbs.db",
    "Thumbs.db",
]


def macos_preset() -> GitIgnorePreset:
    return _preset("macos", "macOS", ".DS_Store, Spotlight, Trashes", OS_MACOS_RULES)


OS_LINUX_RULES = [
    "*~",
    ".*.swp",
    ".directory",
    ".Trash-*",
    "Thumbs.db",
]


def linux_preset() -> GitIgnorePreset:
    return _preset("linux", "Linux", "backup files, swap files, Trash", OS_LINUX_RULES)


IDE_VSCODE_RULES = [
    ".vscode/",
    ".code-workspace",
]


def vscode_preset() -> GitIgnorePreset:
    return _preset("vscode", "VS Code", "vscode settings folder", IDE_VSCODE_RULES)


IDEA_RULES = [
    ".idea/",
    "*.iml",
    "*.ipr",
    "*.iws",
]


def idea_preset() -> GitIgnorePreset:
    return _preset("idea", "IntelliJ IDEA", ".idea, iml, ipr, iws", IDEA_RULES)


ALL_PRESETS: dict[str, GitIgnorePreset] = {
    "python": python_preset(),
    "cpp": cpp_preset(),
    "rust": rust_preset(),
    "go": go_preset(),
    "node": node_preset(),
    "java": java_preset(),
    "csharp": csharp_preset(),
    "swift": swift_preset(),
    "kotlin": kotlin_preset(),
    "php": php_preset(),
    "ruby": ruby_preset(),
    "games": game_preset(),
    "docker": docker_preset(),
    "terraform": terraform_preset(),
    "windows": windows_preset(),
    "macos": macos_preset(),
    "linux": linux_preset(),
    "vscode": vscode_preset(),
    "idea": idea_preset(),
}


def preset_keys() -> list[str]:
    return list(ALL_PRESETS.keys())


def get_preset(key: str) -> GitIgnorePreset | None:
    return ALL_PRESETS.get(key)


def merge_presets(keys: list[str]) -> list[str]:
    """Merge multiple presets, deduplicating rules, preserving first-seen order.

    Mandatory ``.git-tui`` rules are always appended last.
    """
    seen: set[str] = set()
    merged: list[str] = []
    for key in keys:
        preset = get_preset(key)
        if preset is None:
            continue
        for rule in preset.rules:
            if rule not in seen:
                seen.add(rule)
                merged.append(rule)
    for rule in MANDATORY_RULES:
        if rule not in seen:
            seen.add(rule)
            merged.append(rule)
    return merged
