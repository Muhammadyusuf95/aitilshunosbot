"""Yakka mashq rejimi mantiqi (Telegramdan mustaqil): sessiya, javob tekshirish, natijalar."""
import threading
import time
import uuid

from app import levels, questions as qmod
from app.db import get_db

SESSIONS = {}
LAST_RESULT = {}  # uid -> natija kartochkasi uchun oxirgi natija
_lock = threading.Lock()
SESSION_TTL = 3 * 3600
XP_PER_CORRECT = 2


class Session:
    def __init__(self, uid, name, title, qs, mode="practice", chat_id=None, ctx=None):
        self.sid = uuid.uuid4().hex[:5]
        self.uid = uid
        self.name = name
        self.title = title
        self.questions = qs
        self.mode = mode  # practice | review | daily
        self.chat_id = chat_id
        self.ctx = ctx or {}
        self.idx = 0
        self.correct = 0
        self.wrong_keys = []
        self.run = 0
        self.best_run = 0
        self.started = time.time()
        self.q_started = time.time()
        self.time_spent = 0.0
        self.answered = False
        self.finished = False
        self.touched = time.time()

    @property
    def total(self):
        return len(self.questions)

    def current(self):
        return self.questions[self.idx] if self.idx < self.total else None

    def answer(self, chosen):
        """Javobni qayd etadi. Qaytaradi: (to'g'rimi, savol)."""
        q = self.current()
        self.time_spent += max(0.1, time.time() - self.q_started)
        self.answered = True
        self.touched = time.time()
        ok = chosen == q["correct_option_id"]
        if ok:
            self.correct += 1
            self.run += 1
            self.best_run = max(self.best_run, self.run)
        else:
            self.run = 0
            self.wrong_keys.append(qmod.qkey(q))
        return ok, q

    def skip(self):
        q = self.current()
        self.time_spent += max(0.1, time.time() - self.q_started)
        self.run = 0
        self.wrong_keys.append(qmod.qkey(q))
        self.answered = True
        self.touched = time.time()

    def advance(self):
        self.idx += 1
        self.answered = False
        self.q_started = time.time()
        if self.idx >= self.total:
            self.finished = True
        return not self.finished


def create(uid, name, title, qs, mode="practice", chat_id=None, ctx=None):
    s = Session(uid, name, title, qs, mode, chat_id, ctx)
    with _lock:
        now = time.time()
        for k in [k for k, v in SESSIONS.items() if now - v.touched > SESSION_TTL]:
            SESSIONS.pop(k, None)
        SESSIONS[uid] = s
    return s


def get(uid, sid=None):
    s = SESSIONS.get(uid)
    if not s or (sid and s.sid != sid):
        return None
    return s


def drop(uid):
    SESSIONS.pop(uid, None)


def finalize(s):
    """Sessiya yakunida natijani saqlaydi, XP va nishonlarni hisoblaydi.

    Qaytaradi: dict(xp, new_badges, accuracy, points, level_up)
    """
    db = get_db()
    answered = s.idx if s.finished else s.idx + (1 if s.answered else 0)
    total = max(answered, 0)
    acc = round(100 * s.correct / total) if total else 0
    xp = s.correct * XP_PER_CORRECT
    if s.mode != "daily" and total >= 5 and acc >= 70:
        xp += 10
    before = (db.get_user(s.uid) or {}).get("points", 0)
    new_badges = []

    if total:
        if s.mode != "daily":
            db.record_result(s.uid, s.name, s.mode, s.title, s.correct, total, s.time_spent)
        if xp:
            db.add_points(s.uid, xp)
        if s.mode != "daily" and db.award_badge(s.uid, "first_test"):
            new_badges.append("first_test")
        if total >= 5 and s.correct == total and db.award_badge(s.uid, "perfect"):
            new_badges.append("perfect")
        stats = db.user_stats(s.uid)
        if stats["total"] >= 100 and db.award_badge(s.uid, "marathon"):
            new_badges.append("marathon")

    after = (db.get_user(s.uid) or {}).get("points", before)
    if total:
        cur_lv = levels.level_for(after)[0]
        LAST_RESULT[s.uid] = dict(name=s.name, title=s.title, correct=s.correct, answered=total, accuracy=acc,
                                  level=cur_lv[1], streak=(db.get_user(s.uid) or {}).get("streak") or 0)
    lv_before, lv_after = levels.level_for(before)[0], levels.level_for(after)[0]
    return dict(xp=xp, new_badges=new_badges, accuracy=acc, answered=total, points=after,
                level_up=lv_after if lv_after != lv_before else None)


def record_answer(s, q, ok):
    """Xato javobni 'xatolar daftari'ga yozadi; to'g'ri javob bo'lsa va savol daftarda bo'lsa — o'chiradi."""
    db = get_db()
    key = qmod.qkey(q)
    if ok:
        if db.remove_mistake(s.uid, key):
            if db.kv_incr(f"fixed:{s.uid}") >= 10:
                db.award_badge(s.uid, "mistake_fixer")
    else:
        db.add_mistake(s.uid, key, q)


def record_skip(s, q):
    get_db().add_mistake(s.uid, qmod.qkey(q), q)
