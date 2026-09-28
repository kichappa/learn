# learn

A teaching system for [Claude Code](https://claude.com/claude-code). Claude finds where your understanding ends, plans a lesson from first principles, and teaches it one piece at a time. It checks each piece with a graded quiz and draws diagrams it has verified by looking at them. A learner profile records which math and science foundations you hold and how fast you pick things up, so later sessions start at your edge and keep the pace neither boring nor exhausting.

This is a Claude Code port of **[amosblomqvist/learn](https://github.com/amosblomqvist/learn)**, a system for the [pi](https://github.com/earendil-works/pi) agent, explained in the video [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU). The teaching method, the two principles and the probe → plan → teach process come from there. The skills and agents are ported nearly verbatim; the pi extensions are rebuilt from Claude Code parts. The learner profiles and `/learn:reassess` are additions.

## Install

In Claude Code:

```
/plugin marketplace add kichappa/learn
/plugin install learn@learn
```

**Requirements:** Python 3.10+ as `python` on your PATH (hooks and scripts use only the standard library).

**For diagrams** you also need Node.js, Chrome or Edge, and `rsvg-convert` or ImageMagick. Then run this once per machine:

```
! python "<plugin dir>/scripts/render.py" setup
```

It installs mermaid-cli into `~/.cache/learn-visual-tools` and uses your installed browser instead of downloading one. `render.py doctor` shows what it found. The plugin directory is under `~/.claude/plugins/`; `/plugin` shows the exact path.

## Configure (optional, in your user settings)

A plugin can't ship environment variables or permission rules, so add these to `~/.claude/settings.json` if you want them:

```json
{
  "env": {
    "LEARN_PROFILES_DIR": "C:/Users/you/Dropbox/learner-profiles",
    "LEARN_PREVIEW_TAIL": "on"
  },
  "permissions": {
    "allow": [
      "Bash(python *scripts/render.py*)",
      "Bash(python *scripts/md_log.py*)",
      "Bash(python *scripts/profiles.py*)",
      "Read(~/Dropbox/learner-profiles/**)",
      "Edit(~/Dropbox/learner-profiles/**)"
    ]
  }
}
```

- **`LEARN_PROFILES_DIR`:** where learner profiles live. The default is `~/.claude/learner-profiles`. Point it at a synced folder to share profiles between computers.
- **`LEARN_PREVIEW_TAIL`:** `on` by default. Set it to `off` to keep the plugin from installing its VS Code preview extension, and to remove it if it's already installed (see below).
- **The allow rules:** let the diagram makers, the session logger and the profile script run, and let Claude read and edit your profiles, all without prompting. Match the `Read`/`Edit` paths to your `LEARN_PROFILES_DIR`.

## Reading the log in VS Code

When the log is rewritten, VS Code's Markdown preview can jump to the top. The plugin therefore bundles a tiny VS Code extension, **Markdown Preview Tail** (`vscode/md-preview-tail/`, one preview script, no settings):
- **Following:** while you're near the end, it stays pinned to the end as the lesson grows.
- **Paused:** when you scroll up to reread, it holds your place.

A corner badge shows `⤓ following` or `⏸ paused`.

At each session start, the plugin installs or updates it through VS Code's `code` command. This is quick: it reads VS Code's extension registry and calls `code` only when something needs doing. Set `LEARN_PREVIEW_TAIL` to `off` to opt out; the next session start removes it. To manage it by hand, use `python "<plugin dir>/scripts/preview_tail.py" status | install | uninstall`. After a change, run **Developer: Reload Window** in VS Code.

## Use

| Command | What it does |
|---|---|
| `/learn:teach @<learner> <topic>` | Teach a topic. Without `@name` it asks who's learning, and creates a profile on first use. |
| `/learn:reassess @<learner> [topic]` | Re-measure a profile that has drifted. It probes blind to the recorded levels, then compares old against new. |
| `/learn:md-log lessons/<topic>.md` | Mirror the session into a markdown file that renders LaTeX, mermaid, images and quizzes (Obsidian, or VS Code's preview with `bierner.markdown-mermaid`). `/learn:md-log off` stops. To continue a lesson in a new session, run it with the same file: sessions are appended in order, never overwritten. |

The `teach` skill also triggers on its own whenever Claude explains something. Diagrams happen automatically: the teacher calls `visualize` when a picture helps, and PNGs land in `<project>/lessons/viz/`.

## How a session runs

1. **Learner:** loads your profile, or creates one after a short intake.
2. **Probe:**
   - Your goal is settled first.
   - The topic is broken into the math and science foundations it rests on. Claude researches first if it can't list them with confidence, or reads the code if the topic is your repo.
   - Graded quizzes map your edge on each foundation, bracketed by a right answer below it and a miss above it. A quick check replaces the full mapping wherever the profile already has recent evidence.
3. **Plan:** a short outline plus a dependency map from starting truths to your goal. Step size comes from your recorded pace. Nothing is taught until you approve it.
4. **Teach:** node by node: motivate → establish → connect → quiz-check. Claude watches for too-slow and too-hard signals and adjusts the next step.
5. **Wrap-up:** a pace check, then an evidence-backed profile update.

## The learner profile

It's one markdown file per learner, shared across every repo. It is **topic-agnostic**: it records the foundations under whatever was taught, such as "rigid transforms (SO(3) vs O(3))", never the application, such as "motion tracking". That keeps it useful in a repo teaching something unrelated. Each foundation entry records:

- a 0-5 level and a trust status (`self-reported`, `probed` or `confirmed`);
- a floor (hardest thing you reliably get right) and a ceiling (where it broke);
- your pace, and any misconceptions;
- dated evidence lines behind all of the above.

The profile also records how you learn, pace calibration, hypotheses to test next session, and session history. `/learn:reassess` re-measures entries that are badly off, without looking at the recorded numbers first, so they can't anchor the questions.

## How it differs from upstream

| Upstream (pi) | Here | Cost |
|---|---|---|
| A `quiz` tool that held the answer key and graded mechanically | `AskUserQuestion` plus a PreToolUse hook that shuffles options and adds "I don't know"; Claude grades in its next reply | Grading isn't mechanical. At most 3 real options per quiz. |
| `ask-user-question` extension | The built-in `AskUserQuestion` | none |
| `md-log` extension, appending per event | A hook that regenerates the log from the session transcript below a marker line | Edits you make below the marker get overwritten |
| `visual-tools` extension (write/edit/render tools) | `scripts/render.py`, called by the makers through Bash; they `Read` the PNG to check it | Makers get Bash instead of three narrow tools |
| Researcher on GLM-5.3 (OpenRouter) | Researcher on Sonnet | none |

## Where to change things

| To change | Edit |
|---|---|
| The teaching method, phases, pacing and profile rules | `skills/teach/SKILL.md` |
| What a new profile starts with | `skills/teach/profile-template.md` |
| Re-measurement | `skills/reassess/SKILL.md` |
| When a picture is worth making | `skills/visualize/SKILL.md` |
| Diagram style, and models or effort for the subagents | `agents/*.md`; render flags in `scripts/render.py` |
| Quiz mechanics and how the log looks | `scripts/md_log.py` |

## Known limitations

- **The quiz shuffle** relies on Claude Code applying a PreToolUse hook's `updatedInput` to `AskUserQuestion`. If a quiz shows options in the order Claude wrote them, with no "I don't know", it isn't being applied.
- **The log** misses any assistant text that Claude Code doesn't write to the session transcript. The final reply of each turn is always captured. When a quiz is asked or answered, the transcript can lag the screen by a few seconds, so the log rebuilds once more about 4 s later.
- **Lesson checks.** A `Quiz N` question checks something just taught, so a hook requires lesson text before it (`Probe N` questions, which test prior knowledge, are exempt). Before the quiz, the current message usually isn't in the transcript yet, so that check rarely fires. The dependable check runs after the answer: if the quiz's message had almost no lesson text, Claude is told to write the node's explanation first in its next message. The check counts characters, so it catches missing explanations, not thin ones.
- **Tested on Windows only** (Git Bash shell for hooks). The scripts are written to be cross-platform, but macOS and Linux are untested.

## License

Upstream [amosblomqvist/learn](https://github.com/amosblomqvist/learn) doesn't specify a license, so no license is granted here for material derived from it: the skill texts and agent prompts. All credit for the teaching method goes to its author.
