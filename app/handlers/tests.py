"""Testlar: yaratish (BMB, mavzuli, erkin, attestatsiya), yakka mashq rejimi, xatolar ustida ishlash, kun savoli."""
import time
import uuid
from collections import OrderedDict

from app import config, levels, practice, questions as qmod
from app.content import THEME_CATALOG
from app.db import get_db, today_str
from app.handlers.common import bg, friendly_ai_error, guard, on_cb, remember_admin_post
from app.handlers.tools import state_handler
from app.runtime import answer_cb, bot, clear_state, display_name, set_state, show
from app.security import SECURITY_WARNING, check_security_violation, limiter
from app.textfmt import bar, card, edit_html, esc, send_html
from app.ui import kb, rank_btn, view_theme_catalog

LETTERS = "ABCD"
PENDING = OrderedDict()  # qid -> dict(questions, title, owner, duration)
BUILDERS = {}


def store_pending(uid, qs, title, duration=30):
    qid = "q" + uuid.uuid4().hex[:7]
    PENDING[qid] = dict(questions=qs, title=title, owner=uid, duration=duration, created=time.time())
    while len(PENDING) > 120:
        PENDING.popitem(last=False)
    return qid


# =====================================================================================
#  Test yaratish va tarqatish menyusi
# =====================================================================================
def launch_build(chat_id, user, title, builder, duration=30, then="dispatch", extra=None):
    """Savollarni fon oqimida tayyorlaydi. then: 'dispatch' (tarqatish menyusi) yoki 'practice' (darhol mashq)."""
    ok, why = limiter.check(user.id, today_str())
    if not ok:
        send_html(bot, chat_id, why)
        return

    def job():
        status = send_html(bot, chat_id, f"🧠 <i>«{esc(title[:50])}» savollari tayyorlanmoqda…</i>\n"
                                          "<i>Odatda 10-30 soniya oladi.</i>")
        try:
            qs, meta = builder()
        except Exception as e:  # noqa: BLE001
            try:
                bot.delete_message(chat_id, status.message_id)
            except Exception:  # noqa: BLE001
                pass
            send_html(bot, chat_id, friendly_ai_error(e))
            return
        try:
            bot.delete_message(chat_id, status.message_id)
        except Exception:  # noqa: BLE001
            pass
        if then == "practice":
            start_practice(chat_id, user, qs, title)
        elif then == "duel":
            from app.handlers import growth
            growth.create_duel(chat_id, user, qs)
        elif then == "class":
            from app.handlers import growth
            growth.finish_class_task(chat_id, user, qs, title, (extra or {})["code"])
        else:
            offer_dispatch(chat_id, user, qs, title, meta, duration)

    bg(job)


def offer_dispatch(chat_id, user, qs, title, meta=None, duration=30):
    qid = store_pending(user.id, qs, title, duration)
    src = ""
    if meta:
        parts = []
        if meta.get("ai"):
            parts.append(f"🤖 AI: {meta['ai']}")
        if meta.get("bank"):
            parts.append(f"🗂 tasdiqlangan baza: {meta['bank']}")
        src = "▫️ Manba: " + " · ".join(parts) + "\n" if parts else ""
        if meta.get("short"):
            src += f"⚠️ <i>So'ralgan {meta['requested']} tadan {meta['got']} tasi tayyorlandi.</i>\n"
    body = (f"▫️ Savollar: <b>{len(qs)} ta</b>\n{src}\n"
            "<b>Qayerda o'tkazamiz?</b>\n"
            "📝 <b>Mashq</b> — har savoldan so'ng izoh, xatolar daftari, XP\n"
            "⏱ <b>Vaqtli quiz</b> — Telegram so'rovnomasi, soniyalar bilan")
    rows = [
        [("📝 Yakka mashq (tavsiya)", f"go:p:{qid}")],
        [("⏱ 15s", f"go:t15:{qid}"), ("⏱ 30s", f"go:t30:{qid}"), ("⏱ 45s", f"go:t45:{qid}")],
        [("👥 Guruhga yuborish", f"go:g:{qid}"), ("📤 Ulashish", qid, "switch")],
    ]
    if int(user.id) == int(config.ADMIN_ID):
        rows.append([("📢 Kanalga e'lon qilish", f"go:c:{qid}")])
    send_html(bot, chat_id, card("🎉 TEST TAYYOR", esc(title), body), reply_markup=kb(rows))


