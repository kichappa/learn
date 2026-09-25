---
name: reassess
description: Re-measure a learner profile from scratch when it has drifted too far from reality for small per-session updates to fix. /learn:reassess [@learner] [topic] re-probes the foundations under the topic; with no topic, it re-probes the foundations already in the profile. Probes blind to the recorded levels, then compares old vs new and rewrites the profile. Assessment only, no teaching.
argument-hint: "[@learner] [topic]"
disable-model-invocation: true
allowed-tools: Bash(python *profiles.py*)
---

**This invocation.** Arguments: $ARGUMENTS

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/profiles.py" list`

# Reassess a learner profile

A profile moves in small, evidence-sized steps. That works when it starts near the truth, but not when an entry is badly off: a self-reported level that was wrong, a ceiling found on one unlucky question, or a learner who has since learned a lot elsewhere. Each session then plans around the wrong edge and nudges it only slightly. This command measures the edge again from scratch and replaces the entry.

It only assesses. Don't teach, don't correct misconceptions beyond the grading explanation, and don't plan a lesson.

## Before you start: load the shared rules

`Read` `${CLAUDE_PLUGIN_ROOT}/skills/teach/SKILL.md` and follow these sections exactly as written there: **The learner profile** (topic-agnostic rule, level scale, status, evidence), **The quiz protocol**, **Writing quiz options**, the **breakdown** step before Phase 1a, and **Phase 1a** (bracketing, binary search, misconceptions, mapping every strand). The rules below add to them and never replace them.

## Step 1 — Resolve the learner

Resolve it the same way as teach's Phase 0, step 1. The arguments may start with `@name`, or their first word may be an existing profile's name; anything after that is the topic. If no learner is named, ask with `AskUserQuestion` using the existing profiles. With no profiles at all there is nothing to reassess: say so and suggest `/learn:teach`.

## Step 2 — Decide the scope, blind

Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/profiles.py" foundations <name>`. It lists the foundation entries with their status, last-seen date and evidence count, but **not** their level, floor, ceiling or pace. **Don't `Read` the profile yet.** Probing with the recorded level in view anchors the questions on it, and then the probe mostly confirms the old number.

- **Topic given:** map the topic onto the scientific and mathematical foundations it rests on. Use teach's **breakdown** step (just before Phase 1a in `teach/SKILL.md`) to choose the source: your own knowledge for standard material, a `researcher` call when you can't list the prerequisites with confidence, and the code for this repo's own implementation. The scope is those foundations: existing entries that match, plus new ones the profile doesn't have yet.
- **No topic:** the scope is the entries already in the profile. If there are more than about six, ask which to cover with `AskUserQuestion` (`multiSelect: true`). Offer at most four options: group entries by area, and put first the entries most likely to be wrong, which are `self-reported` ones, stale ones (last seen more than about three months ago), and ones with only one or two evidence lines.

Tell the learner the scope in two or three lines. Then ask with `AskUserQuestion` (not a quiz) what prompted the reassessment: sessions felt too easy, too hard, the profile looked wrong, or they have learned things elsewhere. Their answer tells you which direction to suspect.

## Step 3 — Probe each foundation from neutral ground

For each foundation in scope, run a full Phase 1a mapping with these differences:

- **Start at level 2-3**, whatever the profile says, and binary-search from there with sharp jumps. Take the starting difficulty from the level scale, not from the profile.
- **Bracket it on at least two questions per side.** You need two right answers at the floor and two misses or "I don't know"s at the ceiling. This result replaces an entry, so a single lucky or unlucky answer must not decide it.
- **Write fresh questions.** Don't reuse or paraphrase questions from the profile's evidence lines, which you haven't read yet. That's another reason not to read it.
- **Stay topic-agnostic.** Probe the foundation itself. You can use the topic's setting as a concrete frame, but grade the underlying concept.

Keep a running tally per foundation: questions, answers, notes, the floor and ceiling found, and any misconception.

## Step 4 — Compare, then rewrite the profile

Only now `Read` the profile. For each foundation in scope, compare the recorded level, floor and ceiling with what you just measured:

| Result | Update |
|---|---|
| Same level (within 1) | Keep the level and set status to `confirmed`. Refine the floor and ceiling wording if the new evidence is sharper. |
| Off by 2 or more | Replace the level, floor and ceiling with the new values. Set status to `probed`. Record the old values in an evidence line, e.g. `reassessment: was 4 (self-reported), measured 2`. |
| Not in the profile | Create the entry, with status `probed`. |

In every case, add dated evidence lines tagged `reassessment` and keep the old evidence lines; don't delete history. Then check whether wrong levels had shaped other sections: Pace calibration, "How this learner learns", or Open hypotheses. For example, "slow on X" may have been the teacher aiming two levels too high. Revise those sections, and put anything uncertain under Open hypotheses. Add a Session history row with context `reassessment: <scope>`, and set `updated` in the frontmatter. Don't increment `sessions`: that counts teaching sessions.

Then check what you wrote for topic leakage, as in teach's Phase 4.

## Step 5 — Report

Show the learner a short table: foundation | was | now | what moved it. Add one line on what future `/learn:teach` sessions will do differently because of it.
