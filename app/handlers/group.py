"""Guruh/kanal bellashuvi: lobby (2 kishi tayyor bo'lgach start), vaqtli quiz, pauza/davom etish, reyting, /quiz_start va /stop."""
import random
import threading
import time
from datetime import datetime

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
#
#  Qoidalar (v12.2):
#   • So'rovnomalar YOPILMAYDI (open_period yo'q): test tugagach kirgan odam ham avval o'z variantini
#     belgilaydi, shundan keyingina to'g'ri javob va izohni ko'radi. Javob belgilamaganga savol
#     ishlanmagandek ko'rinadi (Telegram quiz so'rovnomasining tabiiy xulqi).
#   • Reytingga faqat savol vaqti ichida berilgan javoblar kiradi.
#   • Ketma-ket PAUSE_AFTER_MISSES ta savolga hech kim javob bermasa, test pauza qilinadi va
#     kamida bir kishi «Davom etish»ni bosgach davom etadi. Pauza vaqti on_pause(soniya) orqali
#     kanal jadvaliga uzatiladi (keyingi testlar shuncha vaqtga suriladi).
# =====================================================================================
ANSWER_GRACE = 2          # savol vaqtidan keyin javoblarni qabul qilish uchun qo'shimcha soniya
PAUSE_AFTER_MISSES = 2    # nechta savol ketma-ket javobsiz qolsa — pauza
LOBBY_COUNTDOWN = 5       # ishtirokchilar yig'ilgach boshlanishgacha soniya
PAUSES = {}               # token -> quiz state (Davom etish tugmasi uchun)


def _pause_max_sec():
    return max(60, int(config.QUIZ_PAUSE_MAX_MIN) * 60)


def _channel_post_url(chat_id, message_id):
    """Ommaviy kanal posti havolasi (faqat asosiy kanal uchun; maxfiy guruhlar uchun havola yasalmaydi)."""
    uname = str(config.CHANNEL_USERNAME).lstrip("@")
    if str(chat_id).lstrip("@").lower() == uname.lower() and uname:
        return f"https://t.me/{uname}/{message_id}"
    return None


def _wait_pause(chat_id, state, remaining, scheduled):
    """Pauza: «Davom etish» bosilguncha (yoki /stop, yoki chegaraviy vaqt) kutadi. (davom_etdimi, soniya)."""
    token = f"{int(time.time()) % 100000}{random.randint(100, 999)}"
    state["resume"] = threading.Event()
    state["paused"] = True
    PAUSES[token] = state
    max_sec = _pause_max_sec()
    tail = ("\n\n<i>Kanal jadvalidagi keyingi testlar pauza davomiyligiga ortga suriladi.</i>" if scheduled else "")
    text = (f"⏸ <b>TEST PAUZA QILINDI</b>\n\n"
            f"Ketma-ket {PAUSE_AFTER_MISSES} ta savolga hech kim javob bermadi.\n"
            f"Kamida bir kishi «▶️ Davom etish»ni bossa, test qolgan <b>{remaining} ta</b> savol bilan davom etadi.\n"
            f"⏳ {max_sec // 60} daqiqa ichida davom ettirilmasa, test yakunlanadi.{tail}")
    t0 = time.time()
    msg = None
    try:
        msg = send_html(bot, chat_id, text, reply_markup=kb([[("▶️ Davom etish", f"qcont:{token}")]]))
    except Exception:  # noqa: BLE001
        log_exc("pause message")
    resumed = False
    try:
        while True:
            if state["resume"].wait(1):
                resumed = True
                break
            if state["cancel"].is_set() or time.time() - t0 >= max_sec:
                break
    finally:
        PAUSES.pop(token, None)
        state["paused"] = False
    paused = time.time() - t0
    state["pause_total"] = state.get("pause_total", 0) + paused
    if msg is not None:
        if resumed:
            who = state.get("resumed_by")
            note = f" — <b>{esc(who)}</b> davom ettirdi" if who and not state["anonymous"] else ""
            done = f"▶️ <b>Test davom etmoqda!</b>{note}\n⏸ Pauza: {_fmt_dur(paused)}"
        else:
            done = "⏹ <b>Pauza tugadi</b> — test davom ettirilmadi va yakunlandi."
        try:
            from app.textfmt import edit_html
            edit_html(bot, msg.chat.id, msg.message_id, done, None)
        except Exception:  # noqa: BLE001
            pass
    return resumed, paused


