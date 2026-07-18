from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta
import sqlite3
import os
from werkzeug.utils import secure_filename

from docx import Document as DocxDocument
from pypdf import PdfReader

# Turso (libSQL) client. Install with: pip install libsql-experimental
import libsql_experimental as libsql

app = Flask(__name__)

# Vercel's deployment filesystem is read-only except for /tmp, and each
# serverless invocation may get a fresh /tmp — so a local sqlite file is NOT
# permanent on Vercel. To get real persistence there, point this app at a
# Turso database instead by setting these two env vars:
#
#   TURSO_DATABASE_URL   e.g. libsql://your-db-name-yourorg.turso.io
#   TURSO_AUTH_TOKEN     the auth token for that database
#
# If they aren't set, the app falls back to a local sqlite file, which is
# fine for local development but won't persist on Vercel.
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
USE_TURSO = bool(TURSO_DATABASE_URL)

IS_VERCEL = os.environ.get("VERCEL") == "1"
DATA_DIR = "/tmp" if IS_VERCEL else os.path.dirname(__file__)

DB_PATH = os.path.join(DATA_DIR, "todo.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "docx"}


def _rows_to_dicts(cursor, rows):
    """Normalize libsql rows (plain tuples) into dicts so templates can use
    task['col'] the same way they would with sqlite3.Row."""
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


class TursoConnection:
    """Thin wrapper so the rest of the app can keep calling
    conn.execute(...).fetchall()/.fetchone() and get dict-like rows back,
    regardless of whether we're talking to Turso or local sqlite."""

    def __init__(self, url, auth_token):
        self._conn = libsql.connect(url, auth_token=auth_token)

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return TursoCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        # libsql_experimental connections don't require explicit closing,
        # but keep the call symmetrical with sqlite3's API.
        pass


class TursoCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchall(self):
        rows = self._cursor.fetchall()
        return _rows_to_dicts(self._cursor, rows)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _rows_to_dicts(self._cursor, [row])[0]


def get_db():
    if USE_TURSO:
        return TursoConnection(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            due_date TEXT NOT NULL,
            due_time TEXT,
            end_time TEXT,
            done INTEGER NOT NULL DEFAULT 0
        )
    """)
    # migrate older databases created before due_time / end_time existed.
    # due_time doubles as the task's start time; end_time is the optional
    # end of an exact scheduled window (e.g. 09:00 - 10:30).
    existing_cols = [row["name"] if not USE_TURSO else row["name"]
                      for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "due_time" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN due_time TEXT")
    if "end_time" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN end_time TEXT")
    conn.commit()
    conn.close()


def extract_lines_from_docx(path):
    doc = DocxDocument(path)
    lines = [p.text.strip() for p in doc.paragraphs]
    return [l for l in lines if l]


def extract_lines_from_pdf(path):
    reader = PdfReader(path)
    lines = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines


def clean_task_line(line):
    # Strip common list markers like "1.", "-", "*", "•"
    line = line.strip()
    for marker in ("•", "-", "*", "–"):
        if line.startswith(marker):
            line = line[len(marker):].strip()
    parts = line.split(".", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        line = parts[1].strip()
    return line


@app.route("/")
def index():
    conn = get_db()
    tasks = conn.execute(
        "SELECT * FROM tasks ORDER BY done ASC, due_date ASC, "
        "(due_time IS NULL OR due_time = '') ASC, due_time ASC, id ASC"
    ).fetchall()
    total = len(tasks)
    done_count = sum(1 for t in tasks if t["done"])
    pending_count = total - done_count
    done_pct = round((done_count / total) * 100, 1) if total else 0
    pending_pct = round(100 - done_pct, 1) if total else 0
    conn.close()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    celebrate_id = request.args.get("celebrate", type=int)
    return render_template(
        "index.html",
        tasks=tasks,
        tomorrow=tomorrow,
        today=date.today().isoformat(),
        total=total,
        done_count=done_count,
        pending_count=pending_count,
        done_pct=done_pct,
        pending_pct=pending_pct,
        celebrate_id=celebrate_id,
    )


@app.route("/upload", methods=["POST"])
def upload_schedule():
    file = request.files.get("schedule_file")
    due_date = request.form.get("upload_due_date", "").strip()
    due_time = request.form.get("upload_due_time", "").strip()
    end_time = request.form.get("upload_end_time", "").strip()
    if not due_date:
        due_date = (date.today() + timedelta(days=1)).isoformat()

    if not file or file.filename == "":
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_DIR, filename)
    file.save(save_path)

    if ext == "docx":
        lines = extract_lines_from_docx(save_path)
    else:
        lines = extract_lines_from_pdf(save_path)

    conn = get_db()
    for raw_line in lines:
        task_text = clean_task_line(raw_line)
        if task_text:
            conn.execute(
                "INSERT INTO tasks (text, due_date, due_time, end_time, done) VALUES (?, ?, ?, ?, 0)",
                (task_text, due_date, due_time or None, end_time or None),
            )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


@app.route("/add", methods=["POST"])
def add_task():
    text = request.form.get("text", "").strip()
    due_date = request.form.get("due_date", "").strip()
    due_time = request.form.get("due_time", "").strip()
    end_time = request.form.get("end_time", "").strip()

    if not due_date:
        due_date = (date.today() + timedelta(days=1)).isoformat()

    if text:
        conn = get_db()
        conn.execute(
            "INSERT INTO tasks (text, due_date, due_time, end_time, done) VALUES (?, ?, ?, ?, 0)",
            (text, due_date, due_time or None, end_time or None),
        )
        conn.commit()
        conn.close()

    return redirect(url_for("index"))


@app.route("/done/<int:task_id>", methods=["POST"])
def mark_done(task_id):
    conn = get_db()
    task = conn.execute("SELECT done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    became_done = False
    if task is not None:
        new_state = 0 if task["done"] else 1
        became_done = new_state == 1
        conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (new_state, task_id))
        conn.commit()
    conn.close()
    if became_done:
        return redirect(url_for("index", celebrate=task_id))
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
