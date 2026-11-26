import json, time, threading, importlib
from tests import fake_tg as f
from telebot import types

from app import ai, db as dbmod, config
dbmod._db = dbmod.Database("", ":memory:")
from app.handlers import register_all
register_all()
from app.runtime import bot
bot.threaded = False
from app.handlers import tests as T, group as G, tools, admin

USER = {"id": 777, "is_bot": False, "first_name": "Ali", "username": "ali"}
_uid = [1000]

def upd_msg(text=None, user=USER, chat_type="private", photo=False, chat_id=None):
    _uid[0] += 1
    m = {"message_id": _uid[0], "date": int(time.time()), "chat": {"id": chat_id or user["id"], "type": chat_type, "title": "G"}, "from": user}
    if text is not None:
        m["text"] = text
        if text.startswith("/"):
            m["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    if photo:
        m["photo"] = [{"file_id": "p1", "file_unique_id": "u", "width": 1, "height": 1}]
    return types.Update.de_json({"update_id": _uid[0], "message": m})

def upd_cb(data, user=USER):
    _uid[0] += 1
    return types.Update.de_json({"update_id": _uid[0], "callback_query": {"id": str(_uid[0]), "from": user, "chat_instance": "c", "data": data,
        "message": {"message_id": 5, "date": 1, "chat": {"id": user["id"], "type": "private"}, "text": "x", "from": {"id": 1, "is_bot": True, "first_name": "b"}}}})

def send(u):
    bot.process_new_updates([u]); f.settle()

def last_text():
    return f.texts()[-1] if f.texts() else ""

def fake_quiz(n):
    return [{"question": f"Savol {i}", "options": ["a", "b", "c", "d"], "correct_option_id": i % 4, "explanation": "izoh"} for i in range(n)]

def setup_module(m):
    ai.generate_text = lambda p, **k: "## Sarlavha\n**qalin** matn _kursiv_ va `kod`\n* element"
    ai.generate_quiz = lambda prompt, n, seed=None, passage=None: fake_quiz(n)
    ai.generate_vision = lambda p, b, mime="image/jpeg", **k: "Rasm tahlili"
    config.AI_COOLDOWN_SEC = 0
    bot.download_file = lambda path: b'img'
    from app import security; security.limiter._last.clear()

def test_start_and_menu():
    f.reset(); send(upd_msg("/start"))
    assert "Assalomu alaykum" in f.texts()[0] and "Ali" in f.texts()[0]
    for btn in ["🎒 Abituriyent", "👨‍🏫 O'qituvchi", "🎓 Talaba", "🔬 Tadqiqotchi", "🧰 Til asboblari", "🛠 Quiz yaratish", "🏆 Reyting", "👤 Shaxsiy kabinet", "⚡ Kun savoli"]:
        f.reset(); send(upd_msg(btn)); assert f.texts(), btn

def test_ai_tool_and_html():
    f.reset(); send(upd_cb("tool:gazal")); send(upd_msg("Dil ichra tuyg'u"))
    out = [c for c in f.CALLS if c[0] == "sendMessage"][-1][1]
    assert out["parse_mode"] == "HTML" and "<b>qalin</b>" in out["text"] and "<i>kursiv</i>" in out["text"] and "<code>kod</code>" in out["text"]

def test_forbidden():
    f.reset(); send(upd_cb("tool:izoh")); send(upd_msg("din haqida"))
    assert "So'rov qabul qilinmadi" in last_text() and "1/3" in last_text()

def test_practice_full():
    f.reset(); send(upd_cb("quick:10"))
    assert any("Savol 1/10" in t for t in f.texts())
    s = __import__("app.practice", fromlist=["x"]).get(777)
    for i in range(10):
        s = __import__("app.practice", fromlist=["x"]).get(777)
        send(upd_cb(f"pq:{s.sid}:{i}:{i % 4 if i < 7 else 0}"))
        send(upd_cb(f"pn:{s.sid}:{i}"))
    assert any("NATIJA" in t for t in f.texts()), f.texts()[-3:]
    d = dbmod.get_db()
    assert d.user_stats(777)["tests"] == 1
    assert d.count_mistakes(777) >= 1
    f.reset(); send(upd_cb("review:start")); assert any("Savol 1/" in t for t in f.texts())

def test_daily():
    f.reset(); send(upd_msg("⚡ Kun savoli")); assert any("KUN SAVOLI" in t for t in f.texts())
    send(upd_cb("dq:0")); assert any("XP" in t for t in f.texts())
    f.reset(); send(upd_msg("⚡ Kun savoli")); assert any("allaqachon" in t for t in f.texts())

def test_builder_and_dispatch():
    f.reset(); send(upd_cb("qb:start")); send(upd_msg("Qo'shma gap")); send(upd_cb("qb:n:10"))
    assert any("TEST TAYYOR" in t for t in f.texts()), f.texts()

def test_group_quiz_polls():
    f.reset()
    qs = fake_quiz(2); qs[0]["options"][0] = "x" * 120
    G.run_quiz(-100500, qs, 1, "Sinov", 777)
    polls = [c for c in f.CALLS if c[0] == "sendPoll"]
    assert len(polls) == 2
    assert any("NATIJALAR" in t or "ishtirokchi bo'lmadi" in t for t in f.texts())

def test_poll_answer_scoring():
    f.reset()
    G.ACTIVE[-100500] = dict(cancel=threading.Event(), scores={}, starter=1, total=1, anonymous=False)
    G.POLLS["pp"] = dict(chat_id=-100500, correct=1, sent=time.time() - 3)
    bot.process_new_updates([types.Update.de_json({"update_id": 9999, "poll_answer": {"poll_id": "pp", "user": USER, "option_ids": [1], "option_persistent_ids": ["a"]}})])
    assert G.ACTIVE[-100500]["scores"][777]["correct"] == 1
    G.ACTIVE.clear()

def test_essay_photo_and_text():
    f.reset(); send(upd_cb("essay:check")); send(upd_msg(photo=True))
    assert "Rasm tahlili" in last_text() or any("Rasm tahlili" in t for t in f.texts())
    f.reset(); send(upd_cb("essay:check")); send(upd_msg("a" * 200)); assert any("Sarlavha" in t for t in f.texts())

def test_converter_and_suffix():
    f.reset(); send(upd_cb("conv:cyr2lat")); send(upd_msg("Ўзбекистон"))
    assert any("O'zbekiston" in t for t in f.texts(("sendMessage",)))
    f.reset(); send(upd_cb("sfx_hub")); send(upd_msg("-chi")); assert any("NATIJALAR" in t for t in f.texts()), f.texts()

def test_smart_reply_and_profile_rank():
    send(upd_msg("/cancel"))
    f.reset(); send(upd_msg("qalam")); assert any("nima qilamiz" in t for t in f.texts())
    f.reset(); send(upd_msg("👤 Shaxsiy kabinet")); assert any("SHAXSIY KABINET" in t for t in f.texts())
    f.reset(); send(upd_msg("/top")); assert any("TOP-10" in t for t in f.texts())

def test_admin_and_nonadmin():
    f.reset(); send(upd_cb("adm:panel")); assert not f.texts()
    adm = dict(USER, id=config.ADMIN_ID, first_name="Admin")
    f.reset(); send(upd_msg("/admin", user=adm)); assert any("ADMIN PANELI" in t for t in f.texts())
    f.reset(); send(upd_cb("adm:csv", user=adm)); assert any(c[0] == "sendDocument" for c in f.CALLS)

def test_web():
    from app.web import app
    c = app.test_client()
    assert c.get("/health").json["status"] == "ok"
    r = c.get("/api/leaderboard?period=week").json
    assert r["rows"] and "uid" not in r["rows"][0]
    assert c.get("/leaderboard").status_code == 200

def test_init_data_validation():
    import hmac, hashlib
    from urllib.parse import urlencode
    from app.web import validate_init_data
    data = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 5})}
    chk = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    sec = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest()
    assert validate_init_data(urlencode(data), config.TELEGRAM_TOKEN)["id"] == 5
    data["hash"] = "0" * 64
    assert validate_init_data(urlencode(data), config.TELEGRAM_TOKEN) is None