def _fmt_dur(sec):
    sec = int(round(sec))
    m, s = divmod(sec, 60)
    return f"{m} daq. {s} s" if m else f"{s} s"


def run_quiz(chat_id, questions, duration, title, starter_id=None, on_pause=None):
    """Testni yurgizadi. on_pause(soniya) — har bir pauzadan keyin chaqiriladi (kanal jadvalini surish uchun)."""
    if chat_id in ACTIVE:
        send_html(bot, chat_id, "⚠️ Bu yerda test allaqachon davom etmoqda. Tugatish: /stop")
        return
    total = len(questions)
    anonymous = _chat_is_channel(chat_id)
    channel_test = None
    if anonymous:
        # Kanal so'rovnomalari anonim: kim javob berganini bilib bo'lmaydi. Shu sababli test savollari
        # saqlanadi va reyting botda, shu testni ishlaganlar orasida yuritiladi.
        try:
            channel_test = get_db().add_channel_test(title, questions, duration)
        except Exception:  # noqa: BLE001
            log_exc("save channel test")
    state = dict(cancel=threading.Event(), resume=threading.Event(), paused=False, scores={}, starter=starter_id,
                 total=total, anonymous=anonymous, pause_total=0.0, first_msg=None, asked=0,
                 channel_test=channel_test)
    ACTIVE[chat_id] = state
    try:
        mode_line = ("Kanal rejimi: so'rovnomalar anonim; reyting botda yuritiladi" if anonymous
                     else "Reyting: vaqtida berilgan to'g'ri javoblar soni va tezlik bo'yicha")
        start = send_html(bot, chat_id,
                          f"🏁 <b>{esc(title.upper())} BOSHLANDI!</b>\n\n"
                          f"▫️ Savollar: <b>{total} ta</b>\n▫️ Har bir savolga: <b>⏳ {duration} soniya</b>\n"
                          f"▫️ {mode_line}\n"
                          f"▫️ Ketma-ket {PAUSE_AFTER_MISSES} ta savol javobsiz qolsa — pauza\n"
                          "▫️ Savollar yopilmaydi: keyin kirganlar ham javob belgilab, izohni ko'ra oladi"
                          + ("" if anonymous else "\n▫️ To'xtatish: /stop"))
        state["first_msg"] = getattr(start, "message_id", None)
        state["cancel"].wait(2)

        misses = 0
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
                    is_anonymous=anonymous,
                )
                info = dict(chat_id=chat_id, correct=q["correct_option_id"], sent=sent, open=True, votes=0)
                POLLS[msg.poll.id] = info
            except Exception as e:  # noqa: BLE001
                log_exc(f"send_poll {e}")
                send_html(bot, chat_id, "⚠️ So'rovnomani yuborib bo'lmadi. Botga guruhda so'rovnoma yuborish huquqi kerak.")
                break
            state["asked"] = i
            state["cancel"].wait(duration + ANSWER_GRACE)
            info["open"] = False  # reyting oynasi yopildi; so'rovnomaning o'zi ochiq qoladi
            misses = 0 if info["votes"] > 0 else misses + 1
            if misses >= PAUSE_AFTER_MISSES and i < total and not state["cancel"].is_set():
                resumed, paused = _wait_pause(chat_id, state, total - i, scheduled=on_pause is not None)
                if on_pause:
                    try:
                        on_pause(paused)
                    except Exception:  # noqa: BLE001
                        log_exc("on_pause")
                if not resumed:
                    break
                misses = 0
                state["cancel"].wait(2)
    finally:
        ACTIVE.pop(chat_id, None)
        _finish_quiz(chat_id, state, title, total)
    return state


