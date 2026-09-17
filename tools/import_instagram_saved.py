#!/usr/bin/env python3
"""Turn an Instagram "Download Your Information" export into inbox/ folders.

No Meta API returns your saved posts - the DYI export is the only sanctioned
route. The JSON export carries, per saved post: the permalink, the caption,
the creator's handle, the hashtags, and when you saved it. That is the whole
capture, so this writes url.txt, meta.txt *and* caption.txt, and the post is
ready to normalize without anything being pasted by hand.

Usage:
    tools/import_instagram_saved.py <archive> [options]

<archive> is the .zip straight from Instagram, the unzipped directory, or the
saved_posts.json itself.

Options:
    --collection NAME   only posts in that saved collection
    --list-collections  print the collections and their sizes, write nothing
    --dry-run           report what would be created, write nothing
    --allow-unparsed    exit 0 despite entries that yielded no permalink

Safety properties, in order of how much they matter:

1. It never overwrites a file that already exists. Anything you have corrected
   by hand survives a re-run.
2. It dedups on the permalink, not the folder name, so folders you have
   already renamed from the provisional slug are still recognised.
3. A saved entry it cannot parse into a permalink is *reported and fails the
   run*, not skipped. Importing 500 of 548 silently is the failure mode that
   looks like success. --allow-unparsed downgrades that once you have looked.
4. A caption whose encoding cannot be repaired is written as-is rather than
   mangled, and the run says so. Quantities live in these captions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"

SAVED_POSTS_NAME = "saved_posts.json"
COLLECTIONS_NAME = "saved_collections.json"

PERMALINK_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)"
)
_NON_SLUG = re.compile(r"[^a-z0-9]+")

# Byte sequences that only appear when UTF-8 has been read as Latin-1.
_MOJIBAKE_MARKERS = ("â", "Ã©", "ð")


@dataclass(frozen=True)
class SavedPost:
    url: str
    shortcode: str
    handle: str
    display_name: str | None = None
    caption: str | None = None
    title: str | None = None
    saved_on: str | None = None
    hashtags: tuple[str, ...] = ()
    collection: str | None = None
    encoding_repaired: bool = False
    encoding_suspect: bool = False


@dataclass
class ParseResult:
    posts: list[SavedPost] = field(default_factory=list)
    unparsed: list[dict] = field(default_factory=list)


# --- encoding ------------------------------------------------------------


def repair_mojibake(text: str) -> tuple[str, bool, bool]:
    """Undo Instagram's UTF-8-read-as-Latin-1 damage in caption text.

    The export stores a right single quote as three Latin-1 characters - the
    UTF-8 bytes reinterpreted one byte per character. Round-tripping back
    through Latin-1 recovers the original.

    Returns (text, repaired, suspect). The repair is applied only when the
    round trip fully succeeds: on any failure the original is returned
    untouched and flagged, because a half-decoded caption would corrupt
    exactly the quantities and fractions this pipeline exists to get right.
    """
    if not text:
        return text, False, False
    # Text holding real non-Latin-1 characters (emoji, CJK) was stored
    # correctly and must not be touched.
    try:
        raw = text.encode("latin-1")
    except UnicodeEncodeError:
        return text, False, False
    try:
        fixed = raw.decode("utf-8")
    except UnicodeDecodeError:
        suspect = any(marker in text for marker in _MOJIBAKE_MARKERS)
        return text, False, suspect
    return (fixed, True, False) if fixed != text else (text, False, False)


# --- DYI JSON shapes -----------------------------------------------------


def _label_values(entry: dict) -> dict[str, str]:
    """Flat {label: value} for an entry's own labels (URL, Caption, Title)."""
    out: dict[str, str] = {}
    for lv in entry.get("label_values", []):
        if isinstance(lv, dict) and lv.get("label"):
            value = lv.get("value")
            if value is None:
                value = lv.get("href")
            if isinstance(value, str):
                out[lv["label"]] = value
    return out


def _titled_block(entry: dict, title: str) -> list[dict[str, str]]:
    """The nested {"title": <title>, "dict": [...]} block, flattened.

    Owner and Hashtags arrive as a list of sub-entries, each holding its own
    label/value pairs, so this returns one dict per sub-entry.
    """
    rows: list[dict[str, str]] = []
    for lv in entry.get("label_values", []):
        if not isinstance(lv, dict) or lv.get("title") != title:
            continue
        for item in lv.get("dict", []):
            if not isinstance(item, dict):
                continue
            row = {
                d["label"]: d.get("value", "")
                for d in item.get("dict", [])
                if isinstance(d, dict) and d.get("label")
            }
            if row:
                rows.append(row)
    return rows