def test_group_message_ignored():
    f.reset(); send(upd_msg("salom", chat_type="supergroup", chat_id=-100500)); assert not f.texts()


def test_strikes_block_and_offtopic():
    from app.security import strikes
    u = dict(USER, id=4242, first_name="Bad")
    strikes.unblock(4242)
    for _ in range(3):
        f.reset(); send(upd_cb("tool:izoh", user=u)); send(upd_msg("prezident haqida", user=u))
    assert any("24 soatga cheklandi" in t for t in f.texts())
    f.reset(); send(upd_cb("tool:izoh", user=u)); send(upd_msg("qalam", user=u))
    assert any("cheklandi" in t for t in f.texts())
    strikes.unblock(4242)
    # AI mavzudan tashqari deb rad etsa
    old = ai.generate_text
    def refuse(p, **k): raise ai.OffTopic("OFFTOPIC_REFUSED")
    ai.generate_text = refuse
    try:
        f.reset(); send(upd_cb("tool:izoh", user=u)); send(upd_msg("qalam", user=u))
        assert any("So'rov qabul qilinmadi" in t for t in f.texts())
    finally:
        ai.generate_text = old; strikes.unblock(4242)

def test_output_filter():
    old = ai.generate_text
    ai.generate_text = lambda p, **k: "bu haromi odam"
    try:
        f.reset(); send(upd_cb("tool:izoh")); send(upd_msg("qalam"))
        assert not any("haromi" in t for t in f.texts()) and any("So'rov qabul qilinmadi" in t for t in f.texts())
    finally:
        ai.generate_text = old

