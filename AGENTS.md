# Agent instructions: kitchen-hand

**Read this before touching a recipe, a capture, or anything that fetches.**

This file is canonical and harness-neutral — Codex, Cursor, Copilot, Zed,
Aider, Windsurf, Jules and Claude Code all read this filename. `CLAUDE.md`
beside it is a symlink to it. Do not let them drift.

`scripts/doctor.sh` verifies everything below in one command. Run it when
starting cold, or when something looks wrong.

## This repository is public

Nothing goes in that you would not want indexed. It already carries 40
creators' recipes, so the bar is attribution, not secrecy — but check both.

## Never scrape the platforms

Instagram and TikTok `robots.txt` disallow `ClaudeBot` and `*`. Do not fetch
them, not through a browser tool, not through a mirror.

**Check `robots.txt` before fetching any domain**, every time. `tasty.co`
disallows `ClaudeBot`, `Claude-Web` and `anthropic-ai` — its recipes reached
this collection through search results and permitting mirrors only.

Captures arrive through the paths in `docs/ingestion.md`: the Telegram bot, the
Instagram data export, a creator's own site where robots.txt permits it.
`tools/transcribe_audio.py` transcribes audio that is already on disk and
downloads nothing. A source-grep test in `tests/test_telegram.py` enforces that
`getFile` only ever fetches files Evan sent to his own bot.

## Every recipe names where it came from

`source` is a **required** schema field. A recipe without one fails
`tools/validate_recipes.py`. Captured recipes also carry `provenance` with the
creator handle, the source URL and the capture date.

Do not remove attribution, do not summarise a creator out of a `source` line,
and do not add a recipe you cannot attribute. If it is classic technique or
your own, say that in `source` — `bechamel-sauce` and `kung-pao-chicken` show
the wording.

`NOTICE.md` explains what the MIT LICENSE covers and what it does not. The
short version: the code and the file structure are Evan's; the recipes are
not.

## The gates

```
uv run tools/validate_recipes.py            recipes/ against the schema
uv run tools/validate_recipes.py --drafts   recipes/_drafts/
uv run pytest                                the test suite
uv run tools/triage_inbox.py --top 10        what is worth normalising next
scripts/doctor.sh                            all of the above, plus provenance
```

`triage_inbox.py` is **a report, never a gate.** It scores captures; it never
writes to `inbox/` and never deletes. A capture with a draft or a promoted
recipe is never droppable — `pipeline_slugs()` enforces that, and it exists
because a missing `youtube.md` in `CONTENT_FILES` once nearly deleted a real
capture.

## Working a recipe

Drafts land in `recipes/_drafts/` and are promoted to `recipes/` only after a
human reads them. Never promote unread.

**Never invent a quantity, a yield or a temperature.** If the source does not
state it, either ask or record the gap in `extraction_notes`. Where a reviewer
supplied a value, label it as such — `SERVINGS SET BY REVIEWER: 4` is the
established form. Several recipes carry air-fryer phases with no temperature
because the source only showed it on screen; that is recorded honestly rather
than guessed.

`quantity` is a **string** in the schema. `12` fails; `"12"` passes.

## Fail closed

A check that could not run is not a pass. Build from an allow-list, not a
filter. Missing config is a refusal to start, not a silent default.

**And prove it.** Break the gate on purpose and confirm it catches that. This
repo has form: mutation testing found four separate tests passing for the
wrong reason — a no-clobber guard the URL dedup short-circuited before
reaching, a traversal test where an extension check fired first, an offset
ordering test that passed either way, and a comment guard that was dead code.

## Where else things are written down

| file | what |
|---|---|
| `AGENTS.md` | this file — canonical |
| `CLAUDE.md` | symlink to it |
| `NOTICE.md` | what the LICENSE covers and what it does not |
| `docs/ingestion.md` | how captures get in, and what is ruled out |
| `docs/telegram-ingest-spec.md` | the bot, phase by phase |
| `docs/data-sources.md` | external APIs, each with its checked licence |
| `docs/backlog.md` | what is left, with the measured yield curve |
| `CONTRIBUTING.md` | layout and conventions |

Backlog items are also tracked in Plane under the `COLON` project.
