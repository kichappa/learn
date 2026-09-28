# Markdown Preview Tail

A tiny VS Code extension for reading `learn` lesson logs (`/learn:md-log`) in the built-in Markdown preview. It adds one preview script, `tail.js`, and no commands or settings.

When the log is rewritten, VS Code's preview can jump. This script keeps it where you are:

- **Following.** When you're at or near the end, within a third of a screen, it stays pinned to the end as new lesson text arrives. A corner badge shows `⤓ following`.
- **Paused.** When you scroll up to reread, it holds that spot, anchored to the source line at the top of the screen, and shows `⏸ paused`. Scroll back to the end to follow again.

It applies to every Markdown preview, but it changes nothing unless a file is rewritten while you're looking at it.

## Install, update, remove

The `learn` plugin installs it for you when a Claude Code session starts. To manage it by hand:

```
python "<plugin dir>/scripts/preview_tail.py" status
python "<plugin dir>/scripts/preview_tail.py" install
python "<plugin dir>/scripts/preview_tail.py" uninstall
```

To turn it off for good, set `LEARN_PREVIEW_TAIL` to `off` in the `env` block of `~/.claude/settings.json`. The next session start then uninstalls it and leaves it off. After installing or removing it, run **Developer: Reload Window** in VS Code, or reopen the preview.

## Tuning

Constants at the top of `tail.js`: `SLACK_VH` (how close to the end still counts as following), `SETTLE_MS` (how long after a refresh VS Code's own scroll restore is overridden), `PAD`, and `SHOW_BADGE`. Rebuild with `npx @vscode/vsce package --no-dependencies --skip-license` from a plain folder. Packaging from inside Claude Code's scratchpad produced an empty VSIX.
