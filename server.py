"""Small, dependency-free student management API and static-file server."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sqlite3
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = Path(os.environ.get("STUDENT_DB_PATH", ROOT / "students.db"))
FIELDS = ("first_name", "last_name", "email", "phone", "course", "year", "status", "enrollment_date")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db() -> None:
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            phone TEXT NOT NULL DEFAULT '', course TEXT NOT NULL,
            year INTEGER NOT NULL CHECK(year BETWEEN 1 AND 6),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'On leave', 'Graduated')),
            enrollment_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


def validate_student(data: object, partial: bool = False) -> dict | None:
    if not isinstance(data, dict):
        return None
    result = {}
    for field in FIELDS:
        if partial and field not in data:
            continue
        value = data.get(field, "")
        if field == "year":
            try:
                value = int(value)
            except (ValueError, TypeError):
                return None
            if not 1 <= value <= 6:
                return None
        else:
            value = str(value).strip()
            if field in ("first_name", "last_name") and not value:
                return None
            if field == "email" and not EMAIL_RE.fullmatch(value):
                return None
            if field == "course" and not value:
                return None
            if field == "status" and value not in ("Active", "On leave", "Graduated"):
                return None
            if field == "enrollment_date":
                try:
                    date.fromisoformat(value)
                except ValueError:
                    return None
        result[field] = value
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "StudentHub/1.0"

    def send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 32_000:
                raise ValueError
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/students":
            query = parse_qs(parsed.query)
            search = query.get("search", [""])[0].strip()
            status = query.get("status", [""])[0]
            course = query.get("course", [""])[0]
            year = query.get("year", [""])[0]
            sql = "SELECT * FROM students WHERE 1=1"
            args: list = []
            if search:
                sql += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR course LIKE ?)"
                args.extend([f"%{search}%"] * 4)
            if status in ("Active", "On leave", "Graduated"):
                sql += " AND status=?"
                args.append(status)
            if year in ("1", "2", "3", "4", "5", "6"):
                sql += " AND year=?"
                args.append(int(year))
            if course:
                sql += " AND course=?"
                args.append(course)
            sql += " ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE"
            with connect_db() as db:
                students = [dict(row) for row in db.execute(sql, args)]
                stats = db.execute("""SELECT COUNT(*) AS total,
                    SUM(status='Active') AS active,
                    SUM(status='On leave') AS leave_count,
                    SUM(status='Graduated') AS graduated FROM students""").fetchone()
                courses = [row[0] for row in db.execute("SELECT DISTINCT course FROM students ORDER BY course COLLATE NOCASE")]
            return self.send_json({"students": students, "stats": {k: stats[k] or 0 for k in stats.keys()}, "courses": courses})
        match = re.fullmatch(r"/api/students/(\d+)", parsed.path)
        if match:
            with connect_db() as db:
                row = db.execute("SELECT * FROM students WHERE id=?", (int(match[1]),)).fetchone()
            return self.send_json(dict(row)) if row else self.send_json({"error": "Student not found."}, 404)
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/students":
            return self.send_json({"error": "Not found."}, 404)
        data = validate_student(self.read_json())
        if data is None:
            return self.send_json({"error": "Check all fields. Names, a valid email, a course, a year from 1 to 6, a valid status, and a valid enrollment date are required."}, 400)
        columns = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        try:
            with connect_db() as db:
                cur = db.execute(f"INSERT INTO students ({columns}) VALUES ({marks})", list(data.values()))
                student = dict(db.execute("SELECT * FROM students WHERE id=?", (cur.lastrowid,)).fetchone())
            self.send_json(student, 201)
        except sqlite3.IntegrityError as exc:
            self.send_json({"error": "A student with that email address already exists."}, 409)

    def do_PATCH(self) -> None:
        match = re.fullmatch(r"/api/students/(\d+)", urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found."}, 404)
        data = validate_student(self.read_json(), partial=True)
        if data is None or not data:
            return self.send_json({"error": "Check the student details and try again."}, 400)
        assignments = ", ".join(f"{field}=?" for field in data)
        try:
            with connect_db() as db:
                cur = db.execute(f"UPDATE students SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE id=?", [*data.values(), int(match[1])])
                row = db.execute("SELECT * FROM students WHERE id=?", (int(match[1]),)).fetchone()
            if not cur.rowcount:
                return self.send_json({"error": "Student not found."}, 404)
            self.send_json(dict(row))
        except sqlite3.IntegrityError:
            self.send_json({"error": "A student with that email address already exists."}, 409)

    def do_DELETE(self) -> None:
        match = re.fullmatch(r"/api/students/(\d+)", urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found."}, 404)
        with connect_db() as db:
            cur = db.execute("DELETE FROM students WHERE id=?", (int(match[1]),))
        if not cur.rowcount:
            return self.send_json({"error": "Student not found."}, 404)
        self.send_json({"ok": True})

    def serve_static(self, path: str) -> None:
        requested = unquote(path).lstrip("/") or "index.html"
        file_path = (STATIC / requested).resolve()
        if not file_path.is_relative_to(STATIC.resolve()) or not file_path.is_file():
            file_path = STATIC / "index.html"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.log_date_time_string()} {fmt % args}")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    print(f"StudentHub running at http://localhost:{port}")
    try:
        ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStudentHub stopped.")
