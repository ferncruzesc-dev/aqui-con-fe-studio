"""aQui con fe Studio — a private, self-hosted writing desk.

Single-user Flask app with SQLite storage. Run with:
    pip install -r requirements.txt
    python app.py
"""
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, abort, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("STUDIO_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("STUDIO_DB", os.path.join(DATA_DIR, "studio.db"))

JOURNAL_TYPES = [
    "field notes",
    "reading notes",
    "cultural notes",
    "reflections",
    "research notes",
    "faith",
]
PIECE_TYPES = ["poem", "story", "essay"]
ROOMS = [
    ("omg-moments", "OMG! moments", "Original faith-based comedy · tragedy · storytelling"),
    ("aqui-con-fe-video-diary", "aQui con fe video diary", "Makeup · expression · vlog"),
    ("come-for-me", "coMe for Me", "Faith · sex · gender · reading · performance"),
]
# URL slugs used in routes (short, stable)
ROOM_SLUGS = {
    "omg-moments": ("omg-moments", "OMG! moments",
                    "Original faith-based comedy · tragedy · storytelling"),
    "video-diary": ("video-diary", "aQui con fe video diary",
                    "Makeup · expression · vlog"),
    "come-for-me": ("come-for-me", "coMe for Me",
                    "Faith · sex · gender · reading · performance"),
}

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=30)


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

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    entry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER REFERENCES collections(id),
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    extra TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


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


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


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
    # Cheap safety net so the schema exists even if init_db was skipped.
    init_db()


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
    recent_journal = db.execute(
        "SELECT * FROM journal_entries ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    recent_pieces = db.execute(
        "SELECT p.*, c.name AS collection_name FROM pieces p "
        "LEFT JOIN collections c ON c.id = p.collection_id "
        "ORDER BY p.updated_at DESC LIMIT 5"
    ).fetchall()
    recent_drafts = db.execute(
        "SELECT * FROM room_drafts ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    counts = {
        "journal": db.execute("SELECT COUNT(*) c FROM journal_entries").fetchone()["c"],
        "pieces": db.execute("SELECT COUNT(*) c FROM pieces").fetchone()["c"],
        "drafts": db.execute("SELECT COUNT(*) c FROM room_drafts").fetchone()["c"],
        "ready": db.execute(
            "SELECT (SELECT COUNT(*) FROM journal_entries WHERE status='ready') + "
            "(SELECT COUNT(*) FROM pieces WHERE status='ready') + "
            "(SELECT COUNT(*) FROM room_drafts WHERE status='ready') AS c"
        ).fetchone()["c"],
    }
    return render_template(
        "dashboard.html",
        recent_journal=recent_journal,
        recent_pieces=recent_pieces,
        recent_drafts=recent_drafts,
        counts=counts,
        room_names={slug: name for slug, name, _ in ROOM_SLUGS.values()},
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
        "INSERT INTO journal_entries (type, title, body, entry_date, status, created_at, updated_at)"
        " VALUES ('field notes', ?, ?, ?, 'draft', ?, ?)",
        (title, body, today_str(), now_iso(), now_iso()),
    )
    db.commit()
    return redirect(url_for("journal_edit", entry_id=cur.lastrowid))


# ------------------------------------------------------------ journal ----

@app.route("/journal")
@login_required
def journal_list():
    type_filter = request.args.get("type", "")
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM journal_entries WHERE 1=1"
    params = []
    if type_filter in JOURNAL_TYPES:
        query += " AND type = ?"
        params.append(type_filter)
    if status_filter in ("draft", "ready"):
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY entry_date DESC, updated_at DESC"
    entries = get_db().execute(query, params).fetchall()
    return render_template(
        "journal_list.html",
        entries=entries,
        journal_types=JOURNAL_TYPES,
        type_filter=type_filter,
        status_filter=status_filter,
    )


@app.route("/journal/new", methods=["GET", "POST"])
@login_required
def journal_new():
    if request.method == "POST":
        entry_type = request.form.get("type") or "field notes"
        if entry_type not in JOURNAL_TYPES:
            entry_type = "field notes"
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        db = get_db()
        cur = db.execute(
            "INSERT INTO journal_entries (type, title, body, entry_date, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry_type,
                title,
                request.form.get("body") or "",
                request.form.get("entry_date") or today_str(),
                status,
                now_iso(),
                now_iso(),
            ),
        )
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "journal_form.html",
        entry=None,
        journal_types=JOURNAL_TYPES,
        today=today_str(),
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
    if request.method == "POST":
        entry_type = request.form.get("type") or entry["type"]
        if entry_type not in JOURNAL_TYPES:
            entry_type = entry["type"]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        db.execute(
            "UPDATE journal_entries SET type=?, title=?, body=?, entry_date=?, status=?, updated_at=? WHERE id=?",
            (
                entry_type,
                title,
                request.form.get("body") or "",
                request.form.get("entry_date") or entry["entry_date"],
                status,
                now_iso(),
                entry_id,
            ),
        )
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "journal_form.html", entry=entry, journal_types=JOURNAL_TYPES, today=today_str()
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
        db.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        db.commit()
        return redirect(url_for("journal_list"))
    return render_template(
        "confirm_delete.html",
        item_label=f'journal entry "{entry["title"]}"',
        cancel_url=url_for("journal_list"),
    )


