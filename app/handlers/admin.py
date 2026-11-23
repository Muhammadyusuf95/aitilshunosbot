"""Admin paneli: statistika, foydalanuvchilar, xabar tarqatish (tasdiq bilan), CSV eksport, kun hikmati/motivatsiya."""
import csv
import io
import random
import time

from telebot.apihelper import ApiTelegramException

from app import ai, config
from app.content import HISTORICAL_EPOCHS
from app.db import get_db, today_str
from app.handlers.common import ADMIN_POSTS, bg, log_exc, on_cb, on_msg, remember_admin_post
from app.handlers.tools import state_handler
from app.runtime import answer_cb, bot, clear_state, set_state, show
from app.security import limiter
from app.textfmt import card, esc, md_to_html, send_html, send_long
from app.ui import kb, rank_btn

PENDING_BROADCASTS = {}


def is_admin(uid):
    return int(uid) == int(config.ADMIN_ID)


def panel_view():
    db = get_db()
    uc = db.user_counts()
    sc = db.summary_counts()
    try:
        ch = bot.get_chat_member_count(config.CHANNEL_USERNAME)
    except Exception:  # noqa: BLE001
        ch = "N/A"
    body = (
        f"👥 Jami: <b>{uc['total']}</b>  ·  Faol: <b>{uc['active']}</b>  ·  Bloklagan: <b>{uc['blocked']}</b>\n"
        f"📅 Bugun faol: <b>{uc['today']}</b>  ·  7 kunda: <b>{uc['week']}</b>\n"
        f"📝 Yakunlangan testlar: <b>{sc['tests']}</b>  ·  Ishtirokchilar: <b>{sc['participants']}</b>\n"
        f"📢 Kanal a'zolari: <b>{ch}</b>\n"
        f"🤖 AI so'rovlar (siz bugun): <b>{limiter.used_today(config.ADMIN_ID, today_str())}</b>\n"
        f"🗄 Baza: <b>{'PostgreSQL' if db.is_pg else 'SQLite (mahalliy)'}</b>"
    )
    rows = [
        [("👥 Foydalanuvchilar", "adm:users:0"), ("📢 Xabar tarqatish", "adm:bc")],
        [("👤 ID bo'yicha xabar", "adm:pm"), ("📥 CSV eksport", "adm:csv")],
        [("☀️ Kun hikmati", "adm:gen:hikmat"), ("⚡ Motivatsiya", "adm:gen:motiv")],
        [("🔄 Yangilash", "adm:panel"), rank_btn("🏆 Reyting")],
    ]
    return card("👑 ADMIN PANELI", "Boshqaruv va statistika", body), kb(rows)


def send_panel(message):
    if not is_admin(message.from_user.id):
        return
    html, markup = panel_view()
    send_html(bot, message.chat.id, html, reply_markup=markup)


@on_msg(commands=["admin", "stats"])
def cmd_admin(message):
    send_panel(message)


def _deny(call):
    if not is_admin(call.from_user.id):
        answer_cb(call, "Faqat bot administratori uchun!", True)
        return True
    return False


@on_cb("adm:panel")
def cb_panel(call):
    if _deny(call):
        return
    answer_cb(call)
    show(call, *panel_view())


