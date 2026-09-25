#!/usr/bin/env python3
"""profiles.py: learner profiles for the teach skill.

A profile is a topic-agnostic markdown file describing one learner: the scientific and
mathematical foundations they hold (with evidence), and how they learn. Profiles are shared
across repos, so they live outside any repo:

  $LEARN_PROFILES_DIR if set (point it at a synced folder, e.g. in Dropbox, to share
  profiles between machines), else ~/.claude/learner-profiles

    profiles.py list                what /learn:teach injects at the top of the skill
    profiles.py new <name>          create from skills/teach/profile-template.md, print the path
    profiles.py path <name>         print the path of an existing profile
    profiles.py foundations <name>  list foundation entries with status and date but NOT
                                    level/floor/ceiling/pace (for blind re-probing)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = PLUGIN_ROOT / "skills" / "teach" / "profile-template.md"


def profiles_dir() -> Path:
    env = os.environ.get("LEARN_PROFILES_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude" / "learner-profiles"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lstrip("@").lower()).strip("-")


def front(path: Path) -> dict:
    """The key: value pairs of a profile's YAML frontmatter (flat, strings only)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        k, _, v = line.partition(":")
        if v:
            out[k.strip()] = v.strip()
    return out


def all_profiles() -> list[tuple[str, Path, dict]]:
    d = profiles_dir()
    found = [(p.stem, p, front(p)) for p in d.glob("*.md")] if d.is_dir() else []
    return sorted(found, key=lambda t: t[2].get("updated", ""), reverse=True)


def cmd_list() -> None:
    d = profiles_dir()
    profiles = all_profiles()
    print(f"Profiles folder: {d}")
    if not profiles:
        print("Existing profiles: none")
        return
    print("Existing profiles (most recently updated first):")
    for slug, path, meta in profiles:
        print(f"- @{slug}: {meta.get('learner', slug)}, updated {meta.get('updated', '?')}, "
              f"{meta.get('sessions', '0')} sessions ({path})")


def cmd_new(name: str) -> None:
    slug = slugify(name)
    if not slug:
        sys.exit("A profile needs a name.")
    d = profiles_dir()
    path = d / f"{slug}.md"
    if path.exists():
        sys.exit(f"@{slug} already exists: {path}")
    d.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    body = TEMPLATE.read_text(encoding="utf-8")
    body = body.replace("{{name}}", name.strip().lstrip("@")).replace("{{slug}}", slug).replace("{{date}}", today)
    path.write_text(body, encoding="utf-8")
    print(f"Created @{slug}: {path}")


def find(name: str) -> Path:
    slug = slugify(name)
    for s, path, meta in all_profiles():
        if slug in (s, slugify(meta.get("learner", ""))):
            return path
    sys.exit(f"No profile @{slug} in {profiles_dir()}")


def cmd_foundations(name: str) -> None:
    """Foundation entries WITHOUT their level, floor, ceiling or pace, for blind reassessment."""
    path = find(name)
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # the template's example entry
    section = re.search(r"^## Foundations\s*$(.*?)(?=^## )", text, re.M | re.S)
    if not section:
        print("No Foundations section.")
        return
    area, n = None, 0
    for block in re.split(r"(?=^#{3,4} )", section.group(1), flags=re.M):
        head = block.strip().splitlines()[0] if block.strip() else ""
        if head.startswith("### "):
            area = head[4:].strip()
        elif head.startswith("#### "):
            status = re.search(r"\*\*Status:\*\*\s*([\w-]+)", block)
            seen = re.search(r"\*\*Last seen:\*\*\s*([\d-]+)", block)
            n_ev = len(re.findall(r"^\s+- \d{4}-\d{2}-\d{2}", block, re.M))
            print(f"- {head[5:].strip()}  [area: {area}; status: {status.group(1) if status else '?'}; "
                  f"last seen: {seen.group(1) if seen else '?'}; {n_ev} evidence lines]")
            n += 1
    if n == 0:
        print("No foundation entries yet.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252, which mangles "›"
    args = sys.argv[1:]
    if not args or args[0] not in ("list", "new", "path", "foundations"):
        sys.exit(__doc__)
    if args[0] == "list":
        cmd_list()
    elif len(args) < 2:
        sys.exit(f"{args[0]} needs a name")
    elif args[0] == "new":
        cmd_new(" ".join(args[1:]))
    elif args[0] == "foundations":
        cmd_foundations(" ".join(args[1:]))
    else:
        print(find(" ".join(args[1:])))


if __name__ == "__main__":
    main()