# ------------------------------------------------------------ archive ----

@app.route("/archive")
@login_required
def archive():
    db = get_db()
    type_filter = request.args.get("type", "")
    collections = db.execute("SELECT * FROM collections ORDER BY name").fetchall()
    query = (
        "SELECT p.*, c.name AS collection_name FROM pieces p "
        "LEFT JOIN collections c ON c.id = p.collection_id WHERE 1=1"
    )
    params = []
    if type_filter in PIECE_TYPES:
        query += " AND p.type = ?"
        params.append(type_filter)
    query += " ORDER BY p.updated_at DESC"
    pieces = db.execute(query, params).fetchall()
    grouped = []
    for col in collections:
        grouped.append(
            (col, [p for p in pieces if p["collection_id"] == col["id"]])
        )
    uncategorized = [p for p in pieces if p["collection_id"] is None]
    return render_template(
        "archive.html",
        grouped=grouped,
        uncategorized=uncategorized,
        piece_types=PIECE_TYPES,
        type_filter=type_filter,
    )


@app.route("/collections/new", methods=["POST"])
@login_required
def collection_new():
    name = (request.form.get("name") or "").strip() or "Untitled collection"
    db = get_db()
    db.execute(
        "INSERT INTO collections (name, description) VALUES (?, ?)",
        (name, request.form.get("description") or ""),
    )
    db.commit()
    return redirect(url_for("archive"))


@app.route("/collections/<int:collection_id>/edit", methods=["GET", "POST"])
@login_required
def collection_edit(collection_id):
    db = get_db()
    col = db.execute(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    ).fetchone()
    if col is None:
        abort(404)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip() or col["name"]
        db.execute(
            "UPDATE collections SET name=?, description=? WHERE id=?",
            (name, request.form.get("description") or "", collection_id),
        )
        db.commit()
        return redirect(url_for("archive"))
    return render_template("collection_form.html", collection=col)


@app.route("/collections/<int:collection_id>/delete", methods=["GET", "POST"])
@login_required
def collection_delete(collection_id):
    db = get_db()
    col = db.execute(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    ).fetchone()
    if col is None:
        abort(404)
    if request.method == "POST":
        # Keep the pieces; just unfile them.
        db.execute(
            "UPDATE pieces SET collection_id = NULL WHERE collection_id = ?",
            (collection_id,),
        )
        db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        db.commit()
        return redirect(url_for("archive"))
    return render_template(
        "confirm_delete.html",
        item_label=f'collection "{col["name"]}" (its pieces will be kept, unfiled)',
        cancel_url=url_for("archive"),
    )


@app.route("/pieces/new", methods=["GET", "POST"])
@login_required
def piece_new():
    db = get_db()
    collections = db.execute("SELECT * FROM collections ORDER BY name").fetchall()
    if request.method == "POST":
        piece_type = request.form.get("type") or "poem"
        if piece_type not in PIECE_TYPES:
            piece_type = "poem"
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        raw_cid = (request.form.get("collection_id") or "").strip()
        collection_id = int(raw_cid) if raw_cid.isdigit() else None
        cur = db.execute(
            "INSERT INTO pieces (collection_id, type, title, body, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                collection_id,
                piece_type,
                title,
                request.form.get("body") or "",
                status,
                now_iso(),
                now_iso(),
            ),
        )
        db.commit()
        return redirect(url_for("archive"))
    preselect = request.args.get("collection_id", "")
    return render_template(
        "piece_form.html",
        piece=None,
        collections=collections,
        piece_types=PIECE_TYPES,
        preselect=preselect,
    )


@app.route("/pieces/<int:piece_id>/edit", methods=["GET", "POST"])
@login_required
def piece_edit(piece_id):
    db = get_db()
    piece = db.execute("SELECT * FROM pieces WHERE id = ?", (piece_id,)).fetchone()
    if piece is None:
        abort(404)
    collections = db.execute("SELECT * FROM collections ORDER BY name").fetchall()
    if request.method == "POST":
        piece_type = request.form.get("type") or piece["type"]
        if piece_type not in PIECE_TYPES:
            piece_type = piece["type"]
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        raw_cid = (request.form.get("collection_id") or "").strip()
        collection_id = int(raw_cid) if raw_cid.isdigit() else None
        db.execute(
            "UPDATE pieces SET collection_id=?, type=?, title=?, body=?, status=?, updated_at=? WHERE id=?",
            (
                collection_id,
                piece_type,
                title,
                request.form.get("body") or "",
                status,
                now_iso(),
                piece_id,
            ),
        )
        db.commit()
        return redirect(url_for("archive"))
    return render_template(
        "piece_form.html",
        piece=piece,
        collections=collections,
        piece_types=PIECE_TYPES,
        preselect=str(piece["collection_id"] or ""),
    )


