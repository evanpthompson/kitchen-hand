# Notice: what is licensed, and what is not

This repository contains two different kinds of material. The `LICENSE` file
grants MIT terms, and **those terms cover the first kind only.**

## MIT — Evan Thompson's work

The code and the structures around it:

- `tools/`, `service/`, `app/`, `tests/`
- `schema/` — the recipe JSON Schema
- `docs/`, `README.md`, `CONTRIBUTING.md`
- The YAML structure of every recipe file: the field layout, the phase and
  ingredient model, the machine-program fields, and the `extraction_notes`
  prose, which is written here rather than taken from a source.

## Not MIT — other people's recipes

Most of `recipes/` and effectively all of `inbox/` originates with someone
else. As of 2026-09-19 that is 40 of 43 recipes, credited to more than thirty
named creators, and 106 captures.

Every recipe names its origin. `source` is a required schema field — a recipe
without one fails `tools/validate_recipes.py` — and captured recipes carry a
`provenance` block with the creator handle, the source URL and the capture
date.

`inbox/*/caption.txt` holds creator text as written, kept so an extraction can
be checked against what the source actually said.

**Nothing here relicenses any of that.** Evan can license his own code and
cannot license someone else's writing, and the MIT grant should not be read as
attempting to. If you want to use a recipe from this collection for anything
beyond reading it, go to the `source_url` and deal with the creator.

Three recipes are not from a creator and say so in their own `source` field:
`bechamel-sauce` and `chicken-fried-rice` are classic technique, and
`kung-pao-chicken` is an original example written to exercise the schema.

## If you are a creator here and want your recipe removed

Open an issue naming the recipe, or the Instagram handle, and it comes out —
the recipe file, its inbox capture, and the git history entry. No argument, no
delay.

## Scope

This is a statement of intent about attribution, not legal advice, and not a
claim about what copyright does or does not protect in a list of ingredients.
It exists because a blanket MIT file over a directory of other people's work
reads as a claim nobody intended to make.
