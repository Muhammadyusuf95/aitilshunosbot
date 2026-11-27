"""Kirish nuqtalari: /start, /help, /cancel, menyu tugmalari, holat (state) yo'naltiruvchisi, rasm/matn fallback."""
from app import config, levels, questions as qmod
from app.db import get_db
from app.handlers import admin, profile, tests, tools
from app.handlers.common import on_cb, on_msg, send_subscription_prompt, touch
from app.runtime import answer_cb, bot, clear_state, get_state, invalidate_sub, is_subscribed
from app.textfmt import card, esc, send_html
from app.ui import (BTN_ADMIN, MENU_ACTIONS, kb, main_menu, view_conv_hub, view_abit, view_quiz_hub, view_section)

HELP_TEXT = card(
    "📖 YORDAM", "AI Tilshunos qo'llanmasi",
    "🎒 <b>Abituriyent</b> — esse, BMB, mavzuli testlar\n"
    "👨‍🏫 <b>O'qituvchi</b> — dars ishlanmasi, metodlar, attestatsiya\n"
    "🎓 <b>Talaba</b> — g'azal, aruz, etimologiya\n"
    "🔬 <b>Tadqiqotchi</b> — maqola, tezis, annotatsiya\n"
    "⚡ <b>Kun savoli</b> — har kuni bitta savol, +XP\n"
    "🧰 <b>Til asboblari</b> — imlo, alifbo konvertori, qo'shimchalar\n"
    "🛠 <b>Quiz yaratish</b> — o'z mavzu/matningizdan test\n\n"
    "💡 <b>Maslahat:</b> menyuga hojat yo'q — so'z, matn yoki <u>rasm</u> yuboring, bot nima qilishni taklif qiladi.\n\n"
    "<b>Buyruqlar:</b>\n/start — bosh sahifa\n/daily — kun savoli\n/profile — kabinet\n/top — reyting\n/eslatma — eslatmalarni yoqish/o'chirish\n"
    "/cancel — joriy amalni bekor qilish\n\nGuruhda: <code>/quiz_start</code> · <code>/stop</code>")


def send_menu_hint(chat_id, user_id):
    send_html(bot, chat_id, "📋 <b>Asosiy menyu</b> — bo'limni tanlang 👇", reply_markup=main_menu(user_id))


def welcome(message, tr, is_ref=False):
    u = message.from_user
    row = get_db().get_user(u.id) or {}
    points = row.get("points") or 0
    streak = tr["streak"]
    lines = [levels.level_line(points), ""]
    if tr["is_new_user"]:
        lines.append(f"🎁 Xush kelibsiz bonusi: <b>+{tr['gained']} XP</b>")
    elif tr["new_day"]:
        lines.append(f"🔥 Seriya: <b>{streak} kun</b> · bugungi bonus <b>+{tr['gained']} XP</b>")
        if tr["broken"]:
            lines.insert(2, f"<i>Oldingi {tr['prev_streak']} kunlik seriya uzilgan edi — yangidan boshladik.</i>")
    else:
        lines.append(f"🔥 Seriya: <b>{streak} kun</b>")
    if is_ref:
        lines.append("🤝 Do'stingiz taklifi uchun <b>+30 XP</b> qo'shildi!")
    from app.handlers import growth
    ex = growth.exam_line(row)
    if ex:
        lines += ["", ex]
    lines += ["", "<b>Nimadan boshlaymiz?</b> Menyudan tanlang yoki to'g'ridan-to'g'ri so'z, matn, rasm yuboring."]
    send_html(bot, message.chat.id,
              card(f"✨ Assalomu alaykum, {esc(u.first_name or 'do‘st')}!", "AI Tilshunos — ona tili va adabiyot ustozi",
                   "\n".join(lines)),
              reply_markup=main_menu(u.id))


