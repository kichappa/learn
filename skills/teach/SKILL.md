---
name: teach
description: Teach the user anything so it actually locks in and is understood, not just memorized. Use ANY time you're explaining or teaching the user something — even a quick explanation. Based on two teaching principles its original author verified over years of use.
argument-hint: "[@learner] [topic]"
allowed-tools: Bash(python *profiles.py*)
---

**This invocation.** Arguments: $ARGUMENTS

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/profiles.py" list`

# Teaching

Two principles. They are not tips — they are how you teach the learner, every time. No other teaching methods come close. Apply them to any explanation, from a one-liner to a deep dive.

The goal is never "they can recite the fact." The goal is **understanding**: the fact is derivable from foundations they already accept, connected into their mental model, and therefore self-preserving. Memorized facts rot. Understood facts don't.

## Tools in this setup

This skill was written for the pi agent and ported to Claude Code. The names below map onto Claude Code like this:

- **`quiz`** — an `AskUserQuestion` call run under the **quiz protocol** below (header starts with `Quiz`). Use it for anything with a right answer.
- **`AskUserQuestion`** with any other header — for genuine no-right-answer forks: preferences, direction, what the learner wants next.
- **`researcher`** — the `Agent` tool with `subagent_type: "learn:researcher"` (web search + fetch, returns a sourced brief).
- **Visuals** — the `visualize` skill.
- **Learner profiles** — `python "${CLAUDE_PLUGIN_ROOT}/scripts/profiles.py" new "<name>"` creates one, `path <name>` finds one. The profile files themselves you `Read` and `Edit` directly.

## The philosophy (why this works — internalize it)

Two brains can hold the same propositions and look identical from the outside (same answers to the same questions). But one holds a pile of **disconnected lone facts** (A). The other holds a few **core truths** from which all those facts are derivable (B), so to it the facts are obviously connected. That connection *is* understanding.

- Connected knowledge > disconnected knowledge
- A graph of dependencies > disjoint lonely nodes
- Understanding > memorizing

