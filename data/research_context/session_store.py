"""
App-level SQLite session store.

Distinct from the LangGraph SqliteSaver checkpointer — this store provides
structured, queryable access to research data across iterations so that nodes
can retrieve history by session_id (e.g. "give me all results from this
research session across every iteration").

Schema
──────
  plans    — one row per planning iteration (task lists)
  results  — one row per execution iteration (sub-agent results)
  reports  — one row per session (synthesized + final report, output path)

Thread safety
─────────────
  execute_tasks_node runs sub-agents inside a ThreadPoolExecutor. Writes
  in that context go through session_store.save_results(), so all write
  operations are protected by a threading.Lock.
  Reads (get_all_results) are lock-free because SQLite in WAL mode supports
  concurrent readers safely.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from config.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages SQLite persistence for research session data."""

    def __init__(self, db_path: str = SQLITE_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        # Single persistent connection reused for all operations.
        # check_same_thread=False is safe because every write is
        # protected by self._lock.
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables if they do not already exist."""
        with self._lock:
            self._conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS plans (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id  TEXT    NOT NULL,
                        iteration   INTEGER NOT NULL,
                        tasks_json  TEXT    NOT NULL,
                        created_at  TEXT    NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS results (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id   TEXT    NOT NULL,
                        iteration    INTEGER NOT NULL,
                        results_json TEXT    NOT NULL,
                        created_at   TEXT    NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS reports (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id          TEXT NOT NULL UNIQUE,
                        synthesized_report  TEXT,
                        final_report        TEXT,
                        output_path         TEXT,
                        created_at          TEXT NOT NULL,
                        updated_at          TEXT NOT NULL
                    );
                    """
                )
        logger.debug("SessionStore: database initialised at %s", self._db_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Public write methods ───────────────────────────────────────────────

    def save_plan(
        self,
        session_id: str,
        iteration: int,
        tasks: list[dict],
    ) -> None:
        """Persist the task list produced by plan_research_node.

        Called once per planning iteration. Multiple rows may exist for the
        same session_id across different iterations.
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO plans (session_id, iteration, tasks_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, iteration, json.dumps(tasks), self._now()),
            )
            self._conn.commit()
        logger.debug(
            "SessionStore.save_plan: session=%s iteration=%d tasks=%d",
            session_id, iteration, len(tasks),
        )

    def save_results(
        self,
        session_id: str,
        iteration: int,
        results: list[dict],
    ) -> None:
        """Persist sub-agent results from execute_tasks_node.

        Called once per execution iteration after the worker pool finishes.
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO results (session_id, iteration, results_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, iteration, json.dumps(results), self._now()),
            )
            self._conn.commit()
        logger.debug(
            "SessionStore.save_results: session=%s iteration=%d results=%d",
            session_id, iteration, len(results),
        )

    def save_synthesized_report(
        self,
        session_id: str,
        report: str,
    ) -> None:
        """Persist the pre-citation synthesized report (crash recovery).

        Uses INSERT OR REPLACE so there is always at most one report row
        per session_id.
        """
        now = self._now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO reports
                    (session_id, synthesized_report, final_report,
                     output_path, created_at, updated_at)
                VALUES (?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    synthesized_report = excluded.synthesized_report,
                    updated_at         = excluded.updated_at
                """,
                (session_id, report, now, now),
            )
            self._conn.commit()
        logger.debug(
            "SessionStore.save_synthesized_report: session=%s length=%d",
            session_id, len(report),
        )

    def save_final_output(
        self,
        session_id: str,
        final_report: str,
        output_path: str,
    ) -> None:
        """Persist the final cited report and the .docx output path.

        Upserts into the reports table so the row created by
        save_synthesized_report is updated in place.
        """
        now = self._now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO reports
                    (session_id, synthesized_report, final_report,
                     output_path, created_at, updated_at)
                VALUES (?, NULL, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    final_report = excluded.final_report,
                    output_path  = excluded.output_path,
                    updated_at   = excluded.updated_at
                """,
                (session_id, final_report, output_path, now, now),
            )
            self._conn.commit()
        logger.debug(
            "SessionStore.save_final_output: session=%s path=%s",
            session_id, output_path,
        )

    # ── Public read methods ────────────────────────────────────────────────

    def get_all_results(self, session_id: str) -> list[dict]:
        """Return all sub-agent results for this session across every iteration.

        Rows are ordered by iteration ascending so the Lead Researcher sees
        findings in chronological order. Each row's results_json is a list —
        all lists are flattened into a single list before returning.
        """
        rows = self._conn.execute(
            """
            SELECT results_json
            FROM   results
            WHERE  session_id = ?
            ORDER  BY iteration ASC
            """,
            (session_id,),
        ).fetchall()

        all_results: list[dict] = []
        for row in rows:
            try:
                batch = json.loads(row["results_json"])
                if isinstance(batch, list):
                    all_results.extend(batch)
            except json.JSONDecodeError:
                logger.warning(
                    "SessionStore.get_all_results: corrupt JSON row for session=%s",
                    session_id,
                )

        logger.debug(
            "SessionStore.get_all_results: session=%s total_results=%d",
            session_id, len(all_results),
        )
        return all_results