# ---------------- Foydalanuvchilar ----------------
def users_view(page):
    db = get_db()
    uc = db.user_counts()
    per = 8
    pages = max(1, (uc["total"] + per - 1) // per)
    page = max(0, min(page, pages - 1))
    rows_db = db.users_page(page, per)
    lines, rows = [], []
    for i, r in enumerate(rows_db, page * per + 1):
        uname = f"@{r['username']}" if r.get("username") else "—"
        st = "🟢" if r.get("status") != "blocked" else "🔴"
        name = r.get("first_name") or "Foydalanuvchi"
        lines.append(f"{i}. {st} <b>{esc(name)}</b> ({esc(uname)})\n    └ <code>{r['user_id']}</code> · 🔥{r.get('streak') or 0} · {r.get('points') or 0} XP")
        rows.append([(f"💬 {name[:18]}", f"adm:dm:{r['user_id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️", f"adm:users:{page - 1}"))
    nav.append((f"{page + 1}/{pages}", "noop"))
    if page + 1 < pages:
        nav.append(("➡️", f"adm:users:{page + 1}"))
    rows.append(nav)
    rows.append([("🔙 Panel", "adm:panel")])
    return card("👥 FOYDALANUVCHILAR", f"Jami {uc['total']} · XP bo'yicha", "\n".join(lines) or "Hozircha yo'q."), kb(rows)


@on_cb("adm:users:")
def cb_users(call):
    if _deny(call):
        return
    answer_cb(call)
    show(call, *users_view(int(call.data.split(":")[2])))


@on_cb("adm:csv")
def cb_csv(call):
    if _deny(call):
        return
    answer_cb(call, "Tayyorlanmoqda…")
    rows = get_db().export_users()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "username", "first_name", "points", "streak", "best_streak", "status", "last_active", "invites"])
    for r in rows:
        w.writerow([r.get(k, "") for k in ("user_id", "username", "first_name", "points", "streak", "best_streak", "status", "last_active", "invites")])
    data = io.BytesIO(("﻿" + buf.getvalue()).encode("utf-8"))
    data.name = f"users_{today_str()}.csv"
    bot.send_document(call.message.chat.id, data, caption=f"📥 {len(rows)} ta foydalanuvchi")


# ---------------- Individual xabar ----------------
@on_cb("adm:dm:")
def cb_dm(call):
    if _deny(call):
        return
    answer_cb(call)
    target = int(call.data.split(":")[2])
    set_state(call.from_user.id, "adm_dm", target=target)
    send_html(bot, call.message.chat.id, f"✍️ <code>{target}</code> ga yuboriladigan xabarni yozing.\n<i>Bekor qilish: /cancel</i>")


@on_cb("adm:pm")
def cb_pm(call):
    if _deny(call):
        return
    answer_cb(call)
    set_state(call.from_user.id, "adm_pm_id")
    send_html(bot, call.message.chat.id, "👤 Foydalanuvchining <b>Telegram ID</b> raqamini kiriting:")


@state_handler("adm_pm_id")
def st_pm_id(message, st):
    if not is_admin(message.from_user.id):
        return
    t = (message.text or "").strip()
    if not t.isdigit():
        send_html(bot, message.chat.id, "❌ ID faqat raqamlardan iborat bo'lishi kerak.")
        return
    set_state(message.from_user.id, "adm_dm", target=int(t))
    send_html(bot, message.chat.id, f"✍️ <code>{t}</code> ga yuboriladigan xabarni yozing:")


def deliver(uid, html_text):
    """Bitta foydalanuvchiga yuboradi. Qaytaradi: 'ok' | 'blocked' | 'fail'. 429 da kutadi."""
    for attempt in range(3):
        try:
            bot.send_message(uid, html_text, parse_mode="HTML", disable_web_page_preview=True)
            return "ok"
        except ApiTelegramException as e:
            if e.error_code == 429:
                try:
                    wait = int(e.result_json.get("parameters", {}).get("retry_after", 3))
                except Exception:  # noqa: BLE001
                    wait = 3
                time.sleep(min(wait + 1, 20))
                continue
            if e.error_code == 403 or "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                return "blocked"
            if "parse entities" in str(e).lower():
                try:
                    from app.textfmt import strip_tags
                    bot.send_message(uid, strip_tags(html_text))
                    return "ok"
                except Exception:  # noqa: BLE001
                    return "fail"
            return "fail"
        except Exception:  # noqa: BLE001
            return "fail"
    return "fail"


def _wrap(text):
    return f"{md_to_html(text)}\n\n🏛 <a href=\"{config.CHANNEL_URL}\">{esc(config.CHANNEL_USERNAME)}</a>"


@state_handler("adm_dm")
def st_dm(message, st):
    if not is_admin(message.from_user.id):
        return
    target = st["data"]["target"]
    clear_state(message.from_user.id)
    res = deliver(target, f"📬 <b>Administrator xabarnomasi:</b>\n\n{_wrap(message.text or '')}")
    if res == "blocked":
        get_db().set_status(target, "blocked")
    send_html(bot, message.chat.id,
              {"ok": f"✅ Yetkazildi: <code>{target}</code>", "blocked": "❌ Foydalanuvchi botni bloklagan.",
               "fail": "❌ Yetkazib bo'lmadi."}[res])


