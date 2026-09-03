#!/usr/bin/env python3
"""Download, select, version, and stage all configured app releases."""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).with_name("apps.json")
DOWNLOADS = ROOT / ".downloads"


def run(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(map(str, args)))
    return subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=capture)


def github_json(args: list[str]) -> dict:
    return json.loads(run("gh", "api", *args).stdout)


def select_asset(assets: list[dict], patterns: list[str], excludes: list[str]) -> dict | None:
    """Select exactly one asset using pattern priority; reject ambiguous matches."""
    for pattern in patterns:
        candidates = sorted(
            [
                asset for asset in assets
                if fnmatch.fnmatch(asset.get("name", ""), pattern)
                and not any(fnmatch.fnmatch(asset.get("name", ""), exclude) for exclude in excludes)
            ],
            key=lambda asset: asset.get("name", ""),
        )
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            names = ", ".join(asset.get("name", "") for asset in candidates)
            raise ValueError(f"pattern {pattern!r} matched multiple assets: {names}")
    return None


def apk_version(path: Path) -> str:
    result = run("aapt", "dump", "badging", str(path), check=False)
    match = re.search(r"versionName='([^']+)'", result.stdout or "")
    return match.group(1).strip() if match else ""


def filename_version(name: str) -> str:
    """Extract a version-like value from an executable filename as a fallback."""
    match = re.search(r"(?:^|[-_])v?([0-9]+(?:\.[0-9]+){1,5})(?:[-_][A-Za-z][A-Za-z0-9.-]*)?\.exe$", name, re.I)
    return match.group(1) if match else ""


def read_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    if not path.exists():
        return versions
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            if key and value and key != "*":
                versions[key] = value
    return versions


def clean_staging_area() -> None:
    DOWNLOADS.mkdir(exist_ok=True)
    for pattern in ("*_v*.apk", "*_v*.exe"):
        for path in ROOT.glob(pattern):
            path.unlink()


def process_app(app: dict, old_versions: dict[str, str]) -> tuple[str, dict | tuple] | None:
    name = app["name"]
    repo = app["repo"]
    print(f"::group::{app['emoji']} {name} — {repo}")
    destination = DOWNLOADS / name
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    try:
        release = github_json([f"repos/{repo}/releases/latest"])
        tag = release.get("tag_name") or ""
        assets = release.get("assets") or []
        try:
            asset = select_asset(assets, app["patterns"], app.get("exclude", []))
        except ValueError as exc:
            return "failed", (name, str(exc))
        if asset is None:
            print(f"⚠️ No matching asset. Patterns: {app['patterns']}")
            print("Available APK/EXE assets:")
            for candidate in assets:
                asset_name = candidate.get("name", "")
                if asset_name.lower().endswith((".apk", ".exe")):
                    print(f" - {asset_name}")
            return "skipped", (name, "no matching release asset")
        asset_name = asset["name"]
        print(f"Selected: {asset_name} (release {tag})")
        result = run("gh", "release", "download", tag, "--repo", repo, "--pattern", asset_name, "--dir", str(destination), "--clobber", check=False)
        if result.returncode != 0:
            return "failed", (name, "download failed")
        downloaded = [path for path in destination.iterdir() if path.is_file()]
        if len(downloaded) != 1:
            return "failed", (name, f"expected 1 downloaded file, found {len(downloaded)}")
        source = downloaded[0]
        if source.suffix.lower() == ".apk":
            version = apk_version(source)
            if not version:
                return "failed", (name, f"could not read APK versionName from {source.name}")
        else:
            # Release tags are the canonical version for EXE releases. Only fall
            # back to the filename when the tag is missing or clearly unusable.
            version = tag.lstrip("v").strip() or filename_version(source.name)
        if not version:
            return "failed", (name, f"could not determine version from {source.name}")
        previous = old_versions.get(name, "")
        if previous == version and previous:
            return "skipped", (name, f"unchanged v{version}")
        final_path = ROOT / f"{name}_v{version}{source.suffix.lower()}"
        if final_path.exists():
            final_path.unlink()
        shutil.move(str(source), str(final_path))
        item = {"name": name, "old": previous, "new": version, "file": final_path.name, "emoji": app["emoji"], "description": app["description"], "changelog": app["changelog"]}
        print(f"✅ {name}: {previous or 'new'} → {version}")
        return "updated", item
    except Exception as exc:
        print(f"❌ {name}: {exc}")
        return "failed", (name, str(exc))
    finally:
        print("::endgroup::")


def write_results(updated: list[dict], skipped: list[tuple], failed: list[tuple]) -> None:
    (ROOT / ".update-results.json").write_text(json.dumps({"updated": updated, "skipped": skipped, "failed": failed}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(os.environ.get("GITHUB_ENV", os.devnull), "a", encoding="utf-8") as env:
        env.write(f"UPDATED_COUNT={len(updated)}\nFAILED_COUNT={len(failed)}\nSKIPPED_COUNT={len(skipped)}\nHAS_UPDATES={'true' if updated else 'false'}\n")
        env.write("UPDATED_LIST<<EOF\n" + "\n".join(f"- {i['name']}: {i['old']} → {i['new']}" if i['old'] else f"- {i['name']}: {i['new']} (new)" for i in updated) + "\nEOF\n")


def write_summary(updated: list[dict], skipped: list[tuple], failed: list[tuple]) -> None:
    lines = ["# 📦 Android App Updater", "", f"**Updated:** {len(updated)}  ", f"**Skipped:** {len(skipped)}  ", f"**Failed:** {len(failed)}"]
    if updated:
        lines += ["", "## ✅ Updated apps", "", "| App | Previous | New | File |", "|---|---:|---:|---|"]
        lines += [f"| {i['emoji']} {i['name']} | {i['old'] or '—'} | {i['new']} | `{i['file']}` |" for i in updated]
    if failed:
        lines += ["", "## ⚠️ Download failures", ""] + [f"- **{n}** — {r}" for n, r in failed]
    if skipped:
        lines += ["", "## ⏭️ Skipped", ""] + [f"- **{n}** — {r}" for n, r in skipped]
    Path(os.environ.get("GITHUB_STEP_SUMMARY", ROOT / "run-summary.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    clean_staging_area()
    old_versions = read_versions(ROOT / "latest-apk-versions.txt")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    updated: list[dict] = []
    skipped: list[tuple] = []
    failed: list[tuple] = []
    for app in config["apps"]:
        result = process_app(app, old_versions)
        if result:
            status, value = result
            {"updated": updated, "skipped": skipped, "failed": failed}[status].append(value)
    write_results(updated, skipped, failed)
    write_summary(updated, skipped, failed)
    if failed:
        print("::warning::Some apps could not be downloaded; the workflow will continue with successful apps.")
    print(f"Summary: {len(updated)} updated, {len(skipped)} skipped, {len(failed)} failed")


if __name__ == "__main__":
    main()
