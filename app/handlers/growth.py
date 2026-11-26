"""O'sish funksiyalari: imtihon sanasi, eslatmalar, haftalik g'oliblar, do'st bilan bellashuv, sinf rejimi, natija kartochkasi."""
import io
import json
import random
import re
import time
import uuid
from datetime import datetime, timedelta

from telebot.apihelper import ApiTelegramException

from app import config, levels, practice
from app import questions as qmod
from app.db import get_db, today_str
from app.handlers.common import bg, guard, log_exc, on_cb, on_msg
from app.handlers.tools import state_handler
from app.runtime import answer_cb, bot, clear_state, display_name, set_state, show
from app.textfmt import card, esc, send_html
from app.ui import kb, rank_btn

BOT_LINK = f"https://t.me/{config.BOT_USERNAME}"


def share_url(link, text):
    from urllib.parse import quote
    return f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(text)}"


# =====================================================================================
#  1. Imtihon sanasi
# =====================================================================================
EXAMS = {"cert": "Milliy sertifikat", "bmb": "BMB (DTM)", "att": "Attestatsiya", "other": "Imtihon"}


def parse_date(text):
    t = (text or "").strip().replace("/", ".").replace("-", ".")
    for fmt in ("%d.%m.%Y", "%Y.%m.%d", "%d.%m.%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def days_left(date_str):
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - datetime.now(config.TZ).date()).days


def exam_line(row):
    n = days_left((row or {}).get("exam_date"))
    if n is None or n < 0:
        return ""
    name = row.get("exam_name") or "Imtihon"
    if n == 0:
        return f"📅 <b>{esc(name)} — bugun!</b> Omad!"
    return f"📅 {esc(name)}gacha: <b>{n} kun</b>"


def exam_plan(n):
    """(kuniga savol soni, matn)."""
    if n > 60:
        return 10, "Vaqt ko'p — har kuni <b>10 ta</b> savol va haftada 1 ta esse yozing."
    if n > 30:
        return 15, "Faol bosqich — har kuni <b>15 ta</b> savol, haftada 2 ta esse, xatolar ustida ishlash."
    if n > 7:
        return 20, "Qizg'in bosqich — har kuni <b>20 ta</b> savol, 3 kunda 1 ta esse, xatolarni takrorlash."
    return 10, "So'nggi hafta — yangi mavzu o'rganmang: <b>xatolar ustida ishlang</b> va kuniga 10 ta tezkor test."


def exam_view(uid):
    row = get_db().get_user(uid) or {}
    n = days_left(row.get("exam_date"))
    if n is not None and n >= 0:
        per, plan = exam_plan(n)
        body = f"{exam_line(row)}\n\n🎯 <b>Kunlik reja</b>\n{plan}"
        rows = [[(f"⚡ Bugungi mashq ({per} ta)", f"quick:{per}"), ("🔁 Xatolar", "review:start")],
                [("✏️ Sanani o'zgartirish", "exam:change"), ("🗑 O'chirish", "exam:del")],
                [("🔙 Yana bo'limlar", "hub:more")]]
    else:
        body = "Imtihon sanasini kiriting — bot kunlar sanog'ini yuritadi va mos kunlik reja beradi."
        rows = [[(v, f"exam:t:{k}")] for k, v in EXAMS.items()] + [[("🔙 Yana bo'limlar", "hub:more")]]
    return card("📅 IMTIHON SANOG'I", "Tayyorgarlik rejasi", body), kb(rows)


@on_cb("exam:hub")
def cb_exam_hub(call):
    answer_cb(call)
    show(call, *exam_view(call.from_user.id))


@on_cb("exam:change")
def cb_exam_change(call):
    answer_cb(call)
    show(call, card("📅 IMTIHON TURI", "", "Qaysi imtihon?"),
         kb([[(v, f"exam:t:{k}")] for k, v in EXAMS.items()]))


@on_cb("exam:t:")
def cb_exam_type(call):
    key = call.data.split(":")[2]
    answer_cb(call)
    set_state(call.from_user.id, "exam_date", name=EXAMS.get(key, "Imtihon"))
    send_html(bot, call.message.chat.id, "📅 Imtihon sanasini yozing: <code>KK.OO.YYYY</code>\n"
                                          "Masalan: <code>15.03.2027</code>\n<i>Bekor qilish: /cancel</i>")


