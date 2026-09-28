#!/usr/bin/env python3
"""preview_tail.py: install or remove the Markdown Preview Tail VS Code extension.

The extension (vscode/md-preview-tail/) keeps VS Code's Markdown preview where you're
reading when a lesson log is rewritten, instead of jumping to the top.

    preview_tail.py auto        what the plugin's SessionStart hook runs: install or update it,
                                or remove it if LEARN_PREVIEW_TAIL is off. Silent, never fails.
    preview_tail.py install     install (or update) it now
    preview_tail.py uninstall   remove it now
    preview_tail.py status

The switch: set LEARN_PREVIEW_TAIL to "off" (or 0 / false / no) in the env block of
~/.claude/settings.json. The next session start removes the extension and leaves it off.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = PLUGIN_ROOT / "vscode" / "md-preview-tail"
VSIX = EXT_DIR / "md-preview-tail.vsix"
EXT_ID = "learn.md-preview-tail"
OLD_IDS = ["local.md-preview-tail"]  # a hand-built predecessor; two copies would fight over the scroll
OFF = {"off", "0", "false", "no"}


def version() -> str:
    return json.loads((EXT_DIR / "package.json").read_text(encoding="utf-8"))["version"]


def extensions_dir() -> Path:
    return Path(os.environ.get("VSCODE_EXTENSIONS") or Path.home() / ".vscode" / "extensions")


def installed(ext_id: str) -> list[str]:
    """Installed versions, read from VS Code's registry (extensions.json), so there's no need
    to start its CLI. The folder alone isn't proof: after an uninstall VS Code leaves it until
    its next restart, having already dropped it from the registry."""
    d = extensions_dir()
    try:
        registry = json.loads((d / "extensions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return sorted(p.name[len(ext_id) + 1:] for p in d.glob(f"{ext_id}-*") if p.is_dir()) if d.is_dir() else []
    try:
        obsolete = json.loads((d / ".obsolete").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        obsolete = {}
    return sorted(e.get("version", "") for e in registry
                  if str((e.get("identifier") or {}).get("id", "")).lower() == ext_id
                  and not obsolete.get(e.get("relativeLocation", "")))


def code_cli() -> str | None:
    return shutil.which("code") or shutil.which("code.cmd")


def run_code(*args: str) -> bool:
    cli = code_cli()
    if not cli:
        print("VS Code's `code` command isn't on PATH; skipping.", file=sys.stderr)
        return False
    r = subprocess.run([cli, *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print((r.stderr or r.stdout).strip(), file=sys.stderr)
    return r.returncode == 0


def install() -> bool:
    for old in OLD_IDS:
        if installed(old):
            run_code("--uninstall-extension", old)
    if version() in installed(EXT_ID):
        return True
    return run_code("--install-extension", str(VSIX), "--force")


def uninstall() -> bool:
    ok = True
    for ext_id in [EXT_ID, *OLD_IDS]:
        if installed(ext_id):
            ok = run_code("--uninstall-extension", ext_id) and ok
    return ok


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "auto":
        try:
            if os.environ.get("LEARN_PREVIEW_TAIL", "on").strip().lower() in OFF:
                if installed(EXT_ID) or any(installed(o) for o in OLD_IDS):
                    uninstall()
            elif version() not in installed(EXT_ID) or any(installed(o) for o in OLD_IDS):
                install()
        except Exception as exc:  # never disturb a session start
            print(f"preview_tail: {exc!r}", file=sys.stderr)
        return
    if cmd == "install":
        print("Installed. Reload VS Code (Developer: Reload Window) or reopen the preview." if install()
              else "Install failed.")
    elif cmd == "uninstall":
        print("Removed. Reload VS Code to unload it." if uninstall() else "Uninstall failed.")
    elif cmd == "status":
        switch = os.environ.get("LEARN_PREVIEW_TAIL", "on")
        print(f"switch LEARN_PREVIEW_TAIL : {switch} ({'off' if switch.strip().lower() in OFF else 'on'})")
        print(f"bundled version          : {version()}")
        print(f"installed {EXT_ID:15s}: {', '.join(installed(EXT_ID)) or 'no'}")
        for old in OLD_IDS:
            print(f"installed {old:15s}: {', '.join(installed(old)) or 'no'}")
        print(f"VS Code CLI              : {code_cli() or 'not found'}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