def _wait_lobby(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if G.LOBBIES:
            return next(iter(G.LOBBIES))
        time.sleep(0.05)
    raise AssertionError("lobby ochilmadi")


def press(data, user=USER):
    bot.process_new_updates([upd_cb(data, user)])


USER2 = {"id": 888, "is_bot": False, "first_name": "Vali", "username": "vali"}


def test_schedule_due_and_jobs():
    from datetime import datetime
    from app import scheduler as S
    tz = config.TZ
    mk = lambda h, m: tz.localize(datetime(2026, 11, 24, h, m))
    assert [k for k, _ in S.due(mk(7, 28), lambda k: None)] == ["daily"]
    assert [k for k, _ in S.due(mk(19, 40), lambda k: None)] == ["quick"]
    assert S.due(mk(12, 0), lambda k: None) == []
    assert S.due(mk(7, 31), lambda k: "2026-11-24") == []  # bir kunda ikki marta emas
    S.DURATIONS.update(quick=1, theme=1, bmb=1, attest=1)
    G.LOBBY_COUNTDOWN = 0; G.ANSWER_GRACE = 0
    for key in ("quick", "theme", "bmb", "attest"):
        f.reset(); G.ACTIVE.clear(); G.LOBBIES.clear()
        ai.generate_quiz = lambda prompt, n, seed=None, passage=None: fake_quiz(n)
        # AI ishlamasa bazadan zaxira
        S.qmod.ai.generate_quiz = (lambda *a, **k: (_ for _ in ()).throw(ai.AIError("x"))) if key == "bmb" else ai.generate_quiz
        orig = G.run_quiz
        G.run_quiz = lambda chat, qs, dur, title, st=None, on_pause=None, _o=orig: _o(chat, qs[:2], 0.2, title, st, on_pause)
        try:
            t = threading.Thread(target=S.run_slot, args=(key, 0, False)); t.start()
            mid = _wait_lobby()
            assert not [c for c in f.CALLS if c[0] == "sendPoll"]  # 2 kishisiz boshlanmaydi
            press(f"rdy:{mid}", USER); press(f"rdy:{mid}", USER2)
            t.join(30)
        finally:
            G.run_quiz = orig
        polls = [c for c in f.CALLS if c[0] == "sendPoll"]
        assert len(polls) == 2, key
        assert all(c[1]["chat_id"] == config.CHANNEL_USERNAME for c in polls)
        assert all("open_period" not in c[1] for c in polls)  # so'rovnomalar yopilmaydi
    f.reset(); S.run_slot("daily", 0, wait=False)
    assert len([c for c in f.CALLS if c[0] == "sendPoll"]) == 1


# ---------------- O'sish funksiyalari ----------------
USER2 = {"id": 888, "is_bot": False, "first_name": "Vali", "username": "vali"}


def _play(user, n=10, right=10):
    from app import practice
    for i in range(n):
        s = practice.get(user["id"])
        send(upd_cb(f"pq:{s.sid}:{i}:{i % 4 if i < right else (i + 1) % 4}", user))
        send(upd_cb(f"pn:{s.sid}:{i}", user))


def test_more_menu_and_exam():
    from datetime import datetime, timedelta
    f.reset(); send(upd_msg("➕ Yana")); assert any("Do'st bilan bellashuv" in str(c[1].get("reply_markup")) for c in f.CALLS)
    f.reset(); send(upd_cb("exam:hub")); send(upd_cb("exam:t:cert")); send(upd_msg("01.01.2020"))
    assert "noto'g'ri" in last_text()
    d = (datetime.now(config.TZ).date() + timedelta(days=40)).strftime("%d.%m.%Y")
    send(upd_msg(d)); assert "40 kun" in last_text()
    f.reset(); send(upd_msg("/start")); assert "40 kun" in f.texts()[0]
    send(upd_cb("exam:del"))


def test_reminders():
    from app.handlers import growth
    d = dbmod.get_db()
    d.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (dbmod.today_str(-1), 777))
    f.reset(); assert growth.send_reminders() >= 1 and any("seriya" in t.lower() for t in f.texts())
    send(upd_cb("rem:toggle"))
    f.reset(); assert growth.send_reminders() == 0
    send(upd_cb("rem:toggle"))