@state_handler("exam_date")
def st_exam_date(message, st):
    d = parse_date(message.text)
    today = datetime.now(config.TZ).date()
    if not d or d < today or d > today + timedelta(days=730):
        send_html(bot, message.chat.id, "❌ Sana noto'g'ri yoki o'tib ketgan. Format: <code>KK.OO.YYYY</code>")
        return
    clear_state(message.from_user.id)
    get_db().set_exam(message.from_user.id, st["data"]["name"], d.strftime("%Y-%m-%d"))
    html, markup = exam_view(message.from_user.id)
    send_html(bot, message.chat.id, "✅ Saqlandi!\n\n" + html, reply_markup=markup)


@on_cb("exam:del")
def cb_exam_del(call):
    answer_cb(call, "O'chirildi")
    get_db().set_exam(call.from_user.id, None, None)
    show(call, *exam_view(call.from_user.id))


# =====================================================================================
#  2. Eslatmalar
# =====================================================================================
def _toggle_reminders(uid):
    db = get_db()
    row = db.get_user(uid) or {}
    new = not bool(row.get("reminders") if row.get("reminders") is not None else 1)
    db.set_reminders(uid, new)
    return new


@on_cb("rem:toggle")
def cb_rem_toggle(call):
    on = _toggle_reminders(call.from_user.id)
    answer_cb(call, "🔔 Eslatmalar yoqildi" if on else "🔕 Eslatmalar o'chirildi", True)


@on_msg(commands=["eslatma"])
def cmd_eslatma(message):
    on = _toggle_reminders(message.from_user.id)
    send_html(bot, message.chat.id, "🔔 Eslatmalar <b>yoqildi</b>." if on else "🔕 Eslatmalar <b>o'chirildi</b>.")


@on_cb("daily:open")
def cb_daily_open(call):
    answer_cb(call)
    from app.handlers import tests
    tests.start_daily(call)


def send_reminders():
    """Seriyasi uzilish arafasidagi (kecha kirgan) va 3 kundan beri kirmagan foydalanuvchilarga bir martalik eslatma."""
    db = get_db()
    rows = db.users_for_reminder([today_str(-1), today_str(-3)])
    sent = 0
    for r in rows:
        name = esc(r.get("first_name") or "do'st")
        line = ""
        n = days_left(r.get("exam_date"))
        if n is not None and 0 <= n <= 60:
            line = f"\n📅 {esc(r.get('exam_name') or 'Imtihon')}gacha <b>{n} kun</b> qoldi."
        if r["last_active"] == today_str(-1):
            text = (f"🔥 <b>{name}</b>, seriyangiz <b>{(r.get('streak') or 1)} kun</b>!\n"
                    f"Bugun hali kirmadingiz — bitta savol bilan seriyani saqlab qoling.{line}\n\n"
                    "<i>Eslatmalarni o'chirish: /eslatma</i>")
        else:
            text = (f"👋 <b>{name}</b>, sizni sog'indik!\nKun savoli sizni kutyapti — 1 daqiqada +15 XP olasiz.{line}\n\n"
                    "<i>Eslatmalarni o'chirish: /eslatma</i>")
        try:
            bot.send_message(r["user_id"], text, parse_mode="HTML",
                             reply_markup=kb([[("⚡ Kun savoli", "daily:open")]]))
            sent += 1
        except ApiTelegramException as e:
            if e.error_code == 403:
                db.set_status(r["user_id"], "blocked")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.06)
    print(f"[eslatma] {sent}/{len(rows)} yuborildi")
    return sent


# =====================================================================================
#  2a. Kanal testi xabarnomasi (ixtiyoriy, faqat foydalanuvchi roziligi bilan) va /jadval
# =====================================================================================
_ALERT_GAP_SEC = 20 * 60
_last_alert = [0.0]


def _toggle_quiz_alerts(uid):
    db = get_db()
    row = db.get_user(uid) or {}
    new = not bool(row.get("quiz_alerts") or 0)
    db.set_quiz_alerts(uid, new)
    return new


