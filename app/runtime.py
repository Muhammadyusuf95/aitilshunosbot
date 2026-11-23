"""Umumiy ish muhiti: bot obyekti, foydalanuvchi holati (state), obuna tekshiruvi, navigatsiya yordamchilari."""
import threading
import time

import telebot
from telebot.apihelper import ApiTelegramException

from app import config
from app.textfmt import edit_html, send_html

bot = telebot.TeleBot(
    config.TELEGRAM_TOKEN or "0:missing-token",
    parse_mode=None,
    threaded=True,
    num_threads=config.NUM_THREADS,
)

# ---------------- Foydalanuvchi holati (kiritish kutilayotgan bosqichlar) ----------------
_STATE = {}
_STATE_TTL = 30 * 60
_state_lock = threading.Lock()


def set_state(uid, action, **data):
    with _state_lock:
        _STATE[uid] = dict(action=action, data=data, ts=time.time())


def get_state(uid):
    with _state_lock:
        st = _STATE.get(uid)
        if st and time.time() - st["ts"] > _STATE_TTL:
            _STATE.pop(uid, None)
            return None
        return st


def clear_state(uid):
    with _state_lock:
        _STATE.pop(uid, None)


# ---------------- Obuna tekshiruvi ----------------
_sub_cache = {}
_SUB_TTL_OK = 120
_SUB_TTL_NO = 5
_warned = False


def is_subscribed(uid):
    global _warned
    if uid == config.ADMIN_ID:
        return True
    hit = _sub_cache.get(uid)
    if hit and time.time() - hit[1] < (_SUB_TTL_OK if hit[0] else _SUB_TTL_NO):
        return hit[0]
    try:
        cm = bot.get_chat_member(config.CHANNEL_USERNAME, uid)
        ok = cm.status in ("creator", "administrator", "member", "restricted")
    except ApiTelegramException as e:
        msg = str(e).lower()
        if "user not found" in msg or "participant_id_invalid" in msg:
            ok = False
        else:
            # Odatda bot kanalda admin emas — foydalanuvchilarni qulflab qo'ymaymiz.
            if not _warned:
                print(f"[sub] Obunani tekshirib bo'lmadi ({e}). Bot kanalga admin sifatida qo'shilganini tekshiring.")
                _warned = True
            ok = True
    except Exception:  # noqa: BLE001 - tarmoq xatosi
        ok = True
    _sub_cache[uid] = (ok, time.time())
    return ok


def invalidate_sub(uid):
    _sub_cache.pop(uid, None)


# ---------------- Navigatsiya ----------------
def chat_of(obj):
    """Message yoki CallbackQuery dan chat_id."""
    return obj.message.chat.id if hasattr(obj, "message") and obj.message is not None and hasattr(obj, "data") \
        else obj.chat.id


def show(obj, html_text, markup=None):
    """CallbackQuery bo'lsa xabarni joyida yangilaydi, aks holda yangi xabar yuboradi."""
    if hasattr(obj, "data") and getattr(obj, "message", None) is not None:
        try:
            edit_html(bot, obj.message.chat.id, obj.message.message_id, html_text, markup)
            return obj.message
        except ApiTelegramException:
            return send_html(bot, obj.message.chat.id, html_text, reply_markup=markup)
    return send_html(bot, obj.chat.id, html_text, reply_markup=markup)


def answer_cb(call, text=None, alert=False):
    try:
        bot.answer_callback_query(call.id, text=text, show_alert=alert)
    except Exception:  # noqa: BLE001
        pass


def display_name(user):
    name = user.first_name or "Ishtirokchi"
    if getattr(user, "last_name", None):
        name += f" {user.last_name}"
    return name


def webapp_url():
    return f"{config.PUBLIC_URL}/leaderboard" if config.PUBLIC_URL.startswith("https://") else None