@on_msg(commands=["start"], gated=False)
def cmd_start(message):
    if message.chat.type != "private":
        send_html(bot, message.chat.id, f"👋 Men AI Tilshunos. Test o'tkazish uchun: <code>/quiz_start</code>\nBatafsil: @{config.BOT_USERNAME}")
        return
    u = message.from_user
    clear_state(u.id)
    tr = touch(u)
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    is_ref = False
    if payload.startswith("ref_") and payload[4:].isdigit():
        db = get_db()
        inviter = int(payload[4:])
        if db.register_referral(u.id, inviter):
            is_ref = True
            db.award_badge(inviter, "inviter")
            try:
                send_html(bot, inviter, f"🤝 <b>{esc(u.first_name or 'Do‘st')}</b> sizning taklifingiz bilan qo'shildi! <b>+30 XP</b>")
            except Exception:  # noqa: BLE001
                pass
    if not is_subscribed(u.id):
        send_subscription_prompt(message.chat.id)
        return
    welcome(message, tr, is_ref)
    if payload.startswith("q") and payload in tests.PENDING:
        tests.start_shared_quiz(message.chat.id, u, payload)
    elif payload == "daily":
        tests.start_daily(message)
    elif payload == "quick":
        tests.launch_build(message.chat.id, u, "Tezkor test",
                           lambda: qmod.build_quiz(qmod.theme_prompt(qmod.GENERAL_THEME), 10, sections=None), then="practice")
    elif payload.startswith("duel_"):
        from app.handlers import growth
        growth.open_duel(message.chat.id, u, payload[5:])
    elif payload.startswith("cls_"):
        from app.handlers import growth
        growth.join_class(message.chat.id, u, payload[4:].upper())
    elif payload.startswith("ct_"):
        from app.handlers import growth
        growth.open_channel_test(message.chat.id, u, payload[3:])


@on_cb("check_sub", gated=False)
def cb_check_sub(call):
    invalidate_sub(call.from_user.id)
    if is_subscribed(call.from_user.id):
        answer_cb(call, "✅ Obuna tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:  # noqa: BLE001
            pass
        tr = touch(call.from_user)

        class _M:  # welcome() uchun minimal xabar ko'rinishi
            chat = call.message.chat
            from_user = call.from_user

        welcome(_M, tr)
    else:
        answer_cb(call, "❌ Siz hali kanalga a'zo emassiz.", True)


@on_msg(commands=["help"], gated=False)
def cmd_help(message):
    send_html(bot, message.chat.id, HELP_TEXT)


@on_msg(commands=["menu"])
def cmd_menu(message):
    clear_state(message.from_user.id)
    send_menu_hint(message.chat.id, message.from_user.id)


@on_msg(commands=["cancel"])
def cmd_cancel(message):
    clear_state(message.from_user.id)
    send_html(bot, message.chat.id, "✅ Bekor qilindi.", reply_markup=main_menu(message.from_user.id))


@on_msg(commands=["daily"])
def cmd_daily(message):
    tests.start_daily(message)


@on_msg(commands=["profile"])
def cmd_profile(message):
    profile.send_profile(message)


@on_msg(commands=["top"])
def cmd_top(message):
    profile.send_rank(message)


def dispatch_menu(action, message):
    from app.runtime import show
    uid = message.from_user.id
    if action in ("talaba", "oqituvchi", "izlanuvchi", "asboblar"):
        show(message, *view_section(action))
    elif action == "more":
        from app import ui
        show(message, *ui.view_more())
    elif action == "abit":
        show(message, *view_abit())
    elif action == "daily":
        tests.start_daily(message)
    elif action == "quiz":
        show(message, *view_quiz_hub())
    elif action == "rank":
        profile.send_rank(message)
    elif action == "profile":
        profile.send_profile(message)
    elif action == "conv":
        from app.runtime import set_state
        set_state(uid, "conv", mode="lat2new")
        show(message, *view_conv_hub())
    elif action == "admin":
        if admin.is_admin(uid):
            admin.send_panel(message)
    elif action == "menu":
        send_menu_hint(message.chat.id, uid)


@on_msg(func=lambda m: m.chat.type == "private", content_types=["text"])
def text_router(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    if text.startswith("/"):
        send_html(bot, message.chat.id, "❓ Noma'lum buyruq. /help yoki /menu ni bosing.")
        return
    action = MENU_ACTIONS.get(text)
    if action:
        clear_state(uid)
        dispatch_menu(action, message)
        return
    st = get_state(uid)
    if st and st["action"] in tools.STATE_HANDLERS:
        tools.STATE_HANDLERS[st["action"]](message, st)
        return
    tools.smart_reply(message)


@on_msg(func=lambda m: m.chat.type == "private", content_types=["photo"])
def photo_router(message):
    st = get_state(message.from_user.id)
    if st and st["action"] in tools.PHOTO_STATES:
        tools.PHOTO_STATES[st["action"]](message, st)
        return
    tools.smart_photo(message)


@on_msg(func=lambda m: m.chat.type == "private", content_types=["document", "voice", "video", "audio", "sticker"])
def other_router(message):
    send_html(bot, message.chat.id, "📎 Hozircha faqat <b>matn</b> va <b>rasm</b> qabul qilaman.")