@on_cb("go:")
def cb_go(call):
    _, mode, qid = call.data.split(":", 2)
    item = PENDING.get(qid)
    if not item:
        answer_cb(call, "Test ma'lumoti eskirgan. Qaytadan yarating.", True)
        return
    chat_id, user = call.message.chat.id, call.from_user
    from app.handlers import group

    if mode == "p":
        answer_cb(call)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:  # noqa: BLE001
            pass
        start_practice(chat_id, user, list(item["questions"]), item["title"])
    elif mode.startswith("t"):
        answer_cb(call, "Test boshlanmoqda!")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:  # noqa: BLE001
            pass
        seconds = int(mode[1:])
        bg(group.run_quiz, chat_id, item["questions"], seconds, item["title"], user.id)
    elif mode == "g":
        answer_cb(call)
        set_state(user.id, "group_target", qid=qid)
        send_html(bot, chat_id, card(
            "👥 GURUHGA YUBORISH", "",
            "1️⃣ Botni guruhga qo'shing va <b>admin</b> qiling.\n"
            "2️⃣ Guruh <b>username</b>ini (<code>@guruhim</code>) yoki <b>ID</b> raqamini (<code>-100123…</code>) yuboring.\n\n"
            "<i>Guruh ichida to'g'ridan-to'g'ri <code>/quiz_start</code> deb yozsangiz ham bo'ladi.\n"
            "Bekor qilish: /cancel</i>"))
    elif mode == "c":
        if int(user.id) != int(config.ADMIN_ID):
            answer_cb(call, "Faqat admin uchun!", True)
            return
        answer_cb(call, "Kanalga yuborilmoqda…")
        group.open_lobby(config.CHANNEL_USERNAME, item["questions"], item["duration"], item["title"], user.id,
                         notify=True)
        show(call, f"✅ <b>{esc(item['title'])}</b> kanalga e'lon qilindi. "
                   f"{config.MIN_PLAYERS} kishi «Tayyorman»ni bosgach boshlanadi.")


# =====================================================================================
#  Test turlari
# =====================================================================================
@on_cb("bmb30")
def cb_bmb30(call):
    answer_cb(call)
    n = get_db().next_counter("bmb_30")
    title = f"№{n} BMB 30 talik test"
    launch_build(call.message.chat.id, call.from_user, title,
                 lambda: qmod.build_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), 30, sections=None))


@on_cb("quick:")
def cb_quick(call):
    count = int(call.data.split(":")[1])
    answer_cb(call)
    launch_build(call.message.chat.id, call.from_user, "⚡ Tezkor test",
                 lambda: qmod.build_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), count, sections=None), then="practice")


@on_cb("themes:")
def cb_themes(call):
    what = call.data.split(":")[1]
    answer_cb(call)
    if what == "catalog":
        show(call, *view_theme_catalog())
    elif what == "custom":
        set_state(call.from_user.id, "theme_custom")
        send_html(bot, call.message.chat.id,
                  "✍️ <b>Erkin mavzu bo'yicha test</b>\nQaysi darslik mavzusidan 30 talik test tuzay? Mavzuni yozing:")


@on_cb("theme:")
def cb_theme(call):
    key = call.data.split(":")[1]
    info = THEME_CATALOG.get(key)
    if not info:
        answer_cb(call)
        return
    answer_cb(call)
    label, prompt, sections = info
    launch_build(call.message.chat.id, call.from_user, f"{label} (30 ta)",
                 lambda: qmod.build_quiz(qmod.theme_prompt(prompt), 30, sections=sections))


@state_handler("theme_custom")
def st_theme_custom(message, st):
    topic = (message.text or "").strip()
    if not topic:
        return
    if not guard(message.chat.id, message.from_user, topic):
        return
    clear_state(message.from_user.id)
    launch_build(message.chat.id, message.from_user, f"«{topic[:40]}» (30 ta)",
                 lambda: qmod.build_quiz(qmod.theme_prompt(topic), 30, free_topic=topic))


@on_cb("attest_start")
def cb_attest(call):
    answer_cb(call)
    n = get_db().next_counter("attestation")
    launch_build(call.message.chat.id, call.from_user, f"№{n} Attestatsiya (Y1·Y2·Y3)",
                 lambda: (qmod.build_attestation(), dict(requested=40, got=40, ai=40, bank=0, short=False)),
                 duration=40)


