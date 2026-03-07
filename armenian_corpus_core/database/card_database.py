"""Local SQLite database for flashcard data and spaced-repetition reviews.

Migrated from lousardzag/02-src/lousardzag/database.py.

Schema tables:
  anki_cards       — imported Anki notes (word, translation, pos, deck)
  card_enrichment  — computed data (frequency, syllables, morphology, level)
  sentences        — example sentences linked to cards
  users            — user records with A/B group assignment
  card_reviews     — per-user review events for scheduling analytics
  vocabulary       — offline vocabulary cache synced from Anki
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ─── DDL ──────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS anki_cards (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    anki_note_id     INTEGER UNIQUE NOT NULL,
    word             TEXT    NOT NULL,
    translation      TEXT    NOT NULL DEFAULT '',
    pos              TEXT    NOT NULL DEFAULT '',
    deck_name        TEXT    NOT NULL DEFAULT '',
    sub_deck_name    TEXT    NOT NULL DEFAULT '',
    metadata_json    TEXT    NOT NULL DEFAULT '{}',
    created_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS card_enrichment (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          INTEGER UNIQUE NOT NULL REFERENCES anki_cards(id) ON DELETE CASCADE,
    declension_class TEXT    NOT NULL DEFAULT '',
    verb_class       TEXT    NOT NULL DEFAULT '',
    frequency_rank   INTEGER NOT NULL DEFAULT 9999,
    syllable_count   INTEGER NOT NULL DEFAULT 0,
    level            INTEGER NOT NULL DEFAULT 1,
    batch_index      INTEGER NOT NULL DEFAULT 0,
    template_version TEXT    NOT NULL DEFAULT 'v1',
    morphology_json  TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sentences (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          INTEGER NOT NULL REFERENCES anki_cards(id) ON DELETE CASCADE,
    form_label       TEXT    NOT NULL DEFAULT '',
    armenian_text    TEXT    NOT NULL DEFAULT '',
    english_text     TEXT    NOT NULL DEFAULT '',
    grammar_type     TEXT    NOT NULL DEFAULT '',
    vocabulary_used  TEXT    NOT NULL DEFAULT '[]',
    created_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL DEFAULT 'default',
    ab_group   TEXT    NOT NULL DEFAULT 'control',
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS card_reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_id           INTEGER NOT NULL REFERENCES anki_cards(id) ON DELETE CASCADE,
    reviewed_at       TEXT    NOT NULL,
    rating            INTEGER NOT NULL DEFAULT 0,
    response_time_ms  INTEGER NOT NULL DEFAULT 0,
    algorithm_version TEXT    NOT NULL DEFAULT 'v1',
    ease_factor       REAL    NOT NULL DEFAULT 2.5,
    interval_days     REAL    NOT NULL DEFAULT 1.0,
    next_due_at       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma            TEXT    NOT NULL UNIQUE,
    translation      TEXT    NOT NULL DEFAULT '',
    pos              TEXT    NOT NULL DEFAULT '',
    pronunciation    TEXT    NOT NULL DEFAULT '',
    declension_class TEXT    NOT NULL DEFAULT '',
    verb_class       TEXT    NOT NULL DEFAULT '',
    frequency_rank   INTEGER NOT NULL DEFAULT 9999,
    syllable_count   INTEGER NOT NULL DEFAULT 0,
    anki_note_id     INTEGER,
    source_deck      TEXT    NOT NULL DEFAULT '',
    synced_at        TEXT    NOT NULL,
    UNIQUE (lemma, source_deck)
);

CREATE INDEX IF NOT EXISTS idx_anki_cards_note_id   ON anki_cards(anki_note_id);
CREATE INDEX IF NOT EXISTS idx_anki_cards_word      ON anki_cards(word);
CREATE INDEX IF NOT EXISTS idx_anki_cards_deck      ON anki_cards(deck_name, sub_deck_name);
CREATE INDEX IF NOT EXISTS idx_card_enrichment_card ON card_enrichment(card_id);
CREATE INDEX IF NOT EXISTS idx_sentences_card       ON sentences(card_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_card    ON card_reviews(user_id, card_id);
CREATE INDEX IF NOT EXISTS idx_reviews_due          ON card_reviews(user_id, next_due_at);
CREATE INDEX IF NOT EXISTS idx_vocabulary_lemma     ON vocabulary(lemma);
CREATE INDEX IF NOT EXISTS idx_vocabulary_pos       ON vocabulary(pos);
CREATE INDEX IF NOT EXISTS idx_vocabulary_deck      ON vocabulary(source_deck);
"""