def _alerts_text(on):
    return ("🔔 Kanal testlari xabarnomasi <b>yoqildi</b>.\nKanalda test lobbisi ochilganda sizga qisqa xabar keladi — "
            "«Tayyorman»ni bosib, testni boshlashga yordam berasiz.\n\n<i>O'chirish: /testxabar</i>"
            if on else "🔕 Kanal testlari xabarnomasi <b>o'chirildi</b>. Qayta yoqish: /testxabar")


@on_cb("qal:toggle")
def cb_quiz_alerts(call):
    on = _toggle_quiz_alerts(call.from_user.id)
    answer_cb(call)
    send_html(bot, call.message.chat.id, _alerts_text(on))


@on_msg(commands=["testxabar"])
def cmd_testxabar(message):
    if message.chat.type != "private":
        return
    send_html(bot, message.chat.id, _alerts_text(_toggle_quiz_alerts(message.from_user.id)))


def send_quiz_alerts(title, url):
    """Lobby ochilganda roziligini bergan foydalanuvchilarga bitta xabar (spamga qarshi: 20 daqiqada 1 marta)."""
    now = time.time()
    if now - _last_alert[0] < _ALERT_GAP_SEC:
        return 0
    _last_alert[0] = now
    db = get_db()
    rows = db.users_for_quiz_alert()
    sent = 0
    for r in rows:
        try:
            bot.send_message(r["user_id"],
                             f"🧠 Kanalda <b>{esc(title)}</b> lobbisi ochildi!\n"
                             f"{config.MIN_PLAYERS} kishi «Tayyorman»ni bosgach test boshlanadi.\n\n"
                             "<i>Xabarnomani o'chirish: /testxabar</i>",
                             parse_mode="HTML", reply_markup=kb([[("✋ Lobbiga o'tish", url, "url")]]))
            sent += 1
        except ApiTelegramException as e:
            if e.error_code == 403:
                db.set_status(r["user_id"], "blocked")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.06)  # Telegram cheklovi: ~30 xabar/soniya dan oshmaslik
    print(f"[test-xabar] {sent}/{len(rows)} yuborildi")
    return sent


def schedule_card():
    from app import scheduler
    return card("📅 KANAL JADVALI", f"Bugun · {config.CHANNEL_USERNAME}", scheduler.schedule_view())


@on_msg(commands=["jadval"], gated=False)
def cmd_jadval(message):
    send_html(bot, message.chat.id, schedule_card(),
              reply_markup=kb([[("📢 Kanalga o'tish", config.CHANNEL_URL, "url")],
                               [("🔔 Test xabarnomasi", "qal:toggle")]]) if message.chat.type == "private" else None)


@on_cb("sched:view")
def cb_schedule(call):
    answer_cb(call)
    show(call, schedule_card(), kb([[("🔔 Test xabarnomasi", "qal:toggle"), ("📢 Kanal", config.CHANNEL_URL, "url")],
                                    [("🔙 Yana bo'limlar", "hub:more")]]))


# =====================================================================================
#  3. Haftalik g'oliblar
# =====================================================================================
WEEKLY_XP = {1: 50, 2: 30, 3: 20}
WEEKLY_PRIZE = __import__("os").environ.get("WEEKLY_PRIZE", "")


def post_weekly():
    db = get_db()
    rows = [r for r in db.leaderboard("week", 20) if int(r["total"] or 0) >= 10][:3]
    if not rows:
        return False
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, r in enumerate(rows, 1):
        total = int(r["total"] or 0)
        pct = round(100 * int(r["correct"] or 0) / total)
        lines.append(f"{medals[i]} <b>{esc(r['name'] or 'Ishtirokchi')}</b> — {int(r['correct'])} to'g'ri · {pct}%")
        db.award_badge(r["user_id"], "weekly_winner")
        db.add_points(r["user_id"], WEEKLY_XP[i])
        try:
            bot.send_message(r["user_id"], f"{medals[i]} <b>Tabriklaymiz!</b> Siz haftalik reytingda <b>{i}-o'rin</b>ni "
                                           f"egalladingiz.\n➕ <b>{WEEKLY_XP[i]} XP</b> va «{levels.badge_title('weekly_winner')}» nishoni berildi!",
                             parse_mode="HTML")
        except Exception:  # noqa: BLE001
            pass
    prize = f"\n\n🎁 <b>Sovrin:</b> {esc(WEEKLY_PRIZE)}" if WEEKLY_PRIZE else ""
    text = (f"🏆 <b>HAFTA BILIMDONLARI</b>\n━━━━━━━━━━━━━━━\n\n" + "\n".join(lines) + prize +
            "\n\nKeyingi hafta g'olib siz bo'lishingiz mumkin! 👇")
    bot.send_message(config.CHANNEL_USERNAME, text, parse_mode="HTML",
                     reply_markup=kb([[("🚀 Botda ishtirok etish", f"{BOT_LINK}?start=quick", "url")]]))
    return True


