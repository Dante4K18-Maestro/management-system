import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class StudentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "test.sqlite3"
        server.init_db()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.connect_db() as db:
            db.execute("DELETE FROM students")

    def api(self, method, path, data=None, expected=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request) as response:
                result = json.loads(response.read())
                status = response.status
        except HTTPError as error:
            result = json.loads(error.read())
            status = error.code
        if expected is not None:
            self.assertEqual(status, expected, result)
        return result

    @staticmethod
    def student(**overrides):
        return {
            "first_name": "Amara", "last_name": "Okafor", "email": "amara@example.edu",
            "phone": "+1 555 0100", "course": "Computer Science", "year": 2,
            "status": "Active", "enrollment_date": "2025-09-01", **overrides,
        }

    def test_create_list_filter_and_dashboard_counts(self):
        created = self.api("POST", "/api/students", self.student(), 201)
        self.assertEqual(created["first_name"], "Amara")
        self.api("POST", "/api/students", self.student(
            first_name="Leo", last_name="Mensah", email="leo@example.edu",
            course="Mathematics", status="On leave"), 201)
        results = self.api("GET", "/api/students?search=amara&status=Active&year=2")
        self.assertEqual(len(results["students"]), 1)
        self.assertEqual(results["courses"], ["Computer Science", "Mathematics"])
        self.assertEqual(results["stats"], {"total": 2, "active": 1, "leave_count": 1, "graduated": 0})
        self.assertEqual(self.api("GET", "/api/students?year=3")["students"], [])

    def test_update_duplicate_email_and_delete(self):
        first = self.api("POST", "/api/students", self.student(), 201)
        second = self.api("POST", "/api/students", self.student(
            first_name="Leo", last_name="Mensah", email="leo@example.edu"), 201)
        updated = self.api("PATCH", f"/api/students/{first['id']}", {"course": "Design", "year": 3}, 200)
        self.assertEqual((updated["course"], updated["year"]), ("Design", 3))
        self.api("PATCH", f"/api/students/{first['id']}", {"email": second["email"]}, 409)
        self.api("DELETE", f"/api/students/{first['id']}", expected=200)
        self.api("GET", f"/api/students/{first['id']}", expected=404)
        self.api("DELETE", f"/api/students/{second['id']}", expected=200)

    def test_invalid_data_and_missing_records(self):
        self.api("POST", "/api/students", self.student(email="not-an-email"), 400)
        self.api("POST", "/api/students", self.student(year=7), 400)
        self.api("POST", "/api/students", self.student(status="Unknown"), 400)
        self.api("POST", "/api/students", self.student(), 201)
        self.api("POST", "/api/students", self.student(), 409)
        self.api("PATCH", "/api/students/999", {"year": 1}, 404)
        self.api("DELETE", "/api/students/999", expected=404)

    def test_serves_frontend(self):
        with urlopen(self.base + "/") as response:
            body = response.read().decode()
            self.assertIn("Every student.", body)
            self.assertIn("/app.js", body)


if __name__ == "__main__":
    unittest.main()
