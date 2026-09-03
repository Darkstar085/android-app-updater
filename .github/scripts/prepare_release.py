#!/usr/bin/env python3
"""Generate captions, release notes, and version state for updated apps."""

from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / ".update-results.json"
CONFIG_PATH = Path(__file__).with_name("apps.json")
VERSIONS_PATH = ROOT / "latest-apk-versions.txt"
CAPTIONS_PATH = ROOT / "captions.txt"


def read_versions() -> dict[str, str]:
    if not VERSIONS_PATH.exists():
        return {}
    versions: dict[str, str] = {}
    for line in VERSIONS_PATH.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value and key != "*":
                versions[key] = value
    return versions


def configured_app_names() -> set[str]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {app["name"] for app in data.get("apps", [])}


def write_captions(updated: list[dict]) -> None:
    blocks: list[str] = []
    for item in updated:
        version = (
            f"🚀 Version: {item['old']} → {item['new']}"
            if item["old"] else f"🆕 Version: {item['new']}"
        )
        blocks.append("\n".join([
            f"📦 <b>File name</b> – {item['file']}",
            f"{item['emoji']} {item['description']}",
            version,
            "",
            f"Changelog: <a href='{item['changelog']}'>Open</a>",
            "----",
        ]))
    CAPTIONS_PATH.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def write_version_state(updated: list[dict]) -> None:
    latest = read_versions()
    configured = configured_app_names()
    for item in updated:
        latest[item["name"]] = item["new"]
    latest = {name: version for name, version in latest.items() if name in configured}
    VERSIONS_PATH.write_text(
        "".join(f"{name}: {latest[name]}\n" for name in sorted(latest)),
        encoding="utf-8",
    )


def build_release_notes(data: dict) -> str:
    notes = ["## 📦 Updated Apps", ""]
    for item in data["updated"]:
        if item["old"]:
            notes.append(f"- {item['emoji']} **{item['name']}** — {item['old']} → {item['new']}")
        else:
            notes.append(f"- {item['emoji']} **{item['name']}** — {item['new']} (new)")
    if data["failed"]:
        notes.extend(["", "## ⚠️ Skipped Downloads"])
        notes.extend(f"- **{name}** — {reason}" for name, reason in data["failed"])
    notes.extend(["", "Automated by GitHub Actions."])
    return "\n".join(notes)


def build_update_summary(updated: list[dict]) -> str:
    lines = []
    for item in updated:
        if item["old"]:
            lines.append(f"- {item['name']}: {item['old']} → {item['new']}")
        else:
            lines.append(f"- {item['name']}: {item['new']} (new)")
    return "\n".join(lines)


def write_github_environment(release_notes: str, update_summary: str) -> None:
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
        env.write(f"RELEASE_NOTES<<EOF\n{release_notes}\nEOF\n")
        env.write(f"UPDATED_LIST<<EOF\n{update_summary}\nEOF\n")
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        env.write(f"REL_NAME={now:%Y-%m-%d %H:%M} IST\n")


def main() -> None:
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    updated = data["updated"]
    write_captions(updated)
    write_version_state(updated)
    write_github_environment(build_release_notes(data), build_update_summary(updated))


if __name__ == "__main__":
    main()
