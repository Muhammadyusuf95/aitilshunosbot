"""Guruh/kanal bellashuvi: lobby, vaqtli quiz (Telegram so'rovnomalari), jonli reyting, /quiz_start va /stop."""
import random
import threading
import time

from telebot.apihelper import ApiTelegramException

from app import config, questions as qmod
from app.db import get_db
from app.handlers.common import bg, friendly_ai_error, on_cb, on_msg, log_exc
from app.handlers.tools import state_handler
from app.runtime import answer_cb, bot, clear_state, display_name
from app.textfmt import esc, send_html
from app.ui import kb, rank_btn

ACTIVE = {}    # chat_id -> dict(cancel, scores, starter, total)
POLLS = {}     # poll_id -> dict(chat_id, correct, sent)
LOBBIES = {}   # match_id -> dict(...)
_quiz_cmd_last = {}
_lobby_lock = threading.Lock()
LETTERS = "ABCD"


# =====================================================================================
#  So'rovnoma yuklamasi
# =====================================================================================
def poll_payload(q, i, total, duration):
    """Telegram cheklovlari: savol <=300, variant <=100, izoh <=200. Sig'masa — matnli kartochka + A/B/C/D so'rovnoma."""
    head = f"[{i}/{total}] "
    options = list(q["options"])
    needs_card = len(head) + len(q["question"]) > 290 or any(len(o) > 100 for o in options)
    card_html = None
    if needs_card:
        lines = [f"<b>{head.strip()}</b> {esc(q['question'])}", ""]
        lines += [f"<b>{LETTERS[k]})</b> {esc(o)}" for k, o in enumerate(options)]
        if duration:
            lines += ["", f"⏳ <i>{duration} soniya</i>"]
        card_html = "\n".join(lines)
        question = f"{head}Javobni tanlang" + (f" ⏳ {duration}s" if duration else "")
        options = list(LETTERS[:len(options)])
    else:
        question = f"{head}{q['question']}"
    expl = (q.get("explanation") or "").strip()
    tail = f"\n👉 {config.CHANNEL_USERNAME}"
    explanation = (expl[: 200 - len(tail)] + tail) if expl else None
    return dict(question=question[:300], options=options, explanation=explanation, card=card_html)


def _chat_is_channel(chat_id):
    try:
        return bot.get_chat(chat_id).type == "channel"
    except Exception:  # noqa: BLE001
        return str(chat_id).startswith("@")


# =====================================================================================
#  Quiz yurgizuvchi
# =====================================================================================
def run_quiz(chat_id, questions, duration, title, starter_id=None):
    if chat_id in ACTIVE:
        send_html(bot, chat_id, "⚠️ Bu yerda test allaqachon davom etmoqda. Tugatish: /stop")
        return
    total = len(questions)
    anonymous = _chat_is_channel(chat_id)
    state = dict(cancel=threading.Event(), scores={}, starter=starter_id, total=total, anonymous=anonymous)
    ACTIVE[chat_id] = state
    try:
        mode_line = ("Kanal rejimi: so'rovnomalar anonim, reyting yuritilmaydi" if anonymous
                     else "Ochiq rejim: reyting to'g'ri javoblar soni va sarflangan vaqt bo'yicha")
        send_html(bot, chat_id,
                  f"🏁 <b>{esc(title.upper())} BOSHLANDI!</b>\n\n"
                  f"▫️ Savollar: <b>{total} ta</b>\n▫️ Har bir savolga: <b>⏳ {duration} soniya</b>\n"
                  f"▫️ {mode_line}\n▫️ To'xtatish: /stop")
        state["cancel"].wait(2)

        for i, q in enumerate(questions, 1):
            if state["cancel"].is_set():
                break
            payload = poll_payload(q, i, total, duration)
            try:
                if payload["card"]:
                    send_html(bot, chat_id, payload["card"])
                sent = time.time()
                msg = bot.send_poll(
                    chat_id, payload["question"], payload["options"], type="quiz",
                    correct_option_id=q["correct_option_id"], explanation=payload["explanation"],
                    is_anonymous=anonymous, open_period=duration,
                )
                POLLS[msg.poll.id] = dict(chat_id=chat_id, correct=q["correct_option_id"], sent=sent)
            except Exception as e:  # noqa: BLE001
                log_exc(f"send_poll {e}")
                send_html(bot, chat_id, "⚠️ So'rovnomani yuborib bo'lmadi. Botga guruhda so'rovnoma yuborish huquqi kerak.")
                break
            state["cancel"].wait(duration + 2)
    finally:
        ACTIVE.pop(chat_id, None)
        _finish_quiz(chat_id, state, title, total)


def _medal(rank):
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"<b>{rank}.</b>")


