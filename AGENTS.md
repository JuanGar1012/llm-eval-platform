# AGENTS.md

# LLM Eval Platform

## Context management (checkpointing)
- If context usage is at or above ~70% OR user indicates context is high, create a checkpoint before continuing.
- A checkpoint means writing/overwriting these repository-root files:

1. `PROJECT_STATE.md` (overwrite every checkpoint)
- Canonical, concise current state.
- Structured sections only; no large code dumps.

2. `CHECKPOINTS/PROJECT_STATE_<YYYY-MM-DD_HHMM>.md` (new file per checkpoint)
- Snapshot copy of `PROJECT_STATE.md` content.

3. `DECISIONS.md` (append-only)
- Add dated entries for material architecture, data model, or workflow decisions and tradeoffs.

## Required checkpoint contents
- Goal and non-goals
- Current architecture and data model
- Key commands (dev/test/run)
- High-level files created/modified and why
- Completed items
- Open tasks (prioritized)
- Known issues and edge cases
- Next 3 actions checklist

## Post-checkpoint rule
- After checkpointing, use `PROJECT_STATE.md` as canonical context and do not rely on prior chat history.
