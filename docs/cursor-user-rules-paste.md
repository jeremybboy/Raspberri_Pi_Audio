# Paste into Cursor User Rules

**Where:** On the machine where the **Cursor app** runs → **Settings** → **Rules for AI** → **User Rules** (account-wide; applies to SSH Remote too).

**Why a file in the repo:** Cursor does not store User Rules inside this Git repository. This document is the **canonical copy** to paste into the UI so it stays versioned with the project.

---

Copy everything in the block below (from `## Responses` through the last line) into **User Rules**.

```markdown
## Responses
- Default to succinct answers. Lead with the conclusion; add detail only when needed or when asked.

## Terminal / Cursor workflow
- Prefer the Cursor command flow: propose runnable commands so I can approve with Run / OK. Do not ask me to copy-paste shell commands into an external terminal unless I explicitly ask for that.

## Raspberry Pi audio project (SSH Remote)
- Canonical repo on the Pi: $HOME/Raspberri_Pi_Audio (GitHub: jeremybboy/Raspberri_Pi_Audio).
- For any substantive work on that project, read and follow $HOME/Raspberri_Pi_Audio/.cursor/rules/project-context.mdc (hardware, exact commands, Run/OK examples, Git/PR workflow: agent opens PR on wip/feature branches; I merge on GitHub; no direct push of new work to main when that workflow applies).
- If the Cursor workspace is not that folder, still treat that path as the canonical repo unless I override.

## Code / edits (when in Agent mode)
- Small, focused diffs; match existing style; no unrelated refactors unless I ask.

## Citations
- When pointing at existing code, use Cursor-style code references (line ranges + filepath) when helpful.
```

After pasting, save. You can re-open this file anytime to refresh or compare.
