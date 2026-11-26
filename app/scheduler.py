"""Kanal uchun kunlik avtomatik jadval (Toshkent vaqti; BOT_TZ bilan o'zgartiriladi) va Render uyg'otgich.

Jadval (asosiy vaqtlar SAQLANADI):
  07:30  Kun savoli
  19:30  Tezkor 10 talik test
  20:00  Mavzulashtirilgan test (30 ta; mavzu har kuni almashadi)
  20:30  BMB 30 talik test
  21:00  Attestatsiya testi (40 ta)

v12.2 qoidalari:
  • Har bir test kanalda lobby sifatida e'lon qilinadi va 2 kishi «Tayyorman»ni bosgach boshlanadi.
    Lobby keyingi test vaqtiga ulgurib tugaydigan qilib yopiladi — shu sabab kutish jadvalni SURMAYDI.
  • Test davomida pauza bo'lsa, uning davomiyligi kunlik «surilish»ga qo'shiladi (kv: sched_shift:SANA)
    va shu kungi keyingi testlar aynan shuncha vaqtga kechroq boshlanadi. Boshqa sabab bilan surilmaydi.
Savollar test vaqtidan 3 daqiqa oldin tayyorlanadi. Qayta ishga tushish bo'lsa, 60 daqiqagacha kechikkan vazifa bajariladi
va bir kunda ikki marta yuborilmaydi (holat bazada saqlanadi).
"""
import threading
import time
from datetime import datetime, timedelta

import requests

from app import ai, config, questions as qmod
from app.content import THEME_CATALOG
from app.db import get_db
from app.handlers.common import log_exc
from app.runtime import bot
from app.textfmt import esc
from app.ui import kb

SLOTS = [("daily", 7, 30), ("remind", 18, 0), ("weekly", 19, 0), ("quick", 19, 30), ("theme", 20, 0),
         ("bmb", 20, 30), ("attest", 21, 0)]
QUIZ_KEYS = ("quick", "theme", "bmb", "attest")
SLOT_LABELS = {"daily": "☀️ Kun savoli", "quick": "⚡ Tezkor 10 talik", "theme": "🎯 Mavzulashtirilgan 30 talik",
               "bmb": "🧠 BMB 30 talik", "attest": "📝 Attestatsiya 40 talik"}
WEEKLY_WEEKDAY = 6  # yakshanba
PREP_MIN = 3
GRACE_MIN = 60
MIN_LOBBY_SEC = 5 * 60
DURATIONS = {"quick": 30, "theme": 30, "bmb": 30, "attest": 45}  # har bir savolga soniya
_channel_lock = threading.Lock()
_shift_lock = threading.Lock()


# ---------------- Pauza hisobiga surilish ----------------
def _shift_key(day):
    return f"sched_shift:{day}"


def get_shift(kv_get=None, day=None):
    """Bugungi umumiy surilish (soniya)."""
    kv_get = kv_get or get_db().kv_get
    day = day or datetime.now(config.TZ).strftime("%Y-%m-%d")
    try:
        return max(0, int(float(kv_get(_shift_key(day)) or 0)))
    except (TypeError, ValueError):
        return 0


def add_shift(seconds, day=None):
    """Pauza davomiyligini bugungi keyingi testlarga qo'shadi."""
    seconds = int(round(max(0, seconds)))
    if not seconds:
        return get_shift()
    db = get_db()
    day = day or datetime.now(config.TZ).strftime("%Y-%m-%d")
    with _shift_lock:
        cur = get_shift(db.kv_get, day) + seconds
        db.kv_set(_shift_key(day), cur)
    print(f"[jadval] pauza: +{seconds}s, bugungi surilish {cur}s")
    return cur


def slot_time(key, now=None, shift=None):
    """Vazifaning bugungi haqiqiy vaqti (testlar uchun — surilish qo'shilgan holda)."""
    now = now or datetime.now(config.TZ)
    h, m = next((h, m) for k, h, m in SLOTS if k == key)
    base = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if key in QUIZ_KEYS:
        base += timedelta(seconds=get_shift(day=now.strftime("%Y-%m-%d")) if shift is None else shift)
    return base


