import os
import random
import string
from dataclasses import dataclass
from typing import Optional
import psycopg2
import psycopg2.extras


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
    def __init__(self):
        self._url = os.getenv("DATABASE_URL", "")
        self._init_db()

    def _connect(self):
        if self._url:
            return psycopg2.connect(self._url, sslmode="require")
        return psycopg2.connect(
            dbname="politician_cards",
            user="postgres",
            password="postgres",
            host="localhost",
        )

    def _init_db(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        catch_count INTEGER DEFAULT 0,
                        total_power INTEGER DEFAULT 0,
                        joined_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cards (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id),
                        politician_id TEXT NOT NULL,
                        tag TEXT NOT NULL DEFAULT 'XXX',
                        variant TEXT NOT NULL DEFAULT '',
                        power INTEGER NOT NULL DEFAULT 50,
                        influence INTEGER NOT NULL DEFAULT 70,
                        charisma INTEGER NOT NULL DEFAULT 70,
                        stamina INTEGER NOT NULL DEFAULT 80,
                        caught_at TIMESTAMP DEFAULT NOW(),
                        is_favorite BOOLEAN DEFAULT FALSE
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_politician ON cards(politician_id)")
            conn.commit()

    def _ensure_user(self, user_id: int):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (user_id,)
                )
            conn.commit()

    @staticmethod
    def _generate_tag() -> str:
        rare = ["KREMLIN", "WHITE", "CONGRESS", "SENATE", "BUNKER"]
        if random.random() < 0.04:
            return random.choice(rare)
        return "".join(random.choices(string.ascii_uppercase, k=5))

    def add_card(self, user_id: int, politician_id: str, power: int, variant: str = "",
                 influence: int = 70, charisma: int = 70, stamina: int = 80) -> tuple[int, str]:
        self._ensure_user(user_id)
        tag = self._generate_tag()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cards (user_id, politician_id, tag, variant, power, influence, charisma, stamina) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (user_id, politician_id, tag, variant, power, influence, charisma, stamina)
                )
                row_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE users SET catch_count = catch_count + 1, total_power = total_power + %s WHERE user_id = %s",
                    (power, user_id)
                )
            conn.commit()
            return row_id, tag

    def get_cards(self, user_id: int) -> list[Card]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, user_id, politician_id, tag, variant, power, influence, charisma, stamina, caught_at, is_favorite "
                    "FROM cards WHERE user_id = %s ORDER BY is_favorite DESC, caught_at DESC",
                    (user_id,)
                )
                rows = cur.fetchall()
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
                    caught_at=r["caught_at"].strftime("%Y-%m-%d %H:%M:%S") if r["caught_at"] else "",
                    is_favorite=bool(r["is_favorite"])
                ) for r in rows]

    def get_card_count(self, user_id: int, politician_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM cards WHERE user_id = %s AND politician_id = %s",
                    (user_id, politician_id)
                )
                return cur.fetchone()[0]

    def toggle_favorite(self, card_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_favorite FROM cards WHERE id = %s AND user_id = %s",
                    (card_id, user_id)
                )
                row = cur.fetchone()
                if not row:
                    return False
                new_val = not row[0]
                cur.execute(
                    "UPDATE cards SET is_favorite = %s WHERE id = %s",
                    (new_val, card_id)
                )
            conn.commit()
            return new_val

    def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM users WHERE user_id = %s",
                    (user_id,)
                )
                user = cur.fetchone()
                if not user:
                    return None
                cur.execute(
                    "SELECT COUNT(DISTINCT politician_id) as cnt FROM cards WHERE user_id = %s",
                    (user_id,)
                )
                unique = cur.fetchone()["cnt"]
                return UserStats(
                    user_id=user["user_id"],
                    catch_count=user["catch_count"],
                    total_power=user["total_power"],
                    unique_caught=unique
                )

    def get_global_stats(self) -> dict:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM cards")
                total_caught = cur.fetchone()["cnt"]
                cur.execute("SELECT COUNT(*) as cnt FROM users")
                total_users = cur.fetchone()["cnt"]
                cur.execute(
                    "SELECT user_id, catch_count, total_power FROM users ORDER BY total_power DESC LIMIT 10"
                )
                top_users = cur.fetchall()
                return {
                    "total_caught": total_caught,
                    "total_users": total_users,
                    "top_users": [dict(r) for r in top_users]
                }

    def trade_card(self, card_id: int, from_user: int, to_user: int) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM cards WHERE id = %s AND user_id = %s",
                    (card_id, from_user)
                )
                if not cur.fetchone():
                    return False
                self._ensure_user(to_user)
                cur.execute("UPDATE cards SET user_id = %s WHERE id = %s", (to_user, card_id))
            conn.commit()
            return True

    def remove_card(self, card_id: int, user_id: int, card_power: int = 0) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM cards WHERE id = %s AND user_id = %s",
                    (card_id, user_id)
                )
                if not cur.fetchone():
                    return False
                cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
                if card_power > 0:
                    cur.execute(
                        "UPDATE users SET total_power = total_power - %s WHERE user_id = %s",
                        (card_power, user_id)
                    )
            conn.commit()
            return True
