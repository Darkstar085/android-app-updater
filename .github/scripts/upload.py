#!/usr/bin/env python3
"""Upload release assets to Telegram with retries and duplicate protection."""

from __future__ import annotations

import asyncio
import glob
import os
import re
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.sessions import StringSession

RETRIES = max(1, int(os.getenv("UPLOAD_RETRIES", "5")))
RETRY_DELAY = max(1, int(os.getenv("UPLOAD_RETRY_DELAY", "8")))
DEDUP_SCAN_LIMIT = max(0, int(os.getenv("DEDUP_SCAN_LIMIT", "500")))
MAX_CAPTION = 1024

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CHAT = int(CHAT_ID) if CHAT_ID.lstrip("-").isdigit() else CHAT_ID


def normalize(name: str) -> str:
    """Normalize a filename for caption lookup."""
    return re.sub(r"[^a-z0-9]+", "", Path(name).stem.lower())


def load_captions() -> dict[str, str]:
    """Read captions.txt and remove the redundant filename line."""
    path = Path("captions.txt")
    if not path.exists():
        return {}

    captions: dict[str, str] = {}
    blocks = re.split(
        r"\n\s*-{4,}\s*\n",
        path.read_text(encoding="utf-8"),
    )

    for block in blocks:
        match = re.search(
            r"File name</b>\s*[–-]\s*([^\n]+)",
            block,
        )
        if not match:
            continue

        filename = match.group(1).strip()
        caption = re.sub(
            r"^\s*📦\s*<b>File name</b>\s*[–-]\s*[^\n]*\n?",
            "",
            block,
            count=1,
            flags=re.MULTILINE,
        ).strip()
        captions[normalize(filename)] = caption[:MAX_CAPTION]

    return captions


def caption_for(name: str, captions: dict[str, str]) -> str:
    """Find the best caption for an uploaded filename."""
    normalized = normalize(name)

    if normalized in captions:
        return captions[normalized]

    for key, caption in captions.items():
        if normalized.startswith(key) or key.startswith(normalized):
            return caption

    return ""


def release_files() -> list[str]:
    """Return APK/EXE files downloaded from the GitHub release."""
    return sorted(glob.glob("dl/*.apk") + glob.glob("dl/*.exe"))


async def upload_file(
    client: TelegramClient,
    path: str,
    caption: str,
) -> bool:
    """Upload one file with retry and FloodWait handling."""
    name = Path(path).name

    for attempt in range(1, RETRIES + 1):
        try:
            print(f"📤 {name} ({attempt}/{RETRIES})")
            await client.send_file(
                CHAT,
                path,
                caption=caption,
                force_document=True,
                parse_mode="html",
                supports_streaming=False,
            )
            return True

        except FloodWaitError as error:
            delay = max(int(error.seconds), RETRY_DELAY)
            print(f"⏳ Telegram FloodWait: {delay}s")
            await asyncio.sleep(delay)

        except (RPCError, OSError, TimeoutError) as error:
            print(f"⚠️ {error}")
            if attempt < RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)

    return False


async def main() -> None:
    files = release_files()
    if not files:
        raise SystemExit("No files to upload.")

    captions = load_captions()

    async with TelegramClient(
        StringSession(SESSION),
        API_ID,
        API_HASH,
    ) as client:
        existing: set[str] = set()

        if DEDUP_SCAN_LIMIT:
            async for message in client.iter_messages(
                CHAT,
                limit=DEDUP_SCAN_LIMIT,
            ):
                if message.file and message.file.name:
                    existing.add(message.file.name)

        uploaded = 0
        skipped = 0
        failed: list[str] = []

        for path in files:
            name = Path(path).name

            if name in existing:
                print(f"⏭️ Already posted: {name}")
                skipped += 1
                continue

            caption = caption_for(name, captions)
            if await upload_file(client, path, caption):
                existing.add(name)
                uploaded += 1
            else:
                failed.append(name)

    print(
        "\nTelegram summary: "
        f"{uploaded} uploaded, {skipped} skipped, {len(failed)} failed."
    )

    if failed:
        print("Failed:")
        print("\n".join(f" - {name}" for name in failed))
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
