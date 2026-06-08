"""
SQLite geçmiş kaydı — thread-safe, thumbnail desteği.
"""

from __future__ import annotations

import base64
import io
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from PIL import Image

import os

_DB_ENV = os.getenv("DATABASE_URL", "")
DB_PATH = Path(_DB_ENV) if _DB_ENV else Path(__file__).parent.parent / "iqa_history.db"
_lock   = threading.Lock()

_THUMB_MAX = (180, 135)   # px


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        # Write-Ahead Logging: concurrent reads while writing
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                profile     TEXT    NOT NULL DEFAULT 'none',
                overall     REAL,
                verdict     TEXT,
                thumbnail   TEXT,
                result_json TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # thumbnail sütunu yoksa ekle (mevcut DB'lere migration)
        try:
            conn.execute("ALTER TABLE analyses ADD COLUMN thumbnail TEXT")
        except sqlite3.OperationalError:
            pass   # sütun zaten var
        # Sorgu hızlandırma için index (yoksa oluştur)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_profile ON analyses(profile)"
        )
        conn.commit()


def make_thumbnail(pil_img: Image.Image) -> str:
    """Küçük JPEG thumbnail → base64 data-URI."""
    thumb = pil_img.copy()
    thumb.thumbnail(_THUMB_MAX, Image.LANCZOS)
    buf = io.BytesIO()
    thumb.convert("RGB").save(buf, format="JPEG", quality=55, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def save_analysis(result: dict[str, Any], pil_img: Image.Image | None = None) -> int:
    thumb = ""
    if pil_img is not None:
        try:
            thumb = make_thumbnail(pil_img)
        except Exception:
            pass

    # Histogram: 256 bin → 64 bin örnekleme (DB boyutu ~4× küçülür, grafik hâlâ doğru)
    slim = dict(result)
    hist_orig = result.get("histogram", {})
    if hist_orig:
        def _downsample(bins256: list, target: int = 64) -> list:
            step = len(bins256) // target
            return [sum(bins256[i*step:(i+1)*step]) for i in range(target)]

        slim["histogram"] = {
            **{k: v for k, v in hist_orig.items() if k not in ("hist_r", "hist_g", "hist_b")},
            "hist_r": _downsample(hist_orig.get("hist_r", [])),
            "hist_g": _downsample(hist_orig.get("hist_g", [])),
            "hist_b": _downsample(hist_orig.get("hist_b", [])),
        }

    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO analyses (name, profile, overall, verdict, thumbnail, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result.get("name", ""),
                result.get("profile", "none"),
                result.get("overall"),
                result.get("verdict", ""),
                thumb,
                json.dumps(slim, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_history(limit: int = 30) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, profile, overall, verdict, thumbnail, created_at
            FROM analyses ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id":         row["id"],
            "name":       row["name"],
            "profile":    row["profile"],
            "overall":    row["overall"],
            "verdict":    (row["verdict"] or "")[:220],
            "thumbnail":  row["thumbnail"] or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_analysis(analysis_id: int) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT result_json, thumbnail FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["result_json"])
    data["thumbnail"] = row["thumbnail"] or ""
    return data


def delete_analysis(analysis_id: int) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        conn.commit()
        return cur.rowcount > 0