def _medal(rank):
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"<b>{rank}.</b>")


def _finish_quiz(chat_id, state, title, total):
    scores = state["scores"]
    cancelled = state["cancel"].is_set()
    for pid in [p for p, v in POLLS.items() if v["chat_id"] == chat_id]:
        POLLS.pop(pid, None)

    later = ("\n\n📝 <i>Savollar ochiq qoldi: testga kechikkanlar ham javobini belgilab, "
             "to'g'ri javob va izohni ko'rishi mumkin.</i>")
    nxt = ""
    try:
        from app import scheduler
        nxt = scheduler.next_quiz_line()
    except Exception:  # noqa: BLE001
        pass
    nxt = f"\n⏭ Keyingi kanal testi: <b>{esc(nxt)}</b>" if nxt and state["anonymous"] else ""

    if state["anonymous"]:
        text = (f"🏆 <b>{esc(title.upper())} YAKUNLANDI!</b>\n\nKanalda so'rovnomalar anonim, shuning uchun reyting "
                f"botda yuritiladi: testni botda ishlaganlar orasida.\n"
                f"🏆 Jonli reytingni ko'rish uchun pastdagi tugmani bosing." + later + nxt)
    elif not scores:
        text = (f"🏆 <b>{esc(title.upper())} {'TO‘XTATILDI' if cancelled else 'YAKUNLANDI'}!</b>\n\n"
                "Vaqtida javob belgilagan ishtirokchi bo'lmadi." + later)
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
                "\n\n<i>Har bir to'g'ri javob uchun +2 XP berildi.</i>" + later)
    if state.get("pause_total"):
        text += f"\n⏸ Umumiy pauza: {_fmt_dur(state['pause_total'])}"
    rows = []
    first = state.get("first_msg")
    url = _channel_post_url(chat_id, first) if first else None
    if url:
        rows.append([("📌 Test boshiga o'tish", url, "url")])
    if state["anonymous"]:
        tid = state.get("channel_test")
        if tid:
            rows.append([("🏆 Test reytingi (botda)", f"https://t.me/{config.BOT_USERNAME}?start=ct_{tid}", "url")])
        rows.append([("🚀 Natijamni botda bilaman", f"https://t.me/{config.BOT_USERNAME}?start=quick", "url")])
    else:
        rows += [[rank_btn("🏆 Umumiy reyting")], [("📢 Kanalga a'zo bo'lish", config.CHANNEL_URL, "url")]]
    try:
        send_html(bot, chat_id, text, reply_markup=kb(rows))
    except Exception:  # noqa: BLE001
        log_exc("finish message")


@bot.poll_answer_handler()
def on_poll_answer(pa):
    """Ochiq (anonim bo'lmagan) so'rovnomalar: faqat savol vaqti ichidagi javoblar hisoblanadi."""
    try:
        info = POLLS.get(pa.poll_id)
        if not info or not pa.option_ids or not info.get("open", True):
            return
        st = ACTIVE.get(info["chat_id"])
        if not st:
            return
        info["votes"] = info.get("votes", 0) + 1
        user = pa.user
        sc = st["scores"].setdefault(user.id, dict(name=display_name(user), username=user.username or "",
                                                   correct=0, answered=0, time=0.0))
        sc["answered"] += 1
        sc["time"] += max(0.1, time.time() - info["sent"])
        if pa.option_ids[0] == info["correct"]:
            sc["correct"] += 1
    except Exception:  # noqa: BLE001
        log_exc("poll_answer")


@bot.poll_handler(func=lambda p: True)
def on_poll_update(poll):
    """Anonim (kanal) so'rovnomalar: kim javob berganini bilmaymiz, lekin ovozlar sonini bilamiz."""
    try:
        info = POLLS.get(poll.id)
        if info and info.get("open", True):
            info["votes"] = max(info.get("votes", 0), int(poll.total_voter_count or 0))
    except Exception:  # noqa: BLE001
        log_exc("poll_update")


