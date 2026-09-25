#!/usr/bin/env python3
"""md_log.py: port of upstream extensions/md-log.ts, plus the parts of quiz.ts that a hook can do.

Mirrors a Claude Code session into a markdown file for comfortable reading, because the
terminal renders neither LaTeX nor mermaid nor images. Captures only reading-relevant
content: user prompts, assistant prose, and AskUserQuestion Q&A (quizzes and questions).
Tool calls such as Bash, Read and Edit are left out.

Commands (the /learn:md-log skill runs these; --project defaults to $CLAUDE_PROJECT_DIR,
else the nearest folder above the current one that has a .claude folder):
    md_log.py [--project DIR] link <session_id> <path>   link a file and backfill it
    md_log.py [--project DIR] off <session_id>           stop logging
    md_log.py [--project DIR] status <session_id>
    md_log.py hook                                       hook entry point (JSON on stdin)

State lives in the project: <project>/.claude/learn/links.json maps session IDs to log
files, and published diagrams are looked up in <project>/lessons/viz/.

How it differs from upstream:
  * Upstream appended per event. This regenerates everything below a marker line from
    the session transcript on each hook, so it backfills, follows /rewind branches, and
    heals after a missed event. Anything you write ABOVE the marker is kept; anything
    below it is overwritten.
  * Obsidian embeds ![[viz-x.png|500]] are rewritten to standard markdown image links
    relative to the log file, so they render in VS Code's preview too.

Quiz support (a hook stands in for upstream's quiz tool):
  An AskUserQuestion question whose header starts with "Quiz" is a graded quiz. In the
  PreToolUse hook, this script
    * appends an "I don't know" option when there is room (AskUserQuestion allows 4), and
    * shuffles the real options, keeping "I don't know" last, so the correct answer's
      position carries no signal. Header "Quiz fixed" skips the shuffle for ordered options.
  Grading happens in Claude's next reply (see skills/teach/SKILL.md).

Hooks never block and never print to stdout except PreToolUse JSON, because
UserPromptSubmit stdout is injected into Claude's context.
"""

from __future__ import annotations

import glob
import json
import os
import random
import re
import sys
from pathlib import Path

def find_project(explicit: str | None = None) -> Path:
    if explicit or os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(explicit or os.environ["CLAUDE_PROJECT_DIR"])
    cwd = Path.cwd()
    for p in (cwd, *cwd.parents):
        if p != Path.home() and (p / ".claude").is_dir():
            return p
    return cwd


def configure(project: Path) -> None:
    global PROJECT, LINKS_FILE, VIZ_DIR
    PROJECT = project
    LINKS_FILE = project / ".claude" / "learn" / "links.json"
    VIZ_DIR = project / "lessons" / "viz"


configure(find_project())
QA_TOOL = "AskUserQuestion"
MARKER = "<!-- md-log: everything below this line is regenerated from the session; edits here are overwritten -->"
DONT_KNOW_LABEL = "I don't know"
DONT_KNOW_RE = re.compile(r"^\s*i\s+(do\s+not|don'?t)\s+know\s*[.!]?\s*$", re.I)
MAX_OPTIONS = 4

# Context Claude Code wraps around user text that isn't the user's own words
NOISE_TAGS = re.compile(
    r"<(system-reminder|ide_opened_file|ide_selection|local-command-stdout|local-command-stderr|"
    r"local-command-caveat|command-message|command-name|command-args|user-memory-input)\b[^>]*>.*?</\1>",
    re.S,
)
SKIP_PREFIXES = ("<task-notification", "<local-command", "[Request interrupted", "Caveat:")
WIKI_EMBED = re.compile(r"!\[\[([^\]|]+?\.(?:png|jpe?g|gif|svg|webp))(?:\|(\d+))?\]\]", re.I)


# ── quiz helpers ─────────────────────────────────────────────────────────────

def is_quiz(q: dict) -> bool:
    return str(q.get("header", "")).strip().lower().startswith("quiz")


def prepare_quiz(q: dict) -> dict:
    """Add "I don't know" if there's room, then shuffle the real options (IDK stays last)."""
    q = dict(q)
    opts = [dict(o) for o in q.get("options", []) if isinstance(o, dict)]
    idk = [o for o in opts if DONT_KNOW_RE.match(str(o.get("label", "")))]
    real = [o for o in opts if not DONT_KNOW_RE.match(str(o.get("label", "")))]
    if not idk and len(real) < MAX_OPTIONS:
        idk = [{"label": DONT_KNOW_LABEL, "description": "Skip guessing: marks a genuine gap, not a wrong answer."}]
    if "fixed" not in str(q.get("header", "")).lower():
        random.shuffle(real)
    q["options"] = real + idk[:1]
    return q


