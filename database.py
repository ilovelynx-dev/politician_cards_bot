import random
import sqlite3
import string
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Card:
    id: int
    user_id: int
    politician_id: str
    tag: str
    variant: str
    caught_at: str
    is_favorite: bool
    power: int
    influence: int
    charisma: int
    stamina: int


@dataclass
class UserStats:
    user_id: int
    catch_count: int
    total_power: int
    unique_caught: int


class Database:
    def __init__(self, path: str = "politician_cards.db"):
        self._path = path
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    catch_count INTEGER DEFAULT 0,
                    total_power INTEGER DEFAULT 0,
                    joined_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    politician_id TEXT NOT NULL,
                    tag TEXT NOT NULL DEFAULT 'XXX',
                    variant TEXT NOT NULL DEFAULT '',
                    power INTEGER NOT NULL DEFAULT 50,
                    influence INTEGER NOT NULL DEFAULT 70,
                    charisma INTEGER NOT NULL DEFAULT 70,
                    stamina INTEGER NOT NULL DEFAULT 80,
                    caught_at TEXT DEFAULT (datetime('now')),
                    is_favorite INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);
                CREATE INDEX IF NOT EXISTS idx_cards_politician ON cards(politician_id);
            """)
            for col in ("influence", "charisma", "stamina"):
                try:
                    conn.execute(f"ALTER TABLE cards ADD COLUMN {col} INTEGER NOT NULL DEFAULT 70")
                except Exception:
                    pass
            try:
                conn.execute("ALTER TABLE cards ADD COLUMN power INTEGER NOT NULL DEFAULT 50")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE cards ADD COLUMN variant TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass
            old = conn.execute("SELECT id FROM cards WHERE tag = 'XXX'").fetchall()
            for row in old:
                conn.execute("UPDATE cards SET tag = ? WHERE id = ?", (self._generate_tag(), row["id"]))

    def _ensure_user(self, user_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                    (user_id,)
                )

    @staticmethod
    def _generate_tag() -> str:
        rare = ["KGB", "FSB", "CIA", "MI6", "BNE"]
        if random.random() < 0.04:
            return random.choice(rare)
        return "".join(random.choices(string.ascii_uppercase, k=3))

    def add_card(self, user_id: int, politician_id: str, power: int, variant: str = "",
                 influence: int = 70, charisma: int = 70, stamina: int = 80) -> tuple[int, str]:
        self._ensure_user(user_id)
        tag = self._generate_tag()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO cards (user_id, politician_id, tag, variant, power, influence, charisma, stamina) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, politician_id, tag, variant, power, influence, charisma, stamina)
                )
                row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "UPDATE users SET catch_count = catch_count + 1, total_power = total_power + ? WHERE user_id = ?",
                    (power, user_id)
                )
                return row_id, tag

    def get_cards(self, user_id: int) -> list[Card]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, user_id, politician_id, tag, variant, power, influence, charisma, stamina, caught_at, is_favorite FROM cards WHERE user_id = ? ORDER BY is_favorite DESC, caught_at DESC",
                    (user_id,)
                ).fetchall()
                return [Card(
                    id=r["id"],
                    user_id=r["user_id"],
                    politician_id=r["politician_id"],
                    tag=r["tag"],
                    variant=r["variant"],
                    power=r["power"],
                    influence=r["influence"],
                    charisma=r["charisma"],
                    stamina=r["stamina"],
                    caught_at=r["caught_at"],
                    is_favorite=bool(r["is_favorite"])
                ) for r in rows]

    def get_card_count(self, user_id: int, politician_id: str) -> int:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cards WHERE user_id = ? AND politician_id = ?",
                    (user_id, politician_id)
                ).fetchone()
                return row["cnt"] if row else 0

    def toggle_favorite(self, card_id: int, user_id: int) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT is_favorite FROM cards WHERE id = ? AND user_id = ?",
                    (card_id, user_id)
                ).fetchone()
                if not row:
                    return False
                new_val = 0 if row["is_favorite"] else 1
                conn.execute(
                    "UPDATE cards SET is_favorite = ? WHERE id = ?",
                    (new_val, card_id)
                )
                return bool(new_val)

    def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        with self._lock:
            with self._connect() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                if not user:
                    return None
                unique = conn.execute(
                    "SELECT COUNT(DISTINCT politician_id) as cnt FROM cards WHERE user_id = ?",
                    (user_id,)
                ).fetchone()["cnt"]
                return UserStats(
                    user_id=user["user_id"],
                    catch_count=user["catch_count"],
                    total_power=user["total_power"],
                    unique_caught=unique
                )

    def get_global_stats(self) -> dict:
        with self._lock:
            with self._connect() as conn:
                total_caught = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
                total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                top_users = conn.execute(
                    "SELECT user_id, catch_count, total_power FROM users ORDER BY total_power DESC LIMIT 10"
                ).fetchall()
                return {
                    "total_caught": total_caught,
                    "total_users": total_users,
                    "top_users": [dict(r) for r in top_users]
                }

    def trade_card(self, card_id: int, from_user: int, to_user: int) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, politician_id FROM cards WHERE id = ? AND user_id = ?",
                    (card_id, from_user)
                ).fetchone()
                if not row:
                    return False
                self._ensure_user(to_user)
                conn.execute("UPDATE cards SET user_id = ? WHERE id = ?", (to_user, card_id))
                return True

    def remove_card(self, card_id: int, user_id: int, card_power: int = 0) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM cards WHERE id = ? AND user_id = ?",
                    (card_id, user_id)
                ).fetchone()
                if not row:
                    return False
                conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                if card_power > 0:
                    conn.execute(
                        "UPDATE users SET total_power = total_power - ? WHERE user_id = ?",
                        (card_power, user_id)
                    )
                return True
