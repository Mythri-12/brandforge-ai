"""SQLite storage: brand voice samples, generated posts, review state, run metrics."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("BRANDFORGE_DB", "brandforge.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples(
  id INTEGER PRIMARY KEY, brand TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY, brand TEXT, brief TEXT, platform TEXT,
  copy TEXT, original_copy TEXT, hashtags TEXT, visual_prompt TEXT,
  status TEXT DEFAULT 'draft', scheduled_for TEXT,
  edit_ratio REAL, voice_rating INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, brand TEXT, seconds REAL, n_posts INTEGER,
  mode TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""
EDITABLE = {"copy", "hashtags", "visual_prompt", "status", "scheduled_for",
            "edit_ratio", "voice_rating"}


@contextmanager
def conn(path=None):
    c = sqlite3.connect(path or DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def add_samples(brand, texts, path=None):
    with conn(path) as c:
        c.executemany("INSERT INTO samples(brand,text) VALUES(?,?)",
                      [(brand, t.strip()) for t in texts if t.strip()])


def get_samples(brand, path=None):
    with conn(path) as c:
        return [r["text"] for r in
                c.execute("SELECT text FROM samples WHERE brand=? ORDER BY id", (brand,))]


def clear_samples(brand, path=None):
    with conn(path) as c:
        c.execute("DELETE FROM samples WHERE brand=?", (brand,))


def add_posts(brand, brief, posts, path=None):
    with conn(path) as c:
        for p in posts:
            c.execute(
                "INSERT INTO posts(brand,brief,platform,copy,original_copy,hashtags,visual_prompt)"
                " VALUES(?,?,?,?,?,?,?)",
                (brand, brief, p["platform"], p["copy"], p["copy"],
                 " ".join(p["hashtags"]), p["visual_prompt"]))


def list_posts(brand, status=None, path=None):
    q, a = "SELECT * FROM posts WHERE brand=?", [brand]
    if status:
        q, a = q + " AND status=?", a + [status]
    with conn(path) as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id", a)]


def update_post(pid, path=None, **fields):
    fields = {k: v for k, v in fields.items() if k in EDITABLE}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with conn(path) as c:
        c.execute(f"UPDATE posts SET {sets} WHERE id=?", [*fields.values(), pid])


def log_run(brand, seconds, n_posts, mode, path=None):
    with conn(path) as c:
        c.execute("INSERT INTO runs(brand,seconds,n_posts,mode) VALUES(?,?,?,?)",
                  (brand, seconds, n_posts, mode))


def metrics(brand, path=None):
    """The three numbers promised in the idea deck: time-to-pack, edits per post, voice rating."""
    with conn(path) as c:
        run = c.execute("SELECT AVG(seconds) s, COUNT(*) n FROM runs WHERE brand=?", (brand,)).fetchone()
        p = c.execute(
            "SELECT COUNT(*) total,"
            " SUM(status='approved') approved, SUM(status='rejected') rejected,"
            " AVG(CASE WHEN status='approved' THEN edit_ratio END) edit_ratio,"
            " SUM(status='approved' AND edit_ratio=0) unedited,"
            " AVG(voice_rating) rating FROM posts WHERE brand=?", (brand,)).fetchone()
    return {"packs": run["n"], "avg_seconds_per_pack": run["s"],
            "posts": p["total"], "approved": p["approved"] or 0,
            "rejected": p["rejected"] or 0, "avg_edit_ratio": p["edit_ratio"],
            "approved_unedited": p["unedited"] or 0, "avg_voice_rating": p["rating"]}