def _parse_entry(entry: dict, collection: str | None) -> SavedPost | None:
    labels = _label_values(entry)
    url = labels.get("URL")
    if not url:
        return None
    m = PERMALINK_RE.match(url)
    if not m:
        return None

    owner = _titled_block(entry, "Owner")
    handle = (owner[0].get("Username") if owner else None) or "unknown"
    display = (owner[0].get("Name") if owner else None) or None

    caption, repaired, suspect = repair_mojibake(labels.get("Caption", ""))
    title, t_repaired, t_suspect = repair_mojibake(labels.get("Title", ""))

    ts = entry.get("timestamp")
    saved_on = None
    if isinstance(ts, int) and ts > 0:
        saved_on = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()

    return SavedPost(
        url=url,
        shortcode=m.group(1),
        handle=handle,
        display_name=display,
        caption=caption.strip() or None,
        title=title.strip() or None,
        saved_on=saved_on,
        hashtags=tuple(
            r["Name"] for r in _titled_block(entry, "Hashtags") if r.get("Name")
        ),
        collection=collection,
        encoding_repaired=repaired or t_repaired,
        encoding_suspect=suspect or t_suspect,
    )


def _legacy_entries(payload: object) -> list[dict]:
    """Older exports wrapped entries as {"saved_saved_media": [...]}.

    Match on shape (the one value that is a list), because Meta has renamed
    that key between versions.
    """
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [e for e in value if isinstance(e, dict)]
    return []


def _parse_legacy_entry(entry: dict) -> SavedPost | None:
    """The {title, string_map_data: {label: {href, timestamp}}} encoding."""
    smd = entry.get("string_map_data")
    if not isinstance(smd, dict):
        return None
    url = shortcode = None
    timestamp = None
    for f in smd.values():
        if not isinstance(f, dict):
            continue
        href = f.get("href")
        if isinstance(href, str) and url is None:
            m = PERMALINK_RE.match(href)
            if m:
                url, shortcode = href, m.group(1)
        ts = f.get("timestamp")
        if isinstance(ts, int) and ts > 0 and timestamp is None:
            timestamp = ts
    if not url or not shortcode:
        return None
    handle = entry.get("title")
    return SavedPost(
        url=url,
        shortcode=shortcode,
        handle=handle if isinstance(handle, str) and handle else "unknown",
        saved_on=(
            datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
            if timestamp
            else None
        ),
    )


def parse_saved_posts(
    raw: bytes, collections: dict[str, str] | None = None
) -> ParseResult:
    """Parse either export shape. Never drops an entry silently."""
    payload = json.loads(raw)
    entries = (
        [e for e in payload if isinstance(e, dict)]
        if isinstance(payload, list)
        else _legacy_entries(payload)
    )
    collections = collections or {}

    result = ParseResult()
    for entry in entries:
        url = _label_values(entry).get("URL", "")
        post = _parse_entry(entry, collections.get(url)) or _parse_legacy_entry(entry)
        if post is None:
            result.unparsed.append(entry)
        else:
            result.posts.append(post)
    return result


