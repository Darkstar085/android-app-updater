#!/usr/bin/env python3
"""Validate the central application configuration before a release run."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CONFIG_PATH = Path(__file__).with_name("apps.json")
REQUIRED_FIELDS = ("name", "repo", "patterns", "description", "emoji", "changelog")


def main() -> None:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    apps = data.get("apps", [])
    errors: list[str] = []
    names: set[str] = set()

    if not isinstance(apps, list) or not apps:
        raise SystemExit("Configuration errors:\n- apps must be a non-empty list")

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
        excludes = app.get("exclude", [])
        if not isinstance(patterns, list) or not patterns or not all(
            isinstance(pattern, str) and pattern.strip() for pattern in patterns
        ):
            errors.append(f"{name}: patterns must be a non-empty list of strings")
            continue

        if not isinstance(excludes, list) or not all(isinstance(item, str) for item in excludes):
            errors.append(f"{name}: exclude must be a list of strings")
            excludes = []

        for pattern in patterns:
            if any(fnmatch.fnmatchcase(pattern, exclude) for exclude in excludes):
                errors.append(f"{name}: pattern {pattern!r} is completely covered by an exclusion")

        changelog = app.get("changelog", "")
        parsed = urlparse(changelog)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{name}: changelog must be a valid http(s) URL")

    if errors:
        print("Configuration errors:")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)

    print(f"Validated {len(apps)} apps successfully.")


if __name__ == "__main__":
    main()
