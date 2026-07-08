# Recipe data sources — verified terms

Checked 2026-07-07 by fetching each provider's actual terms/license page (not
assumed from a listing). Re-verify before scaling up import volume or before
any public/commercial release — free tiers change terms without much notice.

## Usable for building this collection

- **TheMealDB** (`themealdb.com/api.php`) — test key `1` confirmed live.
  Terms explicitly permit "scrape, copy and modify" data from official API
  endpoints (scraping the *website* itself is prohibited). Test key is for
  development/education only — **cannot** be used in an app published to an
  app store; that requires becoming a paid supporter. Fine for this stage:
  we're building a personal recipe collection, not shipping an app. Must
  attribute TheMealDB as the data source. Check `strCreativeCommons` field
  per-meal for anything with extra CC terms.
- **TheCocktailDB** — same company/policy as TheMealDB, same test-key
  restrictions. Useful later only if we ever add drinks; not a priority now.
- **Open Food Facts** (`world.openfoodfacts.org`) — no key required, confirmed
  working. ODbL (database structure) + DbCL (contents) + CC-BY-SA (images).
  Commercial use and redistribution explicitly allowed; requires attribution
  and share-alike on derivatives. Good for ingredient/nutrition grounding,
  not really a recipe-instructions source.
- **TacoFancy API** (`github.com/evz/tacofancy-api`) — MIT licensed, no key,
  no restrictions. Small/niche (taco components), low priority but zero risk.
- **Food.com Recipes and Reviews** (Kaggle, `irkaal/foodcom-recipes-and-reviews`)
  — CC0 (public domain) per the dataset's stated Kaggle license. ~500k+
  recipes with ingredients, instructions, timing, nutrition. Best candidate
  for a one-time bulk seed rather than a live API — it's a static dataset
  download, not a queryable service. Worth spot-checking a few entries against
  the original Food.com site before trusting the CC0 claim at scale (the
  uploader, not Food.com, applied that license).

## Do NOT use for archiving/storing recipes

- **Edamam** — terms explicitly prohibit automated/programmatic collection
  and prohibit caching or archiving content beyond what's allowed for a
  single live user request. Copying data into files here would violate
  their ToS regardless of tier. Fine only for live lookup features, never
  for seeding the repo.
- **Spoonacular** — caching capped at 1 hour, and all obtained data must be
  deleted if you stop using the API. Same conclusion: not usable for a
  persistent recipe collection.

## Lower priority / not pursued

- **Recipe1M+ / RecipeNLG** — large research datasets, but RecipeNLG's terms
  restrict use to non-commercial research/education, and neither is a good
  fit for hand-curating a small personal collection (huge, image-heavy,
  scraped-without-clear-per-recipe-license).
- **OpenRecipes** (`openrecip.es`) — deliberately excludes preparation
  instructions (metadata/bookmarks only, to avoid conflict with the sites it
  scraped from), and states no clear redistribution license. Not useful here.
- **AIDataNordic Food-Recipe-MCP** (`recipes.aidatanorge.no/mcp`) — semantic
  search over 50k Food.com recipes, live MCP endpoint. Convenient, but same
  underlying-license caveat as the Kaggle Food.com dataset above; treat as
  equivalent, not additional, sourcing.
- **Spoonacular/Edamam-adjacent scrapers on Apify** (Allrecipes, Tasty, NYT
  Cooking, Epicurious, Chefkoch, etc.) — not free (pay-per-run), and scraping
  those sites likely violates their ToS. Skipped.

## Practical conclusion

For seeding `recipes/*.yaml`: pull from **TheMealDB** live (attribute it,
personal-use only until/unless we ever pay for a supporter key) and/or
one-time-import from the **Food.com CC0 Kaggle dataset** for bulk volume.
Use **Open Food Facts** only for ingredient/nutrition enrichment, not full
recipes. Do not build any import path against Edamam or Spoonacular.
