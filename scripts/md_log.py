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
SKIP_COMMANDS = {
    "md-log", "clear", "compact", "resume", "rewind", "model", "config", "cost", "context", "effort",
    "fast", "status", "help", "login", "logout", "plugin", "plugins", "permissions", "hooks", "agents",
    "memory", "init", "doctor", "usage", "exit", "mcp", "theme", "vim", "add-dir", "export", "ide",
    "statusline", "terminal-setup", "upgrade", "bug", "feedback", "release-notes", "output-style",
    "privacy-settings", "reload-plugins", "rename", "sandbox", "todos", "copy", "keybindings",
}
PASTED = re.compile(r"<pasted_content\b[^>]*>(.*?)</pasted_content[^>]*>", re.S)
SKIP_PREFIXES = ("<task-notification", "<local-command", "[Request interrupted", "Caveat:")
WIKI_EMBED = re.compile(r"!\[\[([^\]|]+?\.(?:png|jpe?g|gif|svg|webp))(?:\|(\d+))?\]\]", re.I)


# ── quiz helpers ─────────────────────────────────────────────────────────────

def is_quiz(q: dict) -> bool:
    """Graded question: "Quiz N" checks taught material, "Probe N" tests prior knowledge."""
    return str(q.get("header", "")).strip().lower().startswith(("quiz", "probe"))


def needs_explanation(q: dict) -> bool:
    return str(q.get("header", "")).strip().lower().startswith("quiz")


MIN_EXPLANATION_CHARS = 250


def lesson_since_learner(transcript: Path | None, tool_use_id: str) -> tuple[int, dict | None] | None:
    """(characters of lesson prose since the learner last spoke, the answer entry they last
    spoke in or None if it was a typed prompt). Blockquote lines (the grading callout) don't count: they grade the previous
    quiz, they don't teach the next node.

    The hook can fire before Claude Code has written the current message to the transcript,
    so wait until the entry holding this tool call appears. If it never does, return None:
    the caller then lets the quiz through rather than block on a stale file."""
    if not transcript or not tool_use_id:
        return None
    for _ in range(20):  # up to ~4 s
        if transcript.is_file() and tool_use_id in transcript.read_text(encoding="utf-8", errors="replace"):
            break
        time.sleep(0.2)
    else:
        return None
    chars, stop = 0, None
    chain = active_chain(load_entries(transcript))
    # Count back from the message holding this quiz, not from the end of the session
    here = next((i for i in range(len(chain) - 1, -1, -1) if chain[i].get("type") == "assistant"
                 and tool_use_id in json.dumps(chain[i].get("message", {}).get("content"))), len(chain) - 1)
    for e in reversed(chain[:here + 1]):
        content = e.get("message", {}).get("content")
        if e.get("type") == "user":
            if isinstance(content, list) and any(isinstance(b, dict) and b.get("tool_use_id") == tool_use_id
                                                 for b in content):
                continue  # this quiz's own answer (present when checking after the fact)
            answered = isinstance(e.get("toolUseResult"), dict) and "answers" in e["toolUseResult"]
            if answered or user_prompt(e):
                stop = e if answered else None
                break
            continue
        if e.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    chars += sum(len(ln) for ln in b["text"].splitlines() if not ln.lstrip().startswith(">"))
    return chars, stop


MIN_FOLLOWUP_CHARS = 80


def open_question(stop: dict | None, qs: list[dict]) -> str | None:
    """The learner's typed reply, if their last input was a free-text ("Other") reply to this
    same quiz (same header). That is a clarifying question or a worded attempt: a re-ask must
    respond to it first, but a two-sentence clarification is enough."""
    tur = (stop or {}).get("toolUseResult")
    if not isinstance(tur, dict):
        return None
    headers = {str(q.get("header", "")).strip().lower() for q in qs}
    for q in tur.get("questions") or []:
        if str(q.get("header", "")).strip().lower() not in headers:
            continue
        reply = str((tur.get("answers") or {}).get(q.get("question", ""), ""))
        labels = {str(o.get("label", "")) for o in q.get("options") or []}
        if reply and reply not in labels and not all(p.strip() in labels for p in reply.split(",")):
            return reply
    return None


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
        if cmd.split(":")[-1] in SKIP_COMMANDS:
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


def callout(kind: str, title: str, body: list[str], fold: str = "") -> str:
    """An Obsidian callout (a plain blockquote elsewhere). fold="-" starts it collapsed."""
    return "\n".join([f"> [!{kind}]{fold} {title}"] + [f"> {ln}" if ln else ">" for ln in body])


