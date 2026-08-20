#!/usr/bin/env python3
"""Validate the central application configuration before a release run."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("apps.json")
REQUIRED_FIELDS = ("name", "repo", "patterns", "description", "emoji", "changelog")


def main() -> None:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    apps = data.get("apps", [])

    errors: list[str] = []
    names: set[str] = set()

    for index, app in enumerate(apps, start=1):
        name = app.get("name", "")

        for field in REQUIRED_FIELDS:
            if not app.get(field):
                errors.append(f"#{index}: missing {field}")

        if name in names:
            errors.append(f"duplicate app name: {name}")
        names.add(name)

        repo = app.get("repo", "")
        if not re.fullmatch(r"[^/]+/[^/]+", repo):
            errors.append(f"{name}: invalid repo {repo}")

        patterns = app.get("patterns")
        if not isinstance(patterns, list) or not patterns:
            errors.append(f"{name}: patterns must be a non-empty list")

    if errors:
        print("Configuration errors:")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)

    print(f"Validated {len(apps)} apps successfully.")


if __name__ == "__main__":
    main()
