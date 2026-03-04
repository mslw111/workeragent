"""
sqlite_store.py
Handles all database read/write operations for the briefing system.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "briefing.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            status      TEXT    DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL,
            url         TEXT    NOT NULL,
            title       TEXT,
            content     TEXT,
            fetched_at  TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id  INTEGER NOT NULL,
            run_id      INTEGER NOT NULL,
            summary     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (run_id)     REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS verifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL,
            claim       TEXT    NOT NULL,
            verdict     TEXT    NOT NULL,
            evidence    TEXT,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
    """)
    conn.commit()
    conn.close()


def create_run(topic):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO runs (topic, created_at) VALUES (?, ?)",
        (topic, datetime.utcnow().isoformat()),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def update_run_status(run_id, status):
    conn = get_connection()
    conn.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))
    conn.commit()
    conn.close()


def save_article(run_id, url, title, content):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO articles (run_id, url, title, content, fetched_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, url, title, content, datetime.utcnow().isoformat()),
    )
    article_id = cur.lastrowid
    conn.commit()
    conn.close()
    return article_id


def save_summary(article_id, run_id, summary):
    conn = get_connection()
    conn.execute(
        "INSERT INTO summaries (article_id, run_id, summary, created_at) VALUES (?, ?, ?, ?)",
        (article_id, run_id, summary, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def save_verification(run_id, claim, verdict, evidence):
    conn = get_connection()
    conn.execute(
        "INSERT INTO verifications (run_id, claim, verdict, evidence, created_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, claim, verdict, evidence, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def save_report(run_id, content):
    conn = get_connection()
    conn.execute(
        "INSERT INTO reports (run_id, content, created_at) VALUES (?, ?, ?)",
        (run_id, content, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