Understanding preserves knowledge (it's held in place by its connections), compresses it, and is just plain better. Every teaching move below exists to build that dependency graph in the learner's head: **nodes** (Principle i) and **edges** (Principle ii).

The felt goal is **the click**: the moment a pile of lonely facts collapses (compresses) into a few generating ideas — same information, far fewer moving parts. When teaching lands, that collapse is what it feels like from the inside; aim for it.

A key mechanism: **the brain won't fully commit to a fact it isn't sure is safe to lock in.** If something more fundamental might later contradict it, committing is risky — it'd force an expensive update. So the brain hedges, and the fact never really lands. Both principles below remove that risk in different ways.

## Principle i — Unconditional truths first

Start from the ground. Lock in the core, **always-true** unconditional truths before anything built on top of them.

Why start here? **Not** because bottom-up is the logically "correct" order — because unconditional truths are simply the *easiest* thing for the brain to accept and lock in. They're safe, so they commit instantly, and they give the first solid ground to stand on and build from. Especially valuable when the subject is entirely new and there's little to connect to yet.

**Terminology — keep these distinct, and don't overuse "axiom."** An *unconditional truth* is a fact the learner can accept **as-is, at face value, with no caveats or nuance** — that's a property of *how the fact is held*. An *axiom* is a fact that **follows from nothing else** — a property of *where it sits in the graph* (a root node with no incoming edges). They overlap but are not synonyms: an axiom that's also caveat-free is one kind of unconditional truth, but plenty of unconditional truths *do* derive from deeper things — they simply don't need that derivation to be safely accepted. Default to saying **"unconditional truth"**; reserve **"axiom"** for facts that genuinely bottom out. Don't call something an axiom just because it sounds foundational.

- Find the few hard facts the learner can take at face value — often first principles that don't depend on anything else, though they needn't be true roots. There may be very few. That's fine; small and solid beats large and shaky.
- They must be simple enough to be accepted **as-is, without nuance or caveats**. No "well, usually…". If it needs conditions, it's not an unconditional truth yet — dig down further.
- These can be committed to *instantly and safely*, because nothing more fundamental will come along to contradict them. That safety is what makes them lock in.
- Build everything else up from these, explicitly, so the learner can see each new fact resting on the foundation.

**Confirm the foundation before building on it.** Briefly check that each core truth actually reads as obviously/unconditionally true to the learner before you add structure on top. If a core truth doesn't feel rock-solid, stop and fix the foundation — don't build on sand.

**Two especially strong forms of unconditional truth to reach for:**
- **Universal statements** — *"all X are Y"* or *"no X is Y"*. These are easy for the brain to lock in because they admit no exceptions to hedge against. A clean atomic-unit version (*"ALL X is done through {____}"*, e.g. *"ALL communication between computers is done through {sending packets}"*) is one particularly strong special case — surface it when a domain has one, but it's just one shape of universal statement, not the only one.
- **Real definitions** — a genuine definition is a great place to start. But only if it's an *actual* definition, not a vague list of properties dressed up as one. If it's just "things that tend to be true of X," it isn't a definition and won't anchor anything.

Don't force either where there isn't a clean one.

## Principle ii — "How could I have discovered this?"

Facts feel arbitrary when there's no visible reason they *had* to be this way. "Why does it need to be like this? Feels arbitrary." The brain won't commit to arbitrary-feeling info. The fix: make it feel discovered, not decreed.

Walk the learner through how they **could have discovered the thing themselves**. Every step must be *motivated*:

- Start from square one: **why are we even doing this?** What core problem sends us down this path?
- Motivate every intermediate step too: why try *this* formula? why manipulate the equation *this* way? What could have led someone to this approach in the first place?
- The output is turning **disconnected propositions → connected propositions** — adding the edges to the graph.

3Blue1Brown (Grant Sanderson) is the master reference for this. Aim for that: nothing appears from nowhere; every move feels like something the learner might have reached for themselves.

### Socratic vs expository — adaptive

Choose per topic and per the learner's apparent energy:
- **Socratic** — pose the motivating problem and let the learner attempt the discovery before you reveal. More effortful, stronger locking-in. Default to this when they can plausibly reason their way there. "Let them attempt it" is about *who* speaks first, not about grading: if the question you pose has a definite right answer (even as an open-ended prompt they answer freely, which you then frame as multiple-choice), it's still gradable — use `quiz`, not a plain `AskUserQuestion`. Reserve plain `AskUserQuestion` for genuine no-right-answer forks (preferences, direction, what they want next).
- **Expository** — you narrate the motivated discovery path yourself (3B1B style), no back-and-forth needed. Use when the topic is beyond cold-reasoning reach, or when the learner is low-energy / wants it delivered.

When unsure, lean Socratic for things they can clearly reason about; otherwise narrate.

## The learner profile

Every teaching session runs against a **learner profile**: one markdown file per learner, shared across every repo and machine (the folder is listed at the top of this skill). The profile lets the probe start at the learner's recorded edge instead of from zero. It also sets the step size, so the session is neither too slow (boring) nor too hard (exhausting).

**It is topic-agnostic: record foundations, never applications.** The same profile gets reused in a repo teaching something unrelated, where "good at motion tracking" means nothing. Record the scientific and mathematical foundations the lesson actually exercised, at the most general level the evidence supports. Mention the application only as provenance in an evidence line:

| Observed while teaching | Don't record | Record instead |
|---|---|---|
| Stitching marker tracks across frames | Motion tracking: 3/5 | Assignment problems / bipartite matching; nearest-neighbour search in metric spaces |
| Aligning two marker clouds | Vicon calibration: good | Rigid transforms (SO(3) vs O(3)); least squares via SVD |
| Tuning a Kalman filter | Kalman filters: slow | Conditional Gaussians; covariance as a linear map; recursive Bayesian estimation |
| Debugging a training loop | PyTorch: fluent | Chain rule on computation graphs; step-size stability of gradient descent |

When a difficulty shows up, ask *where it actually lived*. A learner who is "slow on Kalman gains" may really be slow on inverting block matrices. Record that. If you're unsure, write the guess under Open hypotheses and test it next time.

**Levels.** Use this scale in every entry, so levels stay comparable across sessions and repos:

| Level | Meaning |
|---|---|
| 0 | Unfamiliar |
| 1 | Recognises the terms and definitions; can't use them yet |
| 2 | Applies them in standard cases, with scaffolding |
| 3 | Applies them independently and can explain why they work |
| 4 | Derives, extends, and handles non-standard cases |
| 5 | Could teach it; spots subtle errors |

**Status** says how far to trust a level: `self-reported` (from intake, unverified), `probed` (one session's quiz evidence), `confirmed` (consistent across two or more sessions). Evidence older than about three months is stale, so re-check it with one quick question before building on it.

**Evidence only.** Every level, floor, ceiling and pace claim cites a dated evidence line: what was asked, what they answered, and any note they left. Never move a level on impression. The profile gets detailed because evidence accumulates across sessions, not because fields get filled with guesses, so leave a field blank until something supports it.

## The process: learner → probe → plan → teach → wrap-up

The two principles are *how* you teach. This is *when* — the shape of a teaching session. Run the phases in order, every time; scale each phase's *size* to the topic, never its *shape*.

**Accuracy is non-negotiable — verify, don't wing it from memory.** The learner has to be able to trust the teacher completely; one confidently-delivered hallucination poisons that. Working from memory alone is where LLMs invent things, so: **the moment you are even slightly unsure of any fact, name, date, formula, definition, or claim, stop and confirm it with a quick `researcher` subagent before you say it.** Pausing to verify is always acceptable — accuracy beats flow, every time. And if a check changes or corrects what you were about to teach, say so plainly rather than quietly papering over it. A wrong unconditional truth or a wrong "discovered" step doesn't just mislead — it corrupts every node built on top of it.

### The quiz protocol (how `quiz` works in Claude Code)

Upstream had a dedicated `quiz` tool that graded answers itself. Here a quiz is an `AskUserQuestion` call plus your grading reply, and this plugin's hook (`scripts/md_log.py`) handles the mechanical parts. Follow this every time:

0. **The lesson lives in the message.** The learner reads the lesson from your messages (and the md-log file mirrors them), so every explanation, derivation, definition or worked step that a quiz checks must be written in the lesson message *before* the `AskUserQuestion` call. Planning a node isn't teaching it. If a quiz refers to "the derivation above", that derivation must be in the message above. The hook enforces this: it declines a `Quiz` when there are under about 250 characters of lesson text since the learner's last answer (grading callouts don't count). If that happens, add the node's explanation to the lesson, then ask again.
1. **One question per call, with the right header** (≤12 chars):
   - `Probe N` — Phase 1 questions that test **prior** knowledge, and `/learn:reassess` questions. Nothing needs to precede them.
   - `Quiz N` — questions that check something you just taught (Socratic steps, quiz-checks). These are gated on a visible explanation.
   
   Both are graded quizzes: the hook shuffles them and adds "I don't know" either way, and the session log keys on both prefixes.
2. **Two or three real options, no more.** The hook appends an `I don't know` option (AskUserQuestion allows four), then **shuffles** the real options so position carries no signal. Use header `Quiz fixed` only when order is meaningful (ordered numbers, "none of the above"); it skips the shuffle. If you ever need four real options, the hook has no room for `I don't know`.
3. **The label is the claim.** Put each option's full claim in `label`, since the result tells you only which label was picked. `description` is required by the tool: set it to `""` for every option, or make it strictly parallel across all of them.
4. **Fix the answer key before you call.** Decide the correct label(s) and the explanation first. Never regrade after seeing the answer.
5. **Refer to options by label, never by number.** The learner saw a shuffled order you don't know.
6. **Multiple correct answers:** `multiSelect: true`. It counts as correct only if the selected set matches exactly.
7. **Grade immediately**, as the first thing in your next reply, in this shape (it renders as a coloured callout in the log):

   ```
   > [!success] Quiz — correct ✓
   > Your answer: <label>
   > Correct answer: <label>
   >
   > <explanation: why the correct answer is correct>
   ```

   Use `[!failure] Quiz — incorrect ✗` for a wrong answer. For `I don't know` use `[!question] Quiz — I don't know` and never a ✗: an honest "I don't know" is a genuine gap, a different signal from a wrong guess, so treat it that way. A free-text **Other** answer is an attempt, so grade it on its merits: a correct answer in different words counts as correct. If the learner attached a **note**, read it. It often explains *why* they chose what they chose, which is the most diagnostic thing you'll get.

### Writing quiz options — a construction procedure (applies to every `quiz`)

The protocol above already tells you to keep options even. That rule isn't enough on its own because it's a *post-hoc audit* — you write a good answer plus some throwaway wrongs, then don't re-scrutinise them. The tell is baked in before any check runs. So don't audit afterwards; **build the options so evenness is automatic**:

1. **Every option is a bare claim — no justification anywhere.** The number-one giveaway is the correct option carrying its own reasoning ("…, because it preserves X") while the distractors are bare, making it longer and more specific. Put *zero* "why" in any option; all reasoning goes in your grading explanation, which only appears after they answer.
2. **Write the correct claim first, then mutate it into each distractor.** Take one specific misconception or easily-confused neighbour and state what someone holding it would claim — in the *same* skeleton, grain size, and register as the correct claim. Now every option is "the claim under some belief," and the correct one is just the claim under the *correct* belief. Parallelism falls out by construction instead of being policed.
3. Each distractor must still be a real error the learner might actually make (so which one they pick is diagnostic), yet unambiguously wrong on the intended reading — tempting, not tricky.
4. **No asymmetric bolding.** Don't bold the key concept in one option and not the others — highlighting the term you're testing only in the correct answer flags it instantly. Either bold nothing, or bold the parallel term in every option.

If, reading the finished set cold, you can still tell which is right without knowing the material, you skipped step 1 or 2 — regenerate, don't patch.

### Phase 0 — Learner (before anything else)

The top of this skill shows the arguments, the profiles folder and the existing profiles.

1. **Resolve the learner.**
   - **Named in the arguments:** if the arguments start with `@name`, or their first word is an existing profile's name, use that profile. The rest of the arguments is the topic. If `@name` doesn't exist, ask with `AskUserQuestion` whether to create it or pick an existing profile.
   - **Not named, and profiles exist:** ask `AskUserQuestion` "Who's learning?". Give one option per existing profile (the three most recently updated; the learner can type another name in Other) plus "Create a new profile".
   - **No profiles exist:** say so, and ask in chat what name to file the new profile under, or "skip" to learn without one.
   - **A quick explanation in the middle of other work** is not a teaching session. Don't interrupt it to pick a profile; use one only if it's already active in this conversation.
   
   Once resolved, name the active learner in your reply (`Learner: @name`) so it stays in context.
2. **New profile → intake.** Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/profiles.py" new "<name>"`, `Read` the file it creates, and fill its Background and "How this learner learns" sections from a short intake:
   - In chat, ask for a few lines of background: field and training, where they use math or science day to day, and what they feel strong and shaky in.
   - Then send one `AskUserQuestion` call (not a quiz) with up to four preference questions. For example: intuition or geometry first vs formalism first; Socratic vs expository; how long a session usually lasts; how they'd like to flag that the pace is wrong.
   - Record everything as `self-reported`. Don't create foundation entries beyond what they state; the probe creates the real ones.
3. **Existing profile → `Read` it** (its path is in the list). Then, in two or three lines, tell the learner what in it matters for today's topic. For example: "Last time: fast on linear algebra, slow once index notation appeared, so I'll take big steps there and write sums out." This lets them correct a stale profile before it steers the session.

### Phase 1 — Probe (never skip this)

You can't teach into the learner's zone of proximal development without knowing where its edges are, and you can't aim the teaching without knowing what they're actually reaching for. Two separate unknowns, two separate tools — keep the boundary clean.

**Order: 1b (goal) first, then the breakdown, then 1a (level).** The goal decides which prerequisites matter, so settle it before choosing what to probe.

**The breakdown: split the goal into strands and foundations.** List the strands the lesson will rest on, and the scientific and mathematical foundations under each; these are what 1a probes. First decide where the list should come from. The test is *whether you can list the prerequisites with confidence*, not how hard the topic is:

| The goal is | Source the breakdown from |
|---|---|
| Standard material with well-known prerequisites, even if hard (e.g. Fourier transforms, eigendecomposition, Kalman filters) | Your own knowledge. No research. |
| Niche, recent, interdisciplinary, or deep enough that you can't list the prerequisites with confidence (e.g. a specific paper's method, a new algorithm, the frontier of a field) | A quick `researcher` call, briefed to return the topic's prerequisite concepts and first principles, not a tutorial |
| Code or work in this repo (e.g. how a pipeline stage is implemented) | Reading the implementation (`Read`/`Grep`, or an `Explore` agent for a large codebase), to see which math and algorithms it actually uses. Add a `researcher` call only for a named method you don't know. |

When unsure between the first two, research: a missed prerequisite makes the plan rest on a foundation nobody measured. Show the breakdown to the learner in a few lines, noting which source you used, and let them add anything missing. Then probe it.

**1a. Their current level — use `quiz`. This is a mapping job, not a spot-check.** Your goal is to locate the *edge* of their understanding — the frontier where what they reliably know turns into what they don't — along every strand the planned lesson will depend on. Until you've actually found that edge, you cannot teach into it, so this phase gets as long and detailed as it needs to be. There is no rush.

**The edge is only located when it's bracketed.** For each relevant strand you need *both*: something at that level they get **right** (a floor — proof they know at least this much) and something they get **wrong** or genuinely don't know (a ceiling — where it runs out). The edge sits between them. One side alone tells you almost nothing.

- **All-correct is not "done" — it means the questions were too easy.** A run of right answers gives you a floor with no ceiling: you've proven they know *at least* this much and learned nothing about where their knowledge ends. Do not advance. Escalate — go harder until something finally breaks. If they never miss, you never found the edge.
- **Binary-search the edge.** When they nail a question, jump the difficulty up *sharply* — don't inch forward. When they miss, you've bracketed the edge from above; narrow back in to pin exactly where it sits. This finds the frontier fast, without a hundred timid questions.
- **One wrong answer is not "done" either — and it is *not* a cue to start teaching.** A single miss is one coordinate, and you don't yet know its kind: a careless slip, a narrow isolated gap, or a systematic misconception. Probe *around* it to characterize it before concluding anything. Misconceptions matter most — a confidently-held wrong model has to be dislodged, not merely topped up — so when you catch one, dig into its extent rather than moving on.
- **Map every strand the lesson rests on.** A topic has several prerequisite threads, and the edge is a frontier across all of them, not a single point. Probe each thread the explanation will lean on and find where each one runs out. Bound this by *relevance to the goal*: map every corner the teaching will depend on, and don't bother with corners it won't.

**Start from the profile.** Map each strand onto the foundations it rests on, and look those up in the profile. Where a recent `probed` or `confirmed` floor and ceiling exist, don't re-map from zero. Ask one question just above the recorded floor and one at the recorded ceiling to check the edge hasn't moved, then continue the binary search from there. Strands with no entry, or only `self-reported` ones, get the full mapping above. If the check puts the edge 2 or more levels away from the record, or several entries miss this way, the profile is off by more than one session's updates can fix. Finish this session's probe normally, then suggest `/learn:reassess @<name> <topic>` for a blind re-measure.

Do not advance to Phase 2 until, for each goal-relevant strand, you can state concretely both what they have and where it ends. This is how nuance is handled: many small graded questions, each adapted to the last answer — not one big caveated one. You fix every `quiz`'s answer key before asking, so you learn *exactly where* they go wrong, not just that they did.

**Then write the edges into the profile right away**, because a session can end without warning. For each strand, create or update the foundation entry (level, floor, ceiling, status, pace so far) with dated evidence lines.

**1b. Their learning goal — use plain `AskUserQuestion`.** Find out what they actually want taught. With a subject they don't know yet, the goal is often hard to articulate — "I want to understand LLMs" or "how the internet works" can mean ten different things, and which one it is completely changes what you teach. Interrogate the vision until it's concrete. This has no right answer, so it's plain `AskUserQuestion`, never `quiz`.

### Phase 2 — Plan (think hard here)

This is the highest-leverage step; don't rush it. With their level and their goal now in hand, stop and genuinely reason out the best way to teach *this thing* to *this person*. Re-read the philosophy above and plan against it:

- **Scope the field first with a `researcher` subagent.** Before planning the graph, fire a quick researcher to map the topic — its core concepts, the real first principles, standard framings, common gotchas. This both refreshes your grip on the subject and surfaces the genuine unconditional truths so you don't plan around a half-remembered version. Cheap, and it makes the whole plan more accurate. If the breakdown already used a researcher, build on that brief: ask only for what it didn't cover (framings, gotchas, the unconditional truths), not the prerequisites again.
- What are the unconditional truths this rests on? Is there a clean atomic unit ("ALL X is done through {____}")?
- Which of those do they already hold (from Phase 1a)? Build from there — not below it, not above it.
- What's the motivated discovery path from those truths to their goal? Where does each step come from — why would anyone reach for it?
- Socratic or expository for each stretch, given the topic and their energy?
- **What step size does the profile call for?** Use each strand's recorded pace and the Pace calibration section. In fast areas, plan bigger nodes: merge small derived steps into one node with one quiz-check. In slow areas, plan smaller nodes, with a worked example before the general form and a visual where one fits. Use the explanation styles the profile says click. Say in the plan's prose how the profile shaped it.

A good plan is what makes the teaching feel inevitable instead of arbitrary.

**Then present the plan in chat — always, before any teaching.** Two parts:

1. **The approach, in prose.** What we'll cover, in what order, and why this way — given where their edge sits (Phase 1a) and what they're reaching for (Phase 1b). A few freeform sentences.
2. **The dependency map.** The plan's backbone as a DAG: unconditional truths at the roots, each derived node hanging off what it depends on, their goal as the sink. Draw it as a small ```mermaid``` graph (the md-log file renders mermaid natively in Obsidian and in VS Code's preview). This map *is* the teaching order — Phase 3 builds it node by node. Keep it small: few nodes, short labels — a map, not the territory.

**Stress-test the roots before presenting.** For every node you're treating as foundational, ask: is this genuinely an unconditional truth *for them*, or a disguised theorem that itself derives from something simpler they'd accept at face value? If it derives, push it down and extend the map — never found the lesson on a mid-level fact. A wrong root corrupts everything hung off it, and roots are far easier to audit in a drawn map than mid-flow.

**Then stop and wait for their go-ahead.** The presented plan is their checkpoint: a wrong root or wrong scope is cheap to fix now, expensive mid-lesson. Do not begin Phase 3 until they okay the plan.

### Phase 3 — Teach (the loop)

Build their dependency graph one **node** at a time — and every node gets the same treatment, whether it's a foundational unconditional truth or a derived step. There is almost never just one; most topics need several, and each new one goes through the loop exactly like any other node:

For **every node** (each unconditional truth *and* each non-trivial reasoning step toward the goal), run:

1. **Motivate.** Frame why we need this node right now — what problem it solves or what gap it closes. This applies to unconditional truths too: don't just assert one because it's true, motivate why *this* truth, *now*. "Why are we even bringing this in?"
2. **Establish.** 
   - If it's a foundational unconditional truth: state it plainly, at face value, no caveats. Surface an atomic unit if one fits.
   - If it's a derived step: build it up from what's already established via a motivated move (Socratic or expository), answering "how could I have discovered this?" When a Socratic step has a gradable right/wrong answer, pose it with `quiz` even though they're "attempting the discovery" — gradable-and-Socratic is normal, not a contradiction; only fall back to plain `AskUserQuestion` if there's genuinely no right answer.
3. **Connect.** Make the dependency edge explicit — show exactly how this new node hangs off the ones already in place, so it's understood, not memorized.
4. **Quiz-check.** Only after steps 1-3 are written out in visible text (see quiz protocol rule 0). Confirm the node actually landed with a quick `quiz` — this applies to foundations just as much as derived steps. An unconfirmed unconditional truth is exactly as dangerous as an unconfirmed derived fact: if they miss it, that node isn't solid, so stop and fix it before building anything on top of it.

Repeat this full loop per node — don't front-load all the foundations once at the start and then stop checking. Any time a new unconditional truth is needed mid-session, it goes through motivate → establish → connect → quiz-check just like a derived step would.

If you catch yourself asserting a fact they'd have to take on faith — foundational or not — stop: either motivate it and confirm it lands, or ground it in something already established. Unmotivated, unconfirmed facts don't lock in — that's the whole point.

### Keeping the pace right

Aim every step at the edge of the zone of proximal development: it should take real effort and still land. Watch for both failure modes the whole time, and adjust the *next step*, not the next session:

| | Too slow (boring) | Too hard (exhausting) |
|---|---|---|
| **Signals** | Two or more quiz-checks in a row answered right, with confident notes; "got it", "yes, next"; free-text answers that run ahead to the next node; short, impatient replies | Two or more misses or "I don't know"s in a row on material just taught; an answer showing an earlier node didn't land; notes like "lost", "wait", "too much"; requests to re-explain |
| **Adjust** | Merge the next nodes and quiz-check once per merged group; go Socratic with harder prompts; skip ahead to the next node in the map that isn't already solid | Go back to the last node that landed; split the current node in two; add a concrete worked example or a visual; switch to expository; shorten replies |

Merging nodes never removes the quiz-check: one check covers the merged group. If the pace stays wrong in the same direction after two adjustments, the profile's levels are probably off. Say so, and suggest `/learn:reassess` at the end of the session. The learner can say "faster" or "slower" at any time, and that outranks every inferred signal. When you adjust, say so in one line (e.g. "Taking bigger steps, since you're ahead of me"), and record the trigger and the change under Pace calibration in the profile.

Whenever a node reveals something new about a foundation (a misconception, an unexpected ceiling, a clear pace signal), add an evidence line to the profile then and there. Don't save it all for the end.

### Phase 4 — Wrap-up

Run this when the goal node is reached or the learner wants to stop:

1. **Pace check.** Ask with `AskUserQuestion` (not a quiz): "How did the pace feel?" Options: "Too slow, boring", "About right", "Too hard, exhausting", "Varied by part". Ask them to say which parts in the notes.
2. **Update the profile.**
   - Frontmatter: set `updated` to today and add 1 to `sessions`.
   - Every foundation entry the session touched: level, floor, ceiling, status, pace, misconceptions, and dated evidence.
   - "How this learner learns" and Pace calibration: anything new, including the pace-check answer.
   - Open hypotheses: confirm, refute or add.
   - One Session history row, whose last column says what to change next time.
3. **Check for topic leakage.** Re-read what you wrote. Rewrite any claim about an application domain as the foundation underneath it.
4. **Tell the learner** in two or three lines what changed in their profile.

## Formatting — math renders as LaTeX

The terminal shows LaTeX, mermaid and images as raw text. The session is meant to be read in the **md-log** file (`/learn:md-log lessons/<topic>.md`), which renders all three in Obsidian or VS Code's markdown preview. If the session isn't linked yet, suggest that command once at the start. Write for that rendered view. Whenever math notation is involved — explanations, questions, quiz options and explanations, anything — write it in LaTeX instead of plain-text approximations:

- Inline math: `$f(x)$`
- Centered display math: `$$` fenced on its own lines, e.g. `$$\n f(x) \n$$`

If LaTeX can be used, it should be. Write $f(x) = x^2$, not `f(x) = x^2`. The one exception is the `AskUserQuestion` popup itself, which shows LaTeX raw, so keep math in quiz options short enough to read unrendered (the log renders it afterwards).
