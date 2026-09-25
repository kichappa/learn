---
name: md-log
description: Mirror this session into a markdown file that renders LaTeX, mermaid, images and quiz callouts (Obsidian or VS Code preview). /learn:md-log <file> links and backfills; /learn:md-log off stops. Use when the user asks to log, mirror or save the session to a file for reading.
argument-hint: "<lessons/topic.md> | off"
allowed-tools: Bash(python *md_log.py*)
---

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/md_log.py" --project "${CLAUDE_PROJECT_DIR}" link "${CLAUDE_SESSION_ID}" "$ARGUMENTS"`

The output above is the result of the link command, which has already run. Report it to the user in one short line and stop. From here on, this plugin's hooks regenerate the file after every prompt, quiz question, answer and reply, so there is nothing else to do.
