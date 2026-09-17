# Telegram Ingest — Spec

**Date:** 2026-09-17
**Status:** Phases 0 and 1 built. Phases 2 and 3 outstanding.
**Audience:** whoever builds it (solo)

A one-tap path from "I am looking at a recipe on my phone" to
`inbox/<slug>/`, with no export, no scraping, and no public endpoint.

---

## 1. The problem this solves

Ingestion today has two speeds and neither is the one that matches how a
recipe is actually encountered.

| Path | Latency | Gets the method? |
|---|---|---|
| `import_instagram_saved.py` (DYI export) | hours to days | yes |
| `transcribe_audio.py` | immediate | yes, if you have the file |
| Capture screen in `app/` | immediate | yes, at a computer |

The export is a **compliance artifact, not an API**: a manual click-path that
cannot be automated, no format contract (Meta has already shipped two shapes
— see `import_instagram_saved.py`), and batch delivery when the behaviour it
serves is one recipe at a time on a phone.

You see a Reel at 9pm on the sofa. Everything that gets it into the
collection currently happens at a desk, days later.

## 2. Why Telegram

The requirement is "send it to a chat and it lands". The candidates differ on
exactly one axis that matters.

| | WhatsApp Cloud API | **Telegram Bot API** | iCloud queue file |
|---|---|---|---|
| Public HTTPS webhook | **required** | **not required** | n/a |
| Business verification | required | none | none |
| Dedicated phone number | required | none | none |
| Cost | free tier, metered | free, unmetered | free |
| Durable server-side queue | yes | yes | no (sync, not queue) |
| Voice notes | yes | yes | no |
| Setup | days | ~2 minutes | ~20 minutes |

**The webhook is the whole decision.** WhatsApp pushes, so it needs a public
HTTPS endpoint — a tunnel, a certificate, something always reachable. That is
incompatible with `docs/app-spec.md`'s "local only, single user, no auth".
Telegram permits **long polling**: our side calls `getUpdates` and pulls. A
script behind NAT on a laptop works with nothing exposed.

Telegram also holds messages server-side until collected, which gives the
property capture most needs: **it cannot fail at the moment you saw the
recipe.** Mac asleep, on a plane, laptop shut — the message waits. An iCloud
file is a synced file, not a queue, and a POST to `localhost:8000` fails
exactly when the Mac is off.

**Accepted costs, to be chosen knowingly:** caption text transits Telegram's
servers, and it is one more account and one more secret to hold. Neither is
a blocker for text that is already public, but neither is nothing.

## 3. Where the code lives

**Decision: `kitchen-hand/tools/`, as two modules —
`telegram_transport.py` and `poll_telegram.py`.** Not a separate repo
yet; see "Why not its own repo, yet" below for the trigger that would
change that.