# =====================================================================================
#  4. Do'st bilan bellashuv (1-ga-1)
# =====================================================================================
def _duel_get(did):
    raw = get_db().kv_get(f"duel:{did}")
    return json.loads(raw) if raw else None


def _duel_save(did, d):
    get_db().kv_set(f"duel:{did}", json.dumps(d, ensure_ascii=False))


@on_cb("duel:new")
def cb_duel_new(call):
    answer_cb(call)
    from app.handlers.tests import launch_build
    launch_build(call.message.chat.id, call.from_user, "⚔️ Bellashuv savollari",
                 lambda: qmod.build_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), 10, sections=None), then="duel")


def create_duel(chat_id, user, qs):
    from app.handlers.tests import start_practice
    did = "d" + uuid.uuid4().hex[:7]
    _duel_save(did, dict(questions=qs, creator=user.id, created=time.time(),
                         players={str(user.id): dict(name=display_name(user), done=False)}, settled=False))
    link = f"{BOT_LINK}?start=duel_{did}"
    send_html(bot, chat_id, card(
        "⚔️ BELLASHUV TAYYOR", "10 savol · bir xil savollar · tezlik hisobga olinadi",
        f"Avval o'zingiz yeching, so'ng havolani do'stingizga yuboring:\n<code>{link}</code>\n\n"
        "G'olib: ko'proq to'g'ri javob, teng bo'lsa — tezroq."),
        reply_markup=kb([[("📤 Do'stga yuborish", share_url(link, "Ona tili bo'yicha bellashuvga chaqiraman! Yenga olasanmi? 😎"), "url")]]))
    start_practice(chat_id, user, list(qs), "⚔️ Bellashuv", mode="duel", ctx=dict(duel=did))


def open_duel(chat_id, user, did):
    d = _duel_get(did)
    if not d:
        send_html(bot, chat_id, "⌛ Bu bellashuv topilmadi yoki muddati o'tgan.")
        return
    uid = str(user.id)
    players = d["players"]
    link = f"{BOT_LINK}?start=duel_{did}"
    if uid in players:
        p = players[uid]
        if p["done"]:
            send_html(bot, chat_id, f"Siz bu bellashuvni yakunlagansiz: <b>{p['correct']}/{p['total']}</b>. "
                                    "Raqib natijasi kelganda xabar beraman.")
        else:
            from app.handlers.tests import start_practice
            start_practice(chat_id, user, list(d["questions"]), "⚔️ Bellashuv", mode="duel", ctx=dict(duel=did))
        return
    if len(players) >= 2:
        send_html(bot, chat_id, "Bu bellashuvda ikkala o'rin ham band. O'zingiz yangisini boshlang:",
                  reply_markup=kb([[("⚔️ Yangi bellashuv", "duel:new")]]))
        return
    creator = next(iter(players.values()))
    status = (f"U <b>{creator['correct']}/{creator['total']}</b> natija ko'rsatdi — uni yenga olasizmi? 😎"
              if creator.get("done") else "U hozir o'ynayapti — siz ham boshlang!")
    send_html(bot, chat_id, card("⚔️ BELLASHUVGA CHAQIRUV", "", f"<b>{esc(creator['name'])}</b> sizni bellashuvga chaqirdi.\n{status}"),
              reply_markup=kb([[("🔥 Qabul qilaman", f"duel:join:{did}")]]))


@on_cb("duel:join:")
def cb_duel_join(call):
    did = call.data.split(":")[2]
    d = _duel_get(did)
    uid = str(call.from_user.id)
    if not d or (uid not in d["players"] and len(d["players"]) >= 2):
        answer_cb(call, "Bellashuv band yoki eskirgan.", True)
        return
    answer_cb(call)
    if uid not in d["players"]:
        d["players"][uid] = dict(name=display_name(call.from_user), done=False)
        _duel_save(did, d)
    from app.handlers.tests import start_practice
    start_practice(call.message.chat.id, call.from_user, list(d["questions"]), "⚔️ Bellashuv", mode="duel",
                   ctx=dict(duel=did))


