#!/usr/bin/env python3
"""Score every inbox capture on how much of a recipe its text actually holds.

A bulk import leaves the inbox unworkable: sweeping a real Instagram export
put 549 folders in `inbox/`, of which 443 were guitar tutorials, electronics
and interiors. This sorts them so the queue can be worked, and reports which
captures carry a recipe, which carry a food post with the recipe somewhere
else, and which are not food at all.

Usage:
    tools/triage_inbox.py                      # summary + the top of the list
    tools/triage_inbox.py --bucket strong      # just slugs, one per line
    tools/triage_inbox.py --out /tmp/triage    # write one file per bucket

**This is a report, not a gate. It never writes to or deletes from inbox/.**

That is deliberate and worth keeping. A keyword heuristic cannot be trusted to
decide what is a recipe - the first version of this scoring matched "eat"
inside "great" and filed a GitHub post as food - so the importer takes
everything and the judgement happens afterwards, over what is already on disk
and reviewable. Filtering at import time would have turned that bug into
recipes that were never captured and never missed. To act on a bucket, pipe it
somewhere yourself:

    tools/triage_inbox.py --bucket not-food > drop.txt
    # read drop.txt, then:
    (cd inbox && xargs rm -rf < ../drop.txt)

Buckets, in descending order of how ready a capture is to normalize:

    strong        the caption holds quantities and method - normalize it
    weak          food, partial recipe - read it before deciding
    food-no-text  a food post whose recipe is not in the caption (commonly
                  "comment RECIPE and I'll DM you"). Needs a screenshot or a
                  transcript via the app's capture screen.
    not-food      no food signal at all
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"

STRONG_SCORE = 5
WEAK_SCORE = 2

# Word-bounded on purpose. An unbounded "eat" matches "great" and "creating",
# which filed a GitHub post and an Anthropic post as food, and inflated seven
# unrelated captures into the strong bucket. tests/test_triage_inbox.py pins
# this; loosen the boundaries and those tests fail.
FOOD = re.compile(
    r"\b(?:recipe|recipes|food|foodie|cook|cooking|cooks|eat|eats|eating|meal|"
    r"meals|mealprep|chef|kitchen|dinner|dinners|breakfast|lunch|brunch|bake|"
    r"baked|baking|bbq|grill|grilled|snack|dessert|yum|yummy|delicious|"
    r"homemade|highprotein|airfryer|crockpot|pasta|chicken|steak|soup|sauce|"
    r"smoker|brisket|burger|taco|tacos|pizza|noodle|noodles|tots|casserole|"
    r"marinade|marinated)\b",
    re.I,
)

# A quantity is the single strongest signal that a caption is a recipe rather
# than a photo of one. Anchored on a leading number so a bare "g" or "oz" in
# prose does not count.
MEASURE = re.compile(
    r"\b\d+[\s/\d]*\s*(?:tbsp|tablespoons?|tsp|teaspoons?|cups?|oz|ounces?|lbs?|"
    r"pounds?|grams?|g|ml|cloves?|pinch|dash|quarts?|sticks?)\b",
    re.I,
)

METHOD = re.compile(
    r"\b(?:preheat|bake|saute|sauté|simmer|boil|whisk|marinate|season|fry|"
    r"roast|stir|chop|dice|mince|grill|knead|drain|serve|smoke|braise|sear)\w*\b",
    re.I,
)

# A caption that lays out its own sections is almost certainly a full recipe.
SECTION = re.compile(
    r"^\s*(?:ingredients|directions|instructions|method|steps)\b", re.I | re.M
)


@dataclass(frozen=True)
class Capture:
    slug: str
    caption: str
    handle: str
    hashtags: str
    collection: str
    in_pipeline: bool = False

    @property
    def title(self) -> str:
        text = self.caption.strip()
        return text.splitlines()[0][:70] if text else "(no caption)"


def meta_field(meta: str, key: str) -> str:
    """Read one `key: value` line from a capture's meta.txt.

    Not a YAML parse: meta.txt is a human scratchpad allowed to hold prose and
    comments, and a strict parser would raise on a hand-edited file rather than
    degrade to "field not found". A full-line `#` comment needs no special case
    - the `#` parses as part of the key and never matches a lookup.
    """
    for line in meta.splitlines():
        sep = line.find(":")
        if sep > 0 and line[:sep].strip() == key:
            return line[sep + 1 :].strip()
    return ""


# Every file a capture can carry its recipe text in. Must stay in step with
# core.infer_inbox_source_type in the service and contentFiles in the Flutter
# app - youtube.md was missing here, which scored a real YouTube capture as
# having no text at all and put it in the drop bucket.
CONTENT_FILES = (
    "caption.txt",
    "raw.txt",
    "transcript.txt",
    "youtube.md",
    "jsonld.json",
)


def read_capture(folder: Path, in_pipeline: bool = False) -> Capture:
    def text(name: str) -> str:
        path = folder / name
        return path.read_text(errors="replace") if path.is_file() else ""

    meta = text("meta.txt")
    return Capture(
        slug=folder.name,
        caption="\n".join(filter(None, (text(n) for n in CONTENT_FILES))),
        handle=meta_field(meta, "creator"),
        hashtags=meta_field(meta, "hashtags"),
        collection=meta_field(meta, "collection"),
        in_pipeline=in_pipeline,
    )


def has_food_signal(capture: Capture) -> bool:
    """Is this about food at all, regardless of whether a recipe is present?

    Only the head of the caption is searched: a long tech caption can mention
    lunch in passing, and the subject of a post is stated up front.
    """
    return bool(
        FOOD.search(capture.handle)
        or FOOD.search(capture.hashtags)
        or FOOD.search(capture.caption[:150])
    )


def score_capture(capture: Capture) -> int:
    """How much of a usable recipe this capture's text holds."""
    score = 0
    if FOOD.search(capture.hashtags):
        score += 2
    if FOOD.search(capture.handle):
        score += 2
    if SECTION.search(capture.caption):
        score += 3
    score += min(3, len(MEASURE.findall(capture.caption)))
    score += min(2, len(METHOD.findall(capture.caption)))
    # Already filed in a recipe collection is the user's own judgement, and
    # outranks anything inferred from the text.
    if "recipe" in capture.collection.lower():
        score += 4
    return score