Not `voice-agent-input-hub`, despite that project's README describing almost
exactly this ("captures voice, transcripts, files, images... routes those
bundles to agents, processes, harnesses, and services"). Three reasons:

1. **The hub has no routing yet.** Its own status says real routing targets
   "remain behind future sessions". Building Telegram ingest there means
   building the hub's routing layer first — a much larger project than this
   one, and this one is blocked on it.
2. **The hub is a Flutter desktop app.** A polling bot is a headless process
   on a timer. Wrong shape.
3. **Everything this needs already exists here.** `write_capture()`, the
   permalink dedup, the `inbox/<slug>/` contract, the slug rules, and the
   never-clobber guarantee are all in `tools/import_instagram_saved.py`.
   Reimplementing them elsewhere means reimplementing the bugs they have
   already had.

### The seam: two modules, one import direction

The tool does two separable things, and they live in **two files**, not two
halves of one:

| File | Knows about | Depends on |
|---|---|---|
| `tools/telegram_transport.py` | Telegram | stdlib only |
| `tools/poll_telegram.py` | recipes, `inbox/` | the transport |

**`telegram_transport.py` must not import anything from kitchen-hand.** Not
`write_capture`, not `INBOX`, not the slug rules, not `core`. It takes a
token and an allow-list, and yields normalized message dicts. Everything that
knows what a recipe is lives in `poll_telegram.py`.

That constraint is the entire point and it costs nothing to honour today.
Write a source-grep test for it, the same way `tests/test_transcribe_audio.py`
pins the no-downloader rule:

```python
def test_the_transport_knows_nothing_about_kitchen_hand():
    source = TRANSPORT.read_text()
    for forbidden in ("write_capture", "INBOX", "provisional_slug", "from app"):
        assert forbidden not in source
```

The normalized dict the transport yields:

```python
{
    "message_id": 1234,
    "sender_id": 987654321,
    "date": "2026-09-17T21:04:00Z",
    "text": "...",                  # "" if none
    "urls": ["https://..."],        # entity-extracted, may be empty
    "files": [                      # already downloaded to a temp dir
        {"path": Path(...), "kind": "photo" | "voice" | "video" | "document",
         "original_name": "IMG_1234.HEIC"},
    ],
    "forwarded_from": "..." or None,
}
```

### Why not its own repo, yet

The shareable surface is small and the project-specific surface is not:

| Shared (transport) | ~lines | Project-specific (sink) |
|---|---|---|
| `getUpdates` + long poll | 15 | slug strategy |
| offset persistence | 10 | which files to write |
| allow-list check | 5 | `meta.txt` shape |
| `getFile` + download | 20 | dedup rules |
| normalize message to dict | 30 | fail-closed reporting |
| **~80 lines** | | **the actual work** |

Eighty lines of well-understood HTTP is below the line where a repo pays for
itself. A repo costs a README, CI, tests, a release story, and a version
coupling that breaks two projects when it rots. There is also **no existing
shared-library pattern in `~/files` to slot into** — no project path-depends
on another today — so extracting would mean establishing that pattern for
eighty lines.

Extract on the **second real consumer**, not the first and not a predicted
one. Building shared infrastructure against one real use and one imagined use
produces an abstraction shaped by the imagined one.

> **Extraction trigger.** Move `telegram_transport.py` to its own repo when a
> second project actually needs it. `throughline` is the likely candidate —
> photograph a denial letter, send it to a bot, it becomes a case document is
> the same transport with a different sink. At that point it becomes a `uv`
> path dependency, and that is also the moment to decide whether you want a
> shared-library pattern across `~/files` at all.
>
> Until then this is deliberately deferred, not overlooked. Do not re-litigate
> it without a second consumer in hand.

Because the import direction is enforced by a test rather than by discipline,
extraction when the trigger fires is `git mv` plus a dependency line — not a
rewrite. That asymmetry is what makes deferring strictly better than either
committing now or foreclosing the option.

**Do not build a plugin abstraction, a registry, or a sink interface.** There
is one consumer. Two modules and an import rule is the whole design.

## 4. Non-goals

- **No downloading of anyone else's media.** Reels and TikToks are not
  fetched, ever. `getFile` is used only for files *you* sent to *your own*
  bot — categorically the same as the DYI export, a sanctioned egress path
  for your own data, and unlike scraping a creator's video. The existing
  source-grep test in `tests/test_transcribe_audio.py` should be extended to
  cover this tool.
- **No webhook mode.** Long polling only. Adding webhooks reintroduces the
  public-endpoint requirement that ruled WhatsApp out.
- **No normalization.** Same boundary as everywhere else: this writes raw
  captures. Turning a caption into `recipes/_drafts/*.yaml` stays a human
  step with Claude's help.
- **No multi-user.** One allow-listed sender. See §7.
- **No bot conversation.** It does not ask clarifying questions or hold
  state per chat. It acknowledges and writes.

## 5. Message → capture mapping

One message becomes one capture. A message carrying several things
contributes several files to the same folder.

| Telegram content | Written to | Notes |
|---|---|---|
| URL in text | `url.txt` | first recognised post permalink wins |
| Remaining text | `caption.txt` | the caption you copied before sharing |
| Photo / image document | `screenshot.png` (numbered if several) | for carousel posts |
| Voice note or audio | `<file>.ogg` + `transcript.txt` | via `transcribe_audio.py` |
| Video note / video | saved, then transcribed | same path as audio |
| Forwarded message | same as above | `forwarded_from` recorded in `meta.txt` |

`meta.txt` is written in the same format `import_instagram_saved.py` uses, so
the triage tool, the capture screen and the draft workflow all read it
unchanged:

```
input_type: instagram | tiktok | youtube | url | pasted-text
creator: @handle            # only if derivable — see §6
source_url: <permalink>
captured_date: YYYY-MM-DD
telegram_message_id: 1234   # new field, for the audit trail
```

**A message with no URL and no media is `pasted-text`** and still becomes a
capture, with `raw.txt` rather than `caption.txt` — that is the "from Mom, no
source" case `docs/ingestion.md` already names.

## 6. Slugs

The dish is not known at capture time, so slugs are provisional exactly as
they are for the export importer, and get renamed when a draft is written.

| Source | Slug | Why |
|---|---|---|
| Instagram | `ig-<shortcode>` | the URL carries no handle |
| TikTok | `tt-<handle>-<id>` | the URL does carry the handle |
| YouTube | `yt-<video-id>` | |
| Other URL | `url-<host>-<hash8>` | |
| No URL | `note-<YYYYMMDD>-<hhmm>` | |

Note the asymmetry: the export importer produces `ig-<handle>-<shortcode>`
because the export carries the owner. A bare Instagram URL does not. That is
fine — folder names are provisional, and dedup is on the permalink, not the
name.

## 7. Security

**Anyone who discovers the bot's username can message it.** This is the one
genuinely new exposure in this design, and the whole of the response is an
allow-list.

- `KITCHEN_HAND_TELEGRAM_ALLOWED_IDS` — comma-separated Telegram numeric user
  ids. **Required.** A message from any other id is discarded without being
  written, and counted in the run summary so a stream of them is visible.
- Empty or unset allow-list is a **refusal to start**, not "allow all".
  Missing config is never a permissive default — same rule as larder's
  `DATABASE_PATH`.
- Uploaded files are subject to the same extension allow-list as
  `POST /inbox/{slug}/files` (see `service/app/routers/inbox.py`), and
  filenames are reduced to a basename before being joined to any path. That
  traversal guard was a real defect found there today; do not reinvent it
  here, import the rule.
- The bot token is a credential. It lives in the environment, never in the
  repo. `.gitignore` already covers `.env*`.

## 8. Configuration

Fail closed, and name the missing key rather than guessing a default:

| Variable | Required | Meaning |
|---|---|---|
| `KITCHEN_HAND_TELEGRAM_TOKEN` | yes | from `@BotFather` |
| `KITCHEN_HAND_TELEGRAM_ALLOWED_IDS` | yes | comma-separated numeric ids |
| `KITCHEN_HAND_TELEGRAM_STATE` | no | offset file, default `.telegram-offset` at repo root, gitignored |

Booting without either required key exits non-zero and says which is missing.

## 9. Polling model

- `getUpdates` with `offset` and `timeout=25` (long poll).
- The offset is persisted **only after the capture is written**. A crash
  mid-write re-delivers the message rather than losing it. Duplicate delivery
  is harmless — the permalink dedup and never-clobber make a second write a
  no-op.
- Two run modes:
  - `--once` — drain whatever is queued and exit. For cron.
  - default — loop, long-polling. For a terminal you leave open.
- Telegram retains undelivered updates for 24 hours. A cron every 15 minutes
  is ample; the durability argument in §2 holds regardless of interval.

## 10. Required change to `import_instagram_saved.py`

**This is a prerequisite, not a nicety.** The two paths must be able to
backfill each other, and today they cannot.

`main()` currently does:

```python
if post.url in already:
    skipped.append(post)
    continue
```

So a folder Telegram created from a bare URL — `url.txt` and `meta.txt`, no
caption — is skipped entirely when the export later arrives carrying that
post's caption. **The caption never lands.**

The fix is small because `write_capture()` already never clobbers: on a URL
match, resolve the *existing* folder name and call `write_capture()` against
it anyway. Files present are left alone; missing ones are filled in. Report
those as "backfilled" rather than "created" so the distinction is visible.

That change is what makes the two-speed pipeline actually work:

- **Fast** — Telegram, seconds, URL plus whatever you pasted.
- **Slow** — export, days later, fills in anything you did not paste.

## 11. Fail-closed properties

Every one of these has a precedent in this repo, and each should be tested by
mutation the way the existing tools were:

1. **Never clobber.** Reuse `write_capture()`. A message re-delivered after a
   crash must not overwrite a caption you corrected.
2. **Dedup on permalink, not folder name.** So a renamed folder is still
   recognised.
3. **An unparseable message fails the run, not the message.** Report it with
   its message id and exit non-zero unless `--allow-unparsed`. Importing 9 of
   10 silently is the failure mode this repo refuses everywhere else.
4. **A disallowed sender is discarded and counted**, never written.
5. **A transcript is never trusted output.** Reuse `transcribe_audio.py`'s
   header and low-confidence reporting verbatim.
6. **Missing config refuses to start.**

## 12. Testing

No network and no bot token in the suite. `getUpdates` responses are JSON;
fixtures are cheap.

- Fixture messages for each row of §5, asserted against the resulting folder.
- Allow-list: a disallowed id writes nothing and is counted.
- Offset: persisted only after a successful write; a raised exception
  mid-write leaves the offset unmoved.
- Backfill: a folder with only `url.txt` gains `caption.txt` from a later
  export run, and a hand-corrected `caption.txt` survives it.
- Source-grep, as in `tests/test_transcribe_audio.py`: the tool must not
  contain any fetch of an instagram.com or tiktok.com media URL.
- Source-grep on the import direction: `telegram_transport.py` must contain
  no reference to `write_capture`, `INBOX`, `provisional_slug` or `from app`.
  That test is what keeps extraction cheap, so it is not optional.

## 13. Phases

- **Phase 0 — the backfill fix.** *Built* (`573b783`). §10, on its own,
  before any Telegram code. Without it the two-speed pipeline does not work
  and Phase 1 is worth less than it looks.
- **Phase 1 — text and URLs.** *Built.* Both modules, with the
  import-direction test from the start. `getUpdates`, allow-list, offset, URL
  parsing, and `url.txt` / `caption.txt` / `meta.txt`.

  Two things came out differently from this spec, both for the better:

  - **The import-direction test parses the module rather than grepping it.**
    A grep cannot tell an import from the docstring saying not to write one,
    and the first version of the test failed on the transport's own prose. It
    now asserts the set of imported top-level modules is a subset of the
    standard library, which is the actual property and also catches a
    renamed helper.
  - **A message carrying media is captured, not deferred.** The spec implied
    Phase 1 would leave those for Phase 2. Instead the text and URL are
    written now and the Telegram `file_id` is recorded in `meta.txt` as
    `telegram_pending_media`, because a `file_id` is stable for the life of
    the bot. Phase 2 fetches them with nothing re-sent — the same backfill
    shape as §10.
- **Phase 2 — media.** Photos to `screenshot.png`, voice notes through
  `transcribe_audio.py`.
- **Phase 3 — acknowledgement.** Reply to each message with the slug it
  became, so the phone confirms without opening a laptop. Deliberately last:
  it is the only part that makes the bot a two-way thing, and everything
  before it is useful without it.

## 14. Setup, for the record

1. Message `@BotFather`, `/newbot`, keep the token.
2. Message your own bot once, then read your numeric id from the first
   `getUpdates` response.
3. Put both in the environment.
4. Add the bot to the phone's share sheet (it is a normal chat).
5. `uv run tools/poll_telegram.py --once` on a cron, or leave it looping.