def _duel_session_done(s, info):
    did = s.ctx["duel"]
    d = _duel_get(did)
    if not d:
        return ""
    me = str(s.uid)
    d["players"].setdefault(me, dict(name=s.name))
    d["players"][me].update(done=True, correct=s.correct, total=s.total, time=round(s.time_spent, 1))
    other_id = next((k for k in d["players"] if k != me), None)
    other = d["players"].get(other_id) if other_id else None
    text = ""
    if other and other.get("done") and not d.get("settled"):
        d["settled"] = True
        a, b = d["players"][me], other
        key = lambda p: (-p["correct"], p["time"])  # noqa: E731
        win_id = me if key(a) < key(b) else other_id if key(b) < key(a) else None
        db = get_db()
        res = (f"⚔️ <b>BELLASHUV NATIJASI</b>\n\n"
               f"<b>{esc(a['name'])}</b>: {a['correct']}/{a['total']} · {a['time']:.0f}s\n"
               f"<b>{esc(b['name'])}</b>: {b['correct']}/{b['total']} · {b['time']:.0f}s\n\n")
        if win_id:
            wname = d["players"][win_id]["name"]
            res += f"🏆 G'olib: <b>{esc(wname)}</b> (+20 XP)"
            db.add_points(int(win_id), 20)
            db.award_badge(int(win_id), "duelist")
            lose_id = other_id if win_id == me else me
            db.add_points(int(lose_id), 5)
        else:
            res += "🤝 <b>Durang!</b> (+10 XP ikkalasiga)"
            db.add_points(int(me), 10)
            db.add_points(int(other_id), 10)
        text = res
        try:
            bot.send_message(int(other_id), res, parse_mode="HTML",
                             reply_markup=kb([[("🔁 Qayta bellashuv", "duel:new")]]))
        except Exception:  # noqa: BLE001
            pass
    elif not other:
        link = f"{BOT_LINK}?start=duel_{did}"
        text = ("⏳ Do'stingiz hali qo'shilmadi. Havolani yuboring:\n" f"<code>{link}</code>")
    else:
        text = "⏳ Raqibingiz hali yakunlamadi. Natija tayyor bo'lganda xabar beraman."
    _duel_save(did, d)
    return text


# =====================================================================================
#  5. Sinf rejimi
# =====================================================================================
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CLS_BUILD = {}


def _new_code():
    db = get_db()
    for _ in range(20):
        code = "".join(random.choice(CODE_ALPHABET) for _ in range(6))
        if not db.get_class(code):
            return code
    raise RuntimeError("kod yaratilmadi")


def cls_hub_view(uid):
    db = get_db()
    rows = [[("➕ Sinf yaratish (o'qituvchi)", "cls:new"), ("📋 Mening sinflarim", "cls:mine")],
            [("🎒 Sinfga qo'shilish", "cls:join")]]
    if db.student_classes(uid):
        rows.append([("📝 Topshiriqlarim", "cls:tasks")])
    rows.append([("🔙 Yana bo'limlar", "hub:more")])
    body = ("👨‍🏫 <b>O'qituvchi:</b> sinf yarating → o'quvchilar kod orqali qo'shiladi → mavzu bering → AI savol tuzadi → "
            "natijalarni ko'rasiz.\n🎒 <b>O'quvchi:</b> o'qituvchi kodini kiriting va topshiriqlarni bajaring.")
    return card("🏫 SINF REJIMI", "O'qituvchi va o'quvchilar uchun", body), kb(rows)


@on_cb("cls:hub")
def cb_cls_hub(call):
    answer_cb(call)
    show(call, *cls_hub_view(call.from_user.id))


@on_cb("cls:new")
def cb_cls_new(call):
    answer_cb(call)
    set_state(call.from_user.id, "cls_name")
    send_html(bot, call.message.chat.id, "🏫 Sinf nomini yozing (masalan: <i>9-«A» sinf</i>):")