def _finish_quiz(chat_id, state, title, total):
    scores = state["scores"]
    cancelled = state["cancel"].is_set()
    for pid in [p for p, v in POLLS.items() if v["chat_id"] == chat_id]:
        POLLS.pop(pid, None)

    if state["anonymous"]:
        text = f"🏆 <b>{esc(title.upper())} YAKUNLANDI!</b>\n\nKanalda so'rovnomalar anonim — reyting yuritilmaydi.\n" \
               f"Natijangizni bilish uchun botda ishlang: @{config.BOT_USERNAME}"
    elif not scores:
        text = f"🏆 <b>{esc(title.upper())} {'TO‘XTATILDI' if cancelled else 'YAKUNLANDI'}!</b>\n\nHech kim javob belgilamadi."
    else:
        db = get_db()
        ranked = sorted(scores.items(), key=lambda x: (-x[1]["correct"], x[1]["time"]))
        lines = []
        for rank, (uid, info) in enumerate(ranked[:20], 1):
            pct = round(100 * info["correct"] / total)
            lines.append(f"{_medal(rank)} <b>{esc(info['name'])}</b> — {info['correct']}/{total} ({pct}%) · ⏱ {info['time']:.0f}s")
            try:
                db.ensure_user(uid, info.get("username", ""), info["name"])
                db.record_result(uid, info["name"], "group", title, info["correct"], info["answered"], info["time"])
                if info["correct"]:
                    db.add_points(uid, info["correct"] * 2)
            except Exception:  # noqa: BLE001
                log_exc("save group result")
        text = (f"🏆 <b>{esc(title.upper())} — NATIJALAR</b>\n━━━━━━━━━━━━━━━\n"
                f"👥 Ishtirokchilar: <b>{len(scores)}</b> · Savollar: <b>{total}</b>\n\n" + "\n".join(lines) +
                "\n\n<i>Har bir to'g'ri javob uchun +2 XP berildi.</i>")
    if state["anonymous"]:
        markup = kb([[("🚀 Natijamni botda bilaman", f"https://t.me/{config.BOT_USERNAME}?start=quick", "url")]])
    else:
        markup = kb([[rank_btn("🏆 Umumiy reyting")], [("📢 Kanalga a'zo bo'lish", config.CHANNEL_URL, "url")]])
    try:
        send_html(bot, chat_id, text, reply_markup=markup)
    except Exception:  # noqa: BLE001
        log_exc("finish message")


@bot.poll_answer_handler()
def on_poll_answer(pa):
    try:
        info = POLLS.get(pa.poll_id)
        if not info or not pa.option_ids:
            return
        st = ACTIVE.get(info["chat_id"])
        if not st:
            return
        user = pa.user
        sc = st["scores"].setdefault(user.id, dict(name=display_name(user), username=user.username or "",
                                                   correct=0, answered=0, time=0.0))
        sc["answered"] += 1
        sc["time"] += max(0.1, time.time() - info["sent"])
        if pa.option_ids[0] == info["correct"]:
            sc["correct"] += 1
    except Exception:  # noqa: BLE001
        log_exc("poll_answer")


# =====================================================================================
#  Lobby
# =====================================================================================
def _lobby_markup(mid, count, need):
    return kb([[(f"✋ Men tayyorman ({count}/{need})", f"rdy:{mid}")],
               [("▶️ Hozir boshlash", f"gonow:{mid}"), ("📢 Kanal", config.CHANNEL_URL, "url")]])


def open_lobby(chat_id, questions, duration, title, starter_id):
    mid = f"m{int(time.time()) % 100000}{random.randint(100, 999)}"
    need = config.MIN_PLAYERS
    LOBBIES[mid] = dict(chat_id=chat_id, questions=questions, duration=duration, title=title, starter=starter_id,
                        ready={}, started=False, created=time.time(), need=need)
    text = (f"🧠 <b>{esc(title.upper())}</b>\n━━━━━━━━━━━━━━━\n"
            f"▫️ Savollar: <b>{len(questions)} ta</b>\n▫️ Har biriga: <b>⏳ {duration} soniya</b>\n"
            f"▫️ Reyting: to'g'ri javoblar va tezlik bo'yicha\n\n"
            f"⚠️ Start uchun kamida <b>{need} nafar</b> «Tayyorman»ni bosishi kerak — "
            "yoki boshlovchi «Hozir boshlash»ni bosadi.")
    msg = send_html(bot, chat_id, text, reply_markup=_lobby_markup(mid, 0, need))
    LOBBIES[mid]["msg_id"] = msg.message_id
    LOBBIES[mid]["chat_id_real"] = msg.chat.id
    return mid


def _start_lobby(mid, names, countdown=5):
    m = LOBBIES.get(mid)
    if not m:
        return
    chat_id = m.get("chat_id_real", m["chat_id"])
    try:
        from app.textfmt import edit_html
        edit_html(bot, chat_id, m["msg_id"],
                  f"🎉 <b>Ishtirokchilar yig'ildi!</b> ({esc(', '.join(names[:6]) or '—')})\n\n🚀 Bellashuv {countdown} soniyadan so'ng boshlanadi…")
    except Exception:  # noqa: BLE001
        pass
    time.sleep(countdown)
    LOBBIES.pop(mid, None)
    run_quiz(chat_id, m["questions"], m["duration"], m["title"], m["starter"])


