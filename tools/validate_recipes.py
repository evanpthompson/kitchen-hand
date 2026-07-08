#!/usr/bin/env python3
"""Validate every recipes/*.yaml file against schema/recipe-v1.schema.json."""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent


def main():
    schema = json.loads((ROOT / "schema" / "recipe-v1.schema.json").read_text())
    validator = Draft202012Validator(schema)

    target_dir = ROOT / "recipes" / "_drafts" if "--drafts" in sys.argv else ROOT / "recipes"

    ok = True
    for recipe_path in sorted(target_dir.glob("*.yaml")):
        data = yaml.safe_load(recipe_path.read_text())
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            ok = False
            print(f"FAIL {recipe_path.name}")
            for e in errors:
                loc = "/".join(str(p) for p in e.path)
                print(f"  {loc}: {e.message}")
        elif data.get("id") != recipe_path.stem:
            ok = False
            print(f"FAIL {recipe_path.name}: id '{data.get('id')}' does not match filename")
        else:
            print(f"ok   {recipe_path.name}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