@on_cb("qcont:", gated=False)
def cb_continue(call):
    st = PAUSES.get(call.data.split(":", 1)[1])
    if not st or not st.get("paused"):
        answer_cb(call, "Test allaqachon davom etmoqda yoki yakunlangan.")
        return
    st["resumed_by"] = display_name(call.from_user)
    st["resume"].set()
    answer_cb(call, "▶️ Test davom etmoqda!")


# =====================================================================================
#  Lobby: test faqat MIN_PLAYERS (standart: 2) kishi «Tayyorman»ni bosgach boshlanadi
# =====================================================================================
def _lobby_markup(mid, count, need, share=None):
    rows = [[(f"✋ Men tayyorman ({count}/{need})", f"rdy:{mid}")]]
    second = []
    if share:
        second.append(("📣 Do'stni chaqirish", share, "url"))
    second.append(("📢 Kanal", config.CHANNEL_URL, "url"))
    rows.append(second)
    return kb(rows)


def _share_link(chat_id, msg_id, title):
    from urllib.parse import quote
    url = _channel_post_url(chat_id, msg_id)
    if not url:
        return None
    text = f"«{title}» boshlanmoqda — yana bir kishi «Tayyorman»ni bossa start! Birga ishlaymizmi?"
    return f"https://t.me/share/url?url={quote(url, safe='')}&text={quote(text)}"


def open_lobby(chat_id, questions, duration, title, starter_id, deadline=None, on_pause=None,
               blocking=False, notify=False):
    """Lobby ochadi. deadline — epoch soniya (shu vaqtgacha yig'ilmasa lobby yopiladi).
    blocking=True bo'lsa, shu oqimda kutadi va testni yurgizadi (kanal jadvali uchun); natija: True/False."""
    mid = f"m{int(time.time()) % 100000}{random.randint(100, 999)}"
    need = max(1, int(config.MIN_PLAYERS))
    deadline = deadline or (time.time() + config.LOBBY_TTL_SEC)
    is_channel = _chat_is_channel(chat_id)
    m = dict(chat_id=chat_id, questions=questions, duration=duration, title=title, starter=starter_id,
             ready={}, started=False, created=time.time(), deadline=deadline, need=need, go=threading.Event(),
             on_pause=on_pause, channel=is_channel, share=None)
    LOBBIES[mid] = m
    until = datetime.fromtimestamp(deadline, config.TZ).strftime("%H:%M")
    text = (f"🧠 <b>{esc(title.upper())}</b>\n━━━━━━━━━━━━━━━\n"
            f"▫️ Savollar: <b>{len(questions)} ta</b>\n▫️ Har biriga: <b>⏳ {duration} soniya</b>\n"
            f"▫️ Ketma-ket {PAUSE_AFTER_MISSES} ta savol javobsiz qolsa — pauza\n\n"
            f"✋ Test <b>{need} kishi</b> «Men tayyorman»ni bosgach boshlanadi.\n"
            f"⏰ Lobby <b>{until}</b> gacha ochiq.")
    msg = send_html(bot, chat_id, text, reply_markup=_lobby_markup(mid, 0, need))
    m["msg_id"] = msg.message_id
    m["chat_id_real"] = msg.chat.id
    share = _share_link(chat_id, msg.message_id, title)
    if share:
        m["share"] = share
        try:
            bot.edit_message_reply_markup(msg.chat.id, msg.message_id, reply_markup=_lobby_markup(mid, 0, need, share))
        except Exception:  # noqa: BLE001
            pass
    if notify:
        url = _channel_post_url(chat_id, msg.message_id)
        if url:
            try:
                from app.handlers import growth
                bg(growth.send_quiz_alerts, title, url)
            except Exception:  # noqa: BLE001
                log_exc("quiz alerts")
    if blocking:
        return _lobby_wait(mid)
    bg(_lobby_wait, mid)
    return mid