# ---------------- Erkin mavzu / matn asosidagi quiz konstruktori ----------------
@on_cb("qb:start")
def cb_qb_start(call):
    answer_cb(call)
    set_state(call.from_user.id, "qb_topic")
    send_html(bot, call.message.chat.id, card(
        "✍️ 1-QADAM: MAVZU YOKI MATN", "",
        "Qaysi mavzuda test tuzay? Yozing:\n"
        "▫️ <i>«Boburnoma fitonimlari»</i>, <i>«Qo'shma gap sintaksisi»</i> — mavzu\n"
        "▫️ yoki darslikdan <b>parcha (150+ belgi)</b> — savollar aynan shu matndan tuziladi\n\n"
        "<i>Bekor qilish: /cancel</i>"))


@state_handler("qb_topic")
def st_qb_topic(message, st):
    text = (message.text or "").strip()
    if not text:
        return
    if not guard(message.chat.id, message.from_user, text):
        return
    clear_state(message.from_user.id)
    _ask_count(message.chat.id, message.from_user.id, text)


def start_builder_from_passage(call, text):
    _ask_count(call.message.chat.id, call.from_user.id, text)


def _ask_count(chat_id, uid, text):
    passage = len(text) > 150
    BUILDERS[uid] = dict(topic=text[:4000], passage=passage)
    label = "matn asosida" if passage else f"«{esc(text[:60])}»"
    rows = [[(f"{n} ta", f"qb:n:{n}") for n in (5, 10, 15)], [(f"{n} ta", f"qb:n:{n}") for n in (20, 30)]]
    send_html(bot, chat_id, card("📊 2-QADAM: SAVOLLAR SONI", label, "Nechta savol bo'lsin?"), reply_markup=kb(rows))


@on_cb("qb:n:")
def cb_qb_count(call):
    count = int(call.data.split(":")[2])
    b = BUILDERS.get(call.from_user.id)
    if not b:
        answer_cb(call, "Avval mavzuni kiriting.", True)
        return
    answer_cb(call)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:  # noqa: BLE001
        pass
    topic, passage = b["topic"], b["passage"]
    if passage:
        title = f"Matn asosidagi test ({count} ta)"
        builder = lambda: qmod.build_quiz(qmod.theme_prompt("berilgan matn"), count, passage=topic)  # noqa: E731
    else:
        title = f"«{topic[:40]}» testi ({count} ta)"
        builder = lambda: qmod.build_quiz(qmod.theme_prompt(topic), count, free_topic=topic)  # noqa: E731
    launch_build(call.message.chat.id, call.from_user, title, builder)


