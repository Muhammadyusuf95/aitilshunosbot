"""Fon vazifalar: kanalga kunlik avto-post (Tashkent vaqti, qayta ishga tushishga chidamli) va Render uyg'otgich."""
import random
import time
from datetime import datetime

import requests

from app import ai, config, questions as qmod
from app.db import get_db
from app.handlers.common import log_exc
from app.runtime import bot
from app.textfmt import esc, md_to_html

# (kalit, soat, daqiqa)
SLOTS = [("morning", 8, 30), ("evening", 20, 30)]
GRACE_MIN = 90  # belgilangan vaqtdan keyin shuncha daqiqagacha kechikib bo'lsa ham yuboriladi


def _post_morning():
    from app.handlers.admin import generate_didactic
    kind = random.choice(["hikmat", "motiv"])
    text = generate_didactic(kind).split("📚 Aniq manba:")[0].strip()
    post = f"{md_to_html(text)}\n\n───────────────\n🌟 <a href=\"{config.CHANNEL_URL}\">{esc(config.CHANNEL_USERNAME)}</a>"
    bot.send_message(config.CHANNEL_USERNAME, post, parse_mode="HTML", disable_web_page_preview=True)


def _post_evening():
    try:
        qs = ai.generate_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), 3)
    except Exception:  # noqa: BLE001
        qs = []
    if len(qs) < 3:
        qs = (qs + qmod.random_bank_questions(3))[:3]
    bot.send_message(config.CHANNEL_USERNAME,
                     "🌙 <b>Kechki mashq vaqti!</b>\nUch savol — bilimingizni sinab ko'ring 👇", parse_mode="HTML")
    from app.handlers.group import poll_payload
    for i, q in enumerate(qs, 1):
        p = poll_payload(q, i, len(qs), 0)
        if p["card"]:
            bot.send_message(config.CHANNEL_USERNAME, p["card"], parse_mode="HTML")
        bot.send_poll(config.CHANNEL_USERNAME, p["question"], p["options"], type="quiz",
                      correct_option_id=q["correct_option_id"], explanation=p["explanation"], is_anonymous=True)
        time.sleep(1.5)


JOBS = {"morning": _post_morning, "evening": _post_evening}


def auto_poster():
    while True:
        try:
            now = datetime.now(config.TZ)
            today = now.strftime("%Y-%m-%d")
            db = get_db()
            for key, h, m in SLOTS:
                late = (now.hour * 60 + now.minute) - (h * 60 + m)
                if 0 <= late <= GRACE_MIN and db.kv_get(f"autopost:{key}") != today:
                    db.kv_set(f"autopost:{key}", today)  # avval belgilaymiz: xato bo'lsa ham takrorlanmasin
                    try:
                        JOBS[key]()
                        print(f"[autopost] {key} yuborildi")
                    except Exception:  # noqa: BLE001
                        log_exc(f"autopost {key}")
        except Exception:  # noqa: BLE001
            log_exc("auto_poster")
        time.sleep(60)


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
