#!/usr/bin/env bash
# Verify kitchen-hand's invariants. Run from anywhere, in any harness.
#
# Checks what has actually gone wrong here, not a generic list: attribution
# going missing from a public repo of other people's recipes, a recipe pointing
# at a capture that was deleted, and documentation drifting between files.
#
# Exits non-zero on any failure. A check that could not run reports FAIL.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
fail=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }
note() { printf '        %s\n' "$1"; }

echo "kitchen-hand doctor - $REPO"
echo
echo "documentation"
[ -f AGENTS.md ] && ok "AGENTS.md present" || bad "AGENTS.md missing"
if [ -L CLAUDE.md ] && [ "$(readlink CLAUDE.md)" = "AGENTS.md" ]; then
  ok "CLAUDE.md symlinks to AGENTS.md"
else
  bad "CLAUDE.md is not a symlink to AGENTS.md - the two will drift"
fi
[ -f NOTICE.md ] && ok "NOTICE.md present (LICENSE scope)" || bad "NOTICE.md missing"
grep -q "NOTICE.md" LICENSE 2>/dev/null \
  && ok "LICENSE points at NOTICE.md" \
  || bad "LICENSE does not scope itself - it reads as covering creator recipes"

echo
echo "attribution - this repo is public and most recipes are other people's"
python3 - > /tmp/kh-prov.$$ 2>&1 <<'PY'
import pathlib, re
bad = []
nocreator = []
missing_capture = []
files = sorted(pathlib.Path("recipes").glob("*.yaml"))
for f in files:
    t = f.read_text()
    if not re.search(r"^source:", t, re.M):
        bad.append(f.name)
        continue
    # a captured recipe must name its creator and its url
    if re.search(r"^provenance:", t, re.M):
        if not re.search(r"^\s+creator:", t, re.M) or not re.search(r"^\s+source_url:", t, re.M):
            nocreator.append(f.name)
        m = re.search(r"^\s+raw_capture_path:\s*\"?([^\"\n]+)\"?", t, re.M)
        if m and not pathlib.Path(m.group(1).strip()).exists():
            missing_capture.append(f"{f.name} -> {m.group(1).strip()}")
print(f"__COUNT__{len(files)}")
for label, items in (("NOSOURCE", bad), ("NOCREATOR", nocreator), ("NOCAPTURE", missing_capture)):
    for i in items:
        print(f"__{label}__{i}")
PY
count=$(sed -n 's/^__COUNT__//p' /tmp/kh-prov.$$)
nosrc=$(sed -n 's/^__NOSOURCE__//p' /tmp/kh-prov.$$ | tr '\n' ' ' | sed 's/ *$//')
nocre=$(sed -n 's/^__NOCREATOR__//p' /tmp/kh-prov.$$ | tr '\n' ' ' | sed 's/ *$//')
nocap=$(sed -n 's/^__NOCAPTURE__//p' /tmp/kh-prov.$$)
[ -z "$nosrc" ] && ok "all ${count:-?} recipes name a source" || bad "recipes with no source: $nosrc"
[ -z "$nocre" ] && ok "every captured recipe names its creator and URL" || bad "incomplete provenance: $nocre"
if [ -z "$nocap" ]; then ok "every raw_capture_path resolves"
else bad "provenance points at captures that are gone:"; printf '%s\n' "$nocap" | while IFS= read -r l; do [ -n "$l" ] && note "$l"; done; fi
rm -f /tmp/kh-prov.$$

echo
echo "schema validation"
if out="$(uv run tools/validate_recipes.py 2>&1)"; then
  ok "recipes/ validate ($(printf '%s' "$out" | grep -c '^ok') files)"
else
  bad "recipes/ fail validation"; printf '%s\n' "$out" | grep '^ *FAIL\|required' | head -4 | while IFS= read -r l; do note "$l"; done
fi
if [ -n "$(ls recipes/_drafts/*.yaml 2>/dev/null)" ]; then
  uv run tools/validate_recipes.py --drafts >/dev/null 2>&1 \
    && ok "recipes/_drafts/ validate" || bad "drafts fail validation"
else
  ok "no drafts pending"
fi

echo
echo "tests"
# Two suites, two environments. service/ has its own pyproject and fastapi is
# not in the root one, so they cannot be run together.
if uv run pytest -q >/tmp/kh-test.$$ 2>&1; then
  ok "root suite: $(tail -1 /tmp/kh-test.$$ | tr -s ' ')"
else
  bad "root test suite failing"; tail -3 /tmp/kh-test.$$ | while IFS= read -r l; do note "$l"; done
fi
if (cd service && uv run pytest -q) >/tmp/kh-svc.$$ 2>&1; then
  ok "service suite: $(tail -1 /tmp/kh-svc.$$ | tr -s ' ')"
else
  bad "service test suite failing"; tail -3 /tmp/kh-svc.$$ | while IFS= read -r l; do note "$l"; done
fi
rm -f /tmp/kh-test.$$ /tmp/kh-svc.$$

echo
echo "nothing secret in a public repo"
if git grep -nIE '(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{15,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY)' -- . >/dev/null 2>&1; then
  bad "token-shaped strings in tracked files"
else
  ok "no token-shaped strings"
fi
if git ls-files | grep -qE '(^|/)\.env$'; then bad ".env is tracked"; else ok ".env not tracked"; fi

echo
[ "$fail" -eq 0 ] && echo "all checks passed" || echo "$fail check(s) failed"
exit $((fail > 0))
