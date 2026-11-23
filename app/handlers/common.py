"""Handlerlar uchun umumiy vositalar: dekoratorlar (obuna tekshiruvi, xatolarni ushlash), fon oqimlar, AI natijasini yetkazish."""
import functools
import threading
import time
import traceback
from collections import OrderedDict

from app import ai, config
from app.db import get_db, today_str
from app.runtime import answer_cb, bot, is_subscribed
from app.security import (BLOCKED_TEXT, SECURITY_WARNING, check_hard_violation, check_security_violation,
                          limiter, strikes)
from app.textfmt import card, esc, md_to_html, send_html, send_long
from app.ui import kb, rank_btn

_touch_cache = {}
ADMIN_POSTS = OrderedDict()  # kanalga yuborish uchun matnlar (oxirgi 60 ta)


def remember_admin_post(text):
    pid = f"p{int(time.time())}{len(ADMIN_POSTS) % 100}"
    ADMIN_POSTS[pid] = text
    while len(ADMIN_POSTS) > 60:
        ADMIN_POSTS.popitem(last=False)
    return pid


def log_exc(where):
    print(f"[xato] {where}:\n{traceback.format_exc()}")


def bg(fn, *args, **kwargs):
    """Uzoq davom etadigan ishni alohida oqimda ishga tushiradi (handler oqimini band qilmaydi)."""
    def runner():
        try:
            fn(*args, **kwargs)
        except Exception:  # noqa: BLE001
            log_exc(getattr(fn, "__name__", "bg"))

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t


def touch(user):
    """Kunlik faollik/seriya (kuniga bir marta DB ga yoziladi, qolganda xotiradan)."""
    today = today_str()
    hit = _touch_cache.get(user.id)
    if hit and hit["day"] == today:
        return dict(hit["res"], gained=0, new_day=False, broken=False, is_new_user=False)
    try:
        res = get_db().touch_user(user, today)
    except Exception:  # noqa: BLE001
        log_exc("touch_user")
        return dict(streak=1, gained=0, broken=False, new_day=False, is_new_user=False, prev_streak=0, points=0)
    _touch_cache[user.id] = dict(day=today, res=res)
    if res.get("new_day"):
        _after_streak(user.id, res["streak"])
    return res


def _after_streak(uid, streak):
    db = get_db()
    for days, code in ((3, "streak_3"), (7, "streak_7"), (30, "streak_30")):
        if streak >= days:
            try:
                db.award_badge(uid, code)
            except Exception:  # noqa: BLE001
                pass


def send_subscription_prompt(chat_id):
    markup = kb([[("✨ Rasmiy kanalga a'zo bo'lish", config.CHANNEL_URL, "url")],
                 [("🔄 Obunani tasdiqlash", "check_sub")]])
    text = card(
        "🏛 ILMIY-METODIK HAMJAMIYAT", "AI Tilshunos xizmatlaridan to'liq foydalanish uchun",
        f"Rasmiy ta'limiy kanalimizga obuna bo'ling:\n👉 <a href=\"{config.CHANNEL_URL}\">{esc(config.CHANNEL_USERNAME)}</a>\n\n"
        "Obuna bo'lgach, pastdagi tugma bilan tasdiqlang.")
    send_html(bot, chat_id, text, reply_markup=markup)


