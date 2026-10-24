# Northstar · Student Management System

A full stack student records app with a responsive web interface, a REST API, and persistent SQLite storage. The Python backend and the frontend use only standard library / browser APIs, so no dependency installation or build step is needed.

## Run the app

Requirements: Python 3.10 or newer.

```bash
python3 server.py
```

Open <http://localhost:8000>. Student records live in `students.db`, created automatically beside `server.py` on first run. To choose a different database location or port, set `STUDENT_DB_PATH` and `PORT` before starting the app.

## Features

- Create student records with name, email, phone, course, year, status, and enrollment date.
- Edit existing records and remove them after confirming.
- Search by name, email, or course; filter by course and status.
- View live totals by enrollment status and download the current roster as CSV.
- Store and validate records in SQLite, with a unique email address for each student.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/students` | List students, totals, and courses. Optional `search`, `status`, `year`, and `course` query parameters filter the list. |
| GET | `/api/students/{id}` | Read a student's complete record. |
| POST | `/api/students` | Create a student record. |
| PATCH | `/api/students/{id}` | Update one or more student fields. |
| DELETE | `/api/students/{id}` | Permanently delete a student record. |

Years must be 1–6, enrollment dates must use `YYYY-MM-DD`, emails must be valid and unique, and status must be `Active`, `On leave`, or `Graduated`.

## Verify

```bash
python3 -m unittest discover -s tests -v
```
