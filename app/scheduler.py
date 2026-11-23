"""Kanal uchun kunlik avtomatik jadval (Toshkent vaqti; BOT_TZ bilan o'zgartiriladi) va Render uyg'otgich.

Jadval:
  07:30  Kun savoli
  19:30  Tezkor 10 talik test
  20:00  Mavzulashtirilgan test (30 ta; mavzu har kuni almashadi)
  20:30  BMB 30 talik test
  21:00  Attestatsiya testi (40 ta)
Savollar belgilangan vaqtdan 3 daqiqa oldin tayyorlanadi, vaqti kelganda yuboriladi. Testlar bir-biriga
qo'shilib ketmasligi uchun ketma-ket yuritiladi. Qayta ishga tushish bo'lsa, 60 daqiqagacha kechikkan vazifa bajariladi
va bir kunda ikki marta yuborilmaydi (holat bazada saqlanadi).
"""
import threading
import time
from datetime import datetime

import requests

from app import ai, config, questions as qmod
from app.content import THEME_CATALOG
from app.db import get_db
from app.handlers.common import log_exc
from app.runtime import bot
from app.textfmt import esc

SLOTS = [("daily", 7, 30), ("quick", 19, 30), ("theme", 20, 0), ("bmb", 20, 30), ("attest", 21, 0)]
PREP_MIN = 3
GRACE_MIN = 60
DURATIONS = {"quick": 30, "theme": 30, "bmb": 30, "attest": 45}  # har bir savolga soniya
_channel_lock = threading.Lock()


def due(now, kv_get):
    """Hozir ishga tushirilishi kerak bo'lgan vazifalar: [(kalit, daqiqa_farqi)]. Bir kunda bir marta."""
    today = now.strftime("%Y-%m-%d")
    out = []
    for key, h, m in SLOTS:
        delta = (now.hour * 60 + now.minute) - (h * 60 + m)
        if -PREP_MIN <= delta <= GRACE_MIN and kv_get(f"sched:{key}") != today:
            out.append((key, delta))
    return out


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
                     parse_mode="HTML")
    p = poll_payload(q, 1, 1, 0)
    p["question"] = p["question"].replace("[1/1] ", "", 1)
    if p["card"]:
        bot.send_message(config.CHANNEL_USERNAME, p["card"].replace("[1/1]", "").strip(), parse_mode="HTML")
    bot.send_poll(config.CHANNEL_USERNAME, p["question"], p["options"], type="quiz",
                  correct_option_id=q["correct_option_id"], explanation=p["explanation"], is_anonymous=True)


def _wait_until(now_delta_min):
    """Belgilangan daqiqaga (delta<0 — hali vaqt bo'lmagan) qadar kutadi."""
    if now_delta_min < 0:
        time.sleep(max(0, -now_delta_min * 60 - datetime.now(config.TZ).second))


def run_slot(key, delta, wait=True):
    """Bitta vazifani bajaradi: avval tayyorlaydi, so'ng vaqti kelganda yuboradi."""
    content = None
    if key != "daily":
        content = build_job(key)
    if wait:
        _wait_until(delta)
    with _channel_lock:
        if key == "daily":
            send_daily_question()
        else:
            from app.handlers.group import run_quiz
            title, qs, duration = content
            run_quiz(config.CHANNEL_USERNAME, qs, duration, title, None)
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