def _lobby_wait(mid):
    """Ishtirokchilar yig'ilishini (yoki muddat tugashini) kutadi. Test o'tkazilgan bo'lsa — True."""
    m = LOBBIES.get(mid)
    if not m:
        return False
    chat_real = m.get("chat_id_real", m["chat_id"])
    from app.textfmt import edit_html
    while not m["go"].wait(1):
        if time.time() >= m["deadline"]:
            break
    with _lobby_lock:
        ready_now = m["go"].is_set()
        m["started"] = True  # endi tugmalar qabul qilinmaydi
        LOBBIES.pop(mid, None)
    if not ready_now:
        nxt = ""
        if m["channel"]:
            try:
                from app import scheduler
                line = scheduler.next_quiz_line()
                nxt = f"\n⏭ Keyingi test: <b>{esc(line)}</b>" if line else ""
            except Exception:  # noqa: BLE001
                pass
        try:
            edit_html(bot, chat_real, m["msg_id"],
                      f"⌛ <b>{esc(m['title'])}</b>\n\nBelgilangan vaqtgacha {m['need']} kishi yig'ilmadi — "
                      f"test o'tkazilmadi ({len(m['ready'])}/{m['need']}).{nxt}\n\n"
                      f"Yakka mashq qilish: @{config.BOT_USERNAME}", None)
        except Exception:  # noqa: BLE001
            pass
        return False
    names = list(m["ready"].values())
    who = (f" ({esc(', '.join(names[:6]))})" if not m["channel"] else "")
    try:
        edit_html(bot, chat_real, m["msg_id"],
                  f"🎉 <b>{len(names)} kishi tayyor!</b>{who}\n\n🚀 «{esc(m['title'])}» {LOBBY_COUNTDOWN} soniyadan so'ng boshlanadi…",
                  None)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(LOBBY_COUNTDOWN)
    run_quiz(m["chat_id"], m["questions"], m["duration"], m["title"], m["starter"], on_pause=m.get("on_pause"))
    return True


@on_cb("rdy:", gated=False)
def cb_ready(call):
    mid = call.data.split(":", 1)[1]
    with _lobby_lock:
        m = LOBBIES.get(mid)
        if not m or m["started"] or m["go"].is_set() or time.time() > m["deadline"]:
            answer_cb(call, "Bu test boshlangan yoki lobby yopilgan.", True)
            return
        uid = call.from_user.id
        if uid in m["ready"]:
            answer_cb(call, f"Siz tayyorsiz! Yana {m['need'] - len(m['ready'])} kishi kerak…")
            return
        m["ready"][uid] = call.from_user.first_name or "Ishtirokchi"
        count = len(m["ready"])
        if count >= m["need"]:
            m["go"].set()
    answer_cb(call, f"Qabul qilindi! ({count}/{m['need']})")
    if count < m["need"]:
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=_lobby_markup(mid, count, m["need"], m.get("share")))
        except Exception:  # noqa: BLE001
            pass


@on_cb("gonow:", gated=False)
def cb_go_now(call):
    """Eski xabarlardagi tugma uchun: endi test faqat yetarli ishtirokchi yig'ilgach boshlanadi."""
    answer_cb(call, f"Test {config.MIN_PLAYERS} kishi «Tayyorman»ni bosgach avtomatik boshlanadi.", True)


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
                  f"Guruhda {config.MIN_PLAYERS} kishi «Tayyorman»ni bosgach test boshlanadi.")
    except Exception as e:  # noqa: BLE001
        send_html(bot, message.chat.id,
                  "❌ Yuborib bo'lmadi. Bot o'sha guruhda <b>admin</b> ekanini va username/ID to'g'riligini tekshiring.\n"
                  f"<i>Texnik: {esc(str(e)[:120])}</i>")
