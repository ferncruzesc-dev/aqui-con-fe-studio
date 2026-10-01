"""aQui con fe Studio v2 — a constellation.

A private, self-hosted writing studio built as a living archive /
creative ecosystem: Questions sit at the center, and everything
(materials, projects, journal entries, references, room pieces,
voice pieces, serial chapters, newsletter issues) links
to questions, to constellation axes, and to projects.

Single-user Flask app with SQLite storage. Run with:
    pip install -r requirements.txt
    python app.py
"""
import json
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, abort, g, redirect, render_template, request, session, url_for,
)
from jinja2 import Environment, FileSystemLoader
from markupsafe import escape, Markup
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("STUDIO_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("STUDIO_DB", os.path.join(DATA_DIR, "studio.db"))
EXPORT_DIR = os.path.join(BASE_DIR, "export", "constellation")

# ---------------------------------------------------------------- data ----

# (key, display name, tagline, description, sort order, tier)
# Tiers follow the constellation flow:
#   QUESTION → MEMORY → STUDY → CRAFT → CREACIÓN → NEW MATERIAL → NEW QUESTION
AXES = [
    ("FE", "Fe", "the ground of belief",
     "Faith as foundation — what is held true before anything is made.", 1, "study"),
    ("AQUI", "Aquí", "here, in this place",
     "Presence — the discipline of being where you are.", 2, "study"),
    ("MEMORIA", "Memoria", "what the archive keeps",
     "Memory — inheritance, remembrance, and the record.", 3, "memory"),
    ("LETRAS", "Letras", "the word, written and read",
     "Letters — literature, language, the essay, the poem.", 4, "study"),
    ("SONIDO", "Sonido", "what is heard and sung",
     "Sound — music, voice, rhythm.", 5, "craft"),
    ("ARTE", "Arte", "what the hand makes",
     "Art — the visual, the made thing.", 6, "craft"),
    ("ESTUDIO", "Estudio", "the discipline of inquiry",
     "Study — research, scholarship, the question pursued.", 7, "craft"),
    ("CREACION", "Creación", "what is born from the rest",
     "Creation — the new material, the new question.", 8, "creation"),
]

TIER_LABELS = [
    ("memory", "Memory", "what the archive keeps"),
    ("study", "Study", "the question pursued"),
    ("craft", "Craft", "the disciplines of making"),
    ("creation", "Creation", "what is born"),
]

ROOMS = [
    ("omg", "OMG! moments",
     "Original faith-based comedy, tragedy, storytelling.",
     "Bits, tragedies, and stories — for the stage and the page."),
    ("diary", "aQui con fe video diary",
     "Makeup · expression · vlog.",
     "Video diary entries — look, theme, script."),
    ("comeme", "coMe for Me",
     "Faith-based sex and gender exploration — reading / performing in lingerie video diary.",
     "Readings and performances."),
]

ROOM_PIECE_KINDS = {
    "omg": ["comedy bit", "tragedy", "story"],
    "diary": [],  # diary pieces carry theme + date instead of a kind
    "comeme": ["reading", "performance", "reflection"],
}

MATERIAL_KINDS = ["poem", "story", "essay", "note", "fragment"]
REFERENCE_KINDS = ["book", "film", "song", "scripture", "article", "other"]
JOURNAL_KINDS = [
    "field notes",
    "reading notes",
    "cultural notes",
    "reflections",
    "research notes",
    "faith",
]
VOICE_KINDS = [
    "reading",
    "conversation",
    "interview",
    "audio note",
    "live session",
    "podcast episode",
]
VOICE_STATUSES = ["idea", "draft", "recorded", "ready", "published"]
SERIAL_STATUSES = ["draft", "ready", "published"]
NEWSLETTER_STATUSES = ["draft", "ready", "sent"]
POEM_STATUSES = ["draft", "ready", "published"]
STORY_STATUSES = ["draft", "ready", "published"]
QUESTION_STATUSES = ["open", "resting", "closed"]

SEED_QUESTION = "What do we inherit that we did not choose?"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS axes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tagline TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    tier TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    why_asking TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    featured INTEGER NOT NULL DEFAULT 0,
    public INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS question_axes (
    question_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (question_id, axis_id)
);
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'note',
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS material_questions (
    material_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (material_id, question_id)
);
CREATE TABLE IF NOT EXISTS material_axes (
    material_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (material_id, axis_id)
);
CREATE TABLE IF NOT EXISTS material_projects (
    material_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    PRIMARY KEY (material_id, project_id)
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_questions (
    project_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (project_id, question_id)
);
CREATE TABLE IF NOT EXISTS project_axes (
    project_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (project_id, axis_id)
);
CREATE TABLE IF NOT EXISTS "references" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    creator TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'other',
    notes TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reference_questions (
    reference_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (reference_id, question_id)
);
CREATE TABLE IF NOT EXISTS reference_axes (
    reference_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (reference_id, axis_id)
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'field notes',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_questions (
    journal_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (journal_id, question_id)
);
CREATE TABLE IF NOT EXISTS journal_axes (
    journal_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (journal_id, axis_id)
);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    identity TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    structure_notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS room_pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_piece_questions (
    piece_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (piece_id, question_id)
);
CREATE TABLE IF NOT EXISTS room_piece_axes (
    piece_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (piece_id, axis_id)
);
CREATE TABLE IF NOT EXISTS voice_pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'reading',
    body TEXT NOT NULL DEFAULT '',
    audio_url TEXT NOT NULL DEFAULT '',
    duration TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'idea',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_piece_questions (
    voice_piece_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (voice_piece_id, question_id)
);
CREATE TABLE IF NOT EXISTS voice_piece_axes (
    voice_piece_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (voice_piece_id, axis_id)
);
CREATE TABLE IF NOT EXISTS serial_chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    publish_target TEXT NOT NULL DEFAULT '',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS serial_chapter_questions (
    chapter_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (chapter_id, question_id)
);
CREATE TABLE IF NOT EXISTS serial_chapter_axes (
    chapter_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (chapter_id, axis_id)
);
CREATE TABLE IF NOT EXISTS newsletter_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_no INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    send_target TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS newsletter_issue_questions (
    issue_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (issue_id, question_id)
);
CREATE TABLE IF NOT EXISTS newsletter_issue_axes (
    issue_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (issue_id, axis_id)
);
CREATE TABLE IF NOT EXISTS poems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    release_month TEXT NOT NULL DEFAULT '',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poem_questions (
    poem_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (poem_id, question_id)
);
CREATE TABLE IF NOT EXISTS poem_axes (
    poem_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (poem_id, axis_id)
);
CREATE TABLE IF NOT EXISTS story_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_title TEXT NOT NULL DEFAULT '',
    section_no INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    release_target TEXT NOT NULL DEFAULT '',
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS story_section_questions (
    section_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    PRIMARY KEY (section_id, question_id)
);
CREATE TABLE IF NOT EXISTS story_section_axes (
    section_id INTEGER NOT NULL,
    axis_id INTEGER NOT NULL,
    PRIMARY KEY (section_id, axis_id)
);
"""

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)


def nl2br(value):
    return Markup("<br />\n".join(escape(value or "").split("\n")))


app.jinja_env.filters["nl2br"] = nl2br


def get_secret_key():
    env_key = os.environ.get("STUDIO_SECRET_KEY")
    if env_key:
        return env_key
    os.makedirs(DATA_DIR, exist_ok=True)
    key_path = os.path.join(DATA_DIR, ".secret_key")
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_path, "w", encoding="utf-8") as f:
        f.write(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


app.secret_key = get_secret_key()


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def seed_data(db):
    for key, name, tagline, description, order, tier in AXES:
        db.execute(
            "INSERT OR IGNORE INTO axes (key, name, tagline, description, sort_order, tier)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (key, name, tagline, description, order, tier),
        )
    for key, name, identity, description in ROOMS:
        db.execute(
            "INSERT OR IGNORE INTO rooms (key, name, identity, description)"
            " VALUES (?, ?, ?, ?)",
            (key, name, identity, description),
        )
    row = db.execute(
        "SELECT id FROM questions WHERE question_text = ?", (SEED_QUESTION,)
    ).fetchone()
    if row is None:
        cur = db.execute(
            "INSERT INTO questions (question_text, why_asking, created_at, featured, public, status)"
            " VALUES (?, '', ?, 1, 1, 'open')",
            (SEED_QUESTION, now_iso()),
        )
        qid = cur.lastrowid
        axis_ids = db.execute(
            "SELECT id, key FROM axes WHERE key IN ('MEMORIA', 'FE', 'AQUI')"
        ).fetchall()
        for a in axis_ids:
            db.execute(
                "INSERT OR IGNORE INTO question_axes (question_id, axis_id) VALUES (?, ?)",
                (qid, a["id"]),
            )
    db.commit()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    seed_data(db)


# ------------------------------------------------------------ helpers ----

def password_is_set():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key='password_hash'").fetchone()
    return row is not None


def set_password(password):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('password_hash', ?)",
        (generate_password_hash(password),),
    )
    db.commit()


def check_password(password):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key='password_hash'").fetchone()
    return row is not None and check_password_hash(row["value"], password)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def _ensure_schema():
    init_db()


def id_list(form, name):
    ids = []
    for raw in form.getlist(name):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def save_links(db, table, left_col, left_id, right_col, ids):
    db.execute(f"DELETE FROM {table} WHERE {left_col} = ?", (left_id,))
    for rid in ids:
        db.execute(
            f"INSERT OR IGNORE INTO {table} ({left_col}, {right_col}) VALUES (?, ?)",
            (left_id, rid),
        )


def get_links(db, table, left_col, left_id):
    rows = db.execute(
        f"SELECT * FROM {table} WHERE {left_col} = ?", (left_id,)
    ).fetchall()
    right_col = [c for c in rows[0].keys() if c != left_col][0] if rows else None
    if right_col is None:
        # figure out the right column name from the table itself
        cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
        right_col = [c for c in cols if c != left_col][0]
    return {r[right_col] for r in rows}


def pickers(db):
    """Shared data for connection pickers on every form."""
    axes = db.execute("SELECT * FROM axes ORDER BY sort_order").fetchall()
    questions = db.execute(
        "SELECT * FROM questions ORDER BY featured DESC, status, id DESC"
    ).fetchall()
    projects = db.execute("SELECT * FROM projects ORDER BY title").fetchall()
    return axes, questions, projects


def constellation_for_question(db, qid, public_only=False):
    """Everything linked to a question, grouped by type."""
    pub = "AND m.public = 1" if public_only else ""
    materials = db.execute(
        "SELECT m.* FROM materials m JOIN material_questions mq ON mq.material_id = m.id"
        f" WHERE mq.question_id = ? {pub} ORDER BY m.updated_at DESC", (qid,)
    ).fetchall()
    pub = "AND p.public = 1" if public_only else ""
    projects = db.execute(
        "SELECT p.* FROM projects p JOIN project_questions pq ON pq.project_id = p.id"
        f" WHERE pq.question_id = ? {pub} ORDER BY p.title", (qid,)
    ).fetchall()
    journal = [] if public_only else db.execute(
        "SELECT j.* FROM journal_entries j JOIN journal_questions jq ON jq.journal_id = j.id"
        " WHERE jq.question_id = ? ORDER BY j.entry_date DESC", (qid,)
    ).fetchall()
    references = [] if public_only else db.execute(
        'SELECT r.* FROM "references" r JOIN reference_questions rq ON rq.reference_id = r.id'
        " WHERE rq.question_id = ? ORDER BY r.title", (qid,)
    ).fetchall()
    pub = "AND rp.public = 1" if public_only else ""
    pieces = db.execute(
        "SELECT rp.*, rm.name AS room_name, rm.key AS room_key FROM room_pieces rp"
        " JOIN room_piece_questions rqp ON rqp.piece_id = rp.id"
        " JOIN rooms rm ON rm.id = rp.room_id"
        f" WHERE rqp.question_id = ? {pub} ORDER BY rp.updated_at DESC", (qid,)
    ).fetchall()
    pub = "AND v.public = 1" if public_only else ""
    voice = db.execute(
        "SELECT v.* FROM voice_pieces v JOIN voice_piece_questions vq ON vq.voice_piece_id = v.id"
        f" WHERE vq.question_id = ? {pub} ORDER BY v.updated_at DESC", (qid,)
    ).fetchall()
    pub = "AND s.public = 1" if public_only else ""
    serial = db.execute(
        "SELECT s.* FROM serial_chapters s JOIN serial_chapter_questions sq ON sq.chapter_id = s.id"
        f" WHERE sq.question_id = ? {pub} ORDER BY s.number, s.updated_at DESC", (qid,)
    ).fetchall()
    newsletter = [] if public_only else db.execute(
        "SELECT n.* FROM newsletter_issues n JOIN newsletter_issue_questions nq ON nq.issue_id = n.id"
        " WHERE nq.question_id = ? ORDER BY n.issue_no DESC", (qid,)
    ).fetchall()
    pub = "AND p.public = 1" if public_only else ""
    poems = db.execute(
        "SELECT p.* FROM poems p JOIN poem_questions pq ON pq.poem_id = p.id"
        f" WHERE pq.question_id = ? {pub} ORDER BY p.release_month DESC, p.updated_at DESC", (qid,)
    ).fetchall()
    pub = "AND ss.public = 1" if public_only else ""
    stories = db.execute(
        "SELECT ss.* FROM story_sections ss JOIN story_section_questions sq ON sq.section_id = ss.id"
        f" WHERE sq.question_id = ? {pub} ORDER BY ss.story_title, ss.section_no", (qid,)
    ).fetchall()
    axes = db.execute(
        "SELECT a.* FROM axes a JOIN question_axes qa ON qa.axis_id = a.id"
        " WHERE qa.question_id = ? ORDER BY a.sort_order", (qid,)
    ).fetchall()
    return {
        "axes": axes,
        "materials": materials,
        "projects": projects,
        "journal": journal,
        "references": references,
        "pieces": pieces,
        "voice": voice,
        "serial": serial,
        "poems": poems,
        "stories": stories,
        "newsletter": newsletter,
    }


def public_axis_items(db, axis_id):
    questions = db.execute(
        "SELECT q.* FROM questions q JOIN question_axes qa ON qa.question_id = q.id"
        " WHERE qa.axis_id = ? AND q.public = 1 ORDER BY q.featured DESC, q.id DESC",
        (axis_id,),
    ).fetchall()
    materials = db.execute(
        "SELECT m.* FROM materials m JOIN material_axes ma ON ma.material_id = m.id"
        " WHERE ma.axis_id = ? AND m.public = 1 ORDER BY m.updated_at DESC",
        (axis_id,),
    ).fetchall()
    projects = db.execute(
        "SELECT p.* FROM projects p JOIN project_axes pa ON pa.project_id = p.id"
        " WHERE pa.axis_id = ? AND p.public = 1 ORDER BY p.title",
        (axis_id,),
    ).fetchall()
    pieces = db.execute(
        "SELECT rp.*, rm.name AS room_name, rm.key AS room_key FROM room_pieces rp"
        " JOIN room_piece_axes rpa ON rpa.piece_id = rp.id"
        " JOIN rooms rm ON rm.id = rp.room_id"
        " WHERE rpa.axis_id = ? AND rp.public = 1 ORDER BY rp.updated_at DESC",
        (axis_id,),
    ).fetchall()
    voice = db.execute(
        "SELECT v.* FROM voice_pieces v JOIN voice_piece_axes va ON va.voice_piece_id = v.id"
        " WHERE va.axis_id = ? AND v.public = 1 ORDER BY v.updated_at DESC",
        (axis_id,),
    ).fetchall()
    serial = db.execute(
        "SELECT s.* FROM serial_chapters s JOIN serial_chapter_axes sa ON sa.chapter_id = s.id"
        " WHERE sa.axis_id = ? AND s.public = 1 ORDER BY s.number",
        (axis_id,),
    ).fetchall()
    poems = db.execute(
        "SELECT p.* FROM poems p JOIN poem_axes pa ON pa.poem_id = p.id"
        " WHERE pa.axis_id = ? AND p.public = 1 ORDER BY p.release_month DESC",
        (axis_id,),
    ).fetchall()
    stories = db.execute(
        "SELECT ss.* FROM story_sections ss JOIN story_section_axes sa ON sa.section_id = ss.id"
        " WHERE sa.axis_id = ? AND ss.public = 1 ORDER BY ss.story_title, ss.section_no",
        (axis_id,),
    ).fetchall()
    return {
        "questions": questions,
        "materials": materials,
        "projects": projects,
        "pieces": pieces,
        "voice": voice,
        "serial": serial,
        "poems": poems,
        "stories": stories,
    }


def featured_question(db):
    """Rotate daily among featured / open questions, deterministically."""
    rows = db.execute(
        "SELECT * FROM questions WHERE featured = 1 OR status = 'open' ORDER BY id"
    ).fetchall()
    if not rows:
        return None
    day = datetime.now().date().toordinal()
    return rows[day % len(rows)]


def excerpt(text, length=220):
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= length else t[:length].rstrip() + "…"


def _item_excerpt(r):
    keys = r.keys()
    if "body" in keys:
        text = r["body"]
    elif "question_text" in keys:
        text = r["question_text"]
    elif "description" in keys:
        text = r["description"]
    else:
        text = ""
    return excerpt(text)


# ---------------------------------------------------------------- auth ----

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if password_is_set():
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("confirm") or "").strip()
        if not password:
            error = "Please choose a password."
        elif password != confirm:
            error = "The two passwords do not match."
        elif len(password) < 8:
            error = "Please use at least 8 characters."
        else:
            set_password(password)
            session.permanent = True
            session["user"] = "owner"
            return redirect(url_for("dashboard"))
    return render_template("setup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not password_is_set():
        return redirect(url_for("setup"))
    error = None
    if request.method == "POST":
        if check_password(request.form.get("password") or ""):
            session.permanent = True
            session["user"] = "owner"
            return redirect(url_for("dashboard"))
        error = "That password did not match. Try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------- dashboard ----

@app.route("/")
@login_required
def dashboard():
    db = get_db()
    the_question = featured_question(db)
    recent_questions = db.execute(
        "SELECT * FROM questions ORDER BY id DESC LIMIT 5"
    ).fetchall()
    recent_materials = db.execute(
        "SELECT * FROM materials ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    recent_journal = db.execute(
        "SELECT * FROM journal_entries ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    counts = {
        "questions": db.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"],
        "materials": db.execute("SELECT COUNT(*) c FROM materials").fetchone()["c"],
        "projects": db.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"],
        "journal": db.execute("SELECT COUNT(*) c FROM journal_entries").fetchone()["c"],
        "references": db.execute('SELECT COUNT(*) c FROM "references"').fetchone()["c"],
        "pieces": db.execute("SELECT COUNT(*) c FROM room_pieces").fetchone()["c"],
        "voice": db.execute("SELECT COUNT(*) c FROM voice_pieces").fetchone()["c"],
        "serial": db.execute("SELECT COUNT(*) c FROM serial_chapters").fetchone()["c"],
        "poems": db.execute("SELECT COUNT(*) c FROM poems").fetchone()["c"],
        "stories": db.execute("SELECT COUNT(*) c FROM story_sections").fetchone()["c"],
        "newsletter": db.execute("SELECT COUNT(*) c FROM newsletter_issues").fetchone()["c"],
        "public": db.execute(
            "SELECT (SELECT COUNT(*) FROM materials WHERE public=1) + "
            "(SELECT COUNT(*) FROM projects WHERE public=1) + "
            "(SELECT COUNT(*) FROM room_pieces WHERE public=1) + "
            "(SELECT COUNT(*) FROM voice_pieces WHERE public=1) + "
            "(SELECT COUNT(*) FROM serial_chapters WHERE public=1) + "
            "(SELECT COUNT(*) FROM poems WHERE public=1) + "
            "(SELECT COUNT(*) FROM story_sections WHERE public=1) + "
            "(SELECT COUNT(*) FROM questions WHERE public=1) AS c"
        ).fetchone()["c"],
    }
    return render_template(
        "dashboard.html",
        the_question=the_question,
        recent_questions=recent_questions,
        recent_materials=recent_materials,
        recent_journal=recent_journal,
        counts=counts,
    )


@app.route("/quick-capture", methods=["POST"])
@login_required
def quick_capture():
    body = (request.form.get("body") or "").strip()
    if not body:
        return redirect(url_for("dashboard"))
    first_line = body.split("\n")[0].strip()
    title = first_line[:60] if first_line else "Quick capture"
    db = get_db()
    cur = db.execute(
        "INSERT INTO journal_entries (entry_date, title, body, kind, status, created_at, updated_at)"
        " VALUES (?, ?, ?, 'field notes', 'draft', ?, ?)",
        (today_str(), title, body, now_iso(), now_iso()),
    )
    db.commit()
    return redirect(url_for("journal_edit", entry_id=cur.lastrowid))


# ---------------------------------------------------------- questions ----

@app.route("/questions")
@login_required
def question_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM questions WHERE 1=1"
    params = []
    if status_filter in QUESTION_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY featured DESC, id DESC"
    questions = db.execute(query, params).fetchall()
    axis_counts = {
        r["question_id"]: r["c"]
        for r in db.execute(
            "SELECT question_id, COUNT(*) c FROM question_axes GROUP BY question_id"
        ).fetchall()
    }
    return render_template(
        "question_list.html",
        questions=questions,
        statuses=QUESTION_STATUSES,
        status_filter=status_filter,
        axis_counts=axis_counts,
    )


@app.route("/questions/new", methods=["GET", "POST"])
@login_required
def question_new():
    db = get_db()
    axes, _questions, _projects = pickers(db)
    if request.method == "POST":
        text = (request.form.get("question_text") or "").strip()
        if not text:
            return render_template(
                "question_form.html", question=None, axes=axes,
                selected_axes=set(id_list(request.form, "axis_ids")),
                error="The question itself cannot be empty.",
            )
        cur = db.execute(
            "INSERT INTO questions (question_text, why_asking, created_at, featured, public, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                text,
                request.form.get("why_asking") or "",
                now_iso(),
                1 if request.form.get("featured") else 0,
                1 if request.form.get("public") else 0,
                request.form.get("status") if request.form.get("status") in QUESTION_STATUSES else "open",
            ),
        )
        qid = cur.lastrowid
        save_links(db, "question_axes", "question_id", qid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("question_detail", qid=qid))
    return render_template(
        "question_form.html", question=None, axes=axes, selected_axes=set(), error=None
    )


@app.route("/questions/<int:qid>")
@login_required
def question_detail(qid):
    db = get_db()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if question is None:
        abort(404)
    constellation = constellation_for_question(db, qid)
    return render_template(
        "question_detail.html", question=question, constellation=constellation
    )


@app.route("/questions/<int:qid>/edit", methods=["GET", "POST"])
@login_required
def question_edit(qid):
    db = get_db()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if question is None:
        abort(404)
    axes, _questions, _projects = pickers(db)
    if request.method == "POST":
        text = (request.form.get("question_text") or "").strip() or question["question_text"]
        db.execute(
            "UPDATE questions SET question_text=?, why_asking=?, featured=?, public=?, status=? WHERE id=?",
            (
                text,
                request.form.get("why_asking") or "",
                1 if request.form.get("featured") else 0,
                1 if request.form.get("public") else 0,
                request.form.get("status") if request.form.get("status") in QUESTION_STATUSES else question["status"],
                qid,
            ),
        )
        save_links(db, "question_axes", "question_id", qid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("question_detail", qid=qid))
    selected_axes = get_links(db, "question_axes", "question_id", qid)
    return render_template(
        "question_form.html", question=question, axes=axes,
        selected_axes=selected_axes, error=None,
    )


@app.route("/questions/<int:qid>/delete", methods=["GET", "POST"])
@login_required
def question_delete(qid):
    db = get_db()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if question is None:
        abort(404)
    if request.method == "POST":
        for table, col in [
            ("question_axes", "question_id"),
            ("material_questions", "question_id"),
            ("project_questions", "question_id"),
            ("reference_questions", "question_id"),
            ("journal_questions", "question_id"),
            ("room_piece_questions", "question_id"),
        ]:
            db.execute(f"DELETE FROM {table} WHERE {col} = ?", (qid,))
        db.execute("DELETE FROM questions WHERE id = ?", (qid,))
        db.commit()
        return redirect(url_for("question_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'question "{question["question_text"][:70]}"',
        cancel_url=url_for("question_detail", qid=qid),
    )


# ---------------------------------------------------------- materials ----

@app.route("/materials")
@login_required
def material_list():
    db = get_db()
    kind_filter = request.args.get("kind", "")
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM materials WHERE 1=1"
    params = []
    if kind_filter in MATERIAL_KINDS:
        query += " AND kind = ?"
        params.append(kind_filter)
    if status_filter in ("draft", "ready"):
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY updated_at DESC"
    materials = db.execute(query, params).fetchall()
    return render_template(
        "material_list.html", materials=materials, kinds=MATERIAL_KINDS,
        kind_filter=kind_filter, status_filter=status_filter,
    )


def _material_form_common(db, material):
    axes, questions, projects = pickers(db)
    selected = {"axes": set(), "questions": set(), "projects": set()}
    if material is not None:
        mid = material["id"]
        selected["axes"] = get_links(db, "material_axes", "material_id", mid)
        selected["questions"] = get_links(db, "material_questions", "material_id", mid)
        selected["projects"] = get_links(db, "material_projects", "material_id", mid)
    return axes, questions, projects, selected


@app.route("/materials/new", methods=["GET", "POST"])
@login_required
def material_new():
    db = get_db()
    axes, questions, projects, selected = _material_form_common(db, None)
    if request.method == "POST":
        kind = request.form.get("kind") or "note"
        if kind not in MATERIAL_KINDS:
            kind = "note"
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        cur = db.execute(
            "INSERT INTO materials (title, kind, body, status, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, kind, request.form.get("body") or "", status,
             1 if request.form.get("public") else 0, now_iso(), now_iso()),
        )
        mid = cur.lastrowid
        save_links(db, "material_questions", "material_id", mid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "material_axes", "material_id", mid, "axis_id",
                   id_list(request.form, "axis_ids"))
        save_links(db, "material_projects", "material_id", mid, "project_id",
                   id_list(request.form, "project_ids"))
        db.commit()
        return redirect(url_for("material_list"))
    return render_template(
        "material_form.html", material=None, kinds=MATERIAL_KINDS,
        axes=axes, questions=questions, projects=projects, selected=selected,
    )


@app.route("/materials/<int:mid>/edit", methods=["GET", "POST"])
@login_required
def material_edit(mid):
    db = get_db()
    material = db.execute("SELECT * FROM materials WHERE id = ?", (mid,)).fetchone()
    if material is None:
        abort(404)
    axes, questions, projects, selected = _material_form_common(db, material)
    if request.method == "POST":
        kind = request.form.get("kind") or material["kind"]
        if kind not in MATERIAL_KINDS:
            kind = material["kind"]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        db.execute(
            "UPDATE materials SET title=?, kind=?, body=?, status=?, public=?, updated_at=? WHERE id=?",
            (title, kind, request.form.get("body") or "", status,
             1 if request.form.get("public") else 0, now_iso(), mid),
        )
        save_links(db, "material_questions", "material_id", mid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "material_axes", "material_id", mid, "axis_id",
                   id_list(request.form, "axis_ids"))
        save_links(db, "material_projects", "material_id", mid, "project_id",
                   id_list(request.form, "project_ids"))
        db.commit()
        return redirect(url_for("material_list"))
    return render_template(
        "material_form.html", material=material, kinds=MATERIAL_KINDS,
        axes=axes, questions=questions, projects=projects, selected=selected,
    )


@app.route("/materials/<int:mid>/delete", methods=["GET", "POST"])
@login_required
def material_delete(mid):
    db = get_db()
    material = db.execute("SELECT * FROM materials WHERE id = ?", (mid,)).fetchone()
    if material is None:
        abort(404)
    if request.method == "POST":
        for table in ["material_questions", "material_axes", "material_projects"]:
            db.execute(f"DELETE FROM {table} WHERE material_id = ?", (mid,))
        db.execute("DELETE FROM materials WHERE id = ?", (mid,))
        db.commit()
        return redirect(url_for("material_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'material "{material["title"]}"',
        cancel_url=url_for("material_list"),
    )


# ----------------------------------------------------------- projects ----

@app.route("/projects")
@login_required
def project_list():
    db = get_db()
    projects = db.execute("SELECT * FROM projects ORDER BY status, title").fetchall()
    return render_template("project_list.html", projects=projects)


def _project_form_common(db, project):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if project is not None:
        pid = project["id"]
        selected["axes"] = get_links(db, "project_axes", "project_id", pid)
        selected["questions"] = get_links(db, "project_questions", "project_id", pid)
    return axes, questions, selected


@app.route("/projects/new", methods=["GET", "POST"])
@login_required
def project_new():
    db = get_db()
    axes, questions, selected = _project_form_common(db, None)
    if request.method == "POST":
        status = request.form.get("status") or "active"
        if status not in ("active", "resting", "complete"):
            status = "active"
        title = (request.form.get("title") or "").strip() or "Untitled project"
        cur = db.execute(
            "INSERT INTO projects (title, description, status, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, request.form.get("description") or "", status,
             1 if request.form.get("public") else 0, now_iso(), now_iso()),
        )
        pid = cur.lastrowid
        save_links(db, "project_questions", "project_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "project_axes", "project_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("project_list"))
    return render_template(
        "project_form.html", project=None, axes=axes, questions=questions, selected=selected
    )


@app.route("/projects/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def project_edit(pid):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if project is None:
        abort(404)
    axes, questions, selected = _project_form_common(db, project)
    if request.method == "POST":
        status = request.form.get("status") or "active"
        if status not in ("active", "resting", "complete"):
            status = project["status"]
        title = (request.form.get("title") or "").strip() or "Untitled project"
        db.execute(
            "UPDATE projects SET title=?, description=?, status=?, public=?, updated_at=? WHERE id=?",
            (title, request.form.get("description") or "", status,
             1 if request.form.get("public") else 0, now_iso(), pid),
        )
        save_links(db, "project_questions", "project_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "project_axes", "project_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("project_list"))
    return render_template(
        "project_form.html", project=project, axes=axes, questions=questions, selected=selected
    )


@app.route("/projects/<int:pid>/delete", methods=["GET", "POST"])
@login_required
def project_delete(pid):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if project is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM project_questions WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM project_axes WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM material_projects WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        db.commit()
        return redirect(url_for("project_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'project "{project["title"]}"',
        cancel_url=url_for("project_list"),
    )


# --------------------------------------------------------- references ----

@app.route("/references")
@login_required
def reference_list():
    db = get_db()
    refs = db.execute('SELECT * FROM "references" ORDER BY title').fetchall()
    return render_template("reference_list.html", refs=refs)


def _reference_form_common(db, ref):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if ref is not None:
        rid = ref["id"]
        selected["axes"] = get_links(db, "reference_axes", "reference_id", rid)
        selected["questions"] = get_links(db, "reference_questions", "reference_id", rid)
    return axes, questions, selected


@app.route("/references/new", methods=["GET", "POST"])
@login_required
def reference_new():
    db = get_db()
    axes, questions, selected = _reference_form_common(db, None)
    if request.method == "POST":
        kind = request.form.get("kind") or "other"
        if kind not in REFERENCE_KINDS:
            kind = "other"
        title = (request.form.get("title") or "").strip() or "Untitled"
        cur = db.execute(
            'INSERT INTO "references" (title, creator, kind, notes, url, created_at)'
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, request.form.get("creator") or "", kind,
             request.form.get("notes") or "", request.form.get("url") or "", now_iso()),
        )
        rid = cur.lastrowid
        save_links(db, "reference_questions", "reference_id", rid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "reference_axes", "reference_id", rid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("reference_list"))
    return render_template(
        "reference_form.html", ref=None, kinds=REFERENCE_KINDS,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/references/<int:rid>/edit", methods=["GET", "POST"])
@login_required
def reference_edit(rid):
    db = get_db()
    ref = db.execute('SELECT * FROM "references" WHERE id = ?', (rid,)).fetchone()
    if ref is None:
        abort(404)
    axes, questions, selected = _reference_form_common(db, ref)
    if request.method == "POST":
        kind = request.form.get("kind") or ref["kind"]
        if kind not in REFERENCE_KINDS:
            kind = ref["kind"]
        title = (request.form.get("title") or "").strip() or "Untitled"
        db.execute(
            'UPDATE "references" SET title=?, creator=?, kind=?, notes=?, url=? WHERE id=?',
            (title, request.form.get("creator") or "", kind,
             request.form.get("notes") or "", request.form.get("url") or "", rid),
        )
        save_links(db, "reference_questions", "reference_id", rid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "reference_axes", "reference_id", rid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("reference_list"))
    return render_template(
        "reference_form.html", ref=ref, kinds=REFERENCE_KINDS,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/references/<int:rid>/delete", methods=["GET", "POST"])
@login_required
def reference_delete(rid):
    db = get_db()
    ref = db.execute('SELECT * FROM "references" WHERE id = ?', (rid,)).fetchone()
    if ref is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM reference_questions WHERE reference_id = ?", (rid,))
        db.execute("DELETE FROM reference_axes WHERE reference_id = ?", (rid,))
        db.execute('DELETE FROM "references" WHERE id = ?', (rid,))
        db.commit()
        return redirect(url_for("reference_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'reference "{ref["title"]}"',
        cancel_url=url_for("reference_list"),
    )


# ------------------------------------------------------------ journal ----

@app.route("/journal")
@login_required
def journal_list():
    db = get_db()
    kind_filter = request.args.get("kind", "")
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM journal_entries WHERE 1=1"
    params = []
    if kind_filter in JOURNAL_KINDS:
        query += " AND kind = ?"
        params.append(kind_filter)
    if status_filter in ("draft", "ready"):
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY entry_date DESC, updated_at DESC"
    entries = db.execute(query, params).fetchall()
    return render_template(
        "journal_list.html", entries=entries, kinds=JOURNAL_KINDS,
        kind_filter=kind_filter, status_filter=status_filter,
    )


def _journal_form_common(db, entry):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if entry is not None:
        jid = entry["id"]
        selected["axes"] = get_links(db, "journal_axes", "journal_id", jid)
        selected["questions"] = get_links(db, "journal_questions", "journal_id", jid)
    return axes, questions, selected


@app.route("/journal/new", methods=["GET", "POST"])
@login_required
def journal_new():
    db = get_db()
    axes, questions, selected = _journal_form_common(db, None)
    if request.method == "POST":
        kind = request.form.get("kind") or "field notes"
        if kind not in JOURNAL_KINDS:
            kind = "field notes"
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        cur = db.execute(
            "INSERT INTO journal_entries (entry_date, title, body, kind, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request.form.get("entry_date") or today_str(), title,
             request.form.get("body") or "", kind, status, now_iso(), now_iso()),
        )
        jid = cur.lastrowid
        save_links(db, "journal_questions", "journal_id", jid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "journal_axes", "journal_id", jid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "journal_form.html", entry=None, kinds=JOURNAL_KINDS, today=today_str(),
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/journal/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def journal_edit(entry_id):
    db = get_db()
    entry = db.execute(
        "SELECT * FROM journal_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if entry is None:
        abort(404)
    axes, questions, selected = _journal_form_common(db, entry)
    if request.method == "POST":
        kind = request.form.get("kind") or entry["kind"]
        if kind not in JOURNAL_KINDS:
            kind = entry["kind"]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        db.execute(
            "UPDATE journal_entries SET entry_date=?, title=?, body=?, kind=?, status=?, updated_at=? WHERE id=?",
            (request.form.get("entry_date") or entry["entry_date"], title,
             request.form.get("body") or "", kind, status, now_iso(), entry_id),
        )
        save_links(db, "journal_questions", "journal_id", entry_id, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "journal_axes", "journal_id", entry_id, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "journal_form.html", entry=entry, kinds=JOURNAL_KINDS, today=today_str(),
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/journal/<int:entry_id>/delete", methods=["GET", "POST"])
@login_required
def journal_delete(entry_id):
    db = get_db()
    entry = db.execute(
        "SELECT * FROM journal_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if entry is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM journal_questions WHERE journal_id = ?", (entry_id,))
        db.execute("DELETE FROM journal_axes WHERE journal_id = ?", (entry_id,))
        db.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'journal entry "{entry["title"]}"',
        cancel_url=url_for("journal_list"),
    )




# --------------------------------------------------------------- voice ----

def _to_int(raw, default=0):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@app.route("/voice")
@login_required
def voice_list():
    db = get_db()
    kind_filter = request.args.get("kind", "")
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM voice_pieces WHERE 1=1"
    params = []
    if kind_filter in VOICE_KINDS:
        query += " AND kind = ?"
        params.append(kind_filter)
    if status_filter in VOICE_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY updated_at DESC"
    pieces = db.execute(query, params).fetchall()
    return render_template(
        "voice_list.html", pieces=pieces, kinds=VOICE_KINDS,
        statuses=VOICE_STATUSES, kind_filter=kind_filter,
        status_filter=status_filter,
    )


def _voice_form_common(db, piece):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if piece is not None:
        vid = piece["id"]
        selected["axes"] = get_links(db, "voice_piece_axes", "voice_piece_id", vid)
        selected["questions"] = get_links(db, "voice_piece_questions", "voice_piece_id", vid)
    return axes, questions, selected


@app.route("/voice/new", methods=["GET", "POST"])
@login_required
def voice_new():
    db = get_db()
    axes, questions, selected = _voice_form_common(db, None)
    if request.method == "POST":
        kind = request.form.get("kind") or "reading"
        if kind not in VOICE_KINDS:
            kind = "reading"
        status = request.form.get("status") or "idea"
        if status not in VOICE_STATUSES:
            status = "idea"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        cur = db.execute(
            "INSERT INTO voice_pieces (title, kind, body, audio_url, duration,"
            " transcript, status, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, kind, request.form.get("body") or "",
             request.form.get("audio_url") or "", request.form.get("duration") or "",
             request.form.get("transcript") or "", status, public,
             now_iso(), now_iso()),
        )
        vid = cur.lastrowid
        save_links(db, "voice_piece_questions", "voice_piece_id", vid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "voice_piece_axes", "voice_piece_id", vid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("voice_list"))
    return render_template(
        "voice_form.html", piece=None, kinds=VOICE_KINDS, statuses=VOICE_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/voice/<int:vid>/edit", methods=["GET", "POST"])
@login_required
def voice_edit(vid):
    db = get_db()
    piece = db.execute(
        "SELECT * FROM voice_pieces WHERE id = ?", (vid,)
    ).fetchone()
    if piece is None:
        abort(404)
    axes, questions, selected = _voice_form_common(db, piece)
    if request.method == "POST":
        kind = request.form.get("kind") or piece["kind"]
        if kind not in VOICE_KINDS:
            kind = piece["kind"]
        status = request.form.get("status") or "idea"
        if status not in VOICE_STATUSES:
            status = "idea"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        db.execute(
            "UPDATE voice_pieces SET title=?, kind=?, body=?, audio_url=?,"
            " duration=?, transcript=?, status=?, public=?, updated_at=? WHERE id=?",
            (title, kind, request.form.get("body") or "",
             request.form.get("audio_url") or "", request.form.get("duration") or "",
             request.form.get("transcript") or "", status, public, now_iso(), vid),
        )
        save_links(db, "voice_piece_questions", "voice_piece_id", vid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "voice_piece_axes", "voice_piece_id", vid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("voice_list"))
    return render_template(
        "voice_form.html", piece=piece, kinds=VOICE_KINDS, statuses=VOICE_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/voice/<int:vid>/delete", methods=["GET", "POST"])
@login_required
def voice_delete(vid):
    db = get_db()
    piece = db.execute(
        "SELECT * FROM voice_pieces WHERE id = ?", (vid,)
    ).fetchone()
    if piece is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM voice_piece_questions WHERE voice_piece_id = ?", (vid,))
        db.execute("DELETE FROM voice_piece_axes WHERE voice_piece_id = ?", (vid,))
        db.execute("DELETE FROM voice_pieces WHERE id = ?", (vid,))
        db.commit()
        return redirect(url_for("voice_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'voice piece "{piece["title"]}"',
        cancel_url=url_for("voice_list"),
    )


# -------------------------------------------------------------- serial ----

@app.route("/serial")
@login_required
def serial_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM serial_chapters WHERE 1=1"
    params = []
    if status_filter in SERIAL_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY number, updated_at DESC"
    chapters = db.execute(query, params).fetchall()
    return render_template(
        "serial_list.html", chapters=chapters, statuses=SERIAL_STATUSES,
        status_filter=status_filter,
    )


def _serial_form_common(db, chapter):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if chapter is not None:
        cid = chapter["id"]
        selected["axes"] = get_links(db, "serial_chapter_axes", "chapter_id", cid)
        selected["questions"] = get_links(db, "serial_chapter_questions", "chapter_id", cid)
    return axes, questions, selected


@app.route("/serial/new", methods=["GET", "POST"])
@login_required
def serial_new():
    db = get_db()
    axes, questions, selected = _serial_form_common(db, None)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in SERIAL_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        cur = db.execute(
            "INSERT INTO serial_chapters (number, title, body, status,"
            " publish_target, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_to_int(request.form.get("number")), title,
             request.form.get("body") or "", status,
             request.form.get("publish_target") or "", public,
             now_iso(), now_iso()),
        )
        cid = cur.lastrowid
        save_links(db, "serial_chapter_questions", "chapter_id", cid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "serial_chapter_axes", "chapter_id", cid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("serial_list"))
    return render_template(
        "serial_form.html", chapter=None, statuses=SERIAL_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/serial/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def serial_edit(cid):
    db = get_db()
    chapter = db.execute(
        "SELECT * FROM serial_chapters WHERE id = ?", (cid,)
    ).fetchone()
    if chapter is None:
        abort(404)
    axes, questions, selected = _serial_form_common(db, chapter)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in SERIAL_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        db.execute(
            "UPDATE serial_chapters SET number=?, title=?, body=?, status=?,"
            " publish_target=?, public=?, updated_at=? WHERE id=?",
            (_to_int(request.form.get("number"), chapter["number"]), title,
             request.form.get("body") or "", status,
             request.form.get("publish_target") or "", public, now_iso(), cid),
        )
        save_links(db, "serial_chapter_questions", "chapter_id", cid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "serial_chapter_axes", "chapter_id", cid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("serial_list"))
    return render_template(
        "serial_form.html", chapter=chapter, statuses=SERIAL_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/serial/<int:cid>/delete", methods=["GET", "POST"])
@login_required
def serial_delete(cid):
    db = get_db()
    chapter = db.execute(
        "SELECT * FROM serial_chapters WHERE id = ?", (cid,)
    ).fetchone()
    if chapter is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM serial_chapter_questions WHERE chapter_id = ?", (cid,))
        db.execute("DELETE FROM serial_chapter_axes WHERE chapter_id = ?", (cid,))
        db.execute("DELETE FROM serial_chapters WHERE id = ?", (cid,))
        db.commit()
        return redirect(url_for("serial_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'serial chapter "{chapter["title"]}"',
        cancel_url=url_for("serial_list"),
    )


# ---------------------------------------------------------- newsletter ----

@app.route("/newsletter")
@login_required
def newsletter_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM newsletter_issues WHERE 1=1"
    params = []
    if status_filter in NEWSLETTER_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY issue_no DESC, updated_at DESC"
    issues = db.execute(query, params).fetchall()
    return render_template(
        "newsletter_list.html", issues=issues, statuses=NEWSLETTER_STATUSES,
        status_filter=status_filter,
    )


def _newsletter_form_common(db, issue):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if issue is not None:
        nid = issue["id"]
        selected["axes"] = get_links(db, "newsletter_issue_axes", "issue_id", nid)
        selected["questions"] = get_links(db, "newsletter_issue_questions", "issue_id", nid)
    return axes, questions, selected


@app.route("/newsletter/new", methods=["GET", "POST"])
@login_required
def newsletter_new():
    db = get_db()
    axes, questions, selected = _newsletter_form_common(db, None)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in NEWSLETTER_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        cur = db.execute(
            "INSERT INTO newsletter_issues (issue_no, title, body, status,"
            " send_target, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_to_int(request.form.get("issue_no")), title,
             request.form.get("body") or "", status,
             request.form.get("send_target") or "", now_iso(), now_iso()),
        )
        nid = cur.lastrowid
        save_links(db, "newsletter_issue_questions", "issue_id", nid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "newsletter_issue_axes", "issue_id", nid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("newsletter_list"))
    return render_template(
        "newsletter_form.html", issue=None, statuses=NEWSLETTER_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/newsletter/<int:nid>/edit", methods=["GET", "POST"])
@login_required
def newsletter_edit(nid):
    db = get_db()
    issue = db.execute(
        "SELECT * FROM newsletter_issues WHERE id = ?", (nid,)
    ).fetchone()
    if issue is None:
        abort(404)
    axes, questions, selected = _newsletter_form_common(db, issue)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in NEWSLETTER_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        db.execute(
            "UPDATE newsletter_issues SET issue_no=?, title=?, body=?, status=?,"
            " send_target=?, updated_at=? WHERE id=?",
            (_to_int(request.form.get("issue_no"), issue["issue_no"]), title,
             request.form.get("body") or "", status,
             request.form.get("send_target") or "", now_iso(), nid),
        )
        save_links(db, "newsletter_issue_questions", "issue_id", nid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "newsletter_issue_axes", "issue_id", nid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("newsletter_list"))
    return render_template(
        "newsletter_form.html", issue=issue, statuses=NEWSLETTER_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/newsletter/<int:nid>/delete", methods=["GET", "POST"])
@login_required
def newsletter_delete(nid):
    db = get_db()
    issue = db.execute(
        "SELECT * FROM newsletter_issues WHERE id = ?", (nid,)
    ).fetchone()
    if issue is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM newsletter_issue_questions WHERE issue_id = ?", (nid,))
        db.execute("DELETE FROM newsletter_issue_axes WHERE issue_id = ?", (nid,))
        db.execute("DELETE FROM newsletter_issues WHERE id = ?", (nid,))
        db.commit()
        return redirect(url_for("newsletter_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'newsletter letter "{issue["title"]}"',
        cancel_url=url_for("newsletter_list"),
    )

# --------------------------------------------------------------- poems ----

@app.route("/poems")
@login_required
def poem_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM poems WHERE 1=1"
    params = []
    if status_filter in POEM_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY release_month DESC, updated_at DESC"
    poems = db.execute(query, params).fetchall()
    return render_template(
        "poem_list.html", poems=poems, statuses=POEM_STATUSES,
        status_filter=status_filter,
    )


def _poem_form_common(db, poem):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if poem is not None:
        pid = poem["id"]
        selected["axes"] = get_links(db, "poem_axes", "poem_id", pid)
        selected["questions"] = get_links(db, "poem_questions", "poem_id", pid)
    return axes, questions, selected


@app.route("/poems/new", methods=["GET", "POST"])
@login_required
def poem_new():
    db = get_db()
    axes, questions, selected = _poem_form_common(db, None)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in POEM_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        cur = db.execute(
            "INSERT INTO poems (title, body, status, release_month, public,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, request.form.get("body") or "", status,
             request.form.get("release_month") or "", public,
             now_iso(), now_iso()),
        )
        pid = cur.lastrowid
        save_links(db, "poem_questions", "poem_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "poem_axes", "poem_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("poem_list"))
    return render_template(
        "poem_form.html", poem=None, statuses=POEM_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/poems/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def poem_edit(pid):
    db = get_db()
    poem = db.execute(
        "SELECT * FROM poems WHERE id = ?", (pid,)
    ).fetchone()
    if poem is None:
        abort(404)
    axes, questions, selected = _poem_form_common(db, poem)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in POEM_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        db.execute(
            "UPDATE poems SET title=?, body=?, status=?, release_month=?,"
            " public=?, updated_at=? WHERE id=?",
            (title, request.form.get("body") or "", status,
             request.form.get("release_month") or "", public, now_iso(), pid),
        )
        save_links(db, "poem_questions", "poem_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "poem_axes", "poem_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("poem_list"))
    return render_template(
        "poem_form.html", poem=poem, statuses=POEM_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/poems/<int:pid>/delete", methods=["GET", "POST"])
@login_required
def poem_delete(pid):
    db = get_db()
    poem = db.execute(
        "SELECT * FROM poems WHERE id = ?", (pid,)
    ).fetchone()
    if poem is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM poem_questions WHERE poem_id = ?", (pid,))
        db.execute("DELETE FROM poem_axes WHERE poem_id = ?", (pid,))
        db.execute("DELETE FROM poems WHERE id = ?", (pid,))
        db.commit()
        return redirect(url_for("poem_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'poem "{poem["title"]}"',
        cancel_url=url_for("poem_list"),
    )


# -------------------------------------------------------------- stories ----

@app.route("/stories")
@login_required
def story_list():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM story_sections WHERE 1=1"
    params = []
    if status_filter in STORY_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY story_title, section_no, updated_at DESC"
    sections = db.execute(query, params).fetchall()
    return render_template(
        "story_list.html", sections=sections, statuses=STORY_STATUSES,
        status_filter=status_filter,
    )


def _story_form_common(db, section):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if section is not None:
        sid = section["id"]
        selected["axes"] = get_links(db, "story_section_axes", "section_id", sid)
        selected["questions"] = get_links(db, "story_section_questions", "section_id", sid)
    return axes, questions, selected


@app.route("/stories/new", methods=["GET", "POST"])
@login_required
def story_new():
    db = get_db()
    axes, questions, selected = _story_form_common(db, None)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in STORY_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        cur = db.execute(
            "INSERT INTO story_sections (story_title, section_no, title, body,"
            " status, release_target, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (request.form.get("story_title") or "",
             _to_int(request.form.get("section_no")), title,
             request.form.get("body") or "", status,
             request.form.get("release_target") or "", public,
             now_iso(), now_iso()),
        )
        sid = cur.lastrowid
        save_links(db, "story_section_questions", "section_id", sid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "story_section_axes", "section_id", sid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("story_list"))
    return render_template(
        "story_form.html", section=None, statuses=STORY_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/stories/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def story_edit(sid):
    db = get_db()
    section = db.execute(
        "SELECT * FROM story_sections WHERE id = ?", (sid,)
    ).fetchone()
    if section is None:
        abort(404)
    axes, questions, selected = _story_form_common(db, section)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in STORY_STATUSES:
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        public = 1 if request.form.get("public") else 0
        db.execute(
            "UPDATE story_sections SET story_title=?, section_no=?, title=?,"
            " body=?, status=?, release_target=?, public=?, updated_at=?"
            " WHERE id=?",
            (request.form.get("story_title") or "",
             _to_int(request.form.get("section_no")), title,
             request.form.get("body") or "", status,
             request.form.get("release_target") or "", public, now_iso(), sid),
        )
        save_links(db, "story_section_questions", "section_id", sid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "story_section_axes", "section_id", sid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("story_list"))
    return render_template(
        "story_form.html", section=section, statuses=STORY_STATUSES,
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/stories/<int:sid>/delete", methods=["GET", "POST"])
@login_required
def story_delete(sid):
    db = get_db()
    section = db.execute(
        "SELECT * FROM story_sections WHERE id = ?", (sid,)
    ).fetchone()
    if section is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM story_section_questions WHERE section_id = ?", (sid,))
        db.execute("DELETE FROM story_section_axes WHERE section_id = ?", (sid,))
        db.execute("DELETE FROM story_sections WHERE id = ?", (sid,))
        db.commit()
        return redirect(url_for("story_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'story section "{section["title"]}"',
        cancel_url=url_for("story_list"),
    )


# -------------------------------------------------------------- rooms ----

def room_or_404(key):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE key = ?", (key,)).fetchone()
    if room is None:
        abort(404)
    return room


def _piece_extra(raw):
    try:
        data = json.loads(raw or "{}")
    except (ValueError, AttributeError):
        data = {}
    return {"theme": data.get("theme", ""), "diary_date": data.get("diary_date", "")}


@app.route("/rooms/<key>")
@login_required
def room_page(key):
    room = room_or_404(key)
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM room_pieces WHERE room_id = ?"
    params = [room["id"]]
    if status_filter in ("draft", "ready"):
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY updated_at DESC"
    pieces = get_db().execute(query, params).fetchall()
    return render_template(
        "room.html", room=room, pieces=pieces,
        kinds=ROOM_PIECE_KINDS.get(key, []), status_filter=status_filter,
    )


def _piece_form_common(db, piece):
    axes, questions, _projects = pickers(db)
    selected = {"axes": set(), "questions": set()}
    if piece is not None:
        pid = piece["id"]
        selected["axes"] = get_links(db, "room_piece_axes", "piece_id", pid)
        selected["questions"] = get_links(db, "room_piece_questions", "piece_id", pid)
    return axes, questions, selected


@app.route("/rooms/<key>/new", methods=["GET", "POST"])
@login_required
def piece_new(key):
    room = room_or_404(key)
    db = get_db()
    axes, questions, selected = _piece_form_common(db, None)
    kinds = ROOM_PIECE_KINDS.get(key, [])
    if request.method == "POST":
        kind = request.form.get("kind") or ""
        if kinds and kind not in kinds:
            kind = kinds[0]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        extra = json.dumps({
            "theme": request.form.get("theme") or "",
            "diary_date": request.form.get("diary_date") or "",
        })
        cur = db.execute(
            "INSERT INTO room_pieces (room_id, title, kind, body, extra, status, public, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (room["id"], title, kind, request.form.get("body") or "", extra, status,
             1 if request.form.get("public") else 0, now_iso(), now_iso()),
        )
        pid = cur.lastrowid
        save_links(db, "room_piece_questions", "piece_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "room_piece_axes", "piece_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("room_page", key=key))
    return render_template(
        "room_piece_form.html", piece=None, room=room, kinds=kinds, extra=_piece_extra("{}"),
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/room-pieces/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def piece_edit(pid):
    db = get_db()
    piece = db.execute("SELECT * FROM room_pieces WHERE id = ?", (pid,)).fetchone()
    if piece is None:
        abort(404)
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (piece["room_id"],)).fetchone()
    axes, questions, selected = _piece_form_common(db, piece)
    kinds = ROOM_PIECE_KINDS.get(room["key"], [])
    if request.method == "POST":
        kind = request.form.get("kind") or ""
        if kinds and kind not in kinds:
            kind = piece["kind"]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        extra = json.dumps({
            "theme": request.form.get("theme") or "",
            "diary_date": request.form.get("diary_date") or "",
        })
        db.execute(
            "UPDATE room_pieces SET title=?, kind=?, body=?, extra=?, status=?, public=?, updated_at=? WHERE id=?",
            (title, kind, request.form.get("body") or "", extra, status,
             1 if request.form.get("public") else 0, now_iso(), pid),
        )
        save_links(db, "room_piece_questions", "piece_id", pid, "question_id",
                   id_list(request.form, "question_ids"))
        save_links(db, "room_piece_axes", "piece_id", pid, "axis_id",
                   id_list(request.form, "axis_ids"))
        db.commit()
        return redirect(url_for("room_page", key=room["key"]))
    return render_template(
        "room_piece_form.html", piece=piece, room=room, kinds=kinds,
        extra=_piece_extra(piece["extra"]),
        axes=axes, questions=questions, selected=selected,
    )


@app.route("/room-pieces/<int:pid>/delete", methods=["GET", "POST"])
@login_required
def piece_delete(pid):
    db = get_db()
    piece = db.execute("SELECT * FROM room_pieces WHERE id = ?", (pid,)).fetchone()
    if piece is None:
        abort(404)
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (piece["room_id"],)).fetchone()
    if request.method == "POST":
        db.execute("DELETE FROM room_piece_questions WHERE piece_id = ?", (pid,))
        db.execute("DELETE FROM room_piece_axes WHERE piece_id = ?", (pid,))
        db.execute("DELETE FROM room_pieces WHERE id = ?", (pid,))
        db.commit()
        return redirect(url_for("room_page", key=room["key"]))
    return render_template(
        "confirm_delete.html",
        item_label=f'room piece "{piece["title"]}"',
        cancel_url=url_for("room_page", key=room["key"]),
    )


# ------------------------------------------- public constellation (open) ----

@app.route("/constellation/")
def constellation_index():
    db = get_db()
    axes = db.execute("SELECT * FROM axes ORDER BY sort_order").fetchall()
    axis_cards = []
    for a in axes:
        items = public_axis_items(db, a["id"])
        total = sum(len(items[k]) for k in items)
        axis_cards.append({"axis": a, "total": total})
    tiers = []
    for tier_key, tier_name, tier_hint in TIER_LABELS:
        tiers.append({
            "name": tier_name, "hint": tier_hint,
            "cards": [c for c in axis_cards if c["axis"]["tier"] == tier_key],
        })
    the_question = db.execute(
        "SELECT * FROM questions WHERE public = 1 AND (featured = 1 OR status = 'open')"
        " ORDER BY featured DESC, id LIMIT 1"
    ).fetchone()
    return render_template(
        "constellation_index.html", tiers=tiers, the_question=the_question
    )


@app.route("/constellation/axis/<key>")
def constellation_axis(key):
    db = get_db()
    axis = db.execute("SELECT * FROM axes WHERE key = ?", (key.upper(),)).fetchone()
    if axis is None:
        abort(404)
    items = public_axis_items(db, axis["id"])
    return render_template("constellation_axis.html", axis=axis, items=items)


@app.route("/constellation/question/<int:qid>")
def constellation_question(qid):
    db = get_db()
    question = db.execute(
        "SELECT * FROM questions WHERE id = ? AND public = 1", (qid,)
    ).fetchone()
    if question is None:
        abort(404)
    constellation = constellation_for_question(db, qid, public_only=True)
    return render_template(
        "constellation_question.html",
        question=question, constellation=constellation,
    )


# ------------------------------------------------- publish (static) ----

def _export_env():
    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, "export_templates")),
        autoescape=True,
    )
    env.filters["nl2br"] = nl2br
    return env


@app.route("/publish", methods=["GET", "POST"])
@login_required
def publish():
    db = get_db()
    counts = {
        "questions": db.execute("SELECT COUNT(*) c FROM questions WHERE public=1").fetchone()["c"],
        "materials": db.execute("SELECT COUNT(*) c FROM materials WHERE public=1").fetchone()["c"],
        "projects": db.execute("SELECT COUNT(*) c FROM projects WHERE public=1").fetchone()["c"],
        "pieces": db.execute("SELECT COUNT(*) c FROM room_pieces WHERE public=1").fetchone()["c"],
        "voice": db.execute("SELECT COUNT(*) c FROM voice_pieces WHERE public=1").fetchone()["c"],
        "serial": db.execute("SELECT COUNT(*) c FROM serial_chapters WHERE public=1").fetchone()["c"],
        "poems": db.execute("SELECT COUNT(*) c FROM poems WHERE public=1").fetchone()["c"],
        "stories": db.execute("SELECT COUNT(*) c FROM story_sections WHERE public=1").fetchone()["c"],
    }
    result = None
    if request.method == "POST":
        result = build_export()
    return render_template("publish.html", counts=counts, result=result)


def build_export():
    """Render the public constellation to static HTML under export/constellation/."""
    db = get_db()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    shutil.copy(
        os.path.join(BASE_DIR, "static", "style.css"),
        os.path.join(EXPORT_DIR, "style.css"),
    )
    env = _export_env()

    axes = db.execute("SELECT * FROM axes ORDER BY sort_order").fetchall()
    questions = db.execute(
        "SELECT * FROM questions WHERE public = 1 ORDER BY featured DESC, id DESC"
    ).fetchall()

    files = []

    def write(name, html):
        path = os.path.join(EXPORT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        files.append(name)

    # Per-axis pages first (question pages link to them).
    axis_pages = {}
    for a in axes:
        items = public_axis_items(db, a["id"])
        items = {k: [dict(r) | {"excerpt": _item_excerpt(r)} for r in v]
                 for k, v in items.items()}
        fname = f"axis-{a['key']}.html"
        axis_pages[a["id"]] = fname
        write(fname, env.get_template("export_axis.html").render(
            axis=dict(a),
            items=items,
            question_page=lambda qid: f"question-{qid}.html",
        ))

    # Per-question pages.
    for q in questions:
        c = constellation_for_question(db, q["id"], public_only=True)
        c = {k: [dict(r) | {"excerpt": _item_excerpt(r)} for r in v]
             for k, v in c.items()}
        write(f"question-{q['id']}.html", env.get_template("export_question.html").render(
            question=dict(q),
            constellation=c,
            axis_pages=axis_pages,
        ))

    # Index.
    cards = []
    for a in axes:
        items = public_axis_items(db, a["id"])
        total = sum(len(v) for v in items.values())
        cards.append({"axis": dict(a), "total": total, "page": axis_pages[a["id"]]})
    tiers = [
        {"name": name, "hint": hint,
         "cards": [c for c in cards if c["axis"]["tier"] == tkey]}
        for tkey, name, hint in TIER_LABELS
    ]
    the_question = db.execute(
        "SELECT * FROM questions WHERE public = 1 AND (featured = 1 OR status = 'open')"
        " ORDER BY featured DESC, id LIMIT 1"
    ).fetchone()
    write("index.html", env.get_template("export_index.html").render(
        tiers=tiers,
        the_question=dict(the_question) if the_question else None,
    ))

    with open(os.path.join(EXPORT_DIR, "PUBLISH_README.txt"), "w", encoding="utf-8") as f:
        f.write(
            "aQui con fe — public constellation (static snapshot)\n"
            "=====================================================\n\n"
            "This folder is a static snapshot of your Studio's public constellation.\n"
            "Only items you flagged 'public' in the Studio appear here.\n\n"
            "To publish on aquiconfe.org:\n"
            "  1. Copy this whole `constellation` folder into your aqui-con-fe\n"
            "     GitHub repo (e.g. next to index.html, so the site serves\n"
            "     /constellation/index.html).\n"
            "  2. Link to it from your homepage, e.g.:\n"
            '       <a href="/constellation/">The Constellation</a>\n'
            "  3. Commit + push. GitHub Pages serves it as-is — no build step.\n\n"
            "Re-run Publish in the Studio any time to refresh the snapshot.\n"
        )
    files.append("PUBLISH_README.txt")

    return {"count": len(files), "files": sorted(files)}


@app.context_processor
def _inject_rooms():
    try:
        rooms = get_db().execute("SELECT * FROM rooms ORDER BY id").fetchall()
    except Exception:
        rooms = []
    return {"nav_rooms": rooms}


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