# =====================================================================================
#  Yakka mashq rejimi
# =====================================================================================
def question_view(s, chosen=None, skipped=False):
    q = s.current()
    i = s.idx + 1
    done_n = s.idx + (1 if s.answered else 0)
    head = f"<b>Savol {i}/{s.total}</b>   {bar(done_n, s.total)}"
    meta = []
    if q.get("bolim"):
        meta.append(f"<i>{esc(q['bolim'])}</i>")
    if s.run >= 3:
        meta.append(f"🔥 {s.run} ketma-ket")
    lines = [head] + ([" · ".join(meta)] if meta else []) + ["", esc(q["question"]), ""]
    for k, opt in enumerate(q["options"]):
        mark = ""
        if s.answered:
            if k == q["correct_option_id"]:
                mark = "✅ "
            elif k == chosen:
                mark = "❌ "
        lines.append(f"{mark}<b>{LETTERS[k]})</b> {esc(opt)}")
    if s.answered:
        verdict = "⏭ <b>O'tkazildi.</b>" if skipped else (
            "✅ <b>To'g'ri!</b>" if chosen == q["correct_option_id"] else
            f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{LETTERS[q['correct_option_id']]}</b>")
        lines += ["", verdict]
        if q.get("explanation"):
            lines.append(f"<blockquote>💡 {esc(q['explanation'])}</blockquote>")
        last = s.idx + 1 >= s.total
        markup = kb([[("🏁 Natijani ko'rish" if last else "Keyingi ➡️", f"pn:{s.sid}:{s.idx}")]])
    else:
        rows = [[(LETTERS[k], f"pq:{s.sid}:{s.idx}:{k}") for k in range(4)],
                [("⏭ O'tkazish", f"ps:{s.sid}:{s.idx}"), ("⛔ Tugatish", f"pe:{s.sid}")]]
        markup = kb(rows)
    return "\n".join(lines), markup


def summary_view(s, info):
    answered = max(info["answered"], 1)
    secs = int(s.time_spent)
    acc = info["accuracy"]
    if acc >= 90:
        verdict = "🏆 A'lo natija! Siz tayyorsiz."
    elif acc >= 70:
        verdict = "👍 Yaxshi! Yana bir oz mashq — va mukammal."
    elif acc >= 50:
        verdict = "📈 O'rtacha. Xatolar ustida ishlash foyda beradi."
    else:
        verdict = "💪 Boshlanish shunday bo'ladi. Xatolarni takrorlang — natija tez o'sadi."
    body = [
        f"✅ To'g'ri: <b>{s.correct}/{info['answered']}</b>  ({acc}%)",
        bar(s.correct, answered, 12),
        f"⏱ Vaqt: <b>{secs // 60:02d}:{secs % 60:02d}</b>   🔥 Eng uzun seriya: <b>{s.best_run}</b>",
        "",
        verdict,
        "",
        f"➕ <b>{info['xp']} XP</b> olindi",
        levels.level_line(info["points"]),
    ]
    if info.get("level_up"):
        lv = info["level_up"]
        body += ["", f"🎉 <b>Yangi daraja: {lv[2]} {lv[1]}!</b>"]
    for code in info.get("new_badges", []):
        body += ["", f"🏅 Yangi nishon: <b>{levels.badge_title(code)}</b>"]
    mistakes = get_db().count_mistakes(s.uid)
    rows = []
    if mistakes:
        rows.append([(f"🔁 Xatolar ustida ishlash ({mistakes})", "review:start")])
    rows.append([("🖼 Natija kartochkasi", "rescard"), ("⚔️ Do'st bilan bellashuv", "duel:new")])
    rows.append([("⚡ Yana tezkor test", "quick:10"), ("🧠 BMB 30", "bmb30")])
    rows.append([rank_btn(), (f"📤 Ulashish", f"{s.correct}/{info['answered']} natija", "switch")])
    return card("🏁 NATIJA", esc(s.title), "\n".join(body)), kb(rows)


def start_practice(chat_id, user, qs, title, mode="practice", ctx=None):
    s = practice.create(user.id, display_name(user), title, qs, mode, chat_id, ctx)
    html, markup = question_view(s)
    send_html(bot, chat_id, html, reply_markup=markup)


def _session_or_alert(call, sid, idx=None):
    s = practice.get(call.from_user.id, sid)
    if not s or s.finished:
        answer_cb(call, "Bu test yakunlangan yoki eskirgan.", True)
        return None
    if idx is not None and idx != s.idx:
        answer_cb(call, "Bu savol allaqachon yopilgan.", True)
        return None
    return s


@on_cb("pq:")
def cb_practice_answer(call):
    _, sid, idx, k = call.data.split(":")
    s = _session_or_alert(call, sid, int(idx))
    if not s:
        return
    if s.answered:
        answer_cb(call, "Javob allaqachon qabul qilindi.")
        return
    ok, q = s.answer(int(k))
    practice.record_answer(s, q, ok)
    answer_cb(call, "✅ To'g'ri!" if ok else "❌ Noto'g'ri")
    html, markup = question_view(s, chosen=int(k))
    show(call, html, markup)


@on_cb("ps:")
def cb_practice_skip(call):
    _, sid, idx = call.data.split(":")
    s = _session_or_alert(call, sid, int(idx))
    if not s or s.answered:
        return
    q = s.current()
    s.skip()
    practice.record_skip(s, q)
    answer_cb(call, "O'tkazildi")
    html, markup = question_view(s, skipped=True)
    show(call, html, markup)


def _finish(call, s):
    info = practice.finalize(s)
    practice.drop(s.uid)
    html, markup = summary_view(s, info)
    if s.ctx:
        from app.handlers import growth
        extra = growth.session_done(s, info)
        if extra:
            html += "\n\n" + extra
    show(call, html, markup)


@on_cb("pn:")
def cb_practice_next(call):
    _, sid, idx = call.data.split(":")
    s = _session_or_alert(call, sid, int(idx))
    if not s:
        return
    answer_cb(call)
    if s.advance():
        html, markup = question_view(s)
        show(call, html, markup)
    else:
        _finish(call, s)


@on_cb("pe:")
def cb_practice_end(call):
    s = _session_or_alert(call, call.data.split(":")[1])
    if not s:
        return
    answer_cb(call, "Test yakunlandi")
    if s.answered:
        s.idx += 1
        s.answered = False
    s.finished = True
    _finish(call, s)


# ---------------- Xatolar ustida ishlash ----------------
@on_cb("review:start")
def cb_review(call):
    answer_cb(call)
    db = get_db()
    mistakes = db.get_mistakes(call.from_user.id, 10)
    if not mistakes:
        send_html(bot, call.message.chat.id,
                  card("🎉 XATOLAR DAFTARI BO'SH", "", "Hozircha takrorlashga savol yo'q. Yangi test ishlang — "
                       "adashgan savollar shu yerga tushadi."),
                  reply_markup=kb([[("⚡ Tezkor test", "quick:10")]]))
        return
    qs = [qmod.shuffle_options(m) for m in mistakes]
    start_practice(call.message.chat.id, call.from_user, qs, "Xatolar ustida ishlash", mode="review")


# =====================================================================================
#  Kun savoli
# =====================================================================================
def start_daily(obj):
    user = obj.from_user
    chat_id = obj.message.chat.id if hasattr(obj, "data") else obj.chat.id
    db = get_db()
    row = db.get_user(user.id) or {}
    today = today_str()
    if row.get("daily_done") == today:
        send_html(bot, chat_id, card(
            "⚡ KUN SAVOLI", "Bugungi savolga allaqachon javob berdingiz ✅",
            "Yangi savol ertaga ochiladi. Hozircha mashq qilib turing:"),
            reply_markup=kb([[("⚡ Tezkor test", "quick:10"), ("🔁 Xatolar", "review:start")]]))
        return
    q = qmod.daily_question()
    if not q:
        send_html(bot, chat_id, "Hozircha savol mavjud emas.")
        return
    lines = [esc(q["question"]), ""] + [f"<b>{LETTERS[k]})</b> {esc(o)}" for k, o in enumerate(q["options"])]
    rows = [[(LETTERS[k], f"dq:{k}") for k in range(4)]]
    send_html(bot, chat_id, card("⚡ KUN SAVOLI", f"{today} · to'g'ri javob +15 XP", "\n".join(lines)),
              reply_markup=kb(rows))


@on_cb("dq:")
def cb_daily_answer(call):
    k = int(call.data.split(":")[1])
    db = get_db()
    uid = call.from_user.id
    today = today_str()
    row = db.get_user(uid) or {}
    if row.get("daily_done") == today:
        answer_cb(call, "Bugun javob berib bo'ldingiz.", True)
        return
    q = qmod.daily_question()
    ok = k == q["correct_option_id"]
    db.mark_daily_done(uid, today)
    xp = 15 if ok else 3
    points = db.add_points(uid, xp)
    if not ok:
        db.add_mistake(uid, qmod.qkey(q), q)
    badge = ""
    if db.kv_incr(f"daily:{uid}") >= 7 and db.award_badge(uid, "daily_7"):
        badge = f"\n\n🏅 Yangi nishon: <b>{levels.badge_title('daily_7')}</b>"
    lines = [esc(q["question"]), ""]
    for i, o in enumerate(q["options"]):
        mark = "✅ " if i == q["correct_option_id"] else ("❌ " if i == k else "")
        lines.append(f"{mark}<b>{LETTERS[i]})</b> {esc(o)}")
    verdict = f"✅ <b>To'g'ri! +{xp} XP</b>" if ok else f"❌ <b>Noto'g'ri.</b> Ishtirokingiz uchun +{xp} XP"
    lines += ["", verdict]
    if q.get("explanation"):
        lines.append(f"<blockquote>💡 {esc(q['explanation'])}</blockquote>")
    lines += ["", levels.level_line(points)]
    answer_cb(call, "✅ To'g'ri!" if ok else "❌ Noto'g'ri")
    show(call, card("⚡ KUN SAVOLI", "Natija", "\n".join(lines) + badge),
         kb([[("⚡ Tezkor test", "quick:10"), rank_btn("🏆 Reyting")]]))


# ---------------- Chuqur havola: /start qz_xxx ----------------
def start_shared_quiz(chat_id, user, qid):
    item = PENDING.get(qid)
    if not item:
        send_html(bot, chat_id, "⌛ Bu testning muddati tugagan. Quyidagi tugma bilan yangisini boshlang:",
                  reply_markup=kb([[("⚡ Tezkor test (10 ta)", "quick:10")]]))
        return
    start_practice(chat_id, user, list(item["questions"]), item["title"])
