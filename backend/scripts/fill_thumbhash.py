#!/usr/bin/env python3
"""
Backfill dominant-color thumbhash for photos scanned before this feature existed.

For every Photo row where thumbhash IS NULL, open the file with Pillow,
resize to 1×1, and store the dominant color as "#RRGGBB".

Run once from the backend directory:
    cd backend
    python scripts/fill_thumbhash.py

Progress is printed to stdout.  Safe to re-run; already-filled rows are skipped.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "photos.db"
BATCH_SIZE = 200


def dominant_color(file_path: str) -> str | None:
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            tiny = img.convert("RGB").resize((1, 1), Image.LANCZOS)
            r, g, b = tiny.getpixel((0, 0))
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


def run() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    rows = conn.execute(
        "SELECT id, file_path FROM photos WHERE thumbhash IS NULL AND is_deleted = 0"
    ).fetchall()

    total = len(rows)
    if total == 0:
        print("All photos already have a thumbhash — nothing to do.")
        conn.close()
        return

    print(f"Processing {total} photos …")
    filled = 0
    skipped = 0

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        updates: list[tuple[str, int]] = []

        for photo_id, file_path in batch:
            color = dominant_color(file_path)
            if color:
                updates.append((color, photo_id))
                filled += 1
            else:
                skipped += 1

        if updates:
            conn.executemany(
                "UPDATE photos SET thumbhash = ? WHERE id = ?", updates
            )
            conn.commit()

        done = min(i + BATCH_SIZE, total)
        print(f"  {done}/{total}  filled={filled}  skipped={skipped}")

    conn.close()
    print(f"\n✅  Done — {filled} filled, {skipped} skipped (file missing/corrupt)")


if __name__ == "__main__":
    run()
