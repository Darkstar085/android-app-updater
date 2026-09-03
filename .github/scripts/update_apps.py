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
    """Run a command from the repository root and print it to the log."""
    print("$", " ".join(map(str, args)))
    return subprocess.run(args, cwd=ROOT, check=check, text=True, capture_output=capture)


def github_json(args: list[str]) -> dict:
    """Call the GitHub CLI API and decode the JSON response."""
    result = run("gh", "api", *args)
    return json.loads(result.stdout)


def matches(name: str, patterns: list[str], excludes: list[str]) -> bool:
    """Return whether an asset matches an allow-list and no exclusions."""
    allowed = any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
    excluded = any(fnmatch.fnmatch(name, pattern) for pattern in excludes)
    return allowed and not excluded


def select_asset(assets: list[dict], patterns: list[str], excludes: list[str]) -> dict | None:
    """Select one asset deterministically using configured pattern priority."""
    for pattern in patterns:
        candidates = sorted(
            (
                asset
                for asset in assets
                if fnmatch.fnmatch(asset.get("name", ""), pattern)
                and not any(
                    fnmatch.fnmatch(asset.get("name", ""), exclude)
                    for exclude in excludes
                )
            ),
            key=lambda asset: asset.get("name", ""),
        )
        if candidates:
            if len(candidates) > 1:
                names = ", ".join(asset.get("name", "") for asset in candidates)
                print(
                    f"⚠️ Pattern {pattern!r} matched multiple assets; "
                    f"using the first deterministic filename match: {names}"
                )
            return candidates[0]
    return None


def apk_version(path: Path) -> str:
    """Read versionName from an APK using aapt."""
    result = run("aapt", "dump", "badging", str(path), check=False)
    match = re.search(r"versionName='([^']+)'", result.stdout or "")
    return match.group(1).strip() if match else ""


def filename_version(name: str) -> str:
    """Extract a version-like value from an EXE filename."""
    match = re.search(
        r"(?:^|[-_])v?([0-9]+(?:[._-][0-9A-Za-z]+){1,6})(?:[-_][A-Za-z]+)?\.(?:exe)$",
        name,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).replace("_", ".")

    match = re.search(
        r"(?:^|[-_])([0-9]+\.[0-9]+(?:\.[0-9]+){0,3})(?:[-_]|\.)",
        name,
    )
    return match.group(1) if match else ""


def read_versions(path: Path) -> dict[str, str]:
    """Read stored app versions from a simple key/value file."""
    versions: dict[str, str] = {}
    if not path.exists():
        return versions

    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value and key != "*":
                versions[key] = value
    return versions


def clean_staging_area() -> None:
    """Remove previous staged release files without touching app downloads."""
    DOWNLOADS.mkdir(exist_ok=True)
    for path in ROOT.glob("*_v*.apk"):
        path.unlink()
    for path in ROOT.glob("*_v*.exe"):
        path.unlink()


def process_app(app: dict, old_versions: dict[str, str]) -> tuple[str, dict | tuple] | None:
    """Process one configured app and return its result."""
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
        asset = select_asset(assets, app["patterns"], app.get("exclude", []))

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
        result = run(
            "gh", "release", "download", tag, "--repo", repo,
            "--pattern", asset_name, "--dir", str(destination), "--clobber", check=False,
        )
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
            version = filename_version(source.name) or tag.lstrip("v")

        if not version:
            return "failed", (name, f"could not determine version from {source.name}")

        previous = old_versions.get(name, "")
        if previous and previous == version:
            return "skipped", (name, f"unchanged v{version}")

        extension = source.suffix.lower()
        final_path = ROOT / f"{name}_v{version}{extension}"
        if final_path.exists():
            final_path.unlink()
        shutil.move(str(source), str(final_path))

        item = {
            "name": name, "old": previous, "new": version, "file": final_path.name,
            "emoji": app["emoji"], "description": app["description"], "changelog": app["changelog"],
        }
        print(f"✅ {name}: {previous or 'new'} → {version}")
        return "updated", item
    except Exception as exc:  # noqa: BLE001 - one app must not stop the batch.
        print(f"❌ {name}: {exc}")
        return "failed", (name, str(exc))
    finally:
        print("::endgroup::")


def write_results(updated: list[dict], skipped: list[tuple], failed: list[tuple]) -> None:
    """Write machine-readable results and GitHub environment values."""
    results = {"updated": updated, "skipped": skipped, "failed": failed}
    (ROOT / ".update-results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with open(os.environ.get("GITHUB_ENV", os.devnull), "a", encoding="utf-8") as env:
        env.write(f"UPDATED_COUNT={len(updated)}\n")
        env.write(f"FAILED_COUNT={len(failed)}\n")
        env.write(f"SKIPPED_COUNT={len(skipped)}\n")
        env.write(f"HAS_UPDATES={'true' if updated else 'false'}\n")
        lines = []
        for item in updated:
            lines.append(
                f"- {item['name']}: {item['old']} → {item['new']}"
                if item["old"] else f"- {item['name']}: {item['new']} (new)"
            )
        env.write("UPDATED_LIST<<EOF\n")
        env.write("\n".join(lines) + "\nEOF\n")


def write_summary(updated: list[dict], skipped: list[tuple], failed: list[tuple]) -> None:
    """Create the GitHub Actions step summary."""
    summary = [
        "# 📦 Android App Updater", "",
        f"**Updated:** {len(updated)}  ",
        f"**Skipped:** {len(skipped)}  ",
        f"**Failed:** {len(failed)}",
    ]
    if updated:
        summary += ["", "## ✅ Updated apps", "", "| App | Previous | New | File |", "|---|---:|---:|---|"]
        summary += [
            f"| {item['emoji']} {item['name']} | {item['old'] or '—'} | {item['new']} | `{item['file']}` |"
            for item in updated
        ]
    if failed:
        summary += ["", "## ⚠️ Download failures", ""]
        summary += [f"- **{name}** — {reason}" for name, reason in failed]
    if skipped:
        summary += ["", "## ⏭️ Skipped", ""]
        summary += [f"- **{name}** — {reason}" for name, reason in skipped]

    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", ROOT / "run-summary.md"))
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")


def main() -> None:
    clean_staging_area()
    old_versions = read_versions(ROOT / "latest-apk-versions.txt")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    updated: list[dict] = []
    skipped: list[tuple] = []
    failed: list[tuple] = []

    for app in config["apps"]:
        result = process_app(app, old_versions)
        if result is None:
            continue
        status, value = result
        if status == "updated":
            updated.append(value)
        elif status == "skipped":
            skipped.append(value)
        else:
            failed.append(value)

    write_results(updated, skipped, failed)
    write_summary(updated, skipped, failed)
    if failed:
        print("::warning::Some apps could not be downloaded; the workflow will continue with successful apps.")
    print(f"Summary: {len(updated)} updated, {len(skipped)} skipped, {len(failed)} failed")


if __name__ == "__main__":
    main()