def test_duel_flow():
    from app.handlers import growth
    f.reset(); send(upd_cb("duel:new")); f.settle()
    assert any("BELLASHUV TAYYOR" in t for t in f.texts())
    kvs = dbmod.get_db().all("SELECT k FROM kv WHERE k LIKE 'duel:%'")
    did = kvs[0]["k"].split(":")[1]
    _play(USER, 10, 8)
    send(upd_msg(f"/start duel_{did}", USER2)); assert any("BELLASHUVGA CHAQIRUV" in t for t in f.texts())
    send(upd_cb(f"duel:join:{did}", USER2))
    f.reset(); _play(USER2, 10, 4)
    assert any("G'olib" in t and "Ali" in t for t in f.texts()) or any("BELLASHUV NATIJASI" in t for t in f.texts())
    assert any(c[0] == "sendMessage" and str(c[1].get("chat_id")) == "777" and "NATIJASI" in c[1].get("text", "") for c in f.CALLS)
    assert "duelist" in dbmod.get_db().get_badges(777) + dbmod.get_db().get_badges(888) or "Durang" in str(f.texts())


def test_class_mode():
    f.reset(); send(upd_cb("cls:new")); send(upd_msg("9-A sinf"))
    code = dbmod.get_db().teacher_classes(777)[0]["code"]
    send(upd_msg(f"/start cls_{code}", USER2)); assert any("sinfiga" in t for t in f.texts())
    send(upd_cb(f"cls:task:{code}")); send(upd_msg("Fe'l zamonlari")); send(upd_cb(f"cls:n:{code}:5")); f.settle()
    assert any(str(c[1].get("chat_id")) == "888" and "Yangi topshiriq" in c[1].get("text", "") for c in f.CALLS)
    tid = dbmod.get_db().class_tests(code)[0]["id"]
    send(upd_cb(f"cls:play:{tid}", USER2)); _play(USER2, 5, 3)
    f.reset(); send(upd_cb(f"cls:r:{tid}"))
    assert "Vali" in last_text() and "/5" in last_text()
    f.reset(); send(upd_cb(f"cls:play:{tid}", USER2)); assert f.CALLS  # qayta topshirish rad etiladi
    assert dbmod.get_db().has_class_result(tid, 888)