@state_handler("cls_name")
def st_cls_name(message, st):
    name = (message.text or "").strip()[:60]
    if len(name) < 2:
        send_html(bot, message.chat.id, "Nom juda qisqa.")
        return
    if not guard(message.chat.id, message.from_user, name):
        return
    clear_state(message.from_user.id)
    code = _new_code()
    get_db().create_class(code, message.from_user.id, name)
    show_class(message, code, "✅ Sinf yaratildi!\n\n")


def _class_view(code, prefix=""):
    db = get_db()
    c = db.get_class(code)
    members = db.class_members(code)
    link = f"{BOT_LINK}?start=cls_{code}"
    body = (f"{prefix}Kod: <code>{code}</code>\nO'quvchilar: <b>{len(members)}</b>\n\n"
            f"🔗 Taklif havolasi:\n<code>{link}</code>")
    rows = [[("📝 Topshiriq berish", f"cls:task:{code}"), ("📊 Natijalar", f"cls:res:{code}")],
            [("📤 O'quvchilarga yuborish", share_url(link, f"«{c['name']}» sinfiga qo'shiling"), "url")],
            [("🔙 Sinflarim", "cls:mine")]]
    return card(f"🏫 {esc(c['name'])}", "Sinf boshqaruvi", body), kb(rows)


def show_class(obj, code, prefix=""):
    html, markup = _class_view(code, prefix)
    show(obj, html, markup)


@on_cb("cls:mine")
def cb_cls_mine(call):
    answer_cb(call)
    cls = get_db().teacher_classes(call.from_user.id)
    if not cls:
        show(call, card("📋 SINFLARIM", "", "Hali sinf yaratmagansiz."), kb([[("➕ Sinf yaratish", "cls:new")], [("🔙 Orqaga", "cls:hub")]]))
        return
    rows = [[(f"{c['name']} · {c['members']} o'quvchi", f"cls:open:{c['code']}")] for c in cls]
    rows.append([("🔙 Orqaga", "cls:hub")])
    show(call, card("📋 SINFLARIM", "", "Sinfni tanlang:"), kb(rows))


def _own_class(call, code):
    c = get_db().get_class(code)
    if not c or c["teacher_id"] != call.from_user.id:
        answer_cb(call, "Bu sinf sizniki emas.", True)
        return None
    return c


@on_cb("cls:open:")
def cb_cls_open(call):
    code = call.data.split(":")[2]
    if not _own_class(call, code):
        return
    answer_cb(call)
    show_class(call, code)


@on_cb("cls:task:")
def cb_cls_task(call):
    code = call.data.split(":")[2]
    if not _own_class(call, code):
        return
    answer_cb(call)
    set_state(call.from_user.id, "cls_topic", code=code)
    send_html(bot, call.message.chat.id, "📝 <b>Topshiriq mavzusi</b> yoki darslik <b>parchasini</b> yuboring.\n"
                                          "<i>Parcha (150+ belgi) yuborsangiz, savollar aynan shu matndan tuziladi.</i>")


@state_handler("cls_topic")
def st_cls_topic(message, st):
    text = (message.text or "").strip()
    if not text or not guard(message.chat.id, message.from_user, text):
        return
    clear_state(message.from_user.id)
    code = st["data"]["code"]
    CLS_BUILD[message.from_user.id] = dict(topic=text[:4000], passage=len(text) > 150)
    rows = [[(f"{n} ta", f"cls:n:{code}:{n}") for n in (5, 10, 15, 20)]]
    send_html(bot, message.chat.id, card("📊 SAVOLLAR SONI", "", "Nechta savol bo'lsin?"), reply_markup=kb(rows))


@on_cb("cls:n:")
def cb_cls_count(call):
    _, _, code, n = call.data.split(":")
    b = CLS_BUILD.get(call.from_user.id)
    if not b or not _own_class(call, code):
        answer_cb(call, "Avval mavzuni kiriting.", True)
        return
    answer_cb(call)
    count = int(n)
    from app.handlers.tests import launch_build
    topic, passage = b["topic"], b["passage"]
    title = "Matn asosidagi topshiriq" if passage else f"{topic[:50]}"
    builder = ((lambda: qmod.build_quiz(qmod.theme_prompt("berilgan matn"), count, passage=topic)) if passage
               else (lambda: qmod.build_quiz(qmod.theme_prompt(topic), count, free_topic=topic)))
    launch_build(call.message.chat.id, call.from_user, title, builder, then="class", extra=dict(code=code))


