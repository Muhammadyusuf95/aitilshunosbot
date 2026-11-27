"""Ma'lumotlar bazasi qatlami.

- Ishlab chiqarishda: PostgreSQL (Neon) — DATABASE_URL orqali.
- DATABASE_URL yo'q bo'lsa: SQLite (data/local.sqlite3) — bot baribir to'liq ishlaydi.
Barcha so'rovlar `?` belgisi bilan yoziladi, PostgreSQL uchun avtomatik `%s` ga aylantiriladi.
Eski `users` jadvali (user_id, username, first_name, points, streak, last_active, status, joined_at)
bilan to'liq mos: yangi ustunlar `ALTER TABLE` orqali xavfsiz qo'shiladi.
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app import config

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except Exception:  # pragma: no cover - psycopg2 bo'lmasa SQLite ishlaydi
    psycopg2 = None


def utcnow_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def today_str(offset_days=0):
    return (datetime.now(config.TZ) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


class Database:
    def __init__(self, url="", sqlite_path=None):
        self.url = url or ""
        self.is_pg = bool(self.url) and psycopg2 is not None
        self._lock = threading.RLock()
        self._pool = None
        self._sqlite = None
        self.sqlite_path = sqlite_path or os.path.join(config.DATA_DIR, "local.sqlite3")
        self._connect()
        self.init_schema()

    # ---------- ulanish ----------
    def _connect(self):
        if self.is_pg:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                1, 10, self.url, sslmode="require",
                keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
            )
        else:
            if self.sqlite_path != ":memory:":
                os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
            self._sqlite = sqlite3.connect(self.sqlite_path, check_same_thread=False)
            self._sqlite.row_factory = sqlite3.Row
            self._sqlite.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def _cursor(self):
        if self.is_pg:
            conn = self._pool.getconn()
            broken = False
            try:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                yield cur
                conn.commit()
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                broken = True
                raise
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    broken = True
                raise
            finally:
                self._pool.putconn(conn, close=broken or bool(conn.closed))
        else:
            with self._lock:
                cur = self._sqlite.cursor()
                try:
                    yield cur
                    self._sqlite.commit()
                except Exception:
                    self._sqlite.rollback()
                    raise
                finally:
                    cur.close()

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.is_pg else sql

    def _run(self, sql, params, fetch):
        last = None
        for attempt in range(2):
            try:
                with self._cursor() as cur:
                    cur.execute(self._sql(sql), tuple(params))
                    if fetch == "all":
                        return [dict(r) for r in cur.fetchall()]
                    if fetch == "one":
                        r = cur.fetchone()
                        return dict(r) if r else None
                    return cur.rowcount
            except Exception as e:  # ulanish uzilgan bo'lsa bir marta qayta urinamiz
                last = e
                if self.is_pg and isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError)) and attempt == 0:
                    time.sleep(0.3)
                    continue
                raise
        raise last

    def execute(self, sql, params=()):
        return self._run(sql, params, None)

    def all(self, sql, params=()):
        return self._run(sql, params, "all")

    def one(self, sql, params=()):
        return self._run(sql, params, "one")

    # ---------- sxema ----------
    def _has_column(self, table, col):
        if self.is_pg:
            r = self.one(
                "SELECT 1 AS x FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
                (table, col),
            )
            return bool(r)
        rows = self.all(f"PRAGMA table_info({table})")
        return any(r["name"] == col for r in rows)

    def _ensure_column(self, table, col, ddl):
        if not self._has_column(table, col):
            self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    def init_schema(self):
        pk = "BIGSERIAL PRIMARY KEY" if self.is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        self.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_active TEXT,
                status TEXT DEFAULT 'active',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self._ensure_column("users", "best_streak", "INTEGER DEFAULT 0")
        self._ensure_column("users", "referred_by", "BIGINT")
        self._ensure_column("users", "invites", "INTEGER DEFAULT 0")
        self._ensure_column("users", "daily_done", "TEXT")
        self._ensure_column("users", "reminders", "INTEGER DEFAULT 1")
        self._ensure_column("users", "exam_date", "TEXT")
        self._ensure_column("users", "exam_name", "TEXT")
        self._ensure_column("users", "quiz_alerts", "INTEGER DEFAULT 0")  # kanal testi xabarnomasi (faqat rozilik bilan)
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS quiz_results (
                id {pk},
                user_id BIGINT NOT NULL,
                name TEXT,
                mode TEXT,
                title TEXT,
                correct INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                created_at TEXT
            )"""
        )
        self.execute("CREATE INDEX IF NOT EXISTS idx_qr_user ON quiz_results(user_id)")
        self.execute("CREATE INDEX IF NOT EXISTS idx_qr_created ON quiz_results(created_at)")
        self.execute(
            """CREATE TABLE IF NOT EXISTS mistakes (
                user_id BIGINT NOT NULL,
                qkey TEXT NOT NULL,
                payload TEXT,
                created_at TEXT,
                PRIMARY KEY (user_id, qkey)
            )"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS badges (
                user_id BIGINT NOT NULL,
                code TEXT NOT NULL,
                earned_at TEXT,
                PRIMARY KEY (user_id, code)
            )"""
        )
        self.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
        self.execute(
            """CREATE TABLE IF NOT EXISTS classes (
                code TEXT PRIMARY KEY, teacher_id BIGINT NOT NULL, name TEXT, created_at TEXT)"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS class_members (
                code TEXT NOT NULL, user_id BIGINT NOT NULL, name TEXT, joined_at TEXT,
                PRIMARY KEY (code, user_id))"""
        )
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS class_tests (
                id {pk}, code TEXT NOT NULL, title TEXT, questions TEXT, created_at TEXT)"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS class_results (
                test_id BIGINT NOT NULL, user_id BIGINT NOT NULL, name TEXT, correct INTEGER, total INTEGER,
                duration REAL, created_at TEXT, PRIMARY KEY (test_id, user_id))"""
        )
        # Kanal testlari (anonim so'rovnoma) — savollar saqlanadi, reyting esa botda ishlaganlar orasida yuritiladi
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS channel_tests (
                id {pk}, title TEXT, questions TEXT, duration INTEGER DEFAULT 30, created_at TEXT)"""
        )
        self.execute(
            """CREATE TABLE IF NOT EXISTS channel_results (
                test_id BIGINT NOT NULL, user_id BIGINT NOT NULL, name TEXT, correct INTEGER, total INTEGER,
                duration REAL, created_at TEXT, PRIMARY KEY (test_id, user_id))"""
        )

    # ---------- foydalanuvchilar ----------
    def get_user(self, uid):
        return self.one("SELECT * FROM users WHERE user_id = ?", (uid,))

    def ensure_user(self, uid, username="", first_name=""):
        """Foydalanuvchi bo'lmasa yaratadi (guruh ishtirokchilari uchun ham)."""
        self.execute(
            "INSERT INTO users (user_id, username, first_name, points, streak, best_streak, last_active, status) "
            "VALUES (?, ?, ?, 0, 0, 0, '', 'active') ON CONFLICT (user_id) DO NOTHING",
            (uid, username or "", first_name or ""),
        )

    def touch_user(self, user, today=None):
        """Kunlik faollik va seriyani yangilaydi.

        Qaytaradi: dict(streak, gained, broken, new_day, is_new_user, prev_streak, points)
        """
        today = today or today_str()
        yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        uname, fname = (user.username or ""), (user.first_name or "")
        row = self.get_user(user.id)
        if not row:
            self.execute(
                "INSERT INTO users (user_id, username, first_name, points, streak, best_streak, last_active, status) "
                "VALUES (?, ?, ?, 10, 1, 1, ?, 'active') ON CONFLICT (user_id) DO NOTHING",
                (user.id, uname, fname, today),
            )
            return dict(streak=1, gained=10, broken=False, new_day=True, is_new_user=True, prev_streak=0, points=10)

        last = row.get("last_active") or ""
        streak = row.get("streak") or 0
        points = row.get("points") or 0
        if last == today:
            if row.get("status") == "blocked" or row.get("username") != uname or row.get("first_name") != fname:
                self.execute(
                    "UPDATE users SET username = ?, first_name = ?, status = 'active' WHERE user_id = ?",
                    (uname, fname, user.id),
                )
            return dict(streak=streak, gained=0, broken=False, new_day=False, is_new_user=False,
                        prev_streak=streak, points=points)

        prev = streak
        broken = False
        if last == yesterday:
            streak += 1
        else:
            broken = bool(last) and prev >= 2
            streak = 1
        gained = 10 + 3 * min(streak - 1, 10)
        points += gained
        best = max(row.get("best_streak") or 0, streak)
        self.execute(
            "UPDATE users SET username = ?, first_name = ?, points = ?, streak = ?, best_streak = ?, "
            "last_active = ?, status = 'active' WHERE user_id = ?",
            (uname, fname, points, streak, best, today, user.id),
        )
        return dict(streak=streak, gained=gained, broken=broken, new_day=True, is_new_user=False,
                    prev_streak=prev, points=points)

    def add_points(self, uid, n):
        self.execute("UPDATE users SET points = COALESCE(points, 0) + ? WHERE user_id = ?", (n, uid))
        r = self.one("SELECT points FROM users WHERE user_id = ?", (uid,))
        return (r or {}).get("points", 0)

    def set_status(self, uid, status):
        self.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, uid))

    def register_referral(self, new_uid, inviter_uid, bonus=30):
        """Yangi foydalanuvchi taklif orqali kelsa, taklif qilganga bonus beradi (bir marta)."""
        if new_uid == inviter_uid:
            return False
        me = self.get_user(new_uid)
        inviter = self.get_user(inviter_uid)
        if not me or not inviter or me.get("referred_by"):
            return False
        self.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (inviter_uid, new_uid))
        self.execute(
            "UPDATE users SET invites = COALESCE(invites, 0) + 1, points = COALESCE(points, 0) + ? WHERE user_id = ?",
            (bonus, inviter_uid),
        )
        self.add_points(new_uid, bonus)
        return True

    def mark_daily_done(self, uid, today=None):
        self.execute("UPDATE users SET daily_done = ? WHERE user_id = ?", (today or today_str(), uid))

    # ---------- natijalar ----------
    def record_result(self, uid, name, mode, title, correct, total, duration):
        self.execute(
            "INSERT INTO quiz_results (user_id, name, mode, title, correct, total, duration, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, name, mode, (title or "")[:120], int(correct), int(total), float(duration), utcnow_str()),
        )

    def leaderboard(self, period="all", limit=25):
        since = {"week": 7, "month": 30}.get(period)
        params = []
        where = ""
        if since:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=since)).strftime("%Y-%m-%d %H:%M:%S")
            where = "WHERE r.created_at >= ?"
            params.append(cutoff)
        params.append(int(limit))
        return self.all(
            "SELECT r.user_id AS user_id, MAX(r.name) AS name, SUM(r.correct) AS correct, SUM(r.total) AS total, "
            "COUNT(*) AS tests, SUM(r.duration) AS duration, MAX(u.points) AS points, MAX(u.streak) AS streak "
            "FROM quiz_results r LEFT JOIN users u ON u.user_id = r.user_id "
            f"{where} GROUP BY r.user_id "
            "ORDER BY SUM(r.correct) DESC, SUM(r.duration) ASC LIMIT ?",
            params,
        )

    def user_rank(self, uid, period="all"):
        rows = self.leaderboard(period, limit=5000)
        for i, r in enumerate(rows, 1):
            if r["user_id"] == uid:
                return i, len(rows)
        return None, len(rows)

    def user_stats(self, uid):
        r = self.one(
            "SELECT COUNT(*) AS tests, COALESCE(SUM(correct), 0) AS correct, COALESCE(SUM(total), 0) AS total "
            "FROM quiz_results WHERE user_id = ?",
            (uid,),
        ) or {}
        best = self.one(
            "SELECT correct, total FROM quiz_results WHERE user_id = ? AND total >= 5 "
            "ORDER BY (correct * 1.0 / total) DESC, total DESC LIMIT 1",
            (uid,),
        )
        return dict(
            tests=int(r.get("tests") or 0),
            correct=int(r.get("correct") or 0),
            total=int(r.get("total") or 0),
            best=best,
        )

    def summary_counts(self):
        res = dict(tests=0, participants=0)
        r = self.one("SELECT COUNT(*) AS n, COUNT(DISTINCT user_id) AS p FROM quiz_results")
        if r:
            res["tests"], res["participants"] = int(r["n"] or 0), int(r["p"] or 0)
        return res

    # ---------- xatolar ustida ishlash ----------
    def add_mistake(self, uid, qkey, question):
        self.execute(
            "INSERT INTO mistakes (user_id, qkey, payload, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, qkey) DO UPDATE SET payload = excluded.payload",
            (uid, qkey, json.dumps(question, ensure_ascii=False), utcnow_str()),
        )

    def remove_mistake(self, uid, qkey):
        """O'chirilgan bo'lsa True."""
        return bool(self.execute("DELETE FROM mistakes WHERE user_id = ? AND qkey = ?", (uid, qkey)))

    def count_mistakes(self, uid):
        r = self.one("SELECT COUNT(*) AS n FROM mistakes WHERE user_id = ?", (uid,))
        return int((r or {}).get("n") or 0)

    def get_mistakes(self, uid, limit=20):
        rows = self.all(
            "SELECT payload FROM mistakes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (uid, int(limit))
        )
        out = []
        for r in rows:
            try:
                out.append(json.loads(r["payload"]))
            except Exception:
                continue
        return out

    # ---------- nishonlar ----------
    def award_badge(self, uid, code):
        """Yangi nishon berilsa True qaytaradi."""
        n = self.execute(
            "INSERT INTO badges (user_id, code, earned_at) VALUES (?, ?, ?) ON CONFLICT (user_id, code) DO NOTHING",
            (uid, code, utcnow_str()),
        )
        return bool(n)

    def get_badges(self, uid):
        return [r["code"] for r in self.all("SELECT code FROM badges WHERE user_id = ? ORDER BY earned_at", (uid,))]

    # ---------- kv / hisoblagichlar ----------
    def kv_get(self, key, default=None):
        r = self.one("SELECT v FROM kv WHERE k = ?", (key,))
        return r["v"] if r else default

    def kv_set(self, key, value):
        self.execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT (k) DO UPDATE SET v = excluded.v", (key, str(value))
        )

    def kv_incr(self, key, by=1):
        with self._lock:
            n = int(self.kv_get(key, 0) or 0) + by
            self.kv_set(key, n)
            return n

    def next_counter(self, name):
        with self._lock:
            cur = int(self.kv_get(f"counter:{name}", 0) or 0) + 1
            self.kv_set(f"counter:{name}", cur)
            return cur

    # ---------- imtihon va eslatmalar ----------
    def set_exam(self, uid, name, date_str):
        self.execute("UPDATE users SET exam_name = ?, exam_date = ? WHERE user_id = ?", (name, date_str, uid))

    def set_reminders(self, uid, on):
        self.execute("UPDATE users SET reminders = ? WHERE user_id = ?", (1 if on else 0, uid))

    def set_quiz_alerts(self, uid, on):
        self.execute("UPDATE users SET quiz_alerts = ? WHERE user_id = ?", (1 if on else 0, uid))

    def users_for_quiz_alert(self):
        return self.all("SELECT user_id, first_name FROM users WHERE status != 'blocked' AND COALESCE(quiz_alerts, 0) = 1")

    def users_for_reminder(self, last_active_dates):
        marks = ",".join("?" for _ in last_active_dates)
        return self.all(
            "SELECT user_id, first_name, streak, last_active, exam_name, exam_date FROM users "
            f"WHERE status != 'blocked' AND COALESCE(reminders, 1) = 1 AND last_active IN ({marks})",
            list(last_active_dates),
        )

    # ---------- sinf rejimi ----------
    def create_class(self, code, teacher_id, name):
        self.execute("INSERT INTO classes (code, teacher_id, name, created_at) VALUES (?, ?, ?, ?)",
                     (code, teacher_id, name[:60], utcnow_str()))

    def get_class(self, code):
        return self.one("SELECT * FROM classes WHERE code = ?", (code,))

    def teacher_classes(self, teacher_id):
        return self.all("SELECT c.code AS code, c.name AS name, "
                        "(SELECT COUNT(*) FROM class_members m WHERE m.code = c.code) AS members "
                        "FROM classes c WHERE c.teacher_id = ? ORDER BY c.created_at DESC", (teacher_id,))

    def student_classes(self, uid):
        return self.all("SELECT c.code AS code, c.name AS name FROM class_members m JOIN classes c ON c.code = m.code "
                        "WHERE m.user_id = ? ORDER BY m.joined_at DESC", (uid,))

    def join_class(self, code, uid, name):
        return bool(self.execute(
            "INSERT INTO class_members (code, user_id, name, joined_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (code, user_id) DO NOTHING", (code, uid, name, utcnow_str())))

    def class_members(self, code):
        return self.all("SELECT user_id, name FROM class_members WHERE code = ? ORDER BY joined_at", (code,))

    def add_class_test(self, code, title, questions):
        self.execute("INSERT INTO class_tests (code, title, questions, created_at) VALUES (?, ?, ?, ?)",
                     (code, title[:100], json.dumps(questions, ensure_ascii=False), utcnow_str()))
        r = self.one("SELECT MAX(id) AS id FROM class_tests WHERE code = ?", (code,))
        return int(r["id"])

    def get_class_test(self, test_id):
        r = self.one("SELECT * FROM class_tests WHERE id = ?", (test_id,))
        if r:
            r["questions"] = json.loads(r["questions"])
        return r

    def class_tests(self, code, limit=5):
        return self.all("SELECT id, title, created_at FROM class_tests WHERE code = ? ORDER BY id DESC LIMIT ?",
                        (code, limit))

    def save_class_result(self, test_id, uid, name, correct, total, duration):
        """Faqat birinchi urinish hisobga olinadi. Yangi bo'lsa True."""
        return bool(self.execute(
            "INSERT INTO class_results (test_id, user_id, name, correct, total, duration, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (test_id, user_id) DO NOTHING",
            (test_id, uid, name, correct, total, float(duration), utcnow_str())))

    def class_test_results(self, test_id):
        return self.all("SELECT user_id, name, correct, total, duration FROM class_results WHERE test_id = ? "
                        "ORDER BY correct DESC, duration ASC", (test_id,))

    def has_class_result(self, test_id, uid):
        return bool(self.one("SELECT 1 AS x FROM class_results WHERE test_id = ? AND user_id = ?", (test_id, uid)))

    # ---------- kanal testlari reytingi ----------
    def add_channel_test(self, title, questions, duration):
        self.execute(
            "INSERT INTO channel_tests (title, questions, duration, created_at) VALUES (?, ?, ?, ?)",
            (title[:100], json.dumps(questions, ensure_ascii=False), int(duration), utcnow_str()),
        )
        r = self.one("SELECT MAX(id) AS id FROM channel_tests")
        return int(r["id"])

    def get_channel_test(self, tid):
        r = self.one("SELECT * FROM channel_tests WHERE id = ?", (int(tid),))
        if r:
            r["questions"] = json.loads(r["questions"])
        return r

    def recent_channel_tests(self, limit=8):
        return self.all("SELECT id, title, created_at FROM channel_tests ORDER BY id DESC LIMIT ?", (int(limit),))

    def save_channel_result(self, tid, uid, name, correct, total, duration):
        """Har bir kishi uchun faqat birinchi urinish. Yangi bo'lsa True."""
        return bool(self.execute(
            "INSERT INTO channel_results (test_id, user_id, name, correct, total, duration, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (test_id, user_id) DO NOTHING",
            (int(tid), int(uid), name, int(correct), int(total), float(duration), utcnow_str())))

    def channel_board(self, tid, limit=10):
        return self.all(
            "SELECT user_id, name, correct, total, duration FROM channel_results WHERE test_id = ? "
            "ORDER BY correct DESC, duration ASC LIMIT ?", (int(tid), int(limit)))

    def channel_count(self, tid):
        r = self.one("SELECT COUNT(*) AS n FROM channel_results WHERE test_id = ?", (int(tid),))
        return int(r["n"]) if r else 0

    def channel_rank(self, tid, uid):
        """Foydalanuvchining shu test ichidagi o'rni. Ishtirok etmagan bo'lsa None."""
        me = self.one("SELECT correct, duration FROM channel_results WHERE test_id = ? AND user_id = ?",
                      (int(tid), int(uid)))
        if not me:
            return None
        better = self.one(
            "SELECT COUNT(*) AS n FROM channel_results WHERE test_id = ? "
            "AND (correct > ? OR (correct = ? AND duration < ?))",
            (int(tid), me["correct"], me["correct"], me["duration"]))
        return dict(rank=int(better["n"]) + 1, correct=int(me["correct"]), duration=float(me["duration"]))

    # ---------- admin ----------
    def user_counts(self):
        total = int((self.one("SELECT COUNT(*) AS n FROM users") or {}).get("n") or 0)
        blocked = int((self.one("SELECT COUNT(*) AS n FROM users WHERE status = 'blocked'") or {}).get("n") or 0)
        today = int((self.one("SELECT COUNT(*) AS n FROM users WHERE last_active = ?", (today_str(),)) or {}).get("n") or 0)
        week_cut = today_str(-6)
        week = int((self.one("SELECT COUNT(*) AS n FROM users WHERE last_active >= ?", (week_cut,)) or {}).get("n") or 0)
        return dict(total=total, blocked=blocked, active=total - blocked, today=today, week=week)

    def users_page(self, page, per_page=8):
        return self.all(
            "SELECT user_id, username, first_name, points, streak, status FROM users "
            "ORDER BY points DESC, user_id DESC LIMIT ? OFFSET ?",
            (per_page, page * per_page),
        )

    def all_user_ids(self, only_active=True):
        sql = "SELECT user_id FROM users" + (" WHERE status != 'blocked'" if only_active else "")
        return [r["user_id"] for r in self.all(sql)]

    def export_users(self):
        return self.all(
            "SELECT user_id, username, first_name, points, streak, best_streak, status, last_active, invites "
            "FROM users ORDER BY points DESC"
        )


_db = None
_db_lock = threading.Lock()


def get_db():
    """Yagona (lazy) baza obyekti. Postgres ulanmasa SQLite ga tushadi."""
    global _db
    with _db_lock:
        if _db is None:
            try:
                _db = Database(config.DATABASE_URL)
            except Exception as e:
                print(f"[db] Postgres ulanmadi ({e}); SQLite'ga o'tildi.")
                _db = Database("")
        return _db