def user_block(text: str) -> str:
    """The learner's message in a box, with each pasted chunk folded away inside it."""
    body: list[str] = []
    pos = 0
    for m in PASTED.finditer(text):
        own = text[pos:m.start()].strip()
        if own:
            body += own.split("\n") + [""]
        pasted = m.group(1).strip("\n").split("\n")
        n = len(pasted)
        body += callout("note", f"📋 Pasted · {n} line{'s' if n != 1 else ''}", pasted, fold="-").split("\n") + [""]
        pos = m.end()
    own = text[pos:].strip()
    if own:
        body += own.split("\n")
    while body and not body[-1]:
        body.pop()
    return callout("quote", "🧑 You", body)


def demote_headings(text: str) -> str:
    """Push Claude's own headings one level down (## -> ###), outside code fences, so the
    log's outline stays title > session > lesson section."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,5} ", line):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


def assistant_block(text: str) -> str:
    # Plain prose, not boxed, so math, tables and diagrams get the full width
    return f"**🎓 Claude**\n\n{demote_headings(text)}"


def question_title(q: dict) -> str:
    header = str(q.get("header", "")).strip()
    if not is_quiz(q):
        return f"💬 {header or 'Question'}"
    icon = "🔍" if header.lower().startswith("probe") else "📝"
    return f"{icon} {header.replace('fixed', '').replace('Fixed', '').strip() or 'Quiz'}"


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
            body.append(f"{i}. {label}" + (f" — {desc}" if show_desc else ""))
    if q.get("multiSelect"):
        body.append("")
        body.append("*Select all that apply.*")
    return callout("question", question_title(q), body)


def answer_block(q: dict, answer: str | None, note: str | None) -> str:
    quiz = is_quiz(q)
    labels = [str(o.get("label", "")) for o in q.get("options") or []]
    if answer is None:
        return callout("warning", "⏭️ Skipped", [])
    picked: list[str]
    if answer in labels:
        picked = [answer]
    else:
        parts = [p.strip() for p in answer.split(",")]
        picked = parts if parts and all(p in labels for p in parts) else []
    if quiz and picked and all(DONT_KNOW_RE.match(p) for p in picked):
        title, kind, lines = "🤷 I don't know", "question", []
    elif picked:
        title, kind = "✍️ Your answer", "example"
        lines = [f"**{labels.index(p) + 1}.** {p}" for p in picked]
    else:
        title, kind = "✍️ Your answer, in your words", "example"
        lines = answer.split("\n")
    if note:
        lines += ([""] if lines else []) + [f"🗒️ *{note}*"]
    return callout(kind, title, lines)


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
            out.append(callout("warning", "⏭️ Dismissed", []))
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
                    blocks.append(callout("note", f"🧩 Skill: {(b.get('input') or {}).get('skill', '?')}", []))
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
    """Update the log in place. Swapping in a new file (write a temp file, then rename)
    makes editors such as VS Code's markdown preview reload from the top, so instead skip
    the write when nothing changed, and otherwise rewrite only the part that changed."""
    current = ""
    if log.is_file():
        with open(log, encoding="utf-8", errors="replace", newline="") as f:
            current = f.read()
    plain = current.replace("\r\n", "\n")
    i = plain.find(MARKER)
    head = plain[:i] if i >= 0 else (plain.rstrip() + "\n\n" if plain.strip() else "")
    title = log.stem.replace("_", " ").replace("-", " ").strip().capitalize()
    body = head + MARKER + f"\n\n# 📘 {title}\n\n" + "\n\n".join(blocks) + "\n"
    body = re.sub(r"\n{3,}", "\n\n", body)
    if current == body:
        return
    if not log.is_file():
        with open(log, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        return
    # Rewrite only from the first byte that changed, then trim. The file is never emptied
    # (opening it for writing would truncate it to zero first, and a preview that catches
    # the empty file resets to the top), and everything above the change is left alone.
    old, new = current.encode("utf-8"), body.encode("utf-8")
    same = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
    with open(log, "r+b") as f:
        f.seek(same)
        f.write(new[same:])
        f.truncate()


def started_label(iso: str) -> str:
    import datetime as dt
    try:
        when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return iso[:16]
    return when.strftime("%a %d %b %Y, %H:%M")


def render(session_id: str, transcript: Path | None, pending: dict | None = None) -> int:
    stored = load_links().get(session_id)
    if not stored:
        return 0
    log = resolve_log(stored)
    empty = {"questions": {}, "results": {}, "prompt": None, "last_assistant": None}
    # Several sessions can share one log (a lesson continued in a new session): render each
    # linked session in the order it started, so a new session never overwrites an old one.
    parts = []
    for sid in [s for s, p in load_links().items() if resolve_log(p) == log]:
        t = transcript if sid == session_id and transcript else find_transcript(sid)
        entries = load_entries(t) if t and t.is_file() else []
        start = next((e["timestamp"] for e in entries if e.get("timestamp")), "")
        parts.append((start, sid, active_chain(entries)))
    parts.sort()
    blocks: list[str] = []
    for i, (start, sid, chain) in enumerate(parts):
        if len(parts) > 1:
            blocks.append(f"## 📅 Session {i + 1} · {started_label(start)}")
        blocks += build_blocks(chain, log.parent, (pending or empty) if sid == session_id else empty)
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
        # Gate: a check-quiz must come after the lesson text it checks, so the learner (and
        # the log) have the material. Worded around the lesson, not around how it was drafted.
        if any(needs_explanation(q) for q in qs):
            seen = lesson_since_learner(tpath, payload.get("tool_use_id", ""))
            if seen is not None:
                n, stop = seen
                reply = open_question(stop, qs)
                if reply is not None and n < MIN_FOLLOWUP_CHARS:
                    reason = (
                        "Lesson check: the learner's last reply to this quiz was typed text, not a choice, "
                        f"and it hasn't been responded to yet (about {n} characters since). They wrote: "
                        f'"{reply[:500]}". Respond to that in the lesson first (answer their question, or '
                        "grade their worded attempt), then re-ask the quiz if it's still needed.")
                elif reply is None and n < MIN_EXPLANATION_CHARS:
                    reason = (
                        "Lesson check: this quiz checks material that isn't in the lesson yet "
                        f"(about {n} characters of lesson text since the learner's last reply). "
                        "Add the explanation or worked step for this node to the lesson message, "
                        "then ask the quiz. For a question on prior knowledge, use the header "
                        "'Probe N' instead.")
                else:
                    reason = None
                if reason:
                    sys.stdout.write(json.dumps({"hookSpecificOutput": {
                        "hookEventName": "PreToolUse", "permissionDecision": "deny",
                        "permissionDecisionReason": reason}}))
                    return
        if any(is_quiz(q) for q in qs):
            qs = [prepare_quiz(q) if is_quiz(q) else q for q in qs]
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "updatedInput": {**tool_input, "questions": qs}}}
        pending["questions"][payload.get("tool_use_id", "")] = qs
    elif event == "PostToolUse" and payload.get("tool_name") == QA_TOOL:
        tid = payload.get("tool_use_id", "")
        pending["results"][tid] = payload.get("tool_response")
        # After-the-fact lesson check. Before a quiz, the transcript usually doesn't hold the
        # current message yet, so the gate above can't see it; after the answer, it does.
        qs = (payload.get("tool_input") or {}).get("questions") or []
        if any(needs_explanation(q) for q in qs):
            seen = lesson_since_learner(tpath, tid)
            n, stop = seen if seen is not None else (None, None)
            floor = MIN_FOLLOWUP_CHARS if open_question(stop, qs) is not None else MIN_EXPLANATION_CHARS
            if n is not None and n < floor:
                out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
                    "Lesson check: the message that asked this quiz had almost no lesson text "
                    f"(about {n} characters), so the learner answered without the node's explanation "
                    "in front of them, and the lesson log is missing it too. Start your next message by "
                    "writing that node's explanation in the lesson, then grade the answer.")}}
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
        # The transcript can lag the screen when a quiz is asked or answered, so the text
        # just before it may be missing from this render. Rebuild again a few seconds later,
        # in a detached process so the hook (and the quiz popup) isn't held up.
        if event in ("PreToolUse", "PostToolUse") and tpath:
            import subprocess
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--project", str(PROJECT),
                              "rerender", sid, str(tpath), "4"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags, close_fds=True)


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
    elif cmd == "rerender":  # rerender <session_id> <transcript> <delay_s>: the delayed catch-up
        time.sleep(float(args[3]) if len(args) > 3 else 4)
        render(args[1], Path(args[2]) if len(args) > 2 else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