def finish_class_task(chat_id, user, qs, title, code):
    db = get_db()
    tid = db.add_class_test(code, title, qs)
    c = db.get_class(code)
    members = db.class_members(code)
    sent = 0
    for m in members:
        try:
            bot.send_message(m["user_id"], f"📝 <b>Yangi topshiriq!</b>\nSinf: <b>{esc(c['name'])}</b>\nMavzu: {esc(title)} · {len(qs)} ta savol",
                             parse_mode="HTML", reply_markup=kb([[("▶️ Boshlash", f"cls:play:{tid}")]]))
            sent += 1
        except Exception:  # noqa: BLE001
            pass
    send_html(bot, chat_id, f"✅ Topshiriq <b>{len(members)}</b> o'quvchidan <b>{sent}</b> tasiga yuborildi.",
              reply_markup=kb([[("📊 Natijalar", f"cls:res:{code}")]]))


@on_cb("cls:res:")
def cb_cls_res(call):
    code = call.data.split(":")[2]
    if not _own_class(call, code):
        return
    answer_cb(call)
    tests_ = get_db().class_tests(code, 6)
    if not tests_:
        show(call, card("📊 NATIJALAR", "", "Hali topshiriq berilmagan."), kb([[("🔙 Orqaga", f"cls:open:{code}")]]))
        return
    rows = [[(f"{t['title'][:40]}", f"cls:r:{t['id']}")] for t in tests_] + [[("🔙 Orqaga", f"cls:open:{code}")]]
    show(call, card("📊 NATIJALAR", "", "Topshiriqni tanlang:"), kb(rows))


@on_cb("cls:r:")
def cb_cls_r(call):
    tid = int(call.data.split(":")[2])
    db = get_db()
    t = db.get_class_test(tid)
    if not t or not _own_class(call, t["code"]):
        return
    answer_cb(call)
    res = db.class_test_results(tid)
    done = {r["user_id"] for r in res}
    lines = [f"<b>{i}.</b> {esc(r['name'])} — {r['correct']}/{r['total']} · {r['duration']:.0f}s" for i, r in enumerate(res, 1)]
    missing = [esc(m["name"]) for m in db.class_members(t["code"]) if m["user_id"] not in done]
    avg = round(sum(100 * r["correct"] / max(1, r["total"]) for r in res) / len(res)) if res else 0
    body = "\n".join(lines) or "Hali hech kim topshirmagan."
    if res:
        body += f"\n\n📈 O'rtacha: <b>{avg}%</b>"
    if missing:
        body += f"\n\n⏳ Topshirmaganlar ({len(missing)}): " + ", ".join(missing[:15])
    show(call, card(f"📊 {esc(t['title'][:40])}", "Natijalar", body), kb([[("🔙 Orqaga", f"cls:res:{t['code']}")]]))


@on_cb("cls:join")
def cb_cls_join(call):
    answer_cb(call)
    set_state(call.from_user.id, "cls_code")
    send_html(bot, call.message.chat.id, "🎒 O'qituvchi bergan <b>6 belgili kod</b>ni yozing:")


@state_handler("cls_code")
def st_cls_code(message, st):
    code = (message.text or "").strip().upper()
    if join_class(message.chat.id, message.from_user, code):
        clear_state(message.from_user.id)


def join_class(chat_id, user, code):
    db = get_db()
    c = db.get_class(code) if re.fullmatch(r"[A-Z2-9]{6}", code or "") else None
    if not c:
        send_html(bot, chat_id, "❌ Bunday sinf topilmadi. Kodni tekshirib qayta yozing.")
        return False
    new = db.join_class(code, user.id, display_name(user))
    send_html(bot, chat_id, f"✅ <b>{esc(c['name'])}</b> sinfiga {'qo‘shildingiz' if new else 'allaqachon a’zosiz'}!",
              reply_markup=kb([[("📝 Topshiriqlarim", "cls:tasks")]]))
    if new:
        try:
            bot.send_message(c["teacher_id"], f"🎒 <b>{esc(display_name(user))}</b> «{esc(c['name'])}» sinfiga qo'shildi.", parse_mode="HTML")
        except Exception:  # noqa: BLE001
            pass
    return True