def due(now, kv_get):
    """Hozir ishga tushirilishi kerak bo'lgan vazifalar: [(kalit, daqiqa_farqi)]. Bir kunda bir marta."""
    today = now.strftime("%Y-%m-%d")
    shift = get_shift(kv_get, today)
    out = []
    for key, h, m in SLOTS:
        if key == "weekly" and now.weekday() != WEEKLY_WEEKDAY:
            continue
        delta = (now - slot_time(key, now, shift if key in QUIZ_KEYS else 0)).total_seconds() / 60
        if -PREP_MIN <= delta <= GRACE_MIN and kv_get(f"sched:{key}") != today:
            out.append((key, delta))
    return out


def next_quiz_line(now=None):
    """Bugungi hali boshlanmagan eng yaqin kanal testi: «20:30 — 🧠 BMB 30 talik» yoki ''."""
    now = now or datetime.now(config.TZ)
    for key in QUIZ_KEYS:
        t = slot_time(key, now)
        if t > now:
            return f"{t.strftime('%H:%M')} — {SLOT_LABELS[key]}"
    return ""


def schedule_view(now=None):
    """/jadval uchun: bugungi kanal jadvali (asosiy va pauza hisobiga surilgan vaqtlar)."""
    now = now or datetime.now(config.TZ)
    db = get_db()
    today = now.strftime("%Y-%m-%d")
    shift = get_shift(db.kv_get, today)
    lines = []
    for key, h, m in SLOTS:
        if key not in SLOT_LABELS:
            continue
        base = f"{h:02d}:{m:02d}"
        t = slot_time(key, now)
        started = db.kv_get(f"sched:{key}") == today and t <= now + timedelta(minutes=PREP_MIN)
        mark = "✅" if started else "🕒"
        moved = f" → <b>{t.strftime('%H:%M')}</b> <i>(pauza hisobiga)</i>" if key in QUIZ_KEYS and shift and not started else ""
        lines.append(f"{mark} {base}{moved} · {SLOT_LABELS[key]}")
    note = (f"\n\n⏸ Bugun pauzalar hisobiga keyingi testlar <b>{shift // 60} daq. {shift % 60} s</b> ga surildi."
            if shift else "")
    body = ("\n".join(lines) + note +
            f"\n\n✋ Har bir test kanalda {config.MIN_PLAYERS} kishi «Tayyorman»ni bosgach boshlanadi."
            "\n📝 Savollar yopilmaydi: kechikkanlar ham javob belgilab, izohni ko'ra oladi.")
    return body


def _lobby_deadline(key, n_questions, duration, now=None):
    """Lobby yopiladigan vaqt (epoch): test keyingi test vaqtigacha ulgurib tugashi kerak."""
    from app.handlers.group import ANSWER_GRACE
    now = now or datetime.now(config.TZ)
    est = n_questions * (duration + ANSWER_GRACE) + 60
    idx = QUIZ_KEYS.index(key)
    if idx + 1 < len(QUIZ_KEYS):
        nxt = slot_time(QUIZ_KEYS[idx + 1], now)
        deadline = nxt.timestamp() - est
    else:
        deadline = slot_time(key, now).timestamp() + config.LAST_LOBBY_MIN * 60
    return max(deadline, now.timestamp() + MIN_LOBBY_SEC)


def _safe_build(builder, count, fallback_title):
    """AI/baza orqali savollar; xato bo'lsa tasdiqlangan bazadan zaxira."""
    try:
        qs = builder()
        if qs:
            return qs, fallback_title
    except Exception:  # noqa: BLE001
        log_exc(f"build {fallback_title}")
    return qmod.random_bank_questions(count), fallback_title


def build_job(key, today_ordinal=None):
    """(sarlavha, savollar, davomiylik) qaytaradi."""
    db = get_db()
    day = today_ordinal or datetime.now(config.TZ).date().toordinal()
    general = qmod.theme_prompt(qmod.GENERAL_THEME)
    if key == "quick":
        qs, _ = _safe_build(lambda: qmod.build_quiz(general, 10, sections=None)[0], 10, "")
        return "⚡ Tezkor 10 talik test", qs, DURATIONS[key]
    if key == "theme":
        themes = list(THEME_CATALOG.values())
        label, prompt, sections = themes[day % len(themes)]
        qs, _ = _safe_build(lambda: qmod.build_quiz(qmod.theme_prompt(prompt), 30, sections=sections)[0], 30, "")
        return f"{label} (30 ta)", qs, DURATIONS[key]
    if key == "bmb":
        n = db.next_counter("bmb_30")
        qs, _ = _safe_build(lambda: qmod.build_quiz(general, 30, sections=None)[0], 30, "")
        return f"№{n} BMB 30 talik test", qs, DURATIONS[key]
    if key == "attest":
        n = db.next_counter("attestation")
        qs, _ = _safe_build(qmod.build_attestation, 40, "")
        return f"№{n} Attestatsiya testi", qs, DURATIONS[key]
    raise ValueError(key)