@app.route("/pieces/<int:piece_id>/delete", methods=["GET", "POST"])
@login_required
def piece_delete(piece_id):
    db = get_db()
    piece = db.execute("SELECT * FROM pieces WHERE id = ?", (piece_id,)).fetchone()
    if piece is None:
        abort(404)
    if request.method == "POST":
        db.execute("DELETE FROM pieces WHERE id = ?", (piece_id,))
        db.commit()
        return redirect(url_for("archive"))
    return render_template(
        "confirm_delete.html",
        item_label=f'piece "{piece["title"]}"',
        cancel_url=url_for("archive"),
    )


# -------------------------------------------------------------- rooms ----

def room_or_404(slug):
    room = ROOM_SLUGS.get(slug)
    if room is None:
        abort(404)
    return room


@app.route("/rooms/<room>")
@login_required
def room_page(room):
    slug, name, tagline = room_or_404(room)
    status_filter = request.args.get("status", "")
    query = "SELECT * FROM room_drafts WHERE room = ?"
    params = [slug]
    if status_filter in ("draft", "ready"):
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY updated_at DESC"
    drafts = get_db().execute(query, params).fetchall()
    return render_template(
        "room.html",
        room_slug=slug,
        room_name=name,
        room_tagline=tagline,
        drafts=drafts,
        status_filter=status_filter,
    )


def _parse_extra(raw):
    try:
        data = json.loads(raw or "{}")
        return {"look": data.get("look", ""), "script": data.get("script", "")}
    except (ValueError, AttributeError):
        return {"look": "", "script": ""}


@app.route("/rooms/<room>/new", methods=["GET", "POST"])
@login_required
def draft_new(room):
    slug, name, _tagline = room_or_404(room)
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        extra = None
        if slug == "video-diary":
            extra = json.dumps(
                {
                    "look": request.form.get("look") or "",
                    "script": request.form.get("script") or "",
                }
            )
        db = get_db()
        db.execute(
            "INSERT INTO room_drafts (room, title, body, extra, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                slug,
                title,
                request.form.get("body") or "",
                extra,
                status,
                now_iso(),
                now_iso(),
            ),
        )
        db.commit()
        return redirect(url_for("room_page", room=slug))
    return render_template(
        "draft_form.html", draft=None, room_slug=slug, room_name=name, extra=_parse_extra(None)
    )


@app.route("/drafts/<int:draft_id>/edit", methods=["GET", "POST"])
@login_required
def draft_edit(draft_id):
    db = get_db()
    draft = db.execute(
        "SELECT * FROM room_drafts WHERE id = ?", (draft_id,)
    ).fetchone()
    if draft is None:
        abort(404)
    slug, name, _tagline = room_or_404(draft["room"])
    if request.method == "POST":
        status = request.form.get("status") or "draft"
        if status not in ("draft", "ready"):
            status = "draft"
        title = (request.form.get("title") or "").strip() or "Untitled"
        extra = draft["extra"]
        if slug == "video-diary":
            extra = json.dumps(
                {
                    "look": request.form.get("look") or "",
                    "script": request.form.get("script") or "",
                }
            )
        db.execute(
            "UPDATE room_drafts SET title=?, body=?, extra=?, status=?, updated_at=? WHERE id=?",
            (
                title,
                request.form.get("body") or "",
                extra,
                status,
                now_iso(),
                draft_id,
            ),
        )
        db.commit()
        return redirect(url_for("room_page", room=slug))
    return render_template(
        "draft_form.html",
        draft=draft,
        room_slug=slug,
        room_name=name,
        extra=_parse_extra(draft["extra"]),
    )


@app.route("/drafts/<int:draft_id>/delete", methods=["GET", "POST"])
@login_required
def draft_delete(draft_id):
    db = get_db()
    draft = db.execute(
        "SELECT * FROM room_drafts WHERE id = ?", (draft_id,)
    ).fetchone()
    if draft is None:
        abort(404)
    slug, _name, _tagline = room_or_404(draft["room"])
    if request.method == "POST":
        db.execute("DELETE FROM room_drafts WHERE id = ?", (draft_id,))
        db.commit()
        return redirect(url_for("room_page", room=slug))
    return render_template(
        "confirm_delete.html",
        item_label=f'draft "{draft["title"]}"',
        cancel_url=url_for("room_page", room=slug),
    )


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