def test_result_card_and_weekly():
    from app.handlers import growth
    f.reset(); send(upd_cb("rescard", USER2))
    assert any(c[0] == "sendPhoto" for c in f.CALLS)
    buf = growth.make_card(dict(name="Ali", title="Test", correct=8, answered=10, accuracy=80, level="Savodxon", streak=3))
    assert buf.read(8) == b"\x89PNG\r\n\x1a\n"
    f.reset(); assert growth.post_weekly() in (True, False)


# ---------------- v12.2: lobby, pauza, ochiq savollar, jadval surilishi ----------------
USER3 = {"id": 999001, "is_bot": False, "first_name": "Soli"}


def _polls():
    return [c for c in f.CALLS if c[0] == "sendPoll"]


def test_lobby_needs_two_distinct_players():
    G.LOBBY_COUNTDOWN = 0; G.ANSWER_GRACE = 0; G.ACTIVE.clear(); G.LOBBIES.clear()
    f.reset()
    mid = G.open_lobby(-100500, fake_quiz(1), 0.2, "Lobby sinovi", 777)
    press(f"rdy:{mid}", USER); press(f"rdy:{mid}", USER)  # bir kishi ikki marta — hisoblanmaydi
    time.sleep(1.2)
    assert not _polls() and len(G.LOBBIES[mid]["ready"]) == 1
    press(f"rdy:{mid}", USER2)
    t0 = time.time()
    while not _polls() and time.time() - t0 < 5:
        time.sleep(0.1)
    assert len(_polls()) == 1 and "open_period" not in _polls()[0][1]
    time.sleep(1)


def test_lobby_expires():
    G.LOBBIES.clear(); f.reset()
    mid = G.open_lobby(-100500, fake_quiz(2), 0.2, "Muddat", 777, deadline=time.time() + 1)
    time.sleep(2.5)
    assert mid not in G.LOBBIES and not _polls()
    assert any("yig'ilmadi" in t for t in f.texts())


def test_pause_after_two_unanswered_and_resume():
    G.ANSWER_GRACE = 0; G.ACTIVE.clear(); f.reset()
    shifts = []
    t = threading.Thread(target=G.run_quiz, args=(-100500, fake_quiz(4), 0.2, "Pauza", 777),
                         kwargs=dict(on_pause=shifts.append))
    t.start()
    t0 = time.time()
    while not G.PAUSES and time.time() - t0 < 10:
        time.sleep(0.05)
    assert G.PAUSES and len(_polls()) == 2
    time.sleep(1.2)
    assert len(_polls()) == 2  # pauza paytida yangi savol yo'q
    token = next(iter(G.PAUSES))
    press(f"qcont:{token}", USER3)
    t.join(20)
    assert len(_polls()) == 4 and len(shifts) == 1 and shifts[0] >= 1
    assert any("PAUZA" in t for t in f.texts()) and any("davom etmoqda" in t for t in f.texts())


def test_pause_timeout_ends_quiz():
    G.ANSWER_GRACE = 0; G.ACTIVE.clear(); f.reset()
    old = G._pause_max_sec
    G._pause_max_sec = lambda: 1
    try:
        G.run_quiz(-100500, fake_quiz(5), 0.2, "Uzilish", 777)
    finally:
        G._pause_max_sec = old
    assert len(_polls()) == 2 and any("Pauza tugadi" in t for t in f.texts())


