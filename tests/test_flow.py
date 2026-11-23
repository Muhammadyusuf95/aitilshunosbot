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
    assert "Mavzu doirasidan" in last_text()

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
    assert any("NATIJALAR" in t or "Hech kim" in t for t in f.texts())

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