def send_daily_question():
    from app.handlers.group import poll_payload
    q = qmod.daily_question()
    if not q:
        return
    today = datetime.now(config.TZ).strftime("%d.%m.%Y")
    bot.send_message(config.CHANNEL_USERNAME,
                     f"☀️ <b>KUN SAVOLI</b> · {today}\nBugungi savolga javob bering va izohni o'qing 👇",
                     parse_mode="HTML",
                     reply_markup=kb([[("⚡ Botda ishlash", f"https://t.me/{config.BOT_USERNAME}?start=daily", "url")]]))
    p = poll_payload(q, 1, 1, 0)
    p["question"] = p["question"].replace("[1/1] ", "", 1)
    if p["card"]:
        bot.send_message(config.CHANNEL_USERNAME, p["card"].replace("[1/1]", "").strip(), parse_mode="HTML")
    bot.send_poll(config.CHANNEL_USERNAME, p["question"], p["options"], type="quiz",
                  correct_option_id=q["correct_option_id"], explanation=p["explanation"], is_anonymous=True)


def _wait_for_slot(key):
    """Vazifaning haqiqiy vaqtigacha kutadi (surilish kutish davomida o'zgarsa ham hisobga olinadi)."""
    while True:
        left = (slot_time(key) - datetime.now(config.TZ)).total_seconds()
        if left <= 0:
            return
        time.sleep(min(left, 15))


def run_slot(key, delta, wait=True):
    """Bitta vazifani bajaradi: avval tayyorlaydi, so'ng vaqti kelganda yuboradi."""
    if key in ("remind", "weekly"):
        from app.handlers import growth
        (growth.send_reminders if key == "remind" else growth.post_weekly)()
        print(f"[jadval] {key} bajarildi")
        return
    content = None
    if key != "daily":
        content = build_job(key)
    if wait:
        _wait_for_slot(key)
    with _channel_lock:
        if key == "daily":
            send_daily_question()
        else:
            if wait:
                _wait_for_slot(key)  # oldingi test pauza bilan cho'zilgan bo'lsa, surilgan vaqtni kutamiz
            from app.handlers.group import open_lobby
            title, qs, duration = content
            held = open_lobby(config.CHANNEL_USERNAME, qs, duration, title, None,
                              deadline=_lobby_deadline(key, len(qs), duration), on_pause=add_shift,
                              blocking=True, notify=True)
            print(f"[jadval] {key}: {'o‘tkazildi' if held else 'ishtirokchi yig‘ilmadi'}")
            return
    print(f"[jadval] {key} yuborildi")


def auto_poster():
    while True:
        try:
            db = get_db()
            now = datetime.now(config.TZ)
            for key, delta in due(now, db.kv_get):
                db.kv_set(f"sched:{key}", now.strftime("%Y-%m-%d"))  # avval belgilaymiz: takrorlanmasin
                threading.Thread(target=_guard_run, args=(key, delta), daemon=True).start()
        except Exception:  # noqa: BLE001
            log_exc("auto_poster")
        time.sleep(20)


def _guard_run(key, delta):
    try:
        run_slot(key, delta)
    except Exception:  # noqa: BLE001
        log_exc(f"jadval {key}")
        try:
            bot.send_message(config.ADMIN_ID, f"⚠️ Kanal jadvali: «{key}» yuborilmadi. Loglarni tekshiring "
                                              "(bot kanalda admin va post yuborish huquqiga egami?).")
        except Exception:  # noqa: BLE001
            pass


def keep_alive():
    """Bepul hostingda uxlab qolmaslik uchun o'z /health manzilini davriy chaqiradi."""
    if not config.PUBLIC_URL.startswith("https://"):
        return
    while True:
        time.sleep(600)
        try:
            requests.get(f"{config.PUBLIC_URL}/health", timeout=15)
        except Exception:  # noqa: BLE001
            pass