def _collect_urls(node, out: list[str]) -> None:
    """Every post permalink anywhere inside a collection entry.

    Filtered to permalinks on purpose: a collection also carries each
    creator's own website under the same "URL" label, and counting those
    would overstate how big a collection is.
    """
    if isinstance(node, dict):
        value = node.get("value")
        if node.get("label") == "URL" and isinstance(value, str):
            if PERMALINK_RE.match(value):
                out.append(value)
        for value in node.values():
            _collect_urls(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_urls(value, out)


def parse_collections(raw: bytes) -> dict[str, str]:
    """{permalink: collection name} across every saved collection."""
    payload = json.loads(raw)
    entries = payload if isinstance(payload, list) else _legacy_entries(payload)

    mapping: dict[str, str] = {}
    for coll in entries:
        if not isinstance(coll, dict):
            continue
        name = _label_values(coll).get("Name")
        if not name:
            continue
        urls: list[str] = []
        _collect_urls(coll, urls)
        for url in urls:
            mapping.setdefault(url, name.strip())
    return mapping


# --- filesystem ----------------------------------------------------------


def slugify(text: str) -> str:
    return _NON_SLUG.sub("-", text.lower()).strip("-")


def provisional_slug(post: SavedPost) -> str:
    """Folder name at capture time - creator plus shortcode.

    Provisional on purpose: the dish name is not known until the caption has
    been read. Rename to the real dish slug when normalizing into _drafts/.
    """
    return f"ig-{slugify(post.handle) or 'unknown'}-{slugify(post.shortcode)}"


def _read_members(archive: Path) -> dict[str, bytes]:
    wanted = {SAVED_POSTS_NAME, COLLECTIONS_NAME}
    found: dict[str, bytes] = {}

    if archive.is_file() and archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name
                if name in wanted and name not in found:
                    found[name] = zf.read(info)
    elif archive.is_file():
        name = archive.name if archive.name in wanted else SAVED_POSTS_NAME
        found[name] = archive.read_bytes()
        # Collection membership lives in the sibling file; without it a
        # --collection filter would silently match nothing.
        sibling = archive.parent / COLLECTIONS_NAME
        if name == SAVED_POSTS_NAME and sibling.is_file():
            found[COLLECTIONS_NAME] = sibling.read_bytes()
    elif archive.is_dir():
        for name in wanted:
            for path in sorted(archive.rglob(name)):
                found[name] = path.read_bytes()
                break
    else:
        sys.exit(f"not a file or directory: {archive}")

    return found


def captured_urls() -> dict[str, str]:
    """{permalink: folder name} for everything already in inbox/.

    Keyed on the URL so a folder renamed away from the provisional slug is
    still recognised and not re-created.
    """
    seen: dict[str, str] = {}
    if not INBOX.is_dir():
        return seen
    for folder in sorted(INBOX.iterdir()):
        url_file = folder / "url.txt"
        if folder.is_dir() and url_file.is_file():
            for line in url_file.read_text(errors="replace").splitlines():
                line = line.strip()
                if line:
                    seen.setdefault(line, folder.name)
    return seen


def meta_text(post: SavedPost, captured_date: str) -> str:
    lines = ["input_type: instagram", f"creator: @{post.handle}"]
    if post.display_name:
        lines.append(f"creator_name: {post.display_name}")
    lines += [
        f"source_url: {post.url}",
        f"captured_date: {captured_date}",
        f"saved_on: {post.saved_on or 'unknown'}",
        "post_date: unknown",
    ]
    if post.collection:
        lines.append(f"collection: {post.collection}")
    if post.hashtags:
        lines.append("hashtags: " + " ".join("#" + h for h in post.hashtags))
    if post.encoding_suspect:
        lines.append("encoding: SUSPECT - caption may be mis-decoded, check it")
    lines += [
        "",
        "# saved_on is when you saved the post, not when it was published.",
        "# caption.txt is the export's own caption text, unedited. If the",
        "# steps are in the post's images instead, add screenshot.png.",
        "# This folder name is provisional - rename it to the dish slug when",
        "# you normalize into recipes/_drafts/.",
    ]
    return "\n".join(lines) + "\n"


def write_capture(post: SavedPost, slug: str, dry_run: bool) -> list[str]:
    """Create the folder and any missing files. Returns names written."""
    folder = INBOX / slug
    files = {
        "url.txt": post.url + "\n",
        "meta.txt": meta_text(post, date.today().isoformat()),
    }
    if post.caption:
        body = post.caption
        if post.title:
            body = f"{post.title}\n\n{body}"
        files["caption.txt"] = body + "\n"

    written = []
    for name, content in files.items():
        path = folder / name
        if path.exists():
            continue  # never clobber
        written.append(name)
        if not dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return written


# --- cli -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archive", type=Path)
    ap.add_argument("--collection", help="only import posts in this saved collection")
    ap.add_argument("--list-collections", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-unparsed", action="store_true")
    args = ap.parse_args(argv)

    members = _read_members(args.archive)
    if SAVED_POSTS_NAME not in members:
        return _fail(
            f"no {SAVED_POSTS_NAME} in {args.archive}.\n"
            "Request the export in JSON format (not HTML)."
        )

    collections = (
        parse_collections(members[COLLECTIONS_NAME])
        if COLLECTIONS_NAME in members
        else {}
    )

    if args.list_collections:
        counts: dict[str, int] = {}
        for name in collections.values():
            counts[name] = counts.get(name, 0) + 1
        if not counts:
            print("no saved collections in this export")
        for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"{n:5d}  {name}")
        return 0

    result = parse_saved_posts(members[SAVED_POSTS_NAME], collections)
    posts = result.posts
    missing: list[str] = []

    if args.collection:
        wanted = args.collection.strip().lower()
        known = {c.lower() for c in collections.values()}
        if wanted not in known:
            return _fail(
                f"no saved collection named {args.collection!r}. Known: "
                + (", ".join(sorted(set(collections.values()))) or "(none)")
            )
        posts = [p for p in posts if (p.collection or "").lower() == wanted]

        # A collection can name a post that saved_posts.json does not carry
        # (the creator deleted it, or the export is internally inconsistent).
        # Nothing here can recover it, but importing 44 of 45 without saying
        # so is the silent-partial failure this tool exists to refuse.
        in_collection = {
            url for url, name in collections.items() if name.lower() == wanted
        }
        missing[:] = sorted(in_collection - {p.url for p in result.posts})

    already = captured_urls()
    created, backfilled, unchanged, collisions = [], [], [], []
    claimed: dict[str, SavedPost] = {}

    for post in posts:
        if post.url in already:
            # Already captured - but possibly not completely. Another ingest
            # path may have created this folder from a bare URL, with no
            # caption. write_capture never clobbers, so calling it against the
            # existing folder fills the gaps and touches nothing else.
            existing = already[post.url]
            written = write_capture(post, existing, args.dry_run)
            (backfilled if written else unchanged).append((existing, post, written))
            continue
        slug = provisional_slug(post)
        if slug in claimed and claimed[slug].url != post.url:
            collisions.append((slug, claimed[slug].url, post.url))
            continue
        claimed[slug] = post
        written = write_capture(post, slug, args.dry_run)
        if written:
            created.append((slug, post, written))

    verb = "would create" if args.dry_run else "created"
    backfill_verb = "would backfill" if args.dry_run else "backfilled"
    scope = f" in {args.collection!r}" if args.collection else ""
    print(f"saved posts in export{scope}: {len(posts)}")
    print(f"already complete in inbox/: {len(unchanged)}")
    print(f"{verb}: {len(created)}")
    if backfilled:
        print(f"{backfill_verb}: {len(backfilled)}")
        for slug, _, written in backfilled[:20]:
            print(f"  {slug}  (+{', '.join(written)})")
        if len(backfilled) > 20:
            print(f"  ... and {len(backfilled) - 20} more")

    if created:
        with_caption = sum(1 for _, p, _ in created if p.caption)
        repaired = sum(1 for _, p, _ in created if p.encoding_repaired)
        print(f"  caption text included: {with_caption} of {len(created)}")
        print(f"  mis-encoded captions fixed: {repaired}")

    for slug, post, _ in created[:20]:
        mark = "" if post.caption else "   (no caption - check the post)"
        print(f"  {slug}  @{post.handle}{mark}")
    if len(created) > 20:
        print(f"  ... and {len(created) - 20} more")

    sys.stdout.flush()

    suspect = [(s, p) for s, p, _ in created if p.encoding_suspect]
    if suspect:
        print(
            f"\n{len(suspect)} caption(s) could not be decoded cleanly and were "
            "written as-is. Check quantities against the post before trusting "
            "them; each is flagged in its meta.txt as 'encoding: SUSPECT'.",
            file=sys.stderr,
        )
        for slug, _ in suspect[:10]:
            print(f"  {slug}", file=sys.stderr)

    if collisions:
        print("\nslug collisions (not written):", file=sys.stderr)
        for slug, a, b in collisions:
            print(f"  {slug}: {a} vs {b}", file=sys.stderr)

    if missing:
        print(
            f"\n{len(missing)} post(s) in {args.collection!r} are not in "
            f"{SAVED_POSTS_NAME} and could not be imported. The export does not "
            "carry them (deleted by the creator, most likely) - open each and "
            "capture it by hand if it matters:",
            file=sys.stderr,
        )
        for url in missing[:10]:
            print(f"  {url}", file=sys.stderr)

    if result.unparsed:
        n = len(result.unparsed)
        print(
            f"\n{n} saved entr{'y' if n == 1 else 'ies'} yielded no Instagram "
            "permalink. First one:",
            file=sys.stderr,
        )
        print(
            "  " + json.dumps(result.unparsed[0], ensure_ascii=False)[:400],
            file=sys.stderr,
        )
        if not args.allow_unparsed:
            return _fail(
                "refusing to report success on a partial import. Re-run with "
                "--allow-unparsed once you have confirmed these are not recipes."
            )

    if collisions:
        return _fail("slug collisions above were not imported.")
    if missing and not args.allow_unparsed:
        return _fail(
            f"{len(missing)} post(s) in the collection are missing from the "
            "export, so this import is incomplete. Re-run with --allow-unparsed "
            "once you have noted them."
        )
    return 0


def _fail(message: str) -> int:
    sys.stdout.flush()
    print(f"\nerror: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