# ─── Database class ───────────────────────────────────────────────────────────


class CardDatabase:
    """Manages the local SQLite database for Armenian card data.

    Usage::

        db = CardDatabase()                       # uses cwd/data/armenian_cards.db
        db = CardDatabase("/path/to/my.db")       # custom path
    """

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = Path.cwd() / "data" / "armenian_cards.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ─── Internal ─────────────────────────────────────────────────

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
        self._apply_schema_migrations()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _apply_schema_migrations(self):
        """Apply any schema migrations needed for older DBs."""
        with self._connect() as conn:
            cursor = conn.execute("PRAGMA table_info(anki_cards)")
            columns = {row[1] for row in cursor.fetchall()}
            if "deck_name" not in columns:
                conn.execute("ALTER TABLE anki_cards ADD COLUMN deck_name TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE anki_cards ADD COLUMN sub_deck_name TEXT NOT NULL DEFAULT ''")

    # ─── Card CRUD ────────────────────────────────────────────────

    def upsert_card(
        self,
        word: str,
        translation: str = "",
        pos: str = "",
        card_type: str = "",
        metadata: dict | None = None,
        anki_note_id: int | None = None,
        declension_class: str = "",
        verb_class: str = "",
        frequency_rank: int = 9999,
        syllable_count: int = 0,
        level: int = 1,
        batch_index: int = 0,
        template_version: str = "v1",
        morphology: dict | None = None,
        deck_name: str = "",
        sub_deck_name: str = "",
    ) -> int:
        """Insert or update a card. Returns the card id."""
        now = _now_iso()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        morph_json = json.dumps(morphology or {}, ensure_ascii=False)

        with self._connect() as conn:
            if anki_note_id is not None:
                conn.execute(
                    """
                    INSERT INTO anki_cards
                        (anki_note_id, word, translation, pos, deck_name, sub_deck_name,
                         metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(anki_note_id) DO UPDATE SET
                        word          = excluded.word,
                        translation   = excluded.translation,
                        pos           = excluded.pos,
                        deck_name     = excluded.deck_name,
                        sub_deck_name = excluded.sub_deck_name,
                        metadata_json = excluded.metadata_json
                    """,
                    (anki_note_id, word, translation, pos, deck_name, sub_deck_name, meta_json, now),
                )
                row = conn.execute(
                    "SELECT id FROM anki_cards WHERE anki_note_id = ?", (anki_note_id,)
                ).fetchone()
            else:
                cur = conn.execute(
                    """
                    INSERT INTO anki_cards
                        (anki_note_id, word, translation, pos, deck_name, sub_deck_name,
                         metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (0, word, translation, pos, deck_name, sub_deck_name, meta_json, now),
                )
                row = {"id": cur.lastrowid}

            card_id = row["id"] if isinstance(row, sqlite3.Row) else row["id"]

            conn.execute(
                """
                INSERT INTO card_enrichment
                    (card_id, declension_class, verb_class, frequency_rank,
                     syllable_count, level, batch_index, template_version, morphology_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    declension_class = excluded.declension_class,
                    verb_class       = excluded.verb_class,
                    frequency_rank   = excluded.frequency_rank,
                    syllable_count   = excluded.syllable_count,
                    level            = excluded.level,
                    batch_index      = excluded.batch_index,
                    template_version = excluded.template_version,
                    morphology_json  = excluded.morphology_json
                """,
                (card_id, declension_class, verb_class, frequency_rank,
                 syllable_count, level, batch_index, template_version, morph_json),
            )

        if card_id is None:
            raise ValueError("insert/select did not return a card id")
        return int(card_id)

    def get_card(self, card_id: int) -> Optional[dict]:
        """Return a card row by id, or None."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    ac.id, ac.anki_note_id, ac.word, ac.translation, ac.pos,
                    ac.deck_name, ac.sub_deck_name, ac.metadata_json, ac.created_at,
                    ce.declension_class, ce.verb_class, ce.frequency_rank,
                    ce.syllable_count, ce.level, ce.batch_index,
                    ce.template_version, ce.morphology_json
                FROM anki_cards ac
                LEFT JOIN card_enrichment ce ON ce.card_id = ac.id
                WHERE ac.id = ?
                """,
                (card_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
        result["morphology"] = json.loads(result.pop("morphology_json", "{}"))
        return result

    def get_card_by_word(self, word: str) -> Optional[dict]:
        """Return a card row by word (first match)."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    ac.id, ac.anki_note_id, ac.word, ac.translation, ac.pos,
                    ac.deck_name, ac.sub_deck_name, ac.metadata_json, ac.created_at,
                    ce.declension_class, ce.verb_class, ce.frequency_rank,
                    ce.syllable_count, ce.level, ce.batch_index,
                    ce.template_version, ce.morphology_json
                FROM anki_cards ac
                LEFT JOIN card_enrichment ce ON ce.card_id = ac.id
                WHERE ac.word = ?
                LIMIT 1
                """,
                (word,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
        result["morphology"] = json.loads(result.pop("morphology_json", "{}"))
        return result

    def list_cards(
        self,
        pos: str = "",
        level: int | None = None,
    ) -> list[dict]:
        """Return cards, optionally filtered by pos or level."""
        clauses: list[str] = []
        params: list = []
        if pos:
            clauses.append("ac.pos = ?")
            params.append(pos)
        if level is not None:
            clauses.append("ce.level = ?")
            params.append(level)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    ac.id, ac.anki_note_id, ac.word, ac.translation, ac.pos,
                    ac.deck_name, ac.sub_deck_name, ac.metadata_json, ac.created_at,
                    ce.declension_class, ce.verb_class, ce.frequency_rank,
                    ce.syllable_count, ce.level, ce.batch_index,
                    ce.template_version, ce.morphology_json
                FROM anki_cards ac
                LEFT JOIN card_enrichment ce ON ce.card_id = ac.id
                {where}
                ORDER BY ce.level, ce.batch_index, ce.frequency_rank
                """,
                params,
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            d["morphology"] = json.loads(d.pop("morphology_json", "{}"))
            results.append(d)
        return results

    # ─── Sentences ────────────────────────────────────────────────

    def add_sentence(
        self,
        card_id: int,
        form_label: str,
        armenian_text: str,
        english_text: str,
        grammar_type: str = "",
        vocabulary_used: list[str] | None = None,
    ) -> int:
        """Insert a sentence row and return its id."""
        now = _now_iso()
        vocab_json = json.dumps(vocabulary_used or [], ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sentences
                    (card_id, form_label, armenian_text, english_text, grammar_type, vocabulary_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (card_id, form_label, armenian_text, english_text, grammar_type, vocab_json, now),
            )
        rid = cur.lastrowid
        if rid is None:
            raise ValueError("SQLite insert did not return row id")
        return rid

    def get_sentences(self, card_id: int) -> list[dict]:
        """Return all sentences for a card."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sentences WHERE card_id = ? ORDER BY id",
                (card_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ─── Users ────────────────────────────────────────────────────

    def get_or_create_user(self, name: str = "default", ab_group: str = "control") -> int:
        """Return the id of the named user, creating them if necessary."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO users (name, ab_group, created_at) VALUES (?, ?, ?)",
                (name, ab_group, _now_iso()),
            )
        logger.debug("Created user id=%d name=%r ab_group=%r", cur.lastrowid, name, ab_group)
        rid = cur.lastrowid
        if rid is None:
            raise ValueError("SQLite insert did not return row id")
        return rid

    def list_users(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    # ─── Card Reviews ─────────────────────────────────────────────

    def record_review(
        self,
        user_id: int,
        card_id: int,
        rating: int,
        response_time_ms: int = 0,
        algorithm_version: str = "v1",
        ease_factor: float = 2.5,
        interval_days: float = 1.0,
        next_due_at: str = "",
    ) -> int:
        """Insert a review event and return its id."""
        if not next_due_at:
            next_due_at = _now_iso()
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO card_reviews
                    (user_id, card_id, reviewed_at, rating, response_time_ms,
                     algorithm_version, ease_factor, interval_days, next_due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, card_id, now, rating, response_time_ms,
                 algorithm_version, ease_factor, interval_days, next_due_at),
            )
        logger.debug("Recorded review id=%d user=%d card=%d rating=%d",
                      cur.lastrowid, user_id, card_id, rating)
        rid = cur.lastrowid
        if rid is None:
            raise ValueError("SQLite insert did not return row id")
        return rid

    def _latest_review(
        self,
        user_id: int,
        card_id: int,
        algorithm_version: str = "",
    ) -> Optional[dict]:
        """Return the most recent review for a user+card."""
        clauses = ["user_id = ?", "card_id = ?"]
        params: list = [user_id, card_id]
        if algorithm_version:
            clauses.append("algorithm_version = ?")
            params.append(algorithm_version)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM card_reviews WHERE {where} ORDER BY reviewed_at DESC LIMIT 1",
                params,
            ).fetchone()
        return dict(row) if row else None

    def get_reviews(
        self,
        user_id: int | None = None,
        card_id: int | None = None,
        algorithm_version: str = "",
    ) -> list[dict]:
        """Return review rows, optionally filtered."""
        clauses: list[str] = []
        params: list = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if card_id is not None:
            clauses.append("card_id = ?")
            params.append(card_id)
        if algorithm_version:
            clauses.append("algorithm_version = ?")
            params.append(algorithm_version)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM card_reviews {where} ORDER BY reviewed_at",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def due_cards(self, user_id: int, as_of: str = "") -> list[dict]:
        """Return card rows that are due for review by a user."""
        as_of = as_of or _now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ac.id, ac.anki_note_id, ac.word, ac.translation, ac.pos,
                    ac.deck_name, ac.sub_deck_name, ac.metadata_json, ac.created_at,
                    ce.declension_class, ce.verb_class, ce.frequency_rank,
                    ce.syllable_count, ce.level, ce.batch_index,
                    ce.template_version, ce.morphology_json
                FROM anki_cards ac
                LEFT JOIN card_enrichment ce ON ce.card_id = ac.id
                JOIN (
                    SELECT card_id, MAX(reviewed_at) AS last_reviewed, next_due_at
                    FROM card_reviews
                    WHERE user_id = ?
                    GROUP BY card_id
                ) r ON r.card_id = ac.id
                WHERE r.next_due_at <= ?
                ORDER BY r.next_due_at
                """,
                (user_id, as_of),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            d["morphology"] = json.loads(d.pop("morphology_json", "{}"))
            results.append(d)
        return results

    # ─── Reporting ────────────────────────────────────────────────

    def review_stats(self, user_id: int | None = None) -> dict:
        """Return aggregate review statistics for A/B reporting."""
        params: list = []
        user_filter = ""
        if user_id is not None:
            user_filter = "WHERE user_id = ?"
            params.append(user_id)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    algorithm_version,
                    COUNT(*)                           AS total_reviews,
                    ROUND(AVG(rating), 3)              AS avg_rating,
                    ROUND(AVG(response_time_ms), 1)    AS avg_response_ms,
                    SUM(CASE WHEN rating >= 3 THEN 1 ELSE 0 END) AS correct_count,
                    COUNT(DISTINCT user_id)            AS unique_users,
                    COUNT(DISTINCT card_id)            AS unique_cards
                FROM card_reviews
                {user_filter}
                GROUP BY algorithm_version
                ORDER BY algorithm_version
                """,
                params,
            ).fetchall()
        stats: list[dict] = []
        for row in rows:
            d = dict(row)
            total = d["total_reviews"] or 1
            d["accuracy_pct"] = round(100 * d["correct_count"] / total, 1)
            stats.append(d)
        return {"by_algorithm": stats}

    # ─── Vocabulary Cache ─────────────────────────────────────────

    def get_vocabulary_from_cache(self, source_deck: str | None = None) -> list[dict]:
        """Retrieve vocabulary entries from the local cache."""
        with self._connect() as conn:
            if source_deck:
                rows = conn.execute(
                    """
                    SELECT lemma, translation, pos, pronunciation,
                           declension_class, verb_class, frequency_rank, syllable_count,
                           source_deck, synced_at
                    FROM vocabulary WHERE source_deck = ? ORDER BY lemma
                    """,
                    (source_deck,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT lemma, translation, pos, pronunciation,
                           declension_class, verb_class, frequency_rank, syllable_count,
                           source_deck, synced_at
                    FROM vocabulary ORDER BY source_deck, lemma
                    """,
                ).fetchall()
        return [dict(row) for row in rows]

    def upsert_vocabulary(
        self,
        lemma: str,
        translation: str = "",
        pos: str = "",
        pronunciation: str = "",
        declension_class: str = "",
        verb_class: str = "",
        frequency_rank: int = 9999,
        syllable_count: int = 0,
        source_deck: str = "",
    ) -> None:
        """Insert or update a vocabulary entry."""
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO vocabulary
                    (lemma, translation, pos, pronunciation,
                     declension_class, verb_class, frequency_rank, syllable_count,
                     source_deck, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lemma, source_deck) DO UPDATE SET
                    translation      = excluded.translation,
                    pos              = excluded.pos,
                    pronunciation    = excluded.pronunciation,
                    declension_class = excluded.declension_class,
                    verb_class       = excluded.verb_class,
                    frequency_rank   = excluded.frequency_rank,
                    syllable_count   = excluded.syllable_count,
                    synced_at        = excluded.synced_at
                """,
                (lemma, translation, pos, pronunciation,
                 declension_class, verb_class, frequency_rank, syllable_count,
                 source_deck, now),
            )

    def update_vocabulary_frequency_ranks(
        self,
        rank_by_lemma: dict[str, int],
        source_deck: str | None = None,
    ) -> dict:
        """Bulk-update vocabulary frequency_rank from a lemma->rank mapping."""
        with self._connect() as conn:
            if source_deck:
                rows = conn.execute(
                    "SELECT lemma, source_deck, frequency_rank FROM vocabulary WHERE source_deck = ?",
                    (source_deck,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT lemma, source_deck, frequency_rank FROM vocabulary"
                ).fetchall()

            total_vocab = len(rows)
            mapped = 0
            updated = 0

            for row in rows:
                lemma = row["lemma"]
                if lemma not in rank_by_lemma:
                    continue
                new_rank = int(rank_by_lemma[lemma])
                mapped += 1
                if row["frequency_rank"] != new_rank:
                    conn.execute(
                        "UPDATE vocabulary SET frequency_rank = ? WHERE lemma = ? AND source_deck = ?",
                        (new_rank, lemma, row["source_deck"]),
                    )
                    updated += 1

        return {
            "total_vocab": total_vocab,
            "mapped": mapped,
            "updated": updated,
            "unmapped": total_vocab - mapped,
        }

    def has_vocabulary_cache(self, source_deck: str | None = None) -> bool:
        """Check if vocabulary cache is populated."""
        with self._connect() as conn:
            if source_deck:
                count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM vocabulary WHERE source_deck = ?",
                    (source_deck,),
                ).fetchone()
            else:
                count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM vocabulary"
                ).fetchone()
        return count is not None and count["cnt"] > 0