@on_msg(commands=["pm"])
def cmd_pm(message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        send_html(bot, message.chat.id, "Foydalanish: <code>/pm USER_ID xabar matni</code>")
        return
    res = deliver(int(parts[1]), f"📬 <b>Administrator xabarnomasi:</b>\n\n{_wrap(parts[2])}")
    if res == "blocked":
        get_db().set_status(int(parts[1]), "blocked")
    send_html(bot, message.chat.id, "✅ Yetkazildi." if res == "ok" else "❌ Yetkazib bo'lmadi.")


# ---------------- Ommaviy xabar (oldindan ko'rish + tasdiq) ----------------
@on_cb("adm:bc")
def cb_bc(call):
    if _deny(call):
        return
    answer_cb(call)
    set_state(call.from_user.id, "adm_bc")
    send_html(bot, call.message.chat.id,
              "📢 <b>Hammaga xabar</b>\nMatnni yuboring (**qalin**, `kod` kabi belgilar qo'llab-quvvatlanadi).\n"
              "<i>Yuborishdan oldin ko'rib chiqasiz. Bekor qilish: /cancel</i>")


@state_handler("adm_bc")
def st_bc(message, st):
    if not is_admin(message.from_user.id):
        return
    text = message.text or ""
    clear_state(message.from_user.id)
    token = f"b{int(time.time())}"
    PENDING_BROADCASTS[token] = text
    n = len(get_db().all_user_ids())
    send_html(bot, message.chat.id, f"👁 <b>Ko'rib chiqish</b> — {n} ta faol foydalanuvchiga ketadi:\n\n"
                                    f"📢 <b>Umumiy e'lon:</b>\n\n{_wrap(text)}",
              reply_markup=kb([[("✅ Yuborish", f"adm:bcgo:{token}"), ("❌ Bekor", "adm:bccancel")]]))


@on_msg(commands=["send"])
def cmd_send(message):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").replace("/send", "", 1).strip()
    if not text:
        send_html(bot, message.chat.id, "Matn kiriting: <code>/send Yangi test qo'shildi!</code>")
        return
    token = f"b{int(time.time())}"
    PENDING_BROADCASTS[token] = text
    send_html(bot, message.chat.id, f"👁 <b>Ko'rib chiqish:</b>\n\n📢 <b>Umumiy e'lon:</b>\n\n{_wrap(text)}",
              reply_markup=kb([[("✅ Yuborish", f"adm:bcgo:{token}"), ("❌ Bekor", "adm:bccancel")]]))


@on_cb("adm:bccancel")
def cb_bc_cancel(call):
    if _deny(call):
        return
    answer_cb(call, "Bekor qilindi")
    show(call, "❌ Xabar tarqatish bekor qilindi.")


@on_cb("adm:bcgo:")
def cb_bc_go(call):
    if _deny(call):
        return
    token = call.data.split(":", 2)[2]
    text = PENDING_BROADCASTS.pop(token, None)
    if text is None:
        answer_cb(call, "Bu so'rov allaqachon bajarilgan yoki eskirgan.", True)
        return
    answer_cb(call, "Tarqatish boshlandi")
    show(call, "🚀 <b>Tarqatish boshlandi…</b> Yakunlangach hisobot yuboraman.")
    bg(_broadcast, call.message.chat.id, text)


def _broadcast(admin_chat, text):
    db = get_db()
    ids = db.all_user_ids(only_active=True)
    html_text = f"📢 <b>Umumiy e'lon:</b>\n\n{_wrap(text)}"
    ok = blocked = fail = 0
    for uid in ids:
        res = deliver(uid, html_text)
        if res == "ok":
            ok += 1
        elif res == "blocked":
            blocked += 1
            db.set_status(uid, "blocked")
        else:
            fail += 1
        time.sleep(0.05)
    send_html(bot, admin_chat, card("✅ TARQATISH YAKUNLANDI", "",
                                     f"▫️ Yetkazildi: <b>{ok}</b>\n▫️ Botni bloklaganlar: <b>{blocked}</b>\n▫️ Xato: <b>{fail}</b>"))


# ---------------- Kun hikmati / motivatsiya (kanal uchun) ----------------
def generate_didactic(kind="hikmat"):
    epoch, sources = random.choice(HISTORICAL_EPOCHS)
    seed = random.randint(1000, 99999)
    if kind == "hikmat":
        task = "1 ta didaktik hikmatni (ilm, odob, qanoat, vaqt qadri, adolat yoki donolik haqida)"
    else:
        task = "ilm olishga va shaxsiy rivojlanishga undovchi 1 ta motivatsion fikrni"
    prompt = (
        f"Quyidagi adabiy-tarixiy davrga mansub haqiqiy asarlardan {task} keltiring.\n"
        f"Davr: {epoch}\nTavsiya etiladigan manbalar: {sources}\nIdentifikator: #{seed}\n\n"
        "QOIDALAR: 1) Sun'iy to'qilmasin — faqat aniq bilgan haqiqiy iqtibosni keltiring; ishonchingiz komil bo'lmasa, "
        "mashhur va tasdiqlangan hikmatni tanlang. 2) Diniy, siyosiy, tibbiy, huquqiy mavzulardan chetlashing.\n\n"
        "Qat'iy format:\n🏛 Davr: [davr nomi]\n\n[MATN]\n\n📚 Aniq manba: [Muallif, asar nomi, bob/bayt ko'rsatkichi]"
    )
    return ai.generate_text(prompt, temperature=0.6)


@on_cb("adm:gen:")
def cb_gen(call):
    if _deny(call):
        return
    kind = call.data.split(":")[2]
    answer_cb(call, "Tayyorlanmoqda…")
    chat_id = call.message.chat.id

    def job():
        try:
            text = generate_didactic(kind)
        except Exception as e:  # noqa: BLE001
            send_html(bot, chat_id, f"❌ Xatolik: {esc(str(e)[:150])}")
            return
        pid = remember_admin_post(text)
        title = "☀️ KUN HIKMATI" if kind == "hikmat" else "⚡ MOTIVATSIYA"
        send_html(bot, chat_id, card(f"{title} (admin tekshiruvi)", "", md_to_html(text) +
                                     "\n\n<i>Kanalga chiqarilganda «Aniq manba» qismi olib tashlanadi.</i>"),
                  reply_markup=kb([[("📢 Kanalga joylash", f"adm:pub:{pid}"), ("❌ Bekor", "adm:cancel")]]))

    bg(job)


@on_cb("adm:pub:")
def cb_pub(call):
    if _deny(call):
        return
    pid = call.data.split(":", 2)[2]
    text = ADMIN_POSTS.get(pid)
    if not text:
        answer_cb(call, "Matn eskirgan.", True)
        return
    clean = text.split("📚 Aniq manba:")[0].strip()
    post = f"{md_to_html(clean)}\n\n───────────────\n🌟 <a href=\"{config.CHANNEL_URL}\">{esc(config.CHANNEL_USERNAME)}</a>"
    try:
        bot.send_message(config.CHANNEL_USERNAME, post, parse_mode="HTML", disable_web_page_preview=True)
        answer_cb(call, "Kanalga joylandi!")
        show(call, "✅ <b>Kanalga muvaffaqiyatli joylandi.</b>")
    except Exception as e:  # noqa: BLE001
        answer_cb(call, f"Xatolik: {str(e)[:150]}", True)


@on_cb("adm:post:")
def cb_post(call):
    """AI natijasini (to'liq, manbasi bilan) kanalga yuborish."""
    if _deny(call):
        return
    pid = call.data.split(":", 2)[2]
    text = ADMIN_POSTS.get(pid)
    if not text:
        answer_cb(call, "Matn eskirgan.", True)
        return
    try:
        send_long(bot, config.CHANNEL_USERNAME, text)
        answer_cb(call, "Kanalga joylandi!")
    except Exception as e:  # noqa: BLE001
        answer_cb(call, f"Xatolik: {str(e)[:150]}", True)


@on_cb("adm:cancel")
def cb_cancel(call):
    answer_cb(call, "Bekor qilindi")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:  # noqa: BLE001
        pass
