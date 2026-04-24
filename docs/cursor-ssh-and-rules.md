# Cursor, SSH Remote, and where rules live

This document explains how **Cursor User Rules** (on your laptop) relate to **project rules** (on the Raspberry Pi) when you use **Remote SSH**. It matches the mental model used in project discussions so you do not have to rediscover paths each session.

## Two machines, two layers of rules

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  YOUR LAPTOP / PC (Cursor app runs here)                                 │
│                                                                          │
│  ┌──────────────────────────────────────┐                               │
│  │  Cursor User Rules                    │  ← Tied to your Cursor login  │
│  │  (Settings → Rules for AI)            │    Synced with Cursor Cloud   │
│  │  NOT inside the Pi repo               │    Path is inside Cursor app   │
│  │  Applies to EVERY chat window         │    (you don’t browse to it      │
│  │  including SSH Remote                 │     like a normal project file)│
│  └──────────────────────────────────────┘                               │
│                    │                                                     │
│                    │  SSH Remote session                                 │
│                    ▼                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                     │
                     │  files read over SSH
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  RASPBERRY PI (remote filesystem)                                        │
│                                                                          │
│  $HOME/                          ← often what opens first after SSH      │
│    .cursor/rules/                ← OPTIONAL extra rules if you add them  │
│      (only if workspace = $HOME)                                         │
│                                                                          │
│  $HOME/Raspberri_Pi_Audio/       ← this repository (clone path may vary)  │
│    .cursor/rules/                                                        │
│      project-context.mdc         ← PROJECT rules (on disk, on the Pi)    │
│    .venv/  *.py  Readme.md  ...                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Summary**

- **User Rules** live in the **Cursor app / your account** (client side). They apply to every chat, including SSH Remote. They are **not** a file inside this Git repo.
- **Project rules** are files in **this repo**: [`.cursor/rules/project-context.mdc`](../.cursor/rules/project-context.mdc). They load when this folder (or a workspace that includes it appropriately) is the **Cursor workspace root**.

## Conceptual “context bundle” for one chat (JSON shape)

Simplified view of what gets assembled for the model (exact internals are product-defined):

```json
{
  "chat_context_bundle": {
    "always_included": {
      "cursor_user_rules": {
        "source": "Cursor account / app (laptop)",
        "path_on_disk": "opaque — Cursor Settings, not this repo",
        "applies_when": "every conversation, including SSH Remote"
      },
      "system_reminders": {
        "source": "Cursor product",
        "example": "Ask mode, date, workspace hints"
      }
    },
    "workspace_dependent": {
      "workspace_root": {
        "example_ssh_cases": [
          "/home/<unix-user>",
          "/home/<unix-user>/Raspberri_Pi_Audio"
        ],
        "note": "Whichever folder is Open Folder for this window"
      },
      "project_rules_loaded_from": {
        "pattern": "<workspace_root>/.cursor/rules/*.mdc",
        "this_repo": ".cursor/rules/project-context.mdc",
        "only_if": "This repo (or a parent with its own .cursor/rules) is the workspace root"
      },
      "open_files_and_selections": {
        "source": "whatever you have open in the editor"
      }
    }
  }
}
```

## Same Pi, different workspace → different project rules

```text
  Workspace = $HOME
  ┌─────────────────────────────────┐
  │  User Rules            YES       │
  │  project-context.mdc   NO*      │  *unless you also have ~/.cursor/rules
  └─────────────────────────────────┘

  Workspace = $HOME/Raspberri_Pi_Audio  (this repo)
  ┌─────────────────────────────────┐
  │  User Rules            YES       │
  │  project-context.mdc   YES       │
  └─────────────────────────────────┘
```

## Quick reference table

| Item | Where it lives |
|------|----------------|
| User Rules | Cursor → Settings → **Rules for AI** (synced with your account) |
| `project-context.mdc` | This repo: `.cursor/rules/project-context.mdc` (on the Pi disk) |
| Optional home rules | On the Pi: `$HOME/.cursor/rules/` (only if `$HOME` is the workspace) |
| Chat history | This conversation only (not a repo file) |

## Collaboration tips (SSH + Pi)

1. **Open this repo as the folder** in Cursor after connecting (`File → Open Folder…`) so `project-context.mdc` applies automatically.
2. Put **host-wide** habits (e.g. “prefer Run/OK”, “canonical repo path on this Pi”) in **User Rules** so they still apply if the workspace opens as `$HOME` first.
3. Optional: add a small rule under `$HOME/.cursor/rules/` on the Pi if you always land in `$HOME` and want a pointer to this repo without opening the folder.

---

*This file is documentation only; it does not change runtime audio behavior.*