# ── links ────────────────────────────────────────────────────────────────────

def load_links() -> dict:
    try:
        return json.loads(LINKS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_links(links: dict) -> None:
    LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LINKS_FILE.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")


def resolve_log(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else PROJECT / p


def find_transcript(session_id: str) -> Path | None:
    hits = glob.glob(str(Path.home() / ".claude" / "projects" / "*" / f"{session_id}.jsonl"))
    return Path(hits[0]) if hits else None


# ── transcript → blocks ─────────────────────────────────────────────────────

def load_entries(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass  # a line still being written
    return out


def active_chain(entries: list[dict]) -> list[dict]:
    """Main-thread messages on the active branch (so abandoned /rewind branches drop out)."""
    msgs = [e for e in entries if e.get("type") in ("user", "assistant") and not e.get("isSidechain")]
    if not msgs:
        return []
    by_id = {e["uuid"]: e for e in entries if e.get("uuid")}
    chain, seen, cur = [], set(), msgs[-1]
    while cur is not None and cur.get("uuid") not in seen:
        seen.add(cur.get("uuid"))
        chain.append(cur)
        pid = cur.get("parentUuid") or cur.get("logicalParentUuid")
        cur = by_id.get(pid) if pid else None
    chain.reverse()
    chain = [e for e in chain if e.get("type") in ("user", "assistant") and not e.get("isSidechain")]
    # A badly broken parent chain is worse than an abandoned branch: fall back to file order
    return chain if len(chain) >= 0.5 * len(msgs) else msgs


def clean_user_text(text: str) -> str | None:
    stripped = text.lstrip()
    if not stripped or stripped.startswith(SKIP_PREFIXES):
        return None
    name = re.search(r"<command-name>\s*/?([^<\s]+)\s*</command-name>", text)
    if name:
        cmd = name.group(1)
        if cmd.split(":")[-1] in ("md-log", "clear", "compact", "resume", "rewind", "model", "config", "cost", "context"):
            return None
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        rest = NOISE_TAGS.sub("", text).strip()
        line = f"/{cmd} {args.group(1).strip() if args else ''}".strip()
        return f"{line}\n\n{rest}".strip() if rest else line
    text = NOISE_TAGS.sub("", text).strip()
    return text or None


def user_prompt(e: dict) -> str | None:
    if e.get("isMeta") or e.get("isCompactSummary") or e.get("isVisibleInTranscriptOnly"):
        return None
    content = e.get("message", {}).get("content")
    if isinstance(content, str):
        return clean_user_text(content)
    if not isinstance(content, list):
        return None
    blocks = [b for b in content if isinstance(b, dict)]
    if any(b.get("type") == "tool_result" for b in blocks):
        return None
    text = clean_user_text("\n".join(b.get("text", "") for b in blocks if b.get("type") == "text") or " ")
    images = sum(1 for b in blocks if b.get("type") == "image")
    if images:
        text = f"{text or ''}\n\n*({images} image{'s' if images > 1 else ''} attached)*".strip()
    return text


def callout(kind: str, title: str, body: list[str]) -> str:
    return "\n".join([f"> [!{kind}] {title}"] + [f"> {ln}" if ln else ">" for ln in body])


def user_block(text: str) -> str:
    return f"> [!quote] YOU\n\n{text}"


def assistant_block(text: str) -> str:
    return f"> [!abstract] CLAUDE\n\n{text}"


def question_block(q: dict) -> str:
    quiz = is_quiz(q)
    body = str(q.get("question", "")).split("\n")
    opts = q.get("options") or []
    if opts:
        body.append("")
        for i, o in enumerate(opts, 1):
            label, desc = str(o.get("label", "")), str(o.get("description", "") or "").strip()
            # Quiz descriptions of the IDK option are boilerplate; real descriptions stay
            show_desc = desc and not (quiz and DONT_KNOW_RE.match(label))
            body.append(f"{i}. {label}" + (f": {desc}" if show_desc else ""))
    if q.get("multiSelect"):
        body.append("")
        body.append("*(select all that apply)*")
    return callout("question", "Quiz" if quiz else "Question", body)


def answer_block(q: dict, answer: str | None, note: str | None) -> str:
    quiz = is_quiz(q)
    labels = [str(o.get("label", "")) for o in q.get("options") or []]
    if answer is None:
        return callout("warning", "Skipped", ["(no answer)"])
    picked: list[str]
    if answer in labels:
        picked = [answer]
    else:
        parts = [p.strip() for p in answer.split(",")]
        picked = parts if parts and all(p in labels for p in parts) else []
    if picked:
        lines = [f"{labels.index(p) + 1}. {p}" for p in picked]
    else:
        lines = [f"Other: {answer}"]
    if quiz and picked and all(DONT_KNOW_RE.match(p) for p in picked):
        title, kind = "Your answer: I don't know", "question"
        lines = []
    else:
        title, kind = ("Your answer" if quiz else "Answer"), "example"
    if note:
        lines += ([""] if lines else []) + [f"Note: {note}"]
    return callout(kind, title, lines or ["—"])


def qa_blocks(questions: list[dict], result) -> list[str]:
    """Question callouts, followed by answer callouts once there is a result."""
    out = []
    answers = result.get("answers", {}) if isinstance(result, dict) else {}
    notes = result.get("annotations", {}) if isinstance(result, dict) else {}
    for q in questions:
        out.append(question_block(q))
        if result is None:
            continue
        if not isinstance(result, dict):
            out.append(callout("warning", "Cancelled", ["(question dismissed)"]))
            continue
        qtext = q.get("question", "")
        note = (notes.get(qtext) or {}).get("notes") if isinstance(notes.get(qtext), dict) else None
        out.append(answer_block(q, answers.get(qtext), note))
    return out


def embed_links(text: str, log_dir: Path) -> str:
    def repl(m: re.Match) -> str:
        target = VIZ_DIR / m.group(1)
        if not target.is_file():
            return m.group(0)
        rel = os.path.relpath(target, log_dir).replace("\\", "/").replace(" ", "%20")
        alt = f"viz|{m.group(2)}" if m.group(2) else "viz"
        return f"![{alt}]({rel})"
    return WIKI_EMBED.sub(repl, text)


def build_blocks(chain: list[dict], log_dir: Path, pending: dict) -> list[str]:
    """pending: {"questions": {tool_use_id: [q...]}, "results": {tool_use_id: result},
                 "prompt": str|None, "last_assistant": str|None} from the current hook."""
    blocks: list[str] = []
    text_buf: list[str] = []
    qa_calls: dict[str, list[dict]] = {}
    seen_ids: set[str] = set()
    answered: set[str] = set()

    def flush():
        if text_buf:
            blocks.append(assistant_block(embed_links("\n\n".join(text_buf), log_dir)))
            text_buf.clear()

    for e in chain:
        content = e.get("message", {}).get("content")
        if e.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    text_buf.append(b["text"].strip())
                elif b.get("type") == "tool_use" and b.get("name") == QA_TOOL:
                    qa_calls[b.get("id")] = (b.get("input") or {}).get("questions") or []
                elif b.get("type") == "tool_use" and b.get("name") == "Skill":
                    flush()
                    blocks.append(callout("note", f"SKILL loaded: {(b.get('input') or {}).get('skill', '?')}", []))
            continue
        if e.get("type") != "user":
            continue
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in qa_calls:
                    tid = b["tool_use_id"]
                    res = e.get("toolUseResult")
                    # The result echoes the questions as displayed (after the hook's shuffle)
                    qs = res.get("questions") if isinstance(res, dict) and res.get("questions") else qa_calls[tid]
                    flush()
                    blocks.extend(qa_blocks(qs, res))
                    seen_ids.add(tid)
                    answered.add(tid)
        prompt = user_prompt(e)
        if prompt:
            flush()
            blocks.append(user_block(prompt))

    # Questions asked but not yet answered: show them live, in their displayed order
    for tid, qs in qa_calls.items():
        if tid in answered:
            continue
        flush()
        seen_ids.add(tid)
        if tid in pending["results"]:
            res = pending["results"][tid]
            blocks.extend(qa_blocks(res.get("questions") or qs if isinstance(res, dict) else qs, res))
        else:
            blocks.extend(qa_blocks(pending["questions"].get(tid, qs), None))
    flush()

    # Events from this hook that the transcript hasn't recorded yet
    for tid, qs in pending["questions"].items():
        if tid not in seen_ids:
            blocks.extend(qa_blocks(qs, pending["results"].get(tid)))
            seen_ids.add(tid)
    for tid, res in pending["results"].items():
        if tid not in seen_ids and isinstance(res, dict) and res.get("questions"):
            blocks.extend(qa_blocks(res["questions"], res))
    # Stop can fire before the final text reaches the transcript; the next render heals it
    last = embed_links((pending.get("last_assistant") or "").strip(), log_dir)
    squash = lambda s: re.sub(r"\s+", " ", s)
    if last and squash(last)[-200:] not in squash("\n".join(blocks)):
        blocks.append(assistant_block(last))
    prompt = pending.get("prompt")
    if prompt:
        cleaned = None if re.match(r"\s*/(learn:)?md-log\b", prompt) else clean_user_text(prompt)
        if cleaned and (not blocks or blocks[-1] != user_block(cleaned)):
            blocks.append(user_block(cleaned))
    return blocks


def write_log(log: Path, blocks: list[str]) -> None:
    head = ""
    if log.is_file():
        current = log.read_text(encoding="utf-8", errors="replace")
        i = current.find(MARKER)
        head = current[:i] if i >= 0 else (current.rstrip() + "\n\n" if current.strip() else "")
    body = head + MARKER + "\n\n" + "\n\n".join(blocks) + "\n"
    tmp = log.with_name(log.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, log)
    except OSError:  # Windows: the viewer or Dropbox holds the file; write in place instead
        log.write_text(body, encoding="utf-8")
        tmp.unlink(missing_ok=True)


def render(session_id: str, transcript: Path | None, pending: dict | None = None) -> int:
    stored = load_links().get(session_id)
    if not stored:
        return 0
    log = resolve_log(stored)
    transcript = transcript or find_transcript(session_id)
    chain = active_chain(load_entries(transcript)) if transcript and transcript.is_file() else []
    pending = pending or {"questions": {}, "results": {}, "prompt": None, "last_assistant": None}
    blocks = build_blocks(chain, log.parent, pending)
    write_log(log, blocks)
    return len(blocks)


# ── entry points ─────────────────────────────────────────────────────────────

def hook() -> None:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    event = payload.get("hook_event_name")
    sid = payload.get("session_id", "")
    tpath = Path(payload["transcript_path"]) if payload.get("transcript_path") else None
    pending = {"questions": {}, "results": {}, "prompt": None, "last_assistant": None}
    out = None

    if event == "PreToolUse" and payload.get("tool_name") == QA_TOOL:
        tool_input = payload.get("tool_input") or {}
        qs = tool_input.get("questions") or []
        if any(is_quiz(q) for q in qs):
            qs = [prepare_quiz(q) if is_quiz(q) else q for q in qs]
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "updatedInput": {**tool_input, "questions": qs}}}
        pending["questions"][payload.get("tool_use_id", "")] = qs
    elif event == "PostToolUse" and payload.get("tool_name") == QA_TOOL:
        pending["results"][payload.get("tool_use_id", "")] = payload.get("tool_response")
    elif event == "UserPromptSubmit":
        pending["prompt"] = payload.get("prompt") or payload.get("user_prompt")
    elif event == "Stop":
        pending["last_assistant"] = payload.get("last_assistant_message")

    # Print the quiz rewrite first, so a logging failure can't lose it
    if out is not None:
        sys.stdout.write(json.dumps(out))
        sys.stdout.flush()
    if sid in load_links():
        render(sid, tpath, pending)


def cmd_link(session_id: str, path_arg: str) -> None:
    raw = path_arg.strip().strip('"').strip("'")
    if not raw:
        cmd_status(session_id)
        print("Usage: /md-log <path/to/file.md>   (a bare filename goes in lessons/)   |   /md-log off")
        return
    if raw.lower() in ("off", "unlink", "stop"):
        return cmd_off(session_id)
    p = Path(raw)
    if not p.is_absolute():
        p = (PROJECT / ("lessons" if p.parent == Path(".") else "") / p)
    if p.suffix.lower() != ".md":
        p = p.with_suffix(p.suffix + ".md") if p.suffix else p.with_suffix(".md")
    p = p.resolve()
    if p.is_dir():
        sys.exit(f"Not a file: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    links = load_links()
    try:
        links[session_id] = p.relative_to(PROJECT).as_posix()
    except ValueError:
        links[session_id] = str(p)
    save_links(links)
    n = render(session_id, None)
    print(f"Linked: {p} ({n} blocks backfilled). Open it in Obsidian or the VS Code markdown preview.")


def cmd_off(session_id: str) -> None:
    links = load_links()
    stored = links.pop(session_id, None)
    save_links(links)
    print(f"Unlinked: {stored}" if stored else "This session wasn't linked.")


def cmd_status(session_id: str) -> None:
    stored = load_links().get(session_id)
    print(f"Linked to: {resolve_log(stored)}" if stored else "This session isn't linked to a log file.")


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--project":
        configure(find_project(args[1]))
        args = args[2:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "hook":
        try:
            hook()
        except Exception as exc:  # never break the session over logging
            print(f"md_log hook error: {exc!r}", file=sys.stderr)
        return
    if len(args) < 2:
        sys.exit(f"{cmd} needs a session id")
    if cmd == "link":
        cmd_link(args[1], " ".join(args[2:]))
    elif cmd == "off":
        cmd_off(args[1])
    elif cmd == "status":
        cmd_status(args[1])
    elif cmd == "render":
        print(f"{render(args[1], None)} blocks")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