def on_msg(**handler_kwargs):
    """Xabar handleri: xatolarni ushlaydi; shaxsiy chatda — seriya va obuna tekshiruvi."""
    gated = handler_kwargs.pop("gated", True)

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(message):
            try:
                if message.chat.type == "private" and message.from_user:
                    touch(message.from_user)
                    if gated and not is_subscribed(message.from_user.id):
                        send_subscription_prompt(message.chat.id)
                        return
                fn(message)
            except Exception:  # noqa: BLE001
                log_exc(fn.__name__)
                try:
                    bot.send_message(message.chat.id, "⚠️ Kutilmagan xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
                except Exception:  # noqa: BLE001
                    pass

        bot.message_handler(**handler_kwargs)(wrapper)
        return fn

    return deco


def on_cb(*prefixes, gated=True):
    """Callback handleri: prefiks bo'yicha ulanadi; xatolarni ushlaydi; shaxsiy chatda obunani tekshiradi."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(call):
            try:
                msg = call.message
                if gated and msg is not None and msg.chat.type == "private":
                    touch(call.from_user)
                    if not is_subscribed(call.from_user.id):
                        answer_cb(call, "Avval kanalga a'zo bo'ling", True)
                        send_subscription_prompt(msg.chat.id)
                        return
                fn(call)
            except Exception:  # noqa: BLE001
                log_exc(fn.__name__)
                answer_cb(call, "⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.", True)

        bot.callback_query_handler(func=lambda c, p=prefixes: bool(c.data) and c.data.startswith(p))(wrapper)
        return fn

    return deco


# ---------------- AI natijasini yetkazish ----------------
def friendly_ai_error(e):
    if isinstance(e, ai.OffTopic):
        return SECURITY_WARNING
    low = str(e).lower()
    if "api key" in low or "api_key" in low or "permission_denied" in low or "403" in low or "401" in low:
        return "🔧 AI kaliti (GEMINI_API_KEY) noto'g'ri yoki ruxsati yo'q. Administratorga xabar bering."
    if "gemini_api_key" in low:
        return "🔧 AI xizmati hali sozlanmagan (GEMINI_API_KEY). Administratorga xabar bering."
    if "429" in low or "quota" in low or "exhausted" in low:
        return "⏳ AI hozir band (kvota). 1 daqiqadan so'ng qayta urinib ko'ring."
    return "⚠️ AI hozircha javob bera olmadi. Birozdan so'ng qayta urinib ko'ring."


def result_markup(user_id, tool_key=None, admin_post=None):
    rows = []
    if tool_key:
        rows.append([("🔄 Yana so'rov", f"tool:{tool_key}")])
    if admin_post and int(user_id) == int(config.ADMIN_ID):
        rows.append([("📢 Kanalga yuborish", f"adm:post:{admin_post}"), ("❌ Yopish", "adm:cancel")])
    rows.append([("📤 Ulashish", "AI Tilshunos", "switch"), rank_btn("🏆 Reyting")])
    return kb(rows)


def violation(chat_id, user):
    """Qoidabuzarlikni qayd etadi, foydalanuvchiga ogohlantirish yuboradi; 3-marta bo'lsa 24 soatga cheklaydi."""
    count, blocked = strikes.add(user.id)
    if blocked:
        send_html(bot, chat_id, BLOCKED_TEXT)
        try:
            name = esc(user.first_name or "")
            send_html(bot, config.ADMIN_ID, f"🚨 <b>{name}</b> (<code>{user.id}</code>) takroriy qoidabuzarlik tufayli "
                                            f"24 soatga cheklandi. Bekor qilish: <code>/unblock {user.id}</code>")
        except Exception:  # noqa: BLE001
            pass
    else:
        send_html(bot, chat_id, SECURITY_WARNING + f"\n\n<i>Ogohlantirish: {count}/{strikes.LIMIT}</i>")


def guard(chat_id, user, text):
    """Kirish matnini tekshiradi. True — davom etish mumkin."""
    if strikes.is_blocked(user.id):
        send_html(bot, chat_id, BLOCKED_TEXT)
        return False
    if check_security_violation(text):
        violation(chat_id, user)
        return False
    return True


def run_ai_text(chat_id, user, prompt, title, tool_key=None, check_text=None, vision=None):
    """AI so'rovini xavfsizlik filtri, limit va xatolarga chidamli tarzda bajaradi va natijani yetkazadi."""
    uid = user.id
    if strikes.is_blocked(uid):
        send_html(bot, chat_id, BLOCKED_TEXT)
        return False
    if check_text is not None and check_security_violation(check_text):
        violation(chat_id, user)
        return False
    ok, why = limiter.check(uid, today_str())
    if not ok:
        send_html(bot, chat_id, why)
        return False

    status = send_html(bot, chat_id, "⏳ <i>Ekspert tahlil qilmoqda…</i>")
    try:
        bot.send_chat_action(chat_id, "typing")
    except Exception:  # noqa: BLE001
        pass
    try:
        text = ai.generate_vision(prompt, *vision) if vision else ai.generate_text(prompt)
    except Exception as e:  # noqa: BLE001
        try:
            bot.delete_message(chat_id, status.message_id)
        except Exception:  # noqa: BLE001
            pass
        if isinstance(e, ai.OffTopic):
            violation(chat_id, user)
            return False
        retry = kb([[("🔄 Qayta urinish", f"tool:{tool_key}")]]) if tool_key else None
        detail = f"\n\n<b>Admin uchun sabab:</b>\n<code>{esc(str(e)[:350])}</code>" if int(uid) == int(config.ADMIN_ID) else ""
        print(f"[ai-xato] {e}")
        send_html(bot, chat_id, friendly_ai_error(e) + detail, reply_markup=retry)
        return False

    try:
        bot.delete_message(chat_id, status.message_id)
    except Exception:  # noqa: BLE001
        pass
    if check_hard_violation(text):  # chiqish filtri
        send_html(bot, chat_id, SECURITY_WARNING)
        return False
    pid = remember_admin_post(text) if int(uid) == int(config.ADMIN_ID) else None
    body = (f"## {title}\n\n{text}\n\n"
            "──────────────\n"
            "_⚠️ AI yordamchi vosita: muhim joylarni darslik va lug'at bilan solishtiring._\n"
            f"✨ @{config.BOT_USERNAME} · {config.CHANNEL_USERNAME}")
    send_long(bot, chat_id, body, reply_markup=result_markup(uid, tool_key, pid))
    return True