@on_cb("cls:tasks")
def cb_cls_tasks(call):
    answer_cb(call)
    db = get_db()
    rows, lines = [], []
    for c in db.student_classes(call.from_user.id):
        for t in db.class_tests(c["code"], 3):
            done = db.has_class_result(t["id"], call.from_user.id)
            lines.append(f"{'✅' if done else '📝'} {esc(c['name'])} — {esc(t['title'][:40])}")
            if not done:
                rows.append([(f"▶️ {t['title'][:40]}", f"cls:play:{t['id']}")])
    rows.append([("🔙 Orqaga", "cls:hub")])
    show(call, card("📝 TOPSHIRIQLARIM", "", "\n".join(lines) or "Hozircha topshiriq yo'q."), kb(rows))


@on_cb("cls:play:")
def cb_cls_play(call):
    tid = int(call.data.split(":")[2])
    db = get_db()
    t = db.get_class_test(tid)
    uid = call.from_user.id
    if not t or not any(m["user_id"] == uid for m in db.class_members(t["code"])):
        answer_cb(call, "Bu topshiriq sizga tegishli emas.", True)
        return
    if db.has_class_result(tid, uid):
        answer_cb(call, "Siz bu topshiriqni allaqachon topshirgansiz.", True)
        return
    answer_cb(call)
    from app.handlers.tests import start_practice
    start_practice(call.message.chat.id, call.from_user, list(t["questions"]), t["title"], mode="class",
                   ctx=dict(class_test=tid))


def _class_session_done(s, info):
    saved = get_db().save_class_result(s.ctx["class_test"], s.uid, s.name, s.correct, s.total, s.time_spent)
    return "📨 Natijangiz o'qituvchiga yuborildi." if saved else ""


def session_done(s, info):
    """Mashq tugagach: bellashuv/sinf natijasini qayd etadi. Qo'shimcha matn qaytaradi."""
    try:
        if s.ctx.get("duel"):
            return _duel_session_done(s, info)
        if s.ctx.get("class_test"):
            return _class_session_done(s, info)
    except Exception:  # noqa: BLE001
        log_exc("session_done")
    return ""


# =====================================================================================
#  6. Natija kartochkasi (rasm)
# =====================================================================================
def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # eski Pillow
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()


def make_card(r):
    """1080x1350 natija kartochkasi (emoji'siz — shrift muammosiz)."""
    from PIL import Image, ImageDraw
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, bot_ = (30, 27, 75), (88, 64, 214)
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bot_[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((70, 90, W - 70, H - 90), radius=48, fill=(255, 255, 255))
    ink, soft, accent = (28, 27, 60), (120, 122, 150), (108, 92, 231)

    def center(text, y, size, fill):
        f = _font(size)
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=fill)

    center("AI TILSHUNOS", 150, 44, accent)
    center("NATIJA", 215, 38, soft)
    center(str(r["name"])[:28], 330, 64, ink)
    center(str(r["title"])[:38], 415, 36, soft)
    center(f"{r['correct']}/{r['answered']}", 520, 220, accent)
    center(f"{r['accuracy']}% aniqlik", 790, 54, ink)
    # progress bar
    bx0, bx1, by = 170, W - 170, 890
    d.rounded_rectangle((bx0, by, bx1, by + 34), radius=17, fill=(230, 230, 245))
    fill_w = int((bx1 - bx0) * max(0, min(100, r["accuracy"])) / 100)
    if fill_w > 10:
        d.rounded_rectangle((bx0, by, bx0 + fill_w, by + 34), radius=17, fill=accent)
    center(f"Daraja: {r['level']}", 990, 46, ink)
    center(f"Seriya: {r['streak']} kun", 1060, 40, soft)
    center(f"@{config.BOT_USERNAME}", 1180, 46, accent)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    buf.name = "natija.png"
    return buf


@on_cb("rescard")
def cb_rescard(call):
    r = practice.LAST_RESULT.get(call.from_user.id)
    if not r:
        answer_cb(call, "Avval test yakunlang.", True)
        return
    answer_cb(call, "Kartochka tayyorlanmoqda…")
    img = make_card(r)
    bot.send_photo(call.message.chat.id, img,
                   caption=f"🏅 Mening natijam: {r['correct']}/{r['answered']}\n🤖 Siz ham sinab ko'ring: {BOT_LINK}")