def test_answers_prevent_pause_and_late_answers_ignored():
    G.ANSWER_GRACE = 0; G.ACTIVE.clear(); f.reset()
    stop = threading.Event()
    seen = set()

    def voter():  # kanal (anonim) rejimidagi kabi: faqat ovozlar soni keladi
        n = 0
        while not stop.is_set():
            for pid in list(G.POLLS):
                if pid not in seen:
                    seen.add(pid); n += 1
                    bot.process_new_updates([types.Update.de_json({"update_id": 50000 + n, "poll": {
                        "id": pid, "question": "q", "options": [], "total_voter_count": 1, "is_closed": False,
                        "is_anonymous": True, "type": "quiz", "allows_multiple_answers": False}})])
            time.sleep(0.02)
    th = threading.Thread(target=voter); th.start()
    try:
        G.run_quiz(-100500, fake_quiz(4), 0.3, "Ovoz", 777)
    finally:
        stop.set(); th.join()
    assert len(_polls()) == 4 and not any("PAUZA" in t for t in f.texts())
    # Vaqti o'tgan savolga javob reytingga kirmaydi
    G.ACTIVE[-100500] = dict(cancel=threading.Event(), scores={}, starter=1, total=1, anonymous=False)
    G.POLLS["late"] = dict(chat_id=-100500, correct=1, sent=time.time() - 60, open=False, votes=0)
    bot.process_new_updates([types.Update.de_json({"update_id": 59999, "poll_answer": {"poll_id": "late", "user": USER, "option_ids": [1], "option_persistent_ids": ["a"]}})])
    assert G.ACTIVE[-100500]["scores"] == {}
    G.ACTIVE.clear(); G.POLLS.clear()


def test_schedule_shift_only_by_pause():
    from datetime import datetime
    from app import scheduler as S
    tz = config.TZ
    mk = lambda h, m: tz.localize(datetime(2026, 11, 24, h, m))
    kv = {"sched_shift:2026-11-24": "1800"}  # 30 daqiqa pauza
    assert [k for k, _ in S.due(mk(19, 28), kv.get)] == []           # 19:30 -> 20:00 ga surilgan
    assert [k for k, _ in S.due(mk(19, 58), kv.get)] == ["quick"]
    assert "theme" in [k for k, _ in S.due(mk(20, 28), kv.get)]
    assert [k for k, _ in S.due(mk(7, 28), kv.get)] == ["daily"]      # kun savoli surilmaydi
    # Lobby keyingi testga ulguradigan qilib yopiladi
    now = mk(19, 30)
    d = S._lobby_deadline("quick", 10, 30, now=now)
    assert d <= S.slot_time("theme", now, 0).timestamp() or d == now.timestamp() + S.MIN_LOBBY_SEC
    # add_shift bazada yig'iladi
    day = datetime.now(tz).strftime("%Y-%m-%d")
    before = S.get_shift()
    S.add_shift(90); S.add_shift(30)
    assert S.get_shift() == before + 120
    dbmod.get_db().kv_set(f"sched_shift:{day}", before)


def test_jadval_and_quiz_alerts():
    from app.handlers import growth
    f.reset(); send(upd_msg("/jadval")); assert any("KANAL JADVALI" in t for t in f.texts())
    f.reset(); send(upd_msg("/testxabar")); assert "yoqildi" in last_text()
    growth._last_alert[0] = 0
    f.reset(); assert growth.send_quiz_alerts("Sinov", "https://t.me/x/1") >= 1
    assert growth.send_quiz_alerts("Sinov", "https://t.me/x/1") == 0  # spamga qarshi oraliq
    send(upd_msg("/testxabar")); assert "o'chirildi" in last_text()