@on_cb("rdy:", gated=False)
def cb_ready(call):
    mid = call.data.split(":", 1)[1]
    with _lobby_lock:
        m = LOBBIES.get(mid)
        if not m or m["started"] or time.time() - m["created"] > config.LOBBY_TTL_SEC:
            answer_cb(call, "Bu bellashuv boshlangan yoki eskirgan.", True)
            return
        uid = call.from_user.id
        if uid in m["ready"]:
            answer_cb(call, "Siz tayyorsiz! Boshqalarni kutyapmiz…")
            return
        m["ready"][uid] = call.from_user.first_name or "Ishtirokchi"
        count = len(m["ready"])
        start_now = count >= m["need"]
        if start_now:
            m["started"] = True
    answer_cb(call, f"Qabul qilindi! ({count}/{m['need']})")
    if start_now:
        bg(_start_lobby, mid, list(m["ready"].values()))
    else:
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=_lobby_markup(mid, count, m["need"]))
        except Exception:  # noqa: BLE001
            pass


@on_cb("gonow:", gated=False)
def cb_go_now(call):
    mid = call.data.split(":", 1)[1]
    with _lobby_lock:
        m = LOBBIES.get(mid)
        if not m or m["started"]:
            answer_cb(call, "Bu bellashuv boshlangan yoki eskirgan.", True)
            return
        if call.from_user.id not in (m["starter"], config.ADMIN_ID):
            answer_cb(call, "Faqat boshlovchi (yoki admin) ishga tushira oladi.", True)
            return
        m["started"] = True
    answer_cb(call, "Boshlanmoqda!")
    bg(_start_lobby, mid, list(m["ready"].values()), 3)


# =====================================================================================
#  Buyruqlar
# =====================================================================================
def _is_chat_admin(chat_id, uid):
    if uid == config.ADMIN_ID:
        return True
    try:
        return bot.get_chat_member(chat_id, uid).status in ("creator", "administrator")
    except Exception:  # noqa: BLE001
        return False


@on_msg(commands=["quiz_start"], gated=False)
def cmd_quiz_start(message):
    if message.chat.type not in ("group", "supergroup"):
        send_html(bot, message.chat.id, "Bu buyruq faqat guruhlarda ishlaydi. Botda test ishlash uchun «🧠 BMB 30» ni tanlang.")
        return
    cid = message.chat.id
    if cid in ACTIVE:
        send_html(bot, cid, "⚠️ Test allaqachon davom etmoqda. To'xtatish: /stop")
        return
    if time.time() - _quiz_cmd_last.get(cid, 0) < 60:
        send_html(bot, cid, "⏳ Iltimos, bir daqiqa kuting.")
        return
    _quiz_cmd_last[cid] = time.time()
    uid = message.from_user.id
    send_html(bot, cid, "⏳ <i>Guruh uchun BMB testi tayyorlanmoqda…</i>")

    def job():
        n = get_db().next_counter("bmb_30")
        try:
            qs, _ = qmod.build_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), 20, sections=None)
        except Exception as e:  # noqa: BLE001
            send_html(bot, cid, friendly_ai_error(e))
            return
        open_lobby(cid, qs, 30, f"№{n} BMB guruh bellashuvi", uid)

    bg(job)


@on_msg(commands=["stop"], gated=False)
def cmd_stop(message):
    st = ACTIVE.get(message.chat.id)
    if not st:
        send_html(bot, message.chat.id, "Hozir davom etayotgan test yo'q.")
        return
    if not (message.from_user.id == st.get("starter") or _is_chat_admin(message.chat.id, message.from_user.id)):
        send_html(bot, message.chat.id, "Testni faqat boshlovchi yoki guruh adminlari to'xtata oladi.")
        return
    st["cancel"].set()
    send_html(bot, message.chat.id, "⛔ Test to'xtatilmoqda…")


# =====================================================================================
#  Testni guruhga yuborish (shaxsiy chatdan)
# =====================================================================================
@state_handler("group_target")
def st_group_target(message, st):
    from app.handlers.tests import PENDING
    uid = message.from_user.id
    target = (message.text or "").strip()
    item = PENDING.get(st["data"].get("qid"))
    clear_state(uid)
    if not item:
        send_html(bot, message.chat.id, "Test ma'lumoti eskirgan. Qaytadan yarating.")
        return
    if target.lstrip("-").isdigit():
        target = int(target)
    try:
        chat = bot.get_chat(target)
        bot.get_chat_member(chat.id, bot.get_me().id)
        if chat.type not in ("group", "supergroup", "channel"):
            raise ValueError("Faqat guruh yoki kanal")
        open_lobby(chat.id, item["questions"], item["duration"], item["title"], uid)
        send_html(bot, message.chat.id,
                  f"✅ <b>{esc(item['title'])}</b> «{esc(chat.title or target)}» ga yuborildi.\n"
                  "Guruhda «Tayyorman» bosilgach (yoki «Hozir boshlash») test boshlanadi.")
    except Exception as e:  # noqa: BLE001
        send_html(bot, message.chat.id,
                  "❌ Yuborib bo'lmadi. Bot o'sha guruhda <b>admin</b> ekanini va username/ID to'g'riligini tekshiring.\n"
                  f"<i>Texnik: {esc(str(e)[:120])}</i>")
