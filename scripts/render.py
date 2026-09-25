#!/usr/bin/env python3
"""render.py: port of upstream extensions/visual-tools. Mermaid or SVG source on stdin, PNG out.

The maker subagents (agents/mermaid-maker.md, svg-maker.md) call this through Bash:

    python <plugin>/scripts/render.py mermaid --project <project> [--save-as SLUG] <<'EOF'
    graph TD
      A --> B
    EOF

    python <plugin>/scripts/render.py svg --project <project> [--save-as SLUG] <<'EOF'
    <svg ...>...</svg>
    EOF

Without --save-as it renders a preview into <project>/.claude/learn/.preview/ and prints its
path. The maker Reads that PNG to look at it. With --save-as it renders the same source and
publishes it to <project>/lessons/viz/viz-<slug>-<ms>.png, printing the RESULT block the
maker returns to the teacher. Without --project, the project is $CLAUDE_PROJECT_DIR, else
the nearest folder above the current one that has a .claude folder, else the current one.

Upstream had write/edit/render tools sharing a managed source file. Here the maker
sends the whole source on every render, because the sources are small and one command
is simpler than three.

One-time setup per machine (installs mermaid-cli into ~/.cache/learn-visual-tools):

    python <plugin>/scripts/render.py setup
    python <plugin>/scripts/render.py doctor
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

def find_project(explicit: str | None = None) -> Path:
    if explicit or os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(explicit or os.environ["CLAUDE_PROJECT_DIR"])
    cwd = Path.cwd()
    for p in (cwd, *cwd.parents):
        if p != Path.home() and (p / ".claude").is_dir():
            return p
    return cwd


# Set from --project in main(); these defaults serve `doctor` without one
PROJECT = find_project()
PREVIEW_DIR = PROJECT / ".claude" / "learn" / ".preview"
VIZ_DIR = PROJECT / "lessons" / "viz"
SELF = Path(__file__).resolve()
TOOLS_HOME = Path(os.environ.get("LEARN_TOOLS_HOME", Path.home() / ".cache" / "learn-visual-tools"))
MMDC_JS = TOOLS_HOME / "node_modules" / "@mermaid-js" / "mermaid-cli" / "src" / "cli.js"
PUPPETEER_CFG = TOOLS_HOME / "puppeteer.json"
RENDER_TIMEOUT_S = 120
PREVIEW_MAX_AGE_S = 24 * 3600

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if c and os.path.isfile(c):
            return c
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=RENDER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        fail(f"Render timed out after {RENDER_TIMEOUT_S}s: {cmd[0]}")
    except FileNotFoundError:
        fail(f"Not found: {cmd[0]}")


def clean_previews() -> None:
    cutoff = time.time() - PREVIEW_MAX_AGE_S
    for p in PREVIEW_DIR.glob("*"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def render_mermaid(src: Path, png: Path) -> None:
    if not MMDC_JS.is_file():
        fail(f"mermaid-cli is not installed at {TOOLS_HOME}. Run once on this machine: python \"{SELF}\" setup")
    if not PUPPETEER_CFG.is_file():
        write_puppeteer_cfg()
    r = run(["node", str(MMDC_JS), "-i", str(src), "-o", str(png), "-b", "white", "-s", "2",
             "-p", str(PUPPETEER_CFG), "-q"])
    if r.returncode != 0 or not png.is_file():
        # mmdc prints the parse error plus a long stack; the first lines are the useful part
        err = "\n".join((r.stderr or r.stdout).strip().splitlines()[:15])
        fail(f"Mermaid render failed:\n{err}")


def render_svg(src: Path, png: Path) -> None:
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        r = run([rsvg, "-b", "white", "-z", "2", "-o", str(png), str(src)])
        if r.returncode == 0 and png.is_file():
            return
        fail(f"SVG render failed (rsvg-convert):\n{(r.stderr or r.stdout).strip()}")
    magick = shutil.which("magick")
    if magick:
        r = run([magick, "-background", "white", "-density", "192", str(src), str(png)])
        if r.returncode == 0 and png.is_file():
            return
        fail(f"SVG render failed (ImageMagick):\n{(r.stderr or r.stdout).strip()}")
    fail("No SVG renderer found: install rsvg-convert (librsvg) or ImageMagick.")


def publish(png: Path, slug: str) -> Path:
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    clean = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "viz"
    dest = VIZ_DIR / f"viz-{clean}-{int(time.time() * 1000)}.png"
    shutil.copyfile(png, dest)
    return dest


def cmd_render(kind: str, save_as: str | None) -> None:
    source = sys.stdin.buffer.read().decode("utf-8-sig").strip()
    if not source:
        fail(f"Empty source: pipe the {kind} source on stdin (heredoc).")
    if kind == "svg" and "<svg" not in source:
        fail("SVG source must contain a complete <svg>...</svg> element.")
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    clean_previews()
    # Name previews by content hash so parallel makers never overwrite each other's files
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    ext = "mmd" if kind == "mermaid" else "svg"
    src = PREVIEW_DIR / f"{kind}-{digest}.{ext}"
    png = PREVIEW_DIR / f"{kind}-{digest}.png"
    src.write_text(source + "\n", encoding="utf-8")
    if not png.is_file():
        (render_mermaid if kind == "mermaid" else render_svg)(src, png)
    if save_as is None:
        print(f"Rendered preview: {png}")
        print("Read that PNG and look at it before publishing. To publish, re-run with --save-as <slug>.")
        return
    dest = publish(png, save_as)
    print("Published. Read it once more to confirm, then end your reply with:\n")
    print(f"RESULT:\nfilename: {dest.name}\npath: {dest}")


def write_puppeteer_cfg() -> None:
    chrome = find_chrome()
    if not chrome:
        fail("No Chrome/Edge found. Set CHROME_PATH to a Chromium-based browser executable.")
    TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    PUPPETEER_CFG.write_text(json.dumps({"executablePath": chrome, "headless": True}, indent=2),
                             encoding="utf-8")


def cmd_setup() -> None:
    npm = shutil.which("npm")
    if not npm:
        fail("npm not found: install Node.js first.")
    TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    pkg = TOOLS_HOME / "package.json"
    if not pkg.is_file():
        pkg.write_text('{"name": "learn-visual-tools", "private": true}\n', encoding="utf-8")
    # Use the installed Chrome instead of letting puppeteer download its own (~150 MB)
    env = {**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "true"}
    r = subprocess.run([npm, "install", "--no-fund", "--no-audit", "@mermaid-js/mermaid-cli@^11"],
                       cwd=TOOLS_HOME, env=env)
    if r.returncode != 0:
        fail("npm install failed.")
    write_puppeteer_cfg()
    cmd_doctor()


def cmd_doctor() -> None:
    print(f"tools home     : {TOOLS_HOME}")
    print(f"mermaid-cli    : {'ok' if MMDC_JS.is_file() else 'MISSING (run setup)'}")
    print(f"browser        : {find_chrome() or 'MISSING'}")
    print(f"rsvg-convert   : {shutil.which('rsvg-convert') or 'missing'}")
    print(f"magick         : {shutil.which('magick') or 'missing'}")
    print(f"previews       : {PREVIEW_DIR}")
    print(f"published viz  : {VIZ_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["mermaid", "svg", "setup", "doctor"])
    ap.add_argument("--save-as", metavar="SLUG", help="publish the render into lessons/viz under this slug")
    ap.add_argument("--project", metavar="DIR", help="project root (default: $CLAUDE_PROJECT_DIR or nearest .claude)")
    a = ap.parse_args()
    global PROJECT, PREVIEW_DIR, VIZ_DIR
    PROJECT = find_project(a.project)
    PREVIEW_DIR = PROJECT / ".claude" / "learn" / ".preview"
    VIZ_DIR = PROJECT / "lessons" / "viz"
    if a.command in ("mermaid", "svg"):
        cmd_render(a.command, a.save_as)
    elif a.command == "setup":
        cmd_setup()
    else:
        cmd_doctor()


if __name__ == "__main__":
    main()