def bucket_for(capture: Capture) -> str:
    # A capture with a draft or a promoted recipe has already been judged a
    # recipe by a human, and its folder is the audit trail behind that
    # recipe's provenance (docs/ingestion.md). Never droppable, whatever the
    # text scores.
    if capture.in_pipeline:
        return "strong"
    score = score_capture(capture)
    if score >= STRONG_SCORE:
        return "strong"
    if score >= WEAK_SCORE:
        return "weak"
    return "food-no-text" if has_food_signal(capture) else "not-food"


BUCKETS = ("strong", "weak", "food-no-text", "not-food")


def pipeline_slugs(inbox: Path) -> set[str]:
    """Slugs that already have a draft or a promoted recipe next door."""
    repo = inbox.parent
    return {p.stem for p in (repo / "recipes").glob("*.yaml")} | {
        p.stem for p in (repo / "recipes" / "_drafts").glob("*.yaml")
    }


def triage(inbox: Path = INBOX) -> list[tuple[int, str, Capture]]:
    """(score, bucket, capture) for every folder, best first. Reads only."""
    rows = []
    if not inbox.is_dir():
        return rows
    in_pipeline = pipeline_slugs(inbox)
    for folder in sorted(inbox.iterdir()):
        if not folder.is_dir():
            continue
        capture = read_capture(folder, in_pipeline=folder.name in in_pipeline)
        rows.append((score_capture(capture), bucket_for(capture), capture))
    rows.sort(key=lambda r: (-r[0], r[2].slug))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--bucket",
        choices=BUCKETS,
        help="print only this bucket's slugs, one per line, for piping",
    )
    ap.add_argument(
        "--out", type=Path, help="write one <bucket>.txt file per bucket into DIR"
    )
    ap.add_argument(
        "--top", type=int, default=20, help="how many rows to show (default 20)"
    )
    ap.add_argument("--inbox", type=Path, default=INBOX)
    args = ap.parse_args(argv)

    rows = triage(args.inbox)
    if not rows:
        print(f"no captures in {args.inbox}", file=sys.stderr)
        return 1

    if args.bucket:
        for _, bucket, capture in rows:
            if bucket == args.bucket:
                print(capture.slug)
        return 0

    counts = {b: 0 for b in BUCKETS}
    for _, bucket, _ in rows:
        counts[bucket] += 1

    print(f"inbox captures: {len(rows)}")
    for bucket in BUCKETS:
        print(f"  {bucket:13} {counts[bucket]}")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for bucket in BUCKETS:
            path = args.out / f"{bucket}.txt"
            path.write_text(
                "".join(
                    f"{score:3}  {c.slug:48}  {c.handle:26}  {c.title}\n"
                    for score, b, c in rows
                    if b == bucket
                )
            )
            print(f"wrote {path}")

    print(f"\ntop {args.top} by signal:")
    for score, bucket, capture in rows[: args.top]:
        print(f"  {score:3}  {bucket:12}  {capture.handle:26}  {capture.title}")

    remaining = len(rows) - args.top
    if remaining > 0:
        print(f"  ... and {remaining} more (--top N, or --out DIR for the full lists)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
